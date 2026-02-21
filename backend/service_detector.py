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

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            addresses = [socket.inet_ntoa(addr) for addr in info.addresses]
            for ip in addresses:
                with mdns_lock:
                    if ip not in mdns_devices:
                        mdns_devices[ip] = {"services": [], "name": None}
                    mdns_devices[ip]["services"].append({
                        "type": type_,
                        "name": name.split('.')[0],
                        "port": info.port
                    })
                    if not mdns_devices[ip]["name"]:
                        mdns_devices[ip]["name"] = name.split('.')[0]

def start_mdns_discovery(duration=10):
    """Run mDNS discovery for specified duration"""
    global mdns_devices
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
        "_raop._tcp.local.",  # AirPlay audio
        "_companion-link._tcp.local.",  # Apple devices
        "_rtsp._tcp.local.",            # IP cameras / NVRs
    ]

    listeners = []
    for service in services:
        listener = NetworkServiceListener()
        browser = ServiceBrowser(zeroconf, service, listener)
        listeners.append((browser, listener))

    time.sleep(duration)
    zeroconf.close()
    return dict(mdns_devices)

def grab_banner(ip, port, timeout=2):
    """Grab service banner from specified port"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))

        # Send appropriate probe based on port
        if port == 80:
            sock.send(b"GET / HTTP/1.0\r\nHost: %s\r\n\r\n" % ip.encode())
        elif port == 443:
            return {"service": "HTTPS", "banner": "SSL/TLS"}
        elif port == 554:
            # Send RTSP OPTIONS probe — servers reply with "RTSP/1.0 ..."
            sock.send(b"OPTIONS * RTSP/1.0\r\nCSeq: 1\r\n\r\n")
        elif port == 8000:
            # Hikvision HTTP SDK — try a GET to get the Server header
            sock.send(b"GET / HTTP/1.0\r\nHost: %s\r\n\r\n" % ip.encode())
        elif port == 8899:
            # ONVIF HTTP — generic GET
            sock.send(b"GET / HTTP/1.0\r\nHost: %s\r\n\r\n" % ip.encode())
        elif port == 22:
            # SSH sends banner first
            pass
        elif port == 21:
            # FTP sends banner first
            pass
        else:
            sock.send(b"\r\n")

        banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
        sock.close()

        # Parse banner for service info
        service_name = detect_service_from_banner(port, banner)
        return {"service": service_name, "banner": banner[:200]}  # Limit banner length
    except:
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
    # SNMP querying disabled for now - requires complex async setup
    # TODO: Implement SNMP v2c synchronous queries using pysnmp
    return None

def detect_device_type_advanced(ip, ports, vendor, os_guess, hostname):
    """Advanced device type detection using multiple signals.

    Signal priority (highest → lowest):
    1. Unambiguous protocol ports: iOS lockdown (62078), SMB (445) + OS hint, RDP (3389)
    2. NVR / camera ports: RTSP (554), Dahua SDK (37777/34567), Hikvision SDK (8000), ONVIF (8899)
    3. mDNS service announcements  — gated so SMB cannot be overridden by Bonjour
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

        if "_rtsp._tcp.local." in service_types and confidence < 90:
            lbl = vendor if vendor not in ("Unknown", "") else None
            return (f"{lbl} NVR/Camera" if lbl else "NVR/IP Camera"), 90

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
        elif 22 in ports and 80 in ports and 443 in ports:
            if ip.endswith('.1') or ip.endswith('.254'):
                device_type = f"{vendor} Router" if vendor != "Unknown" else "Router/Gateway"
                confidence = 75
            else:
                device_type = "Linux Server"
                confidence = 63
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
    if confidence < 82:
        if vendor in ["TP-Link", "Netgear", "D-Link", "Ubiquiti", "Cisco"]:
            if ip.endswith('.1') or ip.endswith('.254') or len(ports) >= 3:
                device_type = f"{vendor} Router"
                confidence = 80
        elif vendor in ["HP", "Canon", "Epson", "Brother", "Xerox"]:
            device_type = f"{vendor} Printer"
            confidence = 75
        elif vendor == "Synology":
            device_type = "Synology NAS"
            confidence = 90
        elif vendor == "Raspberry Pi":
            device_type = "Raspberry Pi"
            confidence = 85
        elif vendor in ["Sonos", "Roku", "Amazon"]:
            device_type = f"{vendor} Media Device"
            confidence = 80
        elif vendor in ["Nest", "Ring", "Philips Hue", "Belkin"]:
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

    return device_type, confidence

def get_mdns_friendly_name(ip):
    """Get friendly name from mDNS if available"""
    mdns_info = mdns_devices.get(ip, {})
    return mdns_info.get("name", None)
