# Vantage — Network Viewer

A local-network discovery and visualisation tool. Performs active ARP sweeps, passive ARP monitoring, mDNS/ONVIF/SSDP discovery, and OS/port fingerprinting — then displays results as a live force-directed graph.

---

## Requirements

| Component | Minimum |
|-----------|---------|
| OS | Windows 10/11 (64-bit) |
| Python | 3.10 or newer |
| Node.js | 18 or newer |
| Npcap | Latest stable — **required** for raw packet capture on Windows |
| Privileges | Administrator / root — required for Scapy ARP scanning |

> **Linux/macOS:** Run the backend with `sudo python main.py`. Npcap is Windows-only; Linux/macOS use the raw socket stack via Scapy directly.

---

## Quick Start (Windows)

### 1. Install Npcap

Download from **https://npcap.com** and install with default options.

### 2. Clone and set up

```bat
git clone https://github.com/olibucko/vantage.git
cd vantage
```

**Backend:**
```bat
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Frontend:**
```bat
cd ..\frontend
npm install
```

### 3. Launch

Double-click **`start.bat`** in the project root. It self-elevates to Administrator, starts the backend and frontend in separate windows, and opens `http://localhost:5173` in your browser automatically.

Or start manually:

```bat
:: Terminal 1 — backend (must be run as Administrator)
cd backend
venv\Scripts\activate
python main.py

:: Terminal 2 — frontend
cd frontend
npm run dev
```

### 4. Open

Navigate to **http://localhost:5173**. The first scan starts automatically after ~5 seconds and takes up to 30 seconds on large networks.

---

## Usage

| Action | How |
|--------|-----|
| Manual scan | Click **Execute Sweep** in the header |
| View device details | **Right-click** any node on the graph |
| Set a custom device label | Right-click a node → click the pencil icon next to the name |
| Dismiss a device | Wait for the stale timeout (~25 s after it goes offline) |

The graph updates in real time via WebSocket. A background scan runs every 5 minutes to catch devices that joined after the initial sweep.

---

## How It Works

1. **Ping sweep** — wakes sleeping devices before the ARP scan
2. **Parallel discovery** — ARP broadcast, mDNS/Bonjour, ONVIF (cameras/NVRs), and SSDP/UPnP run concurrently
3. **Deep interrogation** — each discovered device gets OS fingerprinting (TTL + TCP window), parallel port scanning, banner grabbing, and reverse-DNS lookup
4. **Passive monitoring** — a continuous ARP sniffer catches devices that join or leave between scans
5. **Real-time push** — results stream to the browser over WebSocket as each device finishes interrogation

---

## Graph Legend

| Colour | Meaning |
|--------|---------|
| 🔵 Blue | Gateway / core network infrastructure |
| 🔷 Light blue | Windows devices |
| 🟡 Amber | Linux / macOS / unknown |
| 🟢 Green | IoT / smart home / cameras |

Device icons appear inside each node (router, phone, camera, printer, etc.). Nodes without a detected type show a **?** glyph.

---

## Data & Privacy

All data is stored locally in the `data/` directory (gitignored):

| File | Contents |
|------|----------|
| `nodes.json` | Last-known device cache |
| `aliases.json` | User-defined device labels (MAC → name) |
| `history.json` | First-seen timestamps per MAC address |

No data is sent externally. The backend binds exclusively to `127.0.0.1` and is not reachable from other devices on the network.

---

## Troubleshooting

**"Npcap is not installed" error on startup**
→ Download and install Npcap from https://npcap.com, then restart Vantage.

**"Administrator privileges are required" error**
→ Re-launch `start.bat` — it self-elevates. If running manually, open your terminal as Administrator.

**Port 8001 already in use**
→ Kill the existing process: `netstat -ano | findstr :8001` then `taskkill /PID <pid> /F`.

**No devices discovered after scanning**
→ Confirm the machine is on the same physical LAN as the target devices (not a separate VLAN). Check that Windows Firewall is not blocking Scapy's raw socket traffic.

**iPhone / mobile devices not appearing**
→ iOS randomises MAC addresses per network. The tool identifies iPhones via mDNS service announcements (`_apple-mobdev2`, `_remotepairing`) — ensure the device is awake and active on the network.

**Graph not loading / blank screen**
→ Open browser DevTools (F12) → Console. WebSocket errors indicate the backend is not running or the port is mismatched. Verify the backend started without errors.

---

## Architecture

```
vantage/
├── backend/
│   ├── main.py             # FastAPI app, WebSocket server, REST endpoints
│   ├── active_scanner.py   # ARP sweep, OS fingerprinting, parallel port scan
│   ├── passive_monitor.py  # Continuous ARP sniffer, keepalive probes
│   ├── service_detector.py # mDNS, ONVIF, SSDP, banner grabbing, device classification
│   ├── vendor_lookup.py    # MAC OUI → vendor name (200+ entries)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── App.tsx         # Main React component, WebSocket client
│       ├── GraphView.tsx   # Force-directed canvas graph
│       └── types.ts        # TypeScript interfaces
├── data/                   # Runtime data — gitignored
├── start.bat               # One-click Windows launcher
└── README.md
```

**Tech stack:** Python 3 · FastAPI · Uvicorn · Scapy · Zeroconf · React 19 · TypeScript · Vite · Tailwind CSS · react-force-graph-2d

---

## Version History

### v1.0.0 — Initial public release
- Active ARP sweep + passive ARP monitoring
- mDNS / Bonjour, ONVIF, and SSDP/UPnP device discovery
- OS fingerprinting via TTL and TCP window analysis
- Parallel port scanning and service banner grabbing
- Device-type classification with confidence scoring
- Force-directed graph with per-device icons and subnet ring
- Real-time WebSocket updates with spawn/despawn animations
- Scan progress bar with live phase messages
- Device aliases (custom labels per MAC address)
- Hover tooltip and right-click detail panel
- Automatic startup scan + periodic background sweeps
- Stale device eviction with disconnect animations
