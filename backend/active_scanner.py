import logging
import warnings
import threading as _threading
from scapy.all import ARP, Ether, srp, IP, ICMP, sr1, TCP
import socket
import struct
import time
import uuid
import concurrent.futures

logger = logging.getLogger("vantage.scanner")

# Suppress Scapy's "MAC address to reach destination not found" warning.
# This fires when sr1/send can't find the target in the ARP cache and falls
# back to broadcast — harmless behaviour but noisy in the backend console.
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message="MAC address to reach destination not found")

def _suppress_scapy_pipe_errors() -> None:
    """Suppress the spurious OSError: [Errno 9] Bad file descriptor that
    Scapy's internal _sndrcv_snd threads raise on Windows when an sr1/srp
    timeout fires while the internal pipe is being torn down.
    The error is purely cosmetic — scan results are unaffected — but it
    pollutes the backend console on every periodic ping sweep.
    """
    _orig = _threading.excepthook
    def _hook(args: _threading.ExceptHookArgs) -> None:
        if (isinstance(args.exc_value, OSError)
                and getattr(args.exc_value, 'errno', None) == 9
                and args.thread is not None
                and '_sndrcv' in (args.thread.name or '')):
            return  # swallow — Scapy internal pipe teardown noise
        _orig(args)
    _threading.excepthook = _hook

_suppress_scapy_pipe_errors()
from vendor_lookup import get_vendor
from service_detector import (
    start_mdns_discovery, grab_banner, detect_device_type_advanced,
    get_mdns_friendly_name, get_mdns_hostname, get_service_name
)

# Hostnames injected by Docker/virtual network adapters that are meaningless as
# device identifiers and should be treated the same as a failed reverse-DNS lookup.
_FAKE_HOSTNAMES = frozenset({
    "host.docker.internal",
    "gateway.docker.internal",
    "kubernetes.docker.internal",
    "docker.internal",
    "host.lima.internal",       # Lima VM (macOS)
    "host.containers.internal", # Podman
})

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

        # TCP SYN for window size analysis.
        # We must check SYN-ACK responses only — a RST (sent when the port is
        # closed) always carries window=0 regardless of OS, so using it would
        # misidentify any device with port 80 blocked/closed as Linux.
        try:
            tcp_pkt = sr1(IP(dst=ip)/TCP(dport=80, flags="S"), timeout=1, verbose=0)
            if tcp_pkt and tcp_pkt.haslayer(TCP):
                flags = tcp_pkt[TCP].flags
                is_synack = (int(flags) & 0x12) == 0x12  # SYN(0x02) + ACK(0x10)
                if is_synack:
                    window = tcp_pkt[TCP].window
                    # Windows typically has larger initial receive windows
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
        except Exception:
            pass

    except Exception:
        pass

    return os_guess, confidence

def _check_port(args: tuple) -> int | None:
    """Check a single TCP port. Returns port number if open, None if closed.
    Used for parallel port scanning — replaces the sequential loop."""
    ip, port = args
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.15)
            return port if s.connect_ex((ip, port)) == 0 else None
    except Exception:
        return None


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

    # Extended port list — covers common services, NVR/camera SDKs, iOS, Windows
    scan_ports = [
        21, 22, 23, 25,          # FTP, SSH, Telnet, SMTP
        80, 443, 8080, 8443,     # HTTP / HTTPS
        445, 139, 135, 3389,     # Windows (SMB, NetBIOS, RPC, RDP)
        548, 5353, 62078,        # Apple (AFP, mDNS, iOS lockdown)
        9100,                    # Printer (JetDirect)
        161,                     # SNMP
        5900,                    # VNC
        1900,                    # UPnP / SSDP
        8008,                    # Chromecast HTTP
        554,                     # RTSP (NVR / IP cameras)
        8000,                    # Hikvision HTTP SDK
        8899,                    # ONVIF HTTP
        37777,                   # Dahua SDK
        34567,                   # Dahua alternate port
        5000,                    # UPnP / various devices
        7547,                    # TR-069 (ISP router management)
    ]

    # ── Parallel port scan ────────────────────────────────────────────────────
    # All ports probed concurrently → ~0.15 s total instead of 3+ s sequential.
    # Cap at 32 workers so we don't exhaust OS socket limits when many devices
    # are interrogated in parallel.
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(scan_ports), 32)) as pe:
        open_ports = sorted(p for p in
                            pe.map(_check_port, [(ip, port) for port in scan_ports])
                            if p is not None)
    info["ports"] = open_ports

    # Banner grabbing for informative ports (done after parallel scan)
    _banner_ports = {21, 22, 25, 80, 443, 554, 8000, 8899}
    for port in open_ports:
        if port in _banner_ports:
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

    # Get mDNS friendly name (e.g. "Oliver's iPhone") and mDNS-derived hostname
    friendly_name = get_mdns_friendly_name(ip)
    if friendly_name:
        info["deviceName"] = friendly_name
    mdns_host = get_mdns_hostname(ip)  # e.g. "Olivers-iPhone"

    # Reverse DNS lookup with a hard 2-second timeout.
    # socket.gethostbyaddr() has no built-in timeout and can block for 30+ seconds
    # when a DNS server is unresponsive.  We run it in a short-lived thread so
    # the interrogation worker is never held up by a stalled name lookup.
    hostname = "Unknown"
    try:
        _dns_result: list = []
        def _do_dns():
            try:
                _dns_result.append(socket.gethostbyaddr(ip)[0])
            except Exception:
                pass
        _t = _threading.Thread(target=_do_dns, daemon=True)
        _t.start()
        _t.join(timeout=2)
        if _dns_result:
            raw = _dns_result[0]
            hostname = raw if raw.lower() not in _FAKE_HOSTNAMES else "Unknown"
    except Exception:
        hostname = "Unknown"

    # Prefer the mDNS hostname when reverse DNS fails or returns a fake entry
    if (not hostname or hostname == "Unknown") and mdns_host:
        hostname = mdns_host

    # Advanced device type detection
    device_type, type_confidence = detect_device_type_advanced(
        ip, info["ports"], vendor, info["os"], hostname, mac
    )
    info["type"] = device_type

    # Use highest confidence
    if type_confidence > info["confidence"]:
        info["confidence"] = type_confidence

    return info, hostname

def discover_onvif_devices(timeout=5):
    """ONVIF WS-Discovery: multicast UDP probe to 239.255.255.250:3702.
    Any ONVIF-compliant NVR, DVR, or IP camera will reply with a ProbeMatch.
    Returns a set of IP address strings.
    """
    probe = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"'
        ' xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"'
        ' xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"'
        ' xmlns:dn="http://www.onvif.org/ver10/network/wsdl">'
        '<e:Header>'
        f'<w:MessageID>uuid:{uuid.uuid4()}</w:MessageID>'
        '<w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>'
        '<w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>'
        '</e:Header>'
        '<e:Body><d:Probe>'
        '<d:Types>dn:NetworkVideoTransmitter</d:Types>'
        '</d:Probe></e:Body>'
        '</e:Envelope>'
    )
    discovered = set()
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.settimeout(timeout)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
        sock.sendto(probe.encode(), ('239.255.255.250', 3702))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                _, addr = sock.recvfrom(65535)
                ip = addr[0]
                if ip and ip != '0.0.0.0':
                    discovered.add(ip)
                    logger.info("ONVIF device found at %s", ip)
            except socket.timeout:
                break
    except Exception as e:
        logger.warning("ONVIF discovery error: %s", e)
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass
    return discovered


def discover_ssdp_devices(timeout=5):
    """SSDP/UPnP M-SEARCH discovery: multicast UDP probe to 239.255.255.250:1900.
    Many NVRs and smart devices respond to this even if they don't respond to ARP probes.
    Returns a set of IP address strings.
    """
    request = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 3\r\n"
        "ST: ssdp:all\r\n"
        "\r\n"
    )
    discovered = set()
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.settimeout(timeout)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
        sock.sendto(request.encode(), ('239.255.255.250', 1900))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                _, addr = sock.recvfrom(65535)
                ip = addr[0]
                if ip and ip != '0.0.0.0':
                    discovered.add(ip)
            except socket.timeout:
                break
    except Exception as e:
        logger.warning("SSDP discovery error: %s", e)
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass
    return discovered


def ping_sweep(subnet: str):
    """Send ICMP pings to wake up sleeping devices"""
    logger.info("Sending wake-up ping sweep...")

    # Parse subnet (e.g., "192.168.20.0/24")
    base_ip = '.'.join(subnet.split('/')[0].split('.')[:-1])

    def ping_host(ip):
        try:
            sr1(IP(dst=ip)/ICMP(), timeout=0.1, verbose=0)
        except Exception:
            pass

    # Ping all IPs in parallel (fast)
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(ping_host, f"{base_ip}.{i}") for i in range(1, 255)]
        concurrent.futures.wait(futures, timeout=3)

    logger.info("Wake-up ping sweep complete")

def scan_network(target_ip: str, mdns_duration: int = 30, progress_callback=None):
    """Comprehensive network scan with multi-method discovery.

    Runs mDNS, ONVIF WS-Discovery, SSDP and ARP concurrently so total discovery
    time equals mdns_duration (~30 s for startup, ~8 s for periodic sweeps).
    ONVIF/SSDP results that the ARP sweep missed are resolved to MAC addresses via
    targeted ARP probes and added to the interrogation queue.
    """

    def _progress(percent: int, message: str) -> None:
        if progress_callback:
            try:
                progress_callback(percent, message)
            except Exception:
                pass

    # Step 1: Wake up sleeping devices with ping sweep
    _progress(5, "Sending ping sweep…")
    ping_sweep(target_ip)

    # Step 2: Run all discovery protocols concurrently with the ARP sweep
    _progress(12, f"Starting parallel discovery (mDNS {mdns_duration}s, ONVIF, SSDP, ARP)…")
    logger.info("Starting parallel discovery (mDNS %ds, ONVIF, SSDP, ARP)...", mdns_duration)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as disc_pool:
        mdns_future  = disc_pool.submit(start_mdns_discovery, mdns_duration)
        onvif_future = disc_pool.submit(discover_onvif_devices, 5)
        ssdp_future  = disc_pool.submit(discover_ssdp_devices, 5)

        # ARP broadcast scan runs in the main thread while the above are in flight
        arp = ARP(pdst=target_ip)
        ether = Ether(dst="ff:ff:ff:ff:ff:ff")
        arp_result = srp(ether/arp, timeout=3, verbose=False)[0]
        arp_devices = {received.psrc: received.hwsrc for _, received in arp_result}
        logger.info("ARP found %d hosts", len(arp_devices))
        _progress(28, f"ARP scan complete — {len(arp_devices)} host(s) found")

        mdns_results = mdns_future.result()
        onvif_ips    = onvif_future.result()
        ssdp_ips     = ssdp_future.result()

    logger.info("mDNS=%d, ONVIF=%d, SSDP=%d discoveries",
                len(mdns_results), len(onvif_ips), len(ssdp_ips))

    # Merge ONVIF/SSDP IPs not already captured by ARP
    extra_ips = (onvif_ips | ssdp_ips) - set(arp_devices.keys())
    if extra_ips:
        logger.info("%d extra device(s) from ONVIF/SSDP — resolving MAC...", len(extra_ips))
        for ip in extra_ips:
            try:
                arpr = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ip),
                           timeout=2, verbose=False)[0]
                arp_devices[ip] = arpr[0][1].hwsrc if arpr else "00:00:00:00:00:00"
            except Exception:
                arp_devices[ip] = "00:00:00:00:00:00"

    total = len(arp_devices)
    logger.info("%d total device(s), beginning deep interrogation...", total)
    _progress(55, f"Discovery complete — interrogating {total} device(s)…")

    nodes = []
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_node = {}
        for ip, mac in arp_devices.items():
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
                logger.warning("Error interrogating %s: %s", node['ip'], e)
                node['hostname'] = "Unknown"
                node['type'] = "Unknown Device"
                node['os'] = "Unknown"
                node['ports'] = []
                node['services'] = []
                node['confidence'] = 0
            completed += 1
            if total > 0:
                pct = 55 + int(completed / total * 38)  # 55 → 93 %
                _progress(pct, f"Interrogating devices… ({completed}/{total})")

    _progress(99, "Finalising results…")
    logger.info("Scan complete. %d devices identified.", len(nodes))
    return nodes
