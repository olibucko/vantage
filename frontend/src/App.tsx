import { useState, useEffect, useMemo, useRef } from 'react';
import GraphView from './GraphView';
import type { GraphViewHandle } from './GraphView';
import { Shield, RefreshCw, Activity, X, Wifi, Monitor, Cpu, HardDrive, Lock, Unlock } from 'lucide-react';
import type { NetworkNode, AnimEntry } from './types';

function App() {
  const [nodes, setNodes] = useState<NetworkNode[]>([]);
  const [selectedNode, setSelectedNode] = useState<NetworkNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<string>('All');
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
  const animStateRef = useRef<Map<string, AnimEntry>>(new Map());
  // Mirror of `nodes` state for synchronous reads inside WS callbacks (avoids stale closures)
  const nodesRef = useRef<NetworkNode[]>([]);
  const graphRef = useRef<GraphViewHandle>(null);

  useEffect(() => {
    const loadCache = async () => {
      try {
        const res = await fetch('http://localhost:8001/nodes');
        const data = await res.json();
        if (data.nodes) {
          const cached: NetworkNode[] = data.nodes;
          const now = performance.now();
          // Stagger spawn animations so cached nodes materialise one-by-one
          cached.forEach((node, i) => {
            animStateRef.current.set(node.ip, { type: 'spawn', startTime: now + i * 80 });
            // Clean up spawn entry once animation completes so links return to idle grey
            setTimeout(() => {
              if (animStateRef.current.get(node.ip)?.type === 'spawn')
                animStateRef.current.delete(node.ip);
            }, 950 + i * 80);
          });
          nodesRef.current = cached;
          setNodes(cached);
        }
      } catch {
        console.error("Vantage: Link Offline");
      }
    };
    loadCache();
  }, []);

  useEffect(() => {
    function connect() {
      console.log("Vantage: Initiating WebSocket connection...");
      setWsStatus('connecting');

      const socket = new WebSocket('ws://localhost:8001/ws');

      socket.onopen = () => {
        console.log("Vantage: WebSocket connected!");
        setWsStatus('connected');
        if (reconnectTimeout.current) {
          clearTimeout(reconnectTimeout.current);
          reconnectTimeout.current = null;
        }
      };

      socket.onmessage = (e) => {
        const d = JSON.parse(e.data);
        console.log("Vantage: Received message:", d.type);

        if (d.type === 'SCAN_COMPLETE') {
          const scanNodes: NetworkNode[] = d.nodes;
          const scanIpSet = new Set(scanNodes.map((n: NetworkNode) => n.ip));
          const prev = nodesRef.current;
          const now = performance.now();

          // Nodes that disappeared → despawn animation
          const removedIps = prev.filter(n => !scanIpSet.has(n.ip)).map(n => n.ip);
          // Nodes that are new → spawn animation
          const prevIpSet = new Set(prev.map(n => n.ip));
          const addedIps = scanNodes.filter((n: NetworkNode) => !prevIpSet.has(n.ip)).map(n => n.ip);

          animStateRef.current.clear();
          removedIps.forEach(ip => animStateRef.current.set(ip, { type: 'despawn', startTime: now }));
          addedIps.forEach(ip => animStateRef.current.set(ip, { type: 'spawn', startTime: now }));

          // Keep removed nodes in the list temporarily so despawn animation plays
          const mergedMap = new Map(prev.map(n => [n.ip, n]));
          scanNodes.forEach((n: NetworkNode) => mergedMap.set(n.ip, n));
          const merged = Array.from(mergedMap.values());
          nodesRef.current = merged;
          setNodes(merged);

          // After despawn animation finishes, remove the stale nodes
          if (removedIps.length > 0) {
            const removedSet = new Set(removedIps);
            setTimeout(() => {
              nodesRef.current = nodesRef.current.filter(n => !removedSet.has(n.ip));
              setNodes([...nodesRef.current]);
              removedIps.forEach(ip => animStateRef.current.delete(ip));
            }, 900);
          }
          // Clean up spawn entries after animation completes
          addedIps.forEach(ip => {
            setTimeout(() => {
              if (animStateRef.current.get(ip)?.type === 'spawn') animStateRef.current.delete(ip);
            }, 950);
          });

          // Place new nodes at the gateway so they emerge from the centre
          if (addedIps.length > 0) {
            const gatewayIp = prev.find(n => n.ip.endsWith('.1'))?.ip ?? scanNodes.find((n: NetworkNode) => n.ip.endsWith('.1'))?.ip ?? '';
            requestAnimationFrame(() => {
              addedIps.forEach(ip => graphRef.current?.initNodeAtGateway(ip, gatewayIp));
            });
          }

          console.log(`Vantage: Scan complete — ${scanNodes.length} live, ${removedIps.length} removed, ${addedIps.length} new`);
          setLoading(false);

        } else if (d.type === 'PASSIVE_UPDATE') {
          // Only add genuinely new IPs — never update existing nodes here.
          // Updating existing nodes would rebuild graphData and reheat the force simulation, causing jitter.
          const existingIps = new Set(nodesRef.current.map(n => n.ip));
          const newNodes = (d.nodes as NetworkNode[]).filter(n => {
            const anim = animStateRef.current.get(n.ip);
            return !existingIps.has(n.ip) && anim?.type !== 'despawn';
          });
          if (newNodes.length > 0) {
            nodesRef.current = [...nodesRef.current, ...newNodes];
            setNodes([...nodesRef.current]);
          }
          console.log(`Vantage: Passive update — ${newNodes.length} new node(s) added`);

        } else if (d.type === 'DEVICE_CONNECTED') {
          const newNode: NetworkNode = d.node;
          // Skip if already visible (e.g. preloaded from cache on startup)
          if (!nodesRef.current.some(n => n.ip === newNode.ip)) {
            animStateRef.current.set(newNode.ip, { type: 'spawn', startTime: performance.now() });
            setTimeout(() => {
              if (animStateRef.current.get(newNode.ip)?.type === 'spawn')
                animStateRef.current.delete(newNode.ip);
            }, 950);
            const gatewayIp = nodesRef.current.find(n => n.ip.endsWith('.1'))?.ip ?? '';
            nodesRef.current = [...nodesRef.current, newNode];
            setNodes([...nodesRef.current]);
            // Place at gateway position after React has committed + ForceGraph2D has processed
            requestAnimationFrame(() => graphRef.current?.initNodeAtGateway(newNode.ip, gatewayIp));
            console.log(`Vantage: Device connected — ${newNode.ip}`);
          }

        } else if (d.type === 'DEVICE_DISCONNECTED') {
          const ip: string = d.ip;
          console.log(`Vantage: Device disconnected — ${ip}`);
          animStateRef.current.set(ip, { type: 'despawn', startTime: performance.now() });
          setTimeout(() => {
            nodesRef.current = nodesRef.current.filter(n => n.ip !== ip);
            setNodes([...nodesRef.current]);
            animStateRef.current.delete(ip);
          }, 900);

        } else if (d.type === 'DEVICE_UPDATED') {
          const updated: NetworkNode = d.node;
          if (nodesRef.current.some(n => n.ip === updated.ip)) {
            nodesRef.current = nodesRef.current.map(n => n.ip === updated.ip ? { ...n, ...updated } : n);
            setNodes([...nodesRef.current]);
            console.log(`Vantage: Device updated — ${updated.ip} (${updated.type})`);
          }

        } else if (d.type === 'HEARTBEAT') {
          // silent
        }
      };

      socket.onerror = (error) => {
        console.error("Vantage: WebSocket error:", error);
        setWsStatus('disconnected');
      };

      socket.onclose = () => {
        console.log("Vantage: WebSocket disconnected, reconnecting in 3s...");
        setWsStatus('disconnected');
        reconnectTimeout.current = setTimeout(connect, 3000);
      };

      ws.current = socket;
    }

    connect();

    return () => {
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
      ws.current?.close();
    };
  }, []);

  const triggerScan = () => { setLoading(true); fetch('http://localhost:8001/scan'); };

  // Use Right Click to avoid Drag competition [cite: 2026-02-20]
  const handleNodeInteraction = (node: NetworkNode, event: MouseEvent) => {
    event.preventDefault();
    setSelectedNode(node);
  };

  // Generate display name: Device Type (Vendor) or fallback to IP
  const getDisplayName = (node: NetworkNode): string => {
    const type = node.type;
    const vendor = node.vendor;

    // If we have a friendly mDNS name, use it
    if (node.deviceName && node.deviceName !== "Unknown") {
      return node.deviceName;
    }

    // Priority: "Device Type" if specific, otherwise fallback hierarchy
    if (type && type !== "Unknown Device" && type !== "Generic Device") {
      // If type already contains vendor (e.g., "TP-Link Router"), use as-is
      if (vendor !== "Unknown" && type.includes(vendor)) {
        return type;
      }
      // Otherwise combine: "Device Type (Vendor)"
      if (vendor !== "Unknown") {
        return `${type} (${vendor})`;
      }
      // Just type
      return type;
    }

    // Fallback: Vendor Device
    if (vendor !== "Unknown") {
      return `${vendor} Device`;
    }

    // Last resort: hostname or IP
    if (node.hostname && node.hostname !== "Unknown") {
      return node.hostname;
    }

    return node.ip;
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
      ...n,
      id: n.ip,
      name: getDisplayName(n),
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

        {/* Connection Status Overlay */}
        {wsStatus === 'connecting' && (
          <div className="absolute inset-0 pointer-events-none -z-5">
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-yellow-500/5 to-transparent animate-pulse" />
            <div className="absolute inset-0 border-2 border-yellow-500/10 animate-pulse" />
          </div>
        )}
        {wsStatus === 'disconnected' && (
          <div className="absolute inset-0 pointer-events-none -z-5">
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-red-500/5 to-transparent animate-pulse" />
            <div className="absolute inset-0 border-2 border-red-500/20 animate-pulse" />
          </div>
        )}
        
        <GraphView ref={graphRef} data={graphData} onNodeRightClick={handleNodeInteraction} onBackgroundClick={() => setSelectedNode(null)} animStateRef={animStateRef} />
        
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
              {/* Detection Confidence & Device Name */}
              {(selectedNode.confidence !== undefined || selectedNode.deviceName) && (
                <div className="flex gap-4">
                  {selectedNode.confidence !== undefined && (
                    <div className="flex-1 p-4 bg-gradient-to-r from-green-600/10 to-emerald-600/10 rounded-xl border border-green-500/20">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-green-400 mb-2">Detection Confidence</p>
                      <div className="flex items-center gap-3">
                        <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-green-500 to-emerald-500 rounded-full transition-all"
                            style={{width: `${selectedNode.confidence}%`}}
                          />
                        </div>
                        <span className="text-2xl font-black text-white">{selectedNode.confidence}%</span>
                      </div>
                    </div>
                  )}
                  {selectedNode.deviceName && (
                    <div className="flex-1 p-4 bg-purple-600/10 rounded-xl border border-purple-500/20">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-purple-400 mb-1">mDNS Name</p>
                      <p className="text-base font-bold text-white">{selectedNode.deviceName}</p>
                    </div>
                  )}
                </div>
              )}

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

              {/* Services & Ports Information */}
              <div className="space-y-3">
                <h3 className="text-xs font-black uppercase tracking-widest text-blue-400 flex items-center gap-2">
                  <HardDrive className="w-4 h-4" /> Detected Services
                </h3>
                {selectedNode.services && selectedNode.services.length > 0 ? (
                  <div className="space-y-2">
                    {selectedNode.services.map((service, idx) => (
                      <div key={idx} className="p-3 bg-gradient-to-r from-orange-600/10 to-red-600/10 rounded-lg border border-orange-500/20">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <Unlock className="w-3 h-3 text-orange-400" />
                              <span className="text-sm font-black text-white">{service.name}</span>
                              <span className="text-xs font-mono text-neutral-400">Port {service.port}</span>
                            </div>
                            {service.banner && (
                              <p className="text-[10px] font-mono text-neutral-400 mt-1 truncate">
                                {service.banner}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : selectedNode.ports.length > 0 ? (
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

          {/* Connection Status Indicator */}
          {wsStatus === 'connected' && (
            <span className="flex items-center gap-2 font-black text-green-500/70 uppercase">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse shadow-[0_0_10px_#22c55e]" />
              Link_Established
            </span>
          )}
          {wsStatus === 'connecting' && (
            <span className="flex items-center gap-2 font-black text-yellow-500/70 uppercase">
              <div className="w-2 h-2 rounded-full bg-yellow-500 animate-ping shadow-[0_0_10px_#eab308]" />
              Establishing_Link
            </span>
          )}
          {wsStatus === 'disconnected' && (
            <span className="flex items-center gap-2 font-black text-red-500/70 uppercase">
              <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse shadow-[0_0_10px_#ef4444]" />
              Link_Severed
            </span>
          )}

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