import { useState, useEffect, useMemo, useRef } from 'react';
import GraphView from './GraphView';
import { Shield, RefreshCw, Activity, X, Wifi, Monitor, Cpu, HardDrive, Lock, Unlock } from 'lucide-react';
import type { NetworkNode } from './types';

function App() {
  const [nodes, setNodes] = useState<NetworkNode[]>([]);
  const [selectedNode, setSelectedNode] = useState<NetworkNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<string>('All');
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    const loadCache = async () => {
      try {
        const res = await fetch('http://localhost:8001/nodes');
        const data = await res.json();
        if (data.nodes) setNodes(data.nodes);
      } catch {
        console.error("Vantage: Link Offline");
      }
    };
    loadCache();
  }, []);

  useEffect(() => {
    function connect() {
      const socket = new WebSocket('ws://localhost:8001/ws');
      socket.onmessage = (e) => {
        const d = JSON.parse(e.data);
        if (d.type === 'SCAN_COMPLETE') { setNodes(d.nodes); setLoading(false); }
      };
      socket.onclose = () => setTimeout(connect, 3000);
      ws.current = socket;
    }
    connect();
    return () => ws.current?.close();
  }, []);

  const triggerScan = () => { setLoading(true); fetch('http://localhost:8001/scan'); };

  // Use Right Click to avoid Drag competition [cite: 2026-02-20]
  const handleNodeInteraction = (node: NetworkNode, event: MouseEvent) => {
    event.preventDefault();
    setSelectedNode(node);
  };

  const graphData = useMemo(() => {
    const filtered = nodes.filter(n => {
      if (filter === 'All') return true;
      if (filter === 'Infrastructure') return n.type.includes('Infrastructure') || n.ip.endsWith('.1');
      if (filter === 'Workstations') return n.type.includes('Workstation') || n.type.includes('PC');
      if (filter === 'IoT') return n.type.includes('IoT') || n.vendor === 'TP-Link';
      return true;
    });

    const gateway = nodes.find(n => n.ip.endsWith('.1')) || { 
      ip: '192.168.20.1', hostname: 'Gateway', mac: '', vendor: 'Network', os: '', type: 'Infrastructure', ports: [] 
    };

    const d3Nodes = filtered.map(n => ({
      ...n, id: n.ip, name: n.hostname !== "Unknown" ? n.hostname : n.ip, 
      val: n.ip === gateway.ip ? 6 : 3,
      color: n.ip === gateway.ip ? '#3b82f6' : (n.os === 'Windows' ? '#0ea5e9' : '#f59e0b')
    }));

    if (!d3Nodes.find(d => d.id === gateway.ip)) {
      d3Nodes.push({
        ...gateway,
        id: gateway.ip,
        name: 'Gateway',
        val: 6,
        color: '#3b82f6',
        x: undefined,
        y: undefined,
        vx: undefined,
        vy: undefined
      });
    }

    return { nodes: d3Nodes, links: filtered.filter(n => n.ip !== gateway.ip).map(n => ({ source: gateway.ip, target: n.ip })) };
  }, [nodes, filter]);

  return (
    <div className="flex flex-col h-screen w-screen bg-[#020202] text-neutral-100 font-sans overflow-hidden">
      {/* Precision Header [cite: 2026-02-20] */}
      <header className="flex items-center justify-between px-10 py-6 border-b border-white/20 bg-black/60 backdrop-blur-3xl z-30 shrink-0">
        <div className="flex items-center gap-5">
          <div className="p-2.5 bg-blue-600/10 rounded-xl border border-blue-500/20 shadow-[0_0_15px_rgba(59,130,246,0.1)]">
            <Shield className="w-7 h-7 text-blue-500" />
          </div>
          <div>
            <h1 className="text-2xl font-black tracking-widest uppercase italic text-white leading-none">Vantage</h1>
            <span className="text-[10px] text-blue-500/60 font-mono tracking-[0.3em] uppercase font-bold">Synoptic Discovery</span>
          </div>
        </div>

        <div className="flex items-center gap-8">
          <nav className="flex bg-white/5 rounded-full p-1.5 border border-white/20 shadow-inner">
            {['All', 'Infrastructure', 'Workstations', 'IoT'].map(f => (
              <button key={f} onClick={() => setFilter(f)} className={`px-5 py-2 rounded-full text-[11px] font-black uppercase tracking-widest transition-all cursor-pointer ${filter === f ? 'bg-white text-black shadow-[0_0_20px_rgba(255,255,255,0.2)]' : 'text-neutral-500 hover:text-white'}`}>{f}</button>
            ))}
          </nav>
          <button onClick={triggerScan} disabled={loading} className="group flex items-center gap-3 px-8 py-3 rounded-full bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 transition-all font-black text-xs uppercase tracking-widest shadow-[0_0_30px_rgba(37,99,235,0.3)]">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            {loading ? 'Interrogating' : 'Execute Sweep'}
          </button>
        </div>
      </header>

      <main className="flex-1 relative z-10 w-full h-full">
        {/* Background Grid Layer [cite: 2026-02-20] */}
        <div
          className="absolute inset-0 opacity-50 pointer-events-none"
          style={{
            zIndex: -10,
            backgroundImage: 'radial-gradient(#2a2a2a 1.5px, transparent 1.5px)',
            backgroundSize: '40px 40px'
          }}
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            zIndex: -10,
            backgroundImage: 'radial-gradient(circle at center, rgba(37, 99, 235, 0.12) 0%, transparent 70%)'
          }}
        />

        {/* Scanning Animation Overlay */}
        {loading && (
          <div className="absolute inset-0 pointer-events-none -z-5">
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-blue-500/10 to-transparent animate-pulse" />
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-blue-500 to-transparent animate-[scan_2s_ease-in-out_infinite]"
                 style={{
                   animation: 'scan 2s ease-in-out infinite',
                   boxShadow: '0 0 20px rgba(59, 130, 246, 0.8)'
                 }}
            />
          </div>
        )}
        
        <GraphView data={graphData} onNodeRightClick={handleNodeInteraction} onBackgroundClick={() => setSelectedNode(null)} />
        
        {/* Tactical Legend [cite: 2026-02-20] */}
        <div className="absolute top-10 left-10 p-6 bg-black/80 border border-white/25 rounded-2xl backdrop-blur-2xl flex flex-col gap-4 pointer-events-none z-20 shadow-2xl">
          <div className="flex items-center gap-4"><div className="w-2.5 h-2.5 rounded-full bg-blue-500 shadow-[0_0_10px_#3b82f6]" /> <span className="text-[11px] uppercase tracking-widest font-black text-neutral-400">Core Network</span></div>
          <div className="flex items-center gap-4"><div className="w-2.5 h-2.5 rounded-full bg-[#0ea5e9] shadow-[0_0_10px_#0ea5e9]" /> <span className="text-[11px] uppercase tracking-widest font-black text-neutral-400">Windows Node</span></div>
          <div className="flex items-center gap-4"><div className="w-2.5 h-2.5 rounded-full bg-[#f59e0b] shadow-[0_0_10px_#f59e0b]" /> <span className="text-[11px] uppercase tracking-widest font-black text-neutral-400">Unix / Apple</span></div>
        </div>

        {/* Device Information Panel */}
        {selectedNode && (
          <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] max-h-[80vh] overflow-auto bg-gradient-to-br from-gray-900 via-gray-800 to-black border-2 border-blue-500/30 rounded-2xl shadow-[0_0_60px_rgba(59,130,246,0.3)] z-[9999] backdrop-blur-xl">
            {/* Header */}
            <div className="sticky top-0 flex items-center justify-between p-6 border-b border-white/20 bg-black/60 backdrop-blur-xl">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-blue-600/20 rounded-xl border border-blue-500/30 shadow-[0_0_20px_rgba(59,130,246,0.2)]">
                  <Monitor className="w-6 h-6 text-blue-400" />
                </div>
                <div>
                  <h2 className="text-xl font-black text-white tracking-wider">
                    {selectedNode.hostname !== 'Unknown' ? selectedNode.hostname : selectedNode.ip}
                  </h2>
                  <p className="text-xs text-blue-400 font-mono tracking-widest uppercase">{selectedNode.type}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="p-2 hover:bg-white/10 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-neutral-400 hover:text-white" />
              </button>
            </div>

            {/* Content Grid */}
            <div className="p-6 space-y-4">
              {/* Network Information */}
              <div className="space-y-3">
                <h3 className="text-xs font-black uppercase tracking-widest text-blue-400 flex items-center gap-2">
                  <Wifi className="w-4 h-4" /> Network Identity
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-white/8 rounded-xl border border-white/20">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-neutral-500 mb-1">IP Address</p>
                    <p className="text-lg font-mono font-bold text-white">{selectedNode.ip}</p>
                  </div>
                  <div className="p-4 bg-white/8 rounded-xl border border-white/20">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-neutral-500 mb-1">MAC Address</p>
                    <p className="text-sm font-mono font-bold text-white break-all">{selectedNode.mac}</p>
                  </div>
                </div>
              </div>

              {/* Hardware Information */}
              <div className="space-y-3">
                <h3 className="text-xs font-black uppercase tracking-widest text-blue-400 flex items-center gap-2">
                  <Cpu className="w-4 h-4" /> Hardware & System
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-white/8 rounded-xl border border-white/20">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-neutral-500 mb-1">Vendor</p>
                    <p className="text-base font-bold text-white">{selectedNode.vendor}</p>
                  </div>
                  <div className="p-4 bg-white/8 rounded-xl border border-white/20">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-neutral-500 mb-1">Operating System</p>
                    <p className="text-base font-bold text-white">{selectedNode.os}</p>
                  </div>
                </div>
                <div className="p-4 bg-white/8 rounded-xl border border-white/20">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-neutral-500 mb-1">Hostname</p>
                  <p className="text-base font-mono font-bold text-white">{selectedNode.hostname}</p>
                </div>
              </div>

              {/* Port Information */}
              <div className="space-y-3">
                <h3 className="text-xs font-black uppercase tracking-widest text-blue-400 flex items-center gap-2">
                  <HardDrive className="w-4 h-4" /> Open Ports
                </h3>
                {selectedNode.ports.length > 0 ? (
                  <div className="grid grid-cols-4 gap-2">
                    {selectedNode.ports.map(port => (
                      <div key={port} className="p-3 bg-gradient-to-br from-red-600/20 to-orange-600/20 rounded-lg border border-red-500/30 text-center">
                        <div className="flex items-center justify-center gap-1 mb-1">
                          <Unlock className="w-3 h-3 text-red-400" />
                        </div>
                        <p className="text-lg font-black text-white font-mono">{port}</p>
                        <p className="text-[8px] uppercase tracking-wider text-neutral-400 font-bold mt-1">
                          {port === 22 ? 'SSH' : port === 80 ? 'HTTP' : port === 443 ? 'HTTPS' : port === 445 ? 'SMB' : port === 62078 ? 'iOS' : 'Other'}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-6 bg-white/8 rounded-xl border border-white/20 text-center">
                    <Lock className="w-8 h-8 text-green-500 mx-auto mb-2" />
                    <p className="text-sm font-bold text-neutral-400">No open ports detected</p>
                  </div>
                )}
              </div>

              {/* Security Status */}
              <div className="p-4 bg-gradient-to-r from-blue-600/10 to-purple-600/10 rounded-xl border border-blue-500/20">
                <div className="flex items-center gap-3">
                  <Shield className="w-5 h-5 text-blue-400" />
                  <div>
                    <p className="text-xs font-bold uppercase tracking-widest text-blue-400">Security Assessment</p>
                    <p className="text-sm text-neutral-300 mt-1">
                      {selectedNode.ports.length === 0 ? 'Minimal attack surface - No exposed services detected' :
                       selectedNode.ports.length <= 2 ? 'Low risk - Few services exposed' :
                       selectedNode.ports.length <= 4 ? 'Medium risk - Multiple services running' :
                       'High risk - Many exposed services'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="px-10 py-4 border-t border-white/20 bg-black/80 backdrop-blur-xl text-[10px] font-mono text-neutral-600 flex justify-between items-center shrink-0">
        <div className="flex items-center gap-8">
          <span className="uppercase tracking-[0.4em] font-bold">Vantage v1.2.8</span>
          <span className="flex items-center gap-2 font-black text-green-500/50 uppercase"><Activity className="w-3.5 h-3.5" /> Engine_Nominal</span>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse shadow-[0_0_10px_#3b82f6]" />
            <span className="uppercase tracking-wider font-bold text-blue-500/70">{nodes.length} Nodes Discovered</span>
          </div>
        </div>
        <span className="text-neutral-500 uppercase tracking-widest font-black">Subnet Scope: 192.168.20.0/24</span>
      </footer>
    </div>
  );
}

export default App;