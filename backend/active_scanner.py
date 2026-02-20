from scapy.all import ARP, Ether, srp, IP, ICMP, sr1
import socket
import concurrent.futures
from vendor_lookup import get_vendor

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP_addr = s.getsockname()[0]
    except Exception:
        IP_addr = '127.0.0.1'
    finally:
        s.close()
    return IP_addr

def reconcile_identity(vendor, os, ports):
    """Elite Logic: Resolves hardware vs software conflicts"""
    # High Confidence overrides
    if 445 in ports: return "Windows Workstation", "Windows"
    if 62078 in ports: return "iPhone/iPad", "iOS"
    if 22 in ports: return ("Raspberry Pi" if "Raspberry" in vendor else "Linux Node"), "Linux"

    # Handle Apple adapters on Windows machines
    if vendor == "Apple" and os == "Windows":
        return "Windows PC (Apple Adapter)", "Windows"
    
    return "Generic Device", os

def deep_interrogate(ip, vendor):
    info = {"os": "Unknown", "type": "Generic", "ports": []}
    try:
        pkt = sr1(IP(dst=ip)/ICMP(), timeout=0.6, verbose=0)
        if pkt:
            ttl = pkt.getlayer(IP).ttl
            if ttl <= 64: info["os"] = "Linux/macOS"
            elif ttl <= 128: info["os"] = "Windows"
    except: pass

    for port in [22, 80, 443, 445, 62078]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.08)
            if s.connect_ex((ip, port)) == 0: info["ports"].append(port)
    
    info["type"], info["os"] = reconcile_identity(vendor, info["os"], info["ports"])
    return info

def scan_network(target_ip: str):
    arp = ARP(pdst=target_ip)
    ether = Ether(dst="ff:ff:ff:ff:ff:ff")
    result = srp(ether/arp, timeout=2, verbose=False)[0]

    nodes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        future_to_node = {}
        for sent, received in result:
            ip, mac = received.psrc, received.hwsrc
            vendor = get_vendor(mac)
            node = {'ip': ip, 'mac': mac, 'vendor': vendor, 'hostname': "..."}
            future_to_node[executor.submit(deep_interrogate, ip, vendor)] = node
            nodes.append(node)

        for future in concurrent.futures.as_completed(future_to_node):
            node = future_to_node[future]
            node.update(future.result())
            try: node['hostname'] = socket.gethostbyaddr(node['ip'])[0]
            except: node['hostname'] = "Unknown"
    return nodes