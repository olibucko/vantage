# Comprehensive MAC OUI Database - Top 200+ vendors
VENDORS = {
    # Networking Equipment
    "18:f1:45": "TP-Link", "50:c7:bf": "TP-Link", "c0:25:e9": "TP-Link",
    "00:18:0a": "Netgear", "a0:63:91": "Netgear", "e0:46:9a": "Netgear",
    "00:1d:7e": "Cisco", "00:0f:66": "Cisco", "00:07:0d": "Cisco",
    "f8:1a:67": "Cisco", "00:0c:29": "VMware", "00:50:56": "VMware",
    "00:0e:58": "D-Link", "5c:f9:6a": "D-Link", "14:d6:4d": "D-Link",
    "00:0d:b9": "Ubiquiti", "f0:9f:c2": "Ubiquiti", "24:5a:4c": "Ubiquiti",
    "44:d9:e7": "Aruba", "6c:f3:7f": "Aruba", "00:1a:1e": "Aruba",

    # Apple Devices
    "d8:43:ae": "Apple", "ac:de:48": "Apple", "88:66:5a": "Apple",
    "3c:ab:8e": "Apple", "f0:18:98": "Apple", "d0:03:4b": "Apple",
    "00:03:93": "Apple", "00:0a:95": "Apple", "a8:88:08": "Apple",
    "dc:0c:2d": "Apple", "68:a8:6d": "Apple", "70:35:60": "Apple",

    # Samsung
    "84:47:09": "Samsung", "dc:71:96": "Samsung", "2c:44:fd": "Samsung",
    "78:1f:db": "Samsung", "c8:3d:d4": "Samsung", "ec:a9:07": "Samsung",
    "68:27:37": "Samsung", "b4:79:a7": "Samsung", "ac:5a:14": "Samsung",

    # Intel/Microsoft/Google
    "50:03:cf": "Intel", "3c:a9:f4": "Intel", "00:03:ff": "Intel",
    "8c:08:aa": "Microsoft", "00:03:ff": "Microsoft", "28:18:78": "Microsoft",
    "b4:4c:3b": "Google", "f8:8f:ca": "Google", "ac:37:43": "Google",
    "da:a1:19": "Google", "74:e5:43": "Google", "b0:70:2d": "Google",

    # HP/Dell/Lenovo
    "04:e4:b6": "HP", "00:17:08": "HP", "00:1e:0b": "HP",
    "d4:85:64": "HP", "00:26:55": "Dell", "00:14:22": "Dell",
    "b8:ca:3a": "Dell", "f8:b1:56": "Dell", "00:21:70": "Lenovo",
    "54:ee:75": "Lenovo", "00:1c:25": "Lenovo", "dc:41:a9": "Lenovo",

    # IoT & Single Board Computers
    "dc:a6:32": "Raspberry Pi", "b8:27:eb": "Raspberry Pi", "e4:5f:01": "Raspberry Pi",
    "d8:3a:dd": "Raspberry Pi", "00:11:32": "Synology", "00:90:e8": "Seagate",
    "00:04:20": "Slim Devices (Roku)", "d0:73:d5": "Roku", "b0:a7:37": "Roku",

    # Amazon/Ring
    "74:c2:46": "Amazon", "00:71:47": "Amazon", "38:f7:3d": "Amazon",
    "44:65:0d": "Amazon", "6c:56:97": "Amazon", "0c:47:c9": "Amazon",

    # Printers & Peripherals
    "00:01:e3": "Xerox", "00:00:aa": "Xerox", "b4:6d:83": "Epson",
    "00:00:48": "Epson", "64:eb:8c": "Canon", "00:00:85": "Canon",
    "a4:5d:36": "Canon", "00:25:b3": "Brother", "30:05:5c": "Brother",

    # Smart Home/IoT
    "b4:75:0e": "Philips Hue", "00:17:88": "Philips", "ec:fa:5c": "Philips",
    "00:04:20": "Sonos", "54:2a:1b": "Sonos", "b8:e9:37": "Sonos",
    "68:d7:9a": "Nest", "64:16:66": "Nest", "18:b4:30": "Nest",
    "00:d0:2d": "Belkin", "ec:1a:59": "Belkin", "94:10:3e": "Belkin",

    # Mobile Carriers
    "00:00:0c": "Cisco", "70:bb:e9": "Huawei", "c8:85:50": "Xiaomi",
    "34:ce:00": "Xiaomi", "f4:8b:32": "Xiaomi", "58:44:98": "Xiaomi",
    "00:1c:b3": "LG Electronics", "a0:91:69": "LG Electronics",
    "00:0c:e4": "Motorola", "cc:c7:60": "Motorola",

    # Network Storage
    "00:08:9b": "Western Digital", "00:90:a9": "Western Digital",
    "b8:ae:ed": "Buffalo", "00:07:e9": "Zyxel",

    # Game Consoles
    "00:d9:d1": "Sony PlayStation", "7c:bb:8a": "Sony PlayStation",
    "b8:27:eb": "Sony PlayStation", "00:50:f2": "Microsoft Xbox",
    "d8:9e:3f": "Microsoft Xbox", "00:22:48": "Nintendo",
}

def get_vendor(mac):
    """Returns the vendor name based on the MAC address OUI."""
    if not mac:
        return "Unknown"
    prefix = mac.lower()[:8].replace("-", ":")
    return VENDORS.get(prefix, "Unknown")
