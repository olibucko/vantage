# Vantage — Synoptic Discovery Engine

A local-network discovery and visualisation tool. Performs active ARP sweeps, passive monitoring, mDNS discovery, and OS/port fingerprinting — then displays results as a live force-directed graph.

![Vantage UI — force-directed network graph with device icons and subnet ring]

---

## Requirements

| Component | Minimum |
|-----------|---------|
| OS        | Windows 10/11 (64-bit) |
| Python    | 3.10 or newer |
| Node.js   | 18 or newer |
| Npcap     | Latest stable — **required** for raw packet capture |
| Privileges | Administrator / root — required for Scapy ARP scanning |

> **Linux/macOS:** The backend runs with `sudo python main.py`. Npcap is Windows-only; Linux uses the built-in raw socket stack via Scapy.

---

## Quick Start (Windows)

### 1. Install Npcap
Download from **https://npcap.com** and install with default options (WinPcap API-compatible mode is not required).

### 2. Clone and set up

```bat
git clone https://github.com/your-org/vantage.git
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

Double-click **`start.bat`** in the project root. It self-elevates to Administrator, opens the backend and frontend in separate terminal windows, and opens `http://localhost:5173` in your browser after a short delay.

Or start manually:

```bat
# Terminal 1 — backend (must be elevated)
cd backend
venv\Scripts\activate
python main.py

# Terminal 2 — frontend
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
| View device details | Right-click any node on the graph |
| Set a custom device label | Right-click a node → click the pencil icon next to the name |
| Search devices | Click the **Search** button or press **Ctrl+K** |
| Export inventory | Click **Export → JSON** or **Export → CSV** |

The graph auto-refreshes via WebSocket. A periodic background scan runs every 5 minutes to catch devices that joined after the initial sweep.

---

## Configuration

### Backend
Copy `backend/.env.example` to `backend/.env` and edit:

```ini
# Backend port (default: 8001)
VANTAGE_PORT=8001

# Allowed frontend CORS origin (default: http://localhost:5173)
VANTAGE_FRONTEND_ORIGIN=http://localhost:5173

# Device stale threshold in seconds (default: 25)
VANTAGE_STALE_THRESHOLD=25

# Seconds between background re-scans (default: 300)
VANTAGE_SCAN_INTERVAL=300
```

### Frontend
Copy `frontend/.env.example` to `frontend/.env`:

```ini
# Backend API URL — change if the backend runs on a different host/port
VITE_API_BASE_URL=http://localhost:8001
```

---

## Data Files

All persistent data is stored in the `data/` directory:

| File | Contents |
|------|----------|
| `nodes.json` | Last-known device cache |
| `aliases.json` | User-defined device labels (MAC → name) |
| `history.json` | First-seen timestamps per MAC address |
| `vantage.log` | Rotating backend log (up to 6 MB across 3 files) |

---

## Troubleshooting

**"Npcap is not installed" error on startup**
→ Download and install Npcap from https://npcap.com, then restart Vantage.

**"Administrator privileges are required" error**
→ Close the window and re-launch `start.bat` — it self-elevates. If running manually, open your terminal as Administrator.

**Port 8001 already in use**
→ Kill the existing process: `netstat -ano | findstr :8001` then `taskkill /PID <pid> /F`. Or set `VANTAGE_PORT=8002` in `backend/.env`.

**No devices discovered after scanning**
→ Confirm the machine running Vantage is on the same physical LAN as the target devices (not a separate VLAN). Check Windows Firewall is not blocking Scapy's raw socket traffic.

**iPhone / mobile devices not appearing**
→ iOS randomises MAC addresses per network. Ensure mDNS is not blocked; the tool identifies iPhones via mDNS service announcements (`_apple-mobdev2`, `_remotepairing`) which require the device to be active on the network.

**Graph not loading (blank screen)**
→ Open DevTools (F12) and check the Console. If you see WebSocket errors, the backend may not be running or the port is mismatched. Verify `VITE_API_BASE_URL` in `frontend/.env`.

---

## Security & Privacy

- Vantage is designed for **local LAN use only** and binds the backend to `127.0.0.1` — it is not reachable from other devices on the network.
- No data is sent externally. All scan results are stored locally in `data/`.
- The ARP scanning and passive monitoring features require elevated privileges; these are used solely for local network packet capture.
- If ARP spoofing is detected (a device advertising a different MAC for a known IP), a warning banner is shown in the UI and logged to `vantage.log`.

---

## Architecture

```
vantage/
├── backend/
│   ├── main.py             # FastAPI app, WebSocket, REST endpoints
│   ├── active_scanner.py   # ARP sweep, OS fingerprinting, port scan
│   ├── passive_monitor.py  # Passive ARP sniffer, keepalive probes
│   ├── service_detector.py # mDNS, banner grabbing, device classification
│   ├── vendor_lookup.py    # MAC OUI → vendor name
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── App.tsx         # Main React component
│       ├── GraphView.tsx   # Force-directed canvas graph
│       └── types.ts        # TypeScript interfaces
├── data/                   # Runtime data (gitignored)
├── start.bat               # One-click Windows launcher
└── README.md
```

---

## Version History

### v1.0.0
- Initial public release
- ARP sweep + passive ARP monitoring
- mDNS / Bonjour device discovery
- OS and device-type fingerprinting (TTL, ports, vendor OUI)
- Force-directed graph with device icons
- Real-time WebSocket updates
- Device aliases, export (JSON/CSV), search, ARP spoofing detection
