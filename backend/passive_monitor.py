from scapy.all import ARP, sniff
import threading
import time
from vendor_lookup import get_vendor
from active_scanner import advanced_os_detection, deep_interrogate

# Shared state
discovered_devices = {}
devices_lock = threading.Lock()
monitoring_active = False
monitor_thread = None

def passive_arp_callback(packet):
    """Callback for each ARP packet detected"""
    if packet.haslayer(ARP):
        arp = packet[ARP]

        # Only process ARP replies (op=2) or announcements
        if arp.op in [1, 2]:  # who-has or is-at
            ip = arp.psrc
            mac = arp.hwsrc

            if ip and mac and ip != "0.0.0.0":
                with devices_lock:
                    if ip not in discovered_devices:
                        print(f"Vantage: New device detected via passive monitoring: {ip} ({mac})")

                        # Quick device info gathering
                        vendor = get_vendor(mac)
                        device_info = {
                            'ip': ip,
                            'mac': mac,
                            'vendor': vendor,
                            'hostname': 'Discovering...',
                            'discovered_at': int(time.time()),
                            'method': 'passive_arp'
                        }

                        discovered_devices[ip] = device_info

                        # Trigger deep interrogation in background
                        threading.Thread(
                            target=interrogate_new_device,
                            args=(ip, mac, vendor),
                            daemon=True
                        ).start()

def interrogate_new_device(ip, mac, vendor):
    """Deep interrogation for passively discovered device"""
    try:
        import socket
        info, hostname = deep_interrogate(ip, vendor, mac)

        with devices_lock:
            if ip in discovered_devices:
                discovered_devices[ip].update(info)
                discovered_devices[ip]['hostname'] = hostname
                print(f"Vantage: Passive discovery complete for {ip}: {info.get('type', 'Unknown')}")
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
