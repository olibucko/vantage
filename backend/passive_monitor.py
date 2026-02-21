from scapy.all import ARP, Ether, sniff, sendp
import threading
import time
from vendor_lookup import get_vendor
from active_scanner import advanced_os_detection, deep_interrogate

# Shared state
discovered_devices = {}
devices_lock = threading.Lock()
monitoring_active = False
monitor_thread = None

# Callbacks registered by main.py to bridge sync threads → async event loop
_on_connect_callback = None
_on_update_callback = None

def set_on_connect_callback(callback):
    global _on_connect_callback
    _on_connect_callback = callback

def set_on_update_callback(callback):
    global _on_update_callback
    _on_update_callback = callback

def get_stale_devices(threshold_seconds: int) -> list:
    """Return copies of devices not seen within threshold_seconds."""
    now = int(time.time())
    stale = []
    with devices_lock:
        for ip, device in discovered_devices.items():
            last = device.get('lastSeen', device.get('discovered_at', now))
            if (now - last) > threshold_seconds:
                stale.append(device.copy())
    return stale

def remove_device(ip: str):
    """Remove a device from the discovered_devices cache."""
    with devices_lock:
        if ip in discovered_devices:
            del discovered_devices[ip]

def probe_known_devices():
    """Send an ARP who-has request to every tracked device.
    Online devices reply; the passive sniffer captures the reply and
    refreshes lastSeen. Offline devices stay silent → go stale.
    """
    with devices_lock:
        targets = [(ip, dev.get('mac', '')) for ip, dev in discovered_devices.items()]

    for ip, mac in targets:
        try:
            # Unicast to the known MAC when available, broadcast otherwise.
            # Treat '00:00:00:00:00:00' (placeholder for unresolved ONVIF/SSDP
            # devices) as missing — sending to it triggers Scapy routing warnings.
            dst = mac if (mac and mac != '00:00:00:00:00:00') else 'ff:ff:ff:ff:ff:ff'
            sendp(Ether(dst=dst) / ARP(op=1, pdst=ip), verbose=0)
        except Exception:
            pass

def preload_from_cache(cache_nodes: list):
    """Seed discovered_devices from persisted node_cache on startup.
    This ensures the stale checker can evict devices that go offline
    even if they never sent an ARP packet in the current session.
    """
    now = int(time.time())
    count = 0
    with devices_lock:
        for node in cache_nodes:
            ip = node.get('ip')
            if ip and ip not in discovered_devices:
                discovered_devices[ip] = {**node, 'lastSeen': now}
                count += 1
    print(f"Vantage: Preloaded {count} cached nodes into passive monitor.")

def passive_arp_callback(packet):
    """Callback for each ARP packet detected"""
    if packet.haslayer(ARP):
        arp = packet[ARP]

        # Only process ARP replies (op=2) or announcements
        if arp.op in [1, 2]:  # who-has or is-at
            ip = arp.psrc
            mac = arp.hwsrc

            if ip and mac and ip != "0.0.0.0":
                is_new = False
                snapshot = None

                with devices_lock:
                    now = int(time.time())
                    if ip not in discovered_devices:
                        is_new = True
                        print(f"Vantage: New device detected via passive monitoring: {ip} ({mac})")

                        vendor = get_vendor(mac)
                        device_info = {
                            'ip': ip,
                            'mac': mac,
                            'vendor': vendor,
                            'hostname': 'Discovering...',
                            'discovered_at': now,
                            'lastSeen': now,
                            'method': 'passive_arp',
                            'os': 'Unknown',
                            'type': 'Unknown Device',
                            'ports': [],
                            'services': [],
                            'confidence': 0,
                            'deviceName': None
                        }
                        discovered_devices[ip] = device_info
                        snapshot = device_info.copy()
                    else:
                        discovered_devices[ip]['lastSeen'] = now

                # Fire callback and start interrogation outside the lock
                if is_new:
                    if _on_connect_callback:
                        try:
                            _on_connect_callback(snapshot)
                        except Exception as e:
                            print(f"Vantage: on_connect_callback error: {e}")
                    threading.Thread(
                        target=interrogate_new_device,
                        args=(ip, mac, get_vendor(mac)),
                        daemon=True
                    ).start()

def interrogate_new_device(ip, mac, vendor):
    """Deep interrogation for a newly discovered device.
    On completion, fires _on_update_callback so main.py can push
    the enriched node data to all connected WebSocket clients.
    """
    try:
        info, hostname = deep_interrogate(ip, vendor, mac)

        snapshot = None
        with devices_lock:
            if ip in discovered_devices:
                discovered_devices[ip].update(info)
                discovered_devices[ip]['hostname'] = hostname
                snapshot = discovered_devices[ip].copy()
                print(f"Vantage: Interrogation complete for {ip}: {info.get('type', 'Unknown')}")

        if snapshot and _on_update_callback:
            try:
                _on_update_callback(snapshot)
            except Exception as e:
                print(f"Vantage: on_update_callback error: {e}")
    except Exception as e:
        print(f"Vantage: Error interrogating passive device {ip}: {e}")

def start_passive_monitoring(interface=None):
    """Start passive ARP monitoring in background thread"""
    global monitoring_active, monitor_thread

    if monitoring_active:
        print("Vantage: Passive monitoring already running")
        return

    monitoring_active = True

    def monitor_loop():
        print("Vantage: Starting passive ARP monitoring...")
        try:
            # Sniff ARP packets indefinitely
            sniff(
                filter="arp",
                prn=passive_arp_callback,
                store=0,
                iface=interface,
                stop_filter=lambda x: not monitoring_active
            )
        except Exception as e:
            print(f"Vantage: Passive monitoring error: {e}")
        finally:
            print("Vantage: Passive monitoring stopped")

    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()

def stop_passive_monitoring():
    """Stop passive monitoring"""
    global monitoring_active
    monitoring_active = False
    print("Vantage: Stopping passive monitoring...")

def get_passive_discoveries():
    """Get list of passively discovered devices"""
    with devices_lock:
        return list(discovered_devices.values())

def clear_passive_discoveries():
    """Clear passive discovery cache"""
    with devices_lock:
        discovered_devices.clear()
    print("Vantage: Passive discovery cache cleared")

def merge_with_active_scan(active_nodes):
    """Merge passive discoveries with active scan results"""
    with devices_lock:
        passive_ips = set(discovered_devices.keys())
        active_ips = set(n['ip'] for n in active_nodes)

        # Add any passive devices not found in active scan
        new_devices = []
        for ip in passive_ips - active_ips:
            device = discovered_devices[ip].copy()
            device['source'] = 'passive'
            new_devices.append(device)

        merged = active_nodes + new_devices
        print(f"Vantage: Merged scan results: {len(active_nodes)} active + {len(new_devices)} passive = {len(merged)} total")
        return merged
