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
        8443: "HTTPS-Alt", 9100: "Printer (JetDirect)", 62078: "iOS Services"
    }
    return services.get(port, f"Port {port}")

def query_snmp(ip, timeout=2):
    """Query SNMP for device information"""
    # SNMP querying disabled for now - requires complex async setup
    # TODO: Implement SNMP v2c synchronous queries using pysnmp
    return None

def detect_device_type_advanced(ip, ports, vendor, os_guess, hostname):
    """Advanced device type detection using multiple signals"""

    device_type = "Unknown Device"
    confidence = 0

    # Check mDNS data
    mdns_info = mdns_devices.get(ip, {})
    if mdns_info:
        services = mdns_info.get("services", [])
        service_types = [s["type"] for s in services]

        # AirPlay/HomeKit = Apple TV/HomePod
        if "_airplay._tcp.local." in service_types or "_raop._tcp.local." in service_types:
            device_type = "Apple TV/HomePod"
            confidence = 90
            return device_type, confidence

        # Printer services
        if "_printer._tcp.local." in service_types or "_ipp._tcp.local." in service_types:
            device_type = f"{vendor} Printer" if vendor != "Unknown" else "Network Printer"
            confidence = 95
            return device_type, confidence

        # Chromecast
        if "_googlecast._tcp.local." in service_types:
            device_type = "Google Chromecast"
            confidence = 95
            return device_type, confidence

    # Port-based detection
    if 9100 in ports:  # JetDirect
        device_type = f"{vendor} Printer" if vendor != "Unknown" else "Network Printer"
        confidence = 85
    elif 62078 in ports:  # iOS devices
        device_type = "Apple iPhone/iPad"
        confidence = 90
    elif 445 in ports and 3389 in ports:  # Windows with RDP
        device_type = "Windows Server"
        confidence = 80
    elif 445 in ports:
        device_type = "Windows Workstation"
        confidence = 70
    elif 22 in ports and 80 in ports and 443 in ports:
        if ".1" in ip or ".254" in ip:
            device_type = f"{vendor} Router" if vendor != "Unknown" else "Router/Gateway"
            confidence = 75
        else:
            device_type = "Linux Server"
            confidence = 65
    elif 22 in ports and len(ports) <= 2:
        device_type = "Linux Device"
        confidence = 60

    # Vendor-specific
    if vendor in ["TP-Link", "Netgear", "D-Link", "Ubiquiti", "Cisco"]:
        if ".1" in ip or ".254" in ip or len(ports) >= 3:
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

    # Hostname hints
    if hostname and hostname != "Unknown":
        hostname_lower = hostname.lower()
        if "iphone" in hostname_lower or "ipad" in hostname_lower:
            device_type = "Apple iPhone/iPad"
            confidence = 85
        elif "android" in hostname_lower:
            device_type = "Android Device"
            confidence = 80
        elif "printer" in hostname_lower or "print" in hostname_lower:
            device_type = f"{vendor} Printer" if vendor != "Unknown" else "Printer"
            confidence = 80
        elif "nas" in hostname_lower or "storage" in hostname_lower:
            device_type = "Network Storage"
            confidence = 75

    return device_type, confidence

def get_mdns_friendly_name(ip):
    """Get friendly name from mDNS if available"""
    mdns_info = mdns_devices.get(ip, {})
    return mdns_info.get("name", None)
