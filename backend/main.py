import os
import json
import asyncio
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Internal module imports
from active_scanner import scan_network, get_local_ip
from passive_monitor import (
    start_passive_monitoring, stop_passive_monitoring,
    get_passive_discoveries, merge_with_active_scan,
    clear_passive_discoveries, set_on_connect_callback,
    set_on_update_callback, get_stale_devices,
    remove_device, preload_from_cache, probe_known_devices
)

# --- Environment Setup ---
DATA_DIR = os.path.abspath("../data")
DATA_FILE = os.path.join(DATA_DIR, "nodes.json")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    print(f"Vantage: Created data directory at {DATA_DIR}")

app = FastAPI(title="Vantage API - Synoptic Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global State & Cache ---
node_cache = []

# True while a full network scan is running — prevents concurrent scans and
# lets newly-connected WebSocket clients know they should show a loading state.
scan_in_progress = False

# Devices not seen within this window are considered disconnected.
# Active ARP probing (every 10 s) keeps lastSeen fresh for online devices,
# so this threshold reliably catches disconnects in ~25-35 s.
STALE_THRESHOLD_SECONDS = 25

# How long between automatic periodic re-scans (seconds).
PERIODIC_SCAN_INTERVAL = 300  # 5 minutes

def load_cache():
    global node_cache
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                node_cache = json.load(f)
                print(f"Vantage: Loaded {len(node_cache)} nodes from cache.")
        except Exception as e:
            print(f"Vantage: Failed to load cache: {e}")
            node_cache = []

load_cache()
preload_from_cache(node_cache)  # Seed passive monitor so stale checker can track cached devices

# --- Cache Persistence Helpers ---

def _write_cache_sync(data: list):
    """Synchronous disk write — always called via run_in_executor, never directly from the event loop."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def _save_cache_async(data: list):
    """Persist node_cache to disk without blocking the event loop."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _write_cache_sync, data)

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Vantage: WebSocket Link Established. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"Vantage: WebSocket Link Severed. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        payload = json.dumps(message)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                disconnected.append(connection)
        for connection in disconnected:
            self.active_connections.remove(connection)

manager = ConnectionManager()

# --- Core Scan Logic (shared by auto-scan, periodic scan, and manual /scan) ---

async def run_scan(mdns_duration: int = 30) -> bool:
    """Run a full network scan and push results to all WebSocket clients.

    Returns True on success, False if a scan was already running or an error occurred.
    mdns_duration controls how long mDNS discovery listens:
      - 30 s for startup / manual scans (best coverage)
      -  8 s for periodic background sweeps (fast enough to catch new devices)
    """
    global node_cache, scan_in_progress
    if scan_in_progress:
        print("Vantage: Scan already in progress — skipping concurrent request.")
        return False

    scan_in_progress = True
    local_ip = get_local_ip()
    subnet = ".".join(local_ip.split('.')[:-1]) + ".0/24"
    print(f"Vantage: Scan starting on {subnet} (mDNS={mdns_duration}s)...")

    try:
        await manager.broadcast({"type": "SCAN_STARTED", "subnet": subnet})
        loop = asyncio.get_event_loop()
        nodes = await loop.run_in_executor(None, scan_network, subnet, mdns_duration)

        # Run merge + preload in executor — both acquire devices_lock (threading.Lock)
        # and should not block the event loop thread.
        merged_nodes = await loop.run_in_executor(None, merge_with_active_scan, nodes)
        # Refresh lastSeen so stale checker doesn't evict devices just confirmed online
        await loop.run_in_executor(None, preload_from_cache, merged_nodes)
        node_cache = merged_nodes

        await _save_cache_async(merged_nodes)

        await manager.broadcast({"type": "SCAN_COMPLETE", "nodes": merged_nodes})
        print(f"Vantage: Scan complete — {len(merged_nodes)} nodes ({len(nodes)} active + passive).")
        return True

    except Exception as e:
        print(f"Vantage: Scan error: {e}")
        await manager.broadcast({"type": "SCAN_FAILED", "error": str(e)})
        return False

    finally:
        scan_in_progress = False

# --- Background Tasks ---

async def startup_scan():
    """Automatically run a full network scan a few seconds after startup.
    This eliminates the need for the user to manually trigger 'Execute Sweep'
    on first launch.
    """
    await asyncio.sleep(5)  # Let the passive monitor and WS server settle
    print("Vantage: Running automatic startup scan...")
    await run_scan(mdns_duration=30)

async def periodic_discovery():
    """Re-scan the network every PERIODIC_SCAN_INTERVAL seconds to catch
    devices that joined after the startup scan or that don't generate ARP traffic
    (e.g., NVRs / static-IP devices).
    Uses a shorter mDNS window for speed; full mDNS was already done at startup.
    """
    # First periodic run starts after startup + startup-scan duration + interval
    await asyncio.sleep(PERIODIC_SCAN_INTERVAL)
    while True:
        print("Vantage: Running periodic discovery sweep...")
        await run_scan(mdns_duration=8)
        await asyncio.sleep(PERIODIC_SCAN_INTERVAL)

async def heartbeat():
    """Keeps WebSocket connections alive by sending a periodic pulse."""
    while True:
        if manager.active_connections:
            await manager.broadcast({"type": "HEARTBEAT"})
        await asyncio.sleep(15)

async def passive_discovery_broadcast():
    """Periodically broadcast passive discoveries to connected clients.
    Only fires when passive monitoring has found devices not yet in node_cache,
    avoiding wasteful full-payload broadcasts every 30 s when nothing changed.
    """
    global node_cache
    await asyncio.sleep(10)  # Wait for initial setup

    while True:
        if manager.active_connections:
            passive_devices = get_passive_discoveries()
            # Only act when passive monitoring has found IPs not already tracked
            active_ips = {n['ip'] for n in node_cache}
            new_passive = [d for d in passive_devices if d['ip'] not in active_ips]
            if new_passive:
                loop = asyncio.get_event_loop()
                merged_nodes = await loop.run_in_executor(None, merge_with_active_scan, node_cache)
                node_cache = merged_nodes

                await _save_cache_async(merged_nodes)

                await manager.broadcast({
                    "type": "PASSIVE_UPDATE",
                    "nodes": merged_nodes,
                    "new_count": len(new_passive)
                })
                print(f"Vantage: Broadcasted passive update ({len(new_passive)} new passive device(s))")

        await asyncio.sleep(30)

async def broadcast_device_connected(device_info: dict):
    """Merge a newly discovered device into cache and notify all clients."""
    global node_cache
    ip = device_info.get('ip')
    if ip and not any(n.get('ip') == ip for n in node_cache):
        node_cache.append(device_info)
    if manager.active_connections:
        await manager.broadcast({"type": "DEVICE_CONNECTED", "node": device_info})
        print(f"Vantage: Broadcasted DEVICE_CONNECTED for {ip}")

async def broadcast_device_updated(device_info: dict):
    """Push enriched device data to all clients after deep interrogation completes.
    node_cache is updated in memory immediately; disk persistence is deferred to
    the next run_scan or passive_discovery_broadcast to avoid blocking the event
    loop with a disk write on every individual device update.
    """
    global node_cache
    ip = device_info.get('ip')
    if ip:
        node_cache = [device_info if n.get('ip') == ip else n for n in node_cache]
    if manager.active_connections:
        await manager.broadcast({"type": "DEVICE_UPDATED", "node": device_info})
        print(f"Vantage: Broadcasted DEVICE_UPDATED for {ip} ({device_info.get('type', 'Unknown')})")

async def stale_device_checker():
    """Periodically evict devices that haven't been seen recently."""
    global node_cache
    await asyncio.sleep(35)  # Startup grace period — longer than STALE_THRESHOLD_SECONDS
    while True:
        stale = get_stale_devices(STALE_THRESHOLD_SECONDS)
        for device in stale:
            ip = device.get('ip')
            if not ip:
                continue
            print(f"Vantage: {ip} stale — broadcasting DEVICE_DISCONNECTED")
            await manager.broadcast({"type": "DEVICE_DISCONNECTED", "ip": ip})
            remove_device(ip)
            node_cache = [n for n in node_cache if n.get('ip') != ip]
        if stale:
            await _save_cache_async(node_cache)
        await asyncio.sleep(10)

async def device_keepalive():
    """Probe all tracked devices every 10 s with an ARP who-has request.
    Online devices reply; the passive sniffer refreshes their lastSeen.
    Devices that go offline stop responding and become stale within STALE_THRESHOLD_SECONDS.
    """
    await asyncio.sleep(20)  # Let passive monitor start up first
    while True:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, probe_known_devices)
        await asyncio.sleep(10)

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()

    # Bridge the sync passive_monitor callbacks into the async event loop
    def on_device_connected(device_info: dict):
        asyncio.run_coroutine_threadsafe(broadcast_device_connected(device_info), loop)

    def on_device_updated(device_info: dict):
        asyncio.run_coroutine_threadsafe(broadcast_device_updated(device_info), loop)

    set_on_connect_callback(on_device_connected)
    set_on_update_callback(on_device_updated)

    asyncio.create_task(heartbeat())
    asyncio.create_task(passive_discovery_broadcast())
    asyncio.create_task(stale_device_checker())
    asyncio.create_task(device_keepalive())
    asyncio.create_task(startup_scan())       # Full scan ~5 s after boot
    asyncio.create_task(periodic_discovery()) # Repeat every PERIODIC_SCAN_INTERVAL

    start_passive_monitoring()

# --- REST Endpoints ---

@app.get("/nodes")
async def get_nodes():
    """Returns the last known network state without scanning."""
    return {"nodes": node_cache}

@app.get("/scan")
async def trigger_scan():
    """Manually trigger a full network scan (results delivered via WebSocket)."""
    if scan_in_progress:
        return {"status": "already_scanning"}
    asyncio.create_task(run_scan(mdns_duration=30))
    return {"status": "scan_started"}

@app.post("/clear")
async def clear_cache():
    global node_cache
    node_cache = []
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    print("Vantage: Cache purged.")
    return {"status": "cleared"}

# --- WebSocket Interface ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # If a scan is already running when this client connects, tell them immediately
    # so the frontend can show the loading screen without waiting for the next message.
    if scan_in_progress:
        try:
            await websocket.send_text(json.dumps({"type": "SCAN_STARTED"}))
        except Exception:
            pass
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"Vantage WS Error: {e}")
        manager.disconnect(websocket)

# --- Entry Point ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
