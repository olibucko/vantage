VENDORS = {
    "18:f1:45": "TP-Link",
    "d8:43:ae": "Apple",
    "84:47:09": "Samsung",
    "04:e4:b6": "HP",
    "50:03:cf": "Intel",
    "8c:08:aa": "Microsoft",
    "b4:4c:3b": "Google",
    "00:11:32": "Synology",
    "dc:a6:32": "Raspberry Pi",
}

def get_vendor(mac):
    """Returns the vendor name based on the MAC address OUI."""
    if not mac:
        return "Unknown"
    prefix = mac.lower()[:8].replace("-", ":")
    return VENDORS.get(prefix, "Unknown")
