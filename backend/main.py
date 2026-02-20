import os
import json
import asyncio
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Internal module imports
from active_scanner import scan_network, get_local_ip

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

# --- Heartbeat Task ---
async def heartbeat():
    """Keeps WebSocket connections alive by sending a periodic pulse."""
    while True:
        if manager.active_connections:
            await manager.broadcast({"type": "HEARTBEAT"})
        await asyncio.sleep(15)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(heartbeat())

# --- REST Endpoints ---

@app.get("/nodes")
async def get_nodes():
    """Returns the last known network state without scanning."""
    return {"nodes": node_cache}

@app.get("/scan")
async def trigger_scan():
    """Manually triggers an active ARP sweep via Scapy."""
    global node_cache
    local_ip = get_local_ip()
    subnet = ".".join(local_ip.split('.')[:-1]) + ".0/24"
    
    print(f"Vantage: Initiating active interrogation on {subnet}...")
    
    try:
        loop = asyncio.get_event_loop()
        # Offload the synchronous Scapy scan to a thread pool
        nodes = await loop.run_in_executor(None, scan_network, subnet)
        
        node_cache = nodes
        with open(DATA_FILE, "w") as f:
            json.dump(nodes, f, indent=4)
            
        await manager.broadcast({"type": "SCAN_COMPLETE", "nodes": nodes})
        print(f"Vantage: Scan complete. Identified {len(nodes)} nodes.")
        return {"status": "success", "count": len(nodes)}
    except Exception as e:
        print(f"Vantage Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
    try:
        while True:
            # Maintain connection and listen for any client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"Vantage WS Error: {e}")
        manager.disconnect(websocket)

# --- Entry Point ---
if __name__ == "__main__":
    # Ensure uvicorn runs on the port specified in App.tsx
    uvicorn.run(app, host="0.0.0.0", port=8001)