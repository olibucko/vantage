# Comprehensive MAC OUI Database
# OUI prefixes are lowercase colon-separated (e.g. "aa:bb:cc").
# IMPORTANT: Python dicts discard duplicate keys — keep each OUI unique.
VENDORS = {
    # ── Networking Equipment ──────────────────────────────────────────────────
    "18:f1:45": "TP-Link", "50:c7:bf": "TP-Link", "c0:25:e9": "TP-Link",
    "98:da:c4": "TP-Link", "b0:95:8e": "TP-Link", "54:af:97": "TP-Link",
    "00:18:0a": "Netgear", "a0:63:91": "Netgear", "e0:46:9a": "Netgear",
    "20:e5:2a": "Netgear", "9c:d3:6d": "Netgear",
    "00:1d:7e": "Cisco",   "00:0f:66": "Cisco",   "00:07:0d": "Cisco",
    "f8:1a:67": "Cisco",   "00:00:0c": "Cisco",   "00:50:f2": "Cisco",
    "00:0e:58": "D-Link",  "5c:f9:6a": "D-Link",  "14:d6:4d": "D-Link",
    "00:0d:b9": "Ubiquiti","f0:9f:c2": "Ubiquiti","24:5a:4c": "Ubiquiti",
    "80:2a:a8": "Ubiquiti","b4:fb:e4": "Ubiquiti",
    "44:d9:e7": "Aruba",   "6c:f3:7f": "Aruba",   "00:1a:1e": "Aruba",
    "94:b4:0f": "Aruba",
    "00:07:e9": "Zyxel",   "b8:ec:a3": "Zyxel",   "e8:37:7a": "Zyxel",
    "70:bb:e9": "Huawei",  "48:ad:08": "Huawei",  "4c:1f:cc": "Huawei",
    "00:e0:fc": "Huawei",  "28:31:52": "Huawei",  "2c:ab:00": "Huawei",
    "cc:53:b5": "Huawei",  "d4:6e:5c": "Huawei",

    # ── Apple Devices ─────────────────────────────────────────────────────────
    "d8:43:ae": "Apple", "ac:de:48": "Apple", "88:66:5a": "Apple",
    "3c:ab:8e": "Apple", "f0:18:98": "Apple", "d0:03:4b": "Apple",
    "00:03:93": "Apple", "00:0a:95": "Apple", "a8:88:08": "Apple",
    "dc:0c:2d": "Apple", "68:a8:6d": "Apple", "70:35:60": "Apple",
    "f4:f1:5a": "Apple", "98:01:a7": "Apple", "8c:85:90": "Apple",
    "54:e4:3a": "Apple", "a4:5e:60": "Apple", "00:cd:fe": "Apple",
    "bc:92:6b": "Apple", "28:37:37": "Apple", "60:f8:1d": "Apple",
    "70:ec:e4": "Apple", "a8:96:8a": "Apple", "b8:09:8a": "Apple",
    "14:8f:c6": "Apple", "3c:22:fb": "Apple", "78:4f:43": "Apple",
    "d4:61:9d": "Apple", "f8:27:93": "Apple", "04:52:f3": "Apple",
    "34:ab:37": "Apple", "1c:91:48": "Apple", "80:be:05": "Apple",
    "dc:2b:61": "Apple", "a8:fa:d8": "Apple",

    # ── Samsung ───────────────────────────────────────────────────────────────
    "84:47:09": "Samsung", "dc:71:96": "Samsung", "2c:44:fd": "Samsung",
    "78:1f:db": "Samsung", "c8:3d:d4": "Samsung", "ec:a9:07": "Samsung",
    "68:27:37": "Samsung", "b4:79:a7": "Samsung", "ac:5a:14": "Samsung",
    "8c:77:12": "Samsung", "cc:07:ab": "Samsung", "50:01:bb": "Samsung",
    "94:35:0a": "Samsung", "f4:42:8f": "Samsung",

    # ── Intel ─────────────────────────────────────────────────────────────────
    "50:03:cf": "Intel", "3c:a9:f4": "Intel", "8c:8d:28": "Intel",
    "a4:c3:f0": "Intel", "00:21:6a": "Intel", "f8:94:c2": "Intel",
    "ac:fd:ce": "Intel", "48:51:b7": "Intel",

    # ── Microsoft ─────────────────────────────────────────────────────────────
    "8c:08:aa": "Microsoft", "28:18:78": "Microsoft", "00:03:ff": "Microsoft",
    "54:52:c0": "Microsoft",

    # ── VMware / Hyper-V ──────────────────────────────────────────────────────
    "00:0c:29": "VMware",  "00:50:56": "VMware",
    "00:15:5d": "Hyper-V",

    # ── Google ────────────────────────────────────────────────────────────────
    "b4:4c:3b": "Google", "f8:8f:ca": "Google", "ac:37:43": "Google",
    "da:a1:19": "Google", "74:e5:43": "Google", "b0:70:2d": "Google",
    "f4:f5:d8": "Google", "58:cb:52": "Google", "54:60:09": "Google",

    # ── HP / Dell / Lenovo ────────────────────────────────────────────────────
    "04:e4:b6": "HP",     "00:17:08": "HP",     "00:1e:0b": "HP",
    "d4:85:64": "HP",     "3c:d9:2b": "HP",
    "00:26:55": "Dell",   "00:14:22": "Dell",   "b8:ca:3a": "Dell",
    "f8:b1:56": "Dell",   "18:03:73": "Dell",   "14:18:77": "Dell",
    "00:21:70": "Lenovo", "54:ee:75": "Lenovo", "00:1c:25": "Lenovo",
    "dc:41:a9": "Lenovo", "40:a8:f0": "Lenovo",

    # ── Raspberry Pi ──────────────────────────────────────────────────────────
    # NOTE: b8:27:eb was also (incorrectly) used by some Sony entries — it
    # belongs exclusively to the Raspberry Pi Foundation.
    "dc:a6:32": "Raspberry Pi", "b8:27:eb": "Raspberry Pi",
    "e4:5f:01": "Raspberry Pi", "d8:3a:dd": "Raspberry Pi",
    "2c:cf:67": "Raspberry Pi",

    # ── Synology / NAS ────────────────────────────────────────────────────────
    "00:11:32": "Synology", "bc:ee:7b": "Synology", "00:90:e8": "Seagate",
    "00:08:9b": "Western Digital", "00:90:a9": "Western Digital",
    "b8:ae:ed": "Buffalo",  "00:0e:a6": "QNAP",

    # ── Roku ──────────────────────────────────────────────────────────────────
    # NOTE: 00:04:20 belongs to Slim Devices (Roku/Logitech), NOT Sonos.
    "00:04:20": "Slim Devices (Roku)", "d0:73:d5": "Roku", "b0:a7:37": "Roku",
    "cc:6d:a0": "Roku",

    # ── Amazon / Ring ─────────────────────────────────────────────────────────
    "74:c2:46": "Amazon", "00:71:47": "Amazon", "38:f7:3d": "Amazon",
    "44:65:0d": "Amazon", "6c:56:97": "Amazon", "0c:47:c9": "Amazon",
    "fc:a6:67": "Amazon", "50:dc:e7": "Amazon",

    # ── Printers & Peripherals ────────────────────────────────────────────────
    "00:01:e3": "Xerox",   "00:00:aa": "Xerox",
    "b4:6d:83": "Epson",   "00:00:48": "Epson",
    "64:eb:8c": "Canon",   "00:00:85": "Canon",   "a4:5d:36": "Canon",
    "00:25:b3": "Brother", "30:05:5c": "Brother",

    # ── Smart Home / IoT ──────────────────────────────────────────────────────
    "b4:75:0e": "Philips Hue", "00:17:88": "Philips",
    "54:2a:1b": "Sonos",       "b8:e9:37": "Sonos",   "94:9f:3e": "Sonos",
    "68:d7:9a": "Nest",        "64:16:66": "Nest",    "18:b4:30": "Nest",
    "00:d0:2d": "Belkin",      "ec:1a:59": "Belkin",  "94:10:3e": "Belkin",

    # ── Xiaomi / OnePlus / Motorola / LG ─────────────────────────────────────
    "c8:85:50": "Xiaomi",     "34:ce:00": "Xiaomi",  "f4:8b:32": "Xiaomi",
    "58:44:98": "Xiaomi",     "64:a2:f9": "Xiaomi",  "00:ec:0a": "Xiaomi",
    "00:1c:b3": "LG Electronics", "a0:91:69": "LG Electronics",
    "00:0c:e4": "Motorola",   "cc:c7:60": "Motorola","5c:51:88": "Motorola",
    "ac:37:43": "OnePlus",

    # ── Security Cameras / NVR ────────────────────────────────────────────────
    "bc:ad:28": "Hikvision", "44:19:b6": "Hikvision", "a0:cc:2b": "Hikvision",
    "c0:56:e3": "Hikvision", "54:c4:15": "Dahua",   "e0:50:8b": "Dahua",
    "90:01:3b": "Dahua",     "3c:ef:8c": "Reolink",  "ec:71:db": "Reolink",

    # ── Game Consoles ─────────────────────────────────────────────────────────
    "00:d9:d1": "Sony PlayStation", "7c:bb:8a": "Sony PlayStation",
    "f8:46:1c": "Sony PlayStation",
    # NOTE: b8:27:eb belongs to Raspberry Pi — Sony does NOT own this OUI.
    "d8:9e:3f": "Microsoft Xbox", "7c:ed:8d": "Microsoft Xbox",
    "98:5f:d3": "Microsoft Xbox",
    "00:22:48": "Nintendo",        "98:e8:fa": "Nintendo",
    "cc:fb:65": "Nintendo",

    # ── Other Mobile / Wearables ──────────────────────────────────────────────
    "50:eb:f6": "Fitbit", "00:1c:b3": "LG Electronics",
}

def get_vendor(mac: str) -> str:
    """Return the vendor name for a MAC address OUI, or 'Unknown'."""
    if not mac:
        return "Unknown"
    # Normalise separators and case, take first 3 octets
    prefix = mac.lower()[:8].replace("-", ":")
    return VENDORS.get(prefix, "Unknown")
