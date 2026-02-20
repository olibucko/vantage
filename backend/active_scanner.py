from scapy.all import ARP, Ether, srp, IP, ICMP, sr1, TCP
import socket
import struct
import time
import concurrent.futures
from vendor_lookup import get_vendor
from service_detector import (
    start_mdns_discovery, grab_banner, detect_device_type_advanced,
    get_mdns_friendly_name, get_service_name
)

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

def advanced_os_detection(ip):
    """Multi-factor OS fingerprinting"""
    os_guess = "Unknown"
    confidence = 0

    try:
        # ICMP Ping for TTL
        pkt = sr1(IP(dst=ip)/ICMP(), timeout=1, verbose=0)
        if pkt:
            ttl = pkt.getlayer(IP).ttl

            # More granular TTL analysis
            if ttl <= 64:
                if ttl > 60:
                    os_guess = "Linux"
                    confidence = 70
                else:
                    os_guess = "Linux/Unix"
                    confidence = 60
            elif ttl <= 128:
                if ttl > 120:
                    os_guess = "Windows"
                    confidence = 75
                else:
                    os_guess = "Windows"
                    confidence = 60
            elif ttl <= 255:
                os_guess = "Network Device"
                confidence = 50

        # TCP SYN for window size analysis
        try:
            tcp_pkt = sr1(IP(dst=ip)/TCP(dport=80, flags="S"), timeout=1, verbose=0)
            if tcp_pkt and tcp_pkt.haslayer(TCP):
                window = tcp_pkt[TCP].window

                # Windows typically has larger windows
                if window >= 64000:
                    if os_guess == "Windows":
                        confidence = 85
                    else:
                        os_guess = "Windows"
                        confidence = 70
                elif window <= 5840:  # Common Linux default
                    if "Linux" in os_guess:
                        confidence = 80
                    else:
                        os_guess = "Linux"
                        confidence = 65
        except:
            pass

    except:
        pass

    return os_guess, confidence

def deep_interrogate(ip, vendor, mac):
    """Comprehensive device interrogation"""
    info = {
        "os": "Unknown",
        "type": "Unknown Device",
        "ports": [],
        "services": [],
        "confidence": 0,
        "deviceName": None
    }

    # OS Detection
    os_guess, os_confidence = advanced_os_detection(ip)
    info["os"] = os_guess
    info["confidence"] = os_confidence

    # Extended port scan - more ports for better detection
    scan_ports = [
        21, 22, 23, 25,  # FTP, SSH, Telnet, SMTP
        80, 443, 8080, 8443,  # HTTP/HTTPS
        445, 139, 135, 3389,  # Windows (SMB, RDP)
        548, 5353, 62078,  # macOS/iOS (AFP, mDNS, iOS)
        9100,  # Printer (JetDirect)
        161, 162,  # SNMP
        5900,  # VNC
        1900,  # UPnP/SSDP
        8080, 8008,  # Alternative HTTP, Chromecast
    ]

    for port in scan_ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                if s.connect_ex((ip, port)) == 0:
                    info["ports"].append(port)

                    # Grab banner for key ports
                    if port in [21, 22, 25, 80, 443]:
                        banner_info = grab_banner(ip, port, timeout=1)
                        info["services"].append({
                            "port": port,
                            "name": banner_info["service"],
                            "banner": banner_info.get("banner")
                        })
                    else:
                        info["services"].append({
                            "port": port,
                            "name": get_service_name(port),
                            "banner": None
                        })
        except:
            continue

    # Get mDNS friendly name
    friendly_name = get_mdns_friendly_name(ip)
    if friendly_name:
        info["deviceName"] = friendly_name

    # Get hostname
    try:
        hostname = socket.gethostbyaddr(ip)[0]
    except:
        hostname = "Unknown"

    # Advanced device type detection
    device_type, type_confidence = detect_device_type_advanced(
        ip, info["ports"], vendor, info["os"], hostname
    )
    info["type"] = device_type

    # Use highest confidence
    if type_confidence > info["confidence"]:
        info["confidence"] = type_confidence

    return info, hostname

def ping_sweep(subnet: str):
    """Send ICMP pings to wake up sleeping devices"""
    print("Vantage: Sending wake-up ping sweep...")

    # Parse subnet (e.g., "192.168.20.0/24")
    base_ip = '.'.join(subnet.split('/')[0].split('.')[:-1])

    def ping_host(ip):
        try:
            sr1(IP(dst=ip)/ICMP(), timeout=0.1, verbose=0)
        except:
            pass

    # Ping all IPs in parallel (fast)
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(ping_host, f"{base_ip}.{i}") for i in range(1, 255)]
        concurrent.futures.wait(futures, timeout=3)

    print("Vantage: Wake-up ping sweep complete")

def scan_network(target_ip: str):
    """Comprehensive network scan with multi-method discovery"""

    # Step 1: Wake up sleeping devices with ping sweep (1-2 seconds)
    ping_sweep(target_ip)

    # Step 2: Start mDNS/Bonjour discovery (30 seconds for better Apple device detection)
    print("Vantage: Starting mDNS/Bonjour discovery (30s)...")
    mdns_results = start_mdns_discovery(duration=30)
    print(f"Vantage: mDNS discovered {len(mdns_results)} devices")

    print(f"Vantage: Starting ARP scan on {target_ip}...")
    # ARP Scan
    arp = ARP(pdst=target_ip)
    ether = Ether(dst="ff:ff:ff:ff:ff:ff")
    result = srp(ether/arp, timeout=3, verbose=False)[0]

    print(f"Vantage: ARP found {len(result)} responses, beginning deep interrogation...")

    nodes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_node = {}
        for sent, received in result:
            ip, mac = received.psrc, received.hwsrc
            vendor = get_vendor(mac)
            node = {
                'ip': ip,
                'mac': mac,
                'vendor': vendor,
                'hostname': "...",
                'lastSeen': int(time.time())
            }
            future_to_node[executor.submit(deep_interrogate, ip, vendor, mac)] = node
            nodes.append(node)

        for future in concurrent.futures.as_completed(future_to_node):
            node = future_to_node[future]
            try:
                interrogation_result, hostname = future.result()
                node.update(interrogation_result)
                node['hostname'] = hostname
            except Exception as e:
                print(f"Vantage: Error interrogating {node['ip']}: {e}")
                node['hostname'] = "Unknown"
                node['type'] = "Unknown Device"
                node['os'] = "Unknown"
                node['ports'] = []
                node['services'] = []
                node['confidence'] = 0

    print(f"Vantage: Scan complete. {len(nodes)} devices identified.")
    return nodes
