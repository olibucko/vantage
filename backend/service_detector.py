import socket
import struct
from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
import threading
import time

# mDNS/Bonjour discovered devices
mdns_devices = {}
mdns_lock = threading.Lock()

class NetworkServiceListener(ServiceListener):
    """Listens for mDNS/Bonjour service advertisements"""

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass  # We don't track service removals during a bounded discovery window

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass  # Re-announced services carry no new info we need

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            addresses = [socket.inet_ntoa(addr) for addr in info.addresses]
            device_name = name.split('.')[0]  # e.g. "Oliver's iPhone"
            # info.server is the mDNS hostname, e.g. "Olivers-iPhone.local."
            mdns_hostname = None
            if info.server:
                mdns_hostname = info.server.rstrip('.')
                if mdns_hostname.lower().endswith('.local'):
                    mdns_hostname = mdns_hostname[:-6]
            for ip in addresses:
                with mdns_lock:
                    if ip not in mdns_devices:
                        mdns_devices[ip] = {"services": [], "name": None, "hostname": None}
                    mdns_devices[ip]["services"].append({
                        "type": type_,
                        "name": device_name,
                        "port": info.port
                    })
                    if not mdns_devices[ip]["name"]:
                        mdns_devices[ip]["name"] = device_name
                    if not mdns_devices[ip].get("hostname") and mdns_hostname:
                        mdns_devices[ip]["hostname"] = mdns_hostname

def start_mdns_discovery(duration=10):
    """Run mDNS discovery for specified duration"""
    global mdns_devices
    with mdns_lock:          # guard the reset so readers don't see a torn state
        mdns_devices = {}

    zeroconf = Zeroconf()
    services = [
        "_http._tcp.local.",
        "_https._tcp.local.",
        "_printer._tcp.local.",
        "_ipp._tcp.local.",
        "_airplay._tcp.local.",
        "_googlecast._tcp.local.",
        "_homekit._tcp.local.",
        "_spotify-connect._tcp.local.",
        "_smb._tcp.local.",
        "_sftp-ssh._tcp.local.",
        "_raop._tcp.local.",              # AirPlay audio
        "_companion-link._tcp.local.",    # Apple Handoff / Continuity
        "_rtsp._tcp.local.",              # IP cameras / NVRs
        "_apple-mobdev2._tcp.local.",     # iPhone / iPad (Apple Mobile Device Protocol v2)
        "_remotepairing._tcp.local.",     # iPhone Mirroring / remote pairing (iOS 17+)
        "_touch-able._tcp.local.",        # iTunes Remote app (iPhone/iPad)
        "_daap._tcp.local.",              # iTunes music sharing (Apple)
        "_sleep-proxy._udp.local.",       # Apple Sleep Proxy (Bonjour sleep)
    ]

    listeners = []
    try:
        for service in services:
            listener = NetworkServiceListener()
            browser = ServiceBrowser(zeroconf, service, listener)
            listeners.append((browser, listener))
        time.sleep(duration)
    finally:
        zeroconf.close()    # always release Zeroconf threads even if an exception fires

    with mdns_lock:
        return dict(mdns_devices)

def grab_banner(ip, port, timeout=2):
    """Grab service banner from specified port.

    NOTE: In Python 3, bytes objects do NOT support %-formatting — use
    str.format().encode() or concatenation instead to build probe packets.
    The socket is managed via context manager to prevent descriptor leaks.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((ip, port))

            # Build and send the appropriate probe for each protocol.
            # HTTP-family probes are constructed as str then encoded to avoid
            # the TypeError that `b"..." % ip.encode()` raises in Python 3.
            if port in (80, 8000, 8080, 8899):
                probe = f"GET / HTTP/1.0\r\nHost: {ip}\r\nConnection: close\r\n\r\n"
                sock.send(probe.encode('ascii'))
            elif port == 443:
                return {"service": "HTTPS", "banner": "SSL/TLS"}
            elif port == 554:
                # RTSP OPTIONS — servers reply with "RTSP/1.0 200 OK ..."
                sock.send(b"OPTIONS * RTSP/1.0\r\nCSeq: 1\r\n\r\n")
            elif port in (22, 21):
                pass          # SSH and FTP push their banners immediately; just recv
            else:
                sock.send(b"\r\n")

            banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()

        service_name = detect_service_from_banner(port, banner)
        return {"service": service_name, "banner": banner[:200]}
    except Exception:
        return {"service": get_service_name(port), "banner": None}

def detect_service_from_banner(port, banner):
    """Detect service type from banner content"""
    banner_lower = banner.lower()

    # Web servers
    if "apache" in banner_lower:
        return "Apache Web Server"
    elif "nginx" in banner_lower:
        return "Nginx Web Server"
    elif "iis" in banner_lower or "microsoft-iis" in banner_lower:
        return "Microsoft IIS"
    elif "lighttpd" in banner_lower:
        return "Lighttpd Web Server"

    # SSH
    elif "ssh" in banner_lower:
        if "openssh" in banner_lower:
            return "OpenSSH"
        return "SSH Server"

    # FTP
    elif "ftp" in banner_lower:
        if "vsftpd" in banner_lower:
            return "vsftpd"
        elif "proftpd" in banner_lower:
            return "ProFTPD"
        return "FTP Server"

    # Email
    elif "smtp" in banner_lower:
        return "SMTP Server"
    elif "pop3" in banner_lower:
        return "POP3 Server"
    elif "imap" in banner_lower:
        return "IMAP Server"

    # Database
    elif "mysql" in banner_lower:
        return "MySQL Database"
    elif "postgresql" in banner_lower:
        return "PostgreSQL Database"
    elif "mongodb" in banner_lower:
        return "MongoDB Database"

    # NVR / IP Camera
    elif "rtsp" in banner_lower:
        if "hikvision" in banner_lower:
            return "Hikvision RTSP"
        elif "dahua" in banner_lower:
            return "Dahua RTSP"
        return "RTSP Server"
    elif "hikvision" in banner_lower:
        return "Hikvision NVR/Camera"
    elif "dahua" in banner_lower:
        return "Dahua NVR/Camera"
    elif "reolink" in banner_lower:
        return "Reolink NVR/Camera"
    elif "amcrest" in banner_lower:
        return "Amcrest Camera"
    elif "onvif" in banner_lower:
        return "ONVIF Camera"

    # Other
    elif "telnet" in banner_lower:
        return "Telnet"
    else:
        return get_service_name(port)

def get_service_name(port):
    """Get common service name by port number"""
    services = {
        20: "FTP Data", 21: "FTP", 22: "SSH", 23: "Telnet",
        25: "SMTP", 53: "DNS", 67: "DHCP", 80: "HTTP",
        110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
        465: "SMTPS", 993: "IMAPS", 995: "POP3S", 3306: "MySQL",
        3389: "RDP", 5432: "PostgreSQL", 5900: "VNC", 8080: "HTTP-Alt",
        8443: "HTTPS-Alt", 9100: "Printer (JetDirect)", 62078: "iOS Services",
        554: "RTSP", 8000: "Hikvision SDK", 8899: "ONVIF HTTP",
        37777: "Dahua SDK", 34567: "Dahua Alt",
    }
    return services.get(port, f"Port {port}")

def query_snmp(ip, timeout=2):
    """Query SNMP for device information"""
    # SNMP querying not currently implemented.
    return None

def detect_device_type_advanced(ip, ports, vendor, os_guess, hostname, mac=""):
    """Advanced device type detection using multiple signals.

    Signal priority (highest → lowest):
    1. Unambiguous protocol ports: iOS lockdown (62078), SMB (445) + OS hint, RDP (3389)
    2. NVR / camera ports: RTSP (554), Dahua SDK (37777/34567), Hikvision SDK (8000), ONVIF (8899)
    3. mDNS service announcements and device name keywords — gated so SMB cannot be overridden
    4. NVR OUI vendor keywords
    5. General port signatures
    6. OS-guided fallback
    7. General OUI vendor keywords (networking gear, peripherals)
    8. Hostname hints

    Rationale: A Windows machine using an Apple USB-C/Thunderbolt adapter has an Apple
    OUI but opens port 445 (SMB) and has a Windows TTL.  Checking SMB *before* mDNS
    and vendor prevents Bonjour services (e.g. iTunes _airplay._tcp) from incorrectly
    classifying it as "Apple TV/HomePod".
    """
    device_type = "Unknown Device"
    confidence = 0
    vendor_lower = vendor.lower()
    os_lower = (os_guess or "").lower()

    # Detect locally-administered (randomized) MAC — strong signal of iOS/Android device
    _is_local_mac = False
    if mac and mac not in ("", "00:00:00:00:00:00"):
        try:
            _is_local_mac = bool(int(mac.split(':')[0], 16) & 0x02)
        except Exception:
            pass

    # ── Priority 1: Unambiguous protocol fingerprints ─────────────────────────
    # iOS lockdown service — exists only on iPhones/iPads
    if 62078 in ports:
        return "Apple iPhone/iPad", 94

    # SMB (445): nearly exclusive to Windows.  Checked before mDNS so a Windows
    # machine advertising Apple Bonjour services isn't misidentified.
    if 445 in ports:
        if 3389 in ports:
            return "Windows Server", 93          # RDP confirms Windows Server
        if 'windows' in os_lower:
            return "Windows Workstation", 92     # OS + SMB = high certainty
        # Without a Windows OS signal, still lean Windows but allow NAS/vendor
        # checks below to override (they run at confidence ≥ 90, this sets 75)
        if 'linux' not in os_lower:             # skip if OS says Linux (Samba)
            device_type = "Windows Workstation"
            confidence = 75

    if 3389 in ports and 'windows' in os_lower and confidence < 85:
        device_type = "Windows Workstation"
        confidence = 85

    # ── Priority 2: NVR / camera-specific ports ───────────────────────────────
    if 554 in ports:
        if 37777 in ports or 34567 in ports:
            return "Dahua NVR/DVR", 95
        if 8000 in ports:
            return "Hikvision NVR/Camera", 95
        if 8899 in ports:
            lbl = vendor if vendor not in ("Unknown", "") else "ONVIF"
            return f"{lbl} Camera", 88
        lbl = vendor if vendor not in ("Unknown", "") else None
        return (f"{lbl} NVR/IP Camera" if lbl else "NVR/IP Camera"), 82

    if 37777 in ports or 34567 in ports:
        return "Dahua NVR/DVR", 90

    if 8000 in ports and 80 in ports and confidence < 93:
        if "hikvision" in vendor_lower:
            return "Hikvision NVR/Camera", 93
        device_type = "NVR/IP Camera"
        confidence = max(confidence, 72)

    if 8899 in ports and confidence < 78:
        lbl = vendor if vendor not in ("Unknown", "") else "ONVIF"
        device_type = f"{lbl} Camera"
        confidence = 78

    # ── Priority 3: mDNS service announcements (gated on current confidence) ──
    mdns_info = mdns_devices.get(ip, {})
    if mdns_info:
        services = mdns_info.get("services", [])
        service_types = [s["type"] for s in services]

        # Check the mDNS device name for Apple device keywords — highest-confidence signal
        # because the device self-reports its name (e.g. "Oliver's iPhone", "Oliver's iPad")
        mdns_name = (mdns_info.get("name") or "").lower()
        if confidence < 96:
            if "iphone" in mdns_name or "ipad" in mdns_name:
                return "Apple iPhone/iPad", 96
            if any(kw in mdns_name for kw in ("macbook", "mac pro", "mac mini", "imac", "mac studio")):
                return "Apple Mac", 92
            if "apple tv" in mdns_name or "homepod" in mdns_name:
                return "Apple TV/HomePod", 94

        if "_rtsp._tcp.local." in service_types and confidence < 90:
            lbl = vendor if vendor not in ("Unknown", "") else None
            return (f"{lbl} NVR/Camera" if lbl else "NVR/IP Camera"), 90

        # Apple Mobile Device services (iPhone/iPad) — checked before AirPlay so a
        # phone with AirPlay enabled isn't misidentified as Apple TV/HomePod
        if confidence < 95:
            if any(t in service_types for t in (
                "_apple-mobdev2._tcp.local.",
                "_remotepairing._tcp.local.",
                "_touch-able._tcp.local.",
            )):
                return "Apple iPhone/iPad", 95

        # Only classify as Apple media if SMB hasn't already pinned it as Windows
        if confidence < 88:
            if "_airplay._tcp.local." in service_types or "_raop._tcp.local." in service_types:
                return "Apple TV/HomePod", 90

        if "_printer._tcp.local." in service_types or "_ipp._tcp.local." in service_types:
            if confidence < 95:
                return (f"{vendor} Printer" if vendor != "Unknown" else "Network Printer"), 95

        if "_googlecast._tcp.local." in service_types and confidence < 95:
            return "Google Chromecast", 95

    # ── Priority 4: NVR OUI vendor keywords ──────────────────────────────────
    NVR_VENDOR_KEYWORDS = [
        ("hikvision", "Hikvision NVR/Camera"),
        ("dahua", "Dahua NVR/DVR"),
        ("reolink", "Reolink NVR/Camera"),
        ("amcrest", "Amcrest Camera"),
        ("foscam", "Foscam Camera"),
        ("axis communications", "Axis Camera"),
        ("hanwha", "Hanwha Camera"),
        ("vivotek", "Vivotek Camera"),
        ("uniview", "Uniview Camera"),
        ("bosch security", "Bosch Security Camera"),
        ("ezviz", "EZVIZ Camera"),
    ]
    if confidence < 92:
        for kw, label in NVR_VENDOR_KEYWORDS:
            if kw in vendor_lower:
                device_type = label
                confidence = 92
                break

    # ── Priority 5: General port signatures ──────────────────────────────────
    if confidence < 85:
        if 9100 in ports:
            device_type = f"{vendor} Printer" if vendor != "Unknown" else "Network Printer"
            confidence = 85
        elif 7547 in ports:
            # TR-069 is exclusively used for ISP router/modem management
            device_type = f"{vendor} Router" if vendor != "Unknown" else "Router/Modem"
            confidence = 82
        elif 3389 in ports and 445 in ports:
            # RDP + SMB — double Windows confirmation
            device_type = "Windows Server" if (80 in ports or 443 in ports) else "Windows Workstation"
            confidence = max(confidence, 88)
        elif 135 in ports and 445 in ports and confidence < 80:
            # WMI/RPC + SMB — Windows service stack
            device_type = "Windows Device"
            confidence = 78
        elif 22 in ports and 80 in ports and 443 in ports:
            if ip.endswith('.1') or ip.endswith('.254'):
                device_type = f"{vendor} Router" if vendor != "Unknown" else "Router/Gateway"
                confidence = 75
            else:
                device_type = "Linux Server"
                confidence = 65
        elif 22 in ports and confidence < 60:
            device_type = "Linux Device"
            confidence = 58

    # ── Priority 6: OS-guided fallback ───────────────────────────────────────
    if confidence < 62:
        if 'windows' in os_lower:
            device_type = "Windows Device"
            confidence = 60
        elif 'linux' in os_lower:
            device_type = "Linux Device"
            confidence = 55

    # ── Priority 7: General OUI vendor keywords ───────────────────────────────
    ROUTER_VENDORS   = {"TP-Link", "Netgear", "D-Link", "Ubiquiti", "Cisco",
                        "Zyxel", "Huawei", "Aruba"}
    PRINTER_VENDORS  = {"HP", "Canon", "Epson", "Brother", "Xerox"}
    MOBILE_VENDORS   = {"Samsung", "Xiaomi", "LG Electronics", "Motorola", "OnePlus"}
    CONSOLE_VENDORS  = {"Sony PlayStation", "Microsoft Xbox", "Nintendo"}
    MEDIA_VENDORS    = {"Sonos", "Roku", "Slim Devices (Roku)", "Amazon"}
    SMARTHOME_VENDORS= {"Nest", "Ring", "Philips Hue", "Philips", "Belkin"}

    if confidence < 88:
        if vendor in ROUTER_VENDORS:
            if ip.endswith('.1') or ip.endswith('.254') or 7547 in ports or len(ports) >= 3:
                device_type = f"{vendor} Router"
                confidence = 82
        elif vendor in CONSOLE_VENDORS and confidence < 85:
            device_type = vendor  # "Sony PlayStation", "Microsoft Xbox", "Nintendo"
            confidence = 85
        elif vendor in MOBILE_VENDORS and confidence < 78:
            # These vendors ship almost exclusively Android devices
            device_type = f"{vendor} Android Device"
            confidence = 72
    if confidence < 92:
        if vendor in PRINTER_VENDORS:
            device_type = f"{vendor} Printer"
            confidence = 78
        elif vendor == "Synology":
            device_type = "Synology NAS"
            confidence = 90
        elif vendor == "QNAP":
            device_type = "QNAP NAS"
            confidence = 90
        elif vendor == "Raspberry Pi":
            device_type = "Raspberry Pi"
            confidence = 85
        elif vendor in MEDIA_VENDORS and confidence < 82:
            device_type = f"{vendor} Media Device"
            confidence = 80
        elif vendor in SMARTHOME_VENDORS and confidence < 87:
            device_type = f"{vendor} Smart Home"
            confidence = 85

    # ── Priority 8: Hostname hints ────────────────────────────────────────────
    if hostname and hostname != "Unknown":
        hl = hostname.lower()
        if ("iphone" in hl or "ipad" in hl) and confidence < 85:
            device_type = "Apple iPhone/iPad"
            confidence = 85
        elif "android" in hl and confidence < 80:
            device_type = "Android Device"
            confidence = 80
        elif ("printer" in hl or "print" in hl) and confidence < 80:
            device_type = f"{vendor} Printer" if vendor != "Unknown" else "Printer"
            confidence = 80
        elif ("nas" in hl or "storage" in hl) and confidence < 75:
            device_type = "Network Storage"
            confidence = 75
        elif any(kw in hl for kw in ("nvr", "dvr", "ipcam", "camera", "cctv",
                                     "hikvision", "dahua", "reolink")) and confidence < 78:
            device_type = f"{vendor} NVR/Camera" if vendor not in ("Unknown", "") else "NVR/IP Camera"
            confidence = 75

    # ── Priority 9: Locally-administered MAC (iOS/Android randomization) ──────
    # A locally-administered MAC means the device chose a random address (iOS 14+
    # does this by default). Combined with a Linux-like TTL and no identified type
    # it's almost certainly a mobile phone or tablet. Fires only when the device is
    # still unclassified — OS detection may have set a high confidence value without
    # ever resolving device_type away from "Unknown Device".
    if _is_local_mac and device_type == "Unknown Device":
        if "linux" in os_lower or os_lower in ("unknown", ""):
            device_type = "Mobile Device"
            confidence = max(confidence, 50)

    return device_type, confidence

def get_mdns_friendly_name(ip):
    """Get friendly name from mDNS if available (e.g. "Oliver's iPhone")."""
    mdns_info = mdns_devices.get(ip, {})
    return mdns_info.get("name", None)

def get_mdns_hostname(ip):
    """Get the mDNS server hostname if available (e.g. "Olivers-iPhone")."""
    mdns_info = mdns_devices.get(ip, {})
    return mdns_info.get("hostname", None)
