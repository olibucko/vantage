import React, { useRef, useImperativeHandle, forwardRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { NetworkNode, GraphNode, GraphData, AnimEntry } from './types';

export interface GraphViewHandle {
  /** Place a newly-added node at the gateway's current position so it
   *  emerges from the centre rather than teleporting in from a random location. */
  initNodeAtGateway(nodeId: string, gatewayId: string): void;
}

interface GraphViewProps {
  data: GraphData;
  onNodeRightClick: (node: NetworkNode, event: MouseEvent) => void;
  onBackgroundClick: () => void;
  animStateRef: React.RefObject<Map<string, AnimEntry>>;
  /** IP of the gateway node — used to draw the subnet ring. */
  gatewayId: string;
}

// ── Device icon system ───────────────────────────────────────────────────────
type IconType =
  | 'gateway' | 'router' | 'windows' | 'phone'
  | 'laptop'  | 'printer' | 'camera' | 'storage'
  | 'media'   | 'smart'   | 'none';

/** Map a GraphNode to one of the icon categories. */
function resolveIcon(node: GraphNode, gatewayId: string): IconType {
  if (node.ip === gatewayId) return 'gateway';
  const t  = (node.type || '').toLowerCase();
  const os = (node.os  || '').toLowerCase();

  if (t.includes('router') || t.includes('gateway') || t.includes('modem')) return 'router';
  if (t.includes('windows') || os.includes('windows'))                       return 'windows';
  if (t.includes('iphone') || t.includes('ipad') || t.includes('mobile')
   || t.includes('android') || t.includes('phone'))                          return 'phone';
  if (t.includes('printer'))                                                  return 'printer';
  if (t.includes('camera') || t.includes('nvr') || t.includes('dvr'))        return 'camera';
  if (t.includes('nas') || t.includes('storage'))                            return 'storage';
  if (t.includes('media') || t.includes('chromecast')
   || t.includes('apple tv') || t.includes('homepod') || t.includes('roku')) return 'media';
  if (t.includes('smart') || t.includes('iot'))                              return 'smart';
  if (t.includes('linux') || t.includes('mac') || t.includes('apple mac')
   || t.includes('raspberry') || t.includes('server')
   || t.includes('workstation') || os.includes('linux')
   || os.includes('macos'))                                                   return 'laptop';
  return 'none';
}

/**
 * Draw a minimal white icon inside the node circle.
 * @param r  node radius in graph units (scales with animation)
 */
function drawIcon(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  r: number,
  icon: IconType,
  alpha: number,
): void {
  if (icon === 'none' || alpha < 0.2) return;

  ctx.save();
  ctx.globalAlpha = alpha * 0.88;
  ctx.strokeStyle = 'rgba(255,255,255,0.88)';
  ctx.fillStyle   = 'rgba(255,255,255,0.88)';
  ctx.lineCap     = 'round';
  ctx.lineJoin    = 'round';

  const s  = r * 0.68;                        // icon scale (graph units)
  const lw = Math.max(r * 0.07, 0.18);        // line width
  ctx.lineWidth = lw;

  switch (icon) {
    // ── WiFi arcs (gateway / ISP router) ────────────────────────────────────
    case 'gateway': {
      const bx = x, by = y + s * 0.12;
      for (let i = 0; i < 3; i++) {
        const ri = s * (0.22 + i * 0.28);
        ctx.beginPath();
        ctx.arc(bx, by, ri, Math.PI * 1.15, Math.PI * 1.85);
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.arc(bx, by, s * 0.08, 0, Math.PI * 2);
      ctx.fill();
      break;
    }

    // ── Hub / spoke (managed router / switch) ────────────────────────────────
    case 'router': {
      const cr = s * 0.18;
      ctx.beginPath();
      ctx.arc(x, y, cr, 0, Math.PI * 2);
      ctx.fill();
      const len = s * 0.65;
      for (let i = 0; i < 4; i++) {
        const angle = (i / 4) * Math.PI * 2 - Math.PI / 4;
        const ex = x + Math.cos(angle) * len;
        const ey = y + Math.sin(angle) * len;
        ctx.beginPath();
        ctx.moveTo(x + Math.cos(angle) * cr, y + Math.sin(angle) * cr);
        ctx.lineTo(ex, ey);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(ex, ey, s * 0.10, 0, Math.PI * 2);
        ctx.fill();
      }
      break;
    }

    // ── Windows logo (4 squares) ─────────────────────────────────────────────
    case 'windows': {
      const sq  = s * 0.40;
      const gap = s * 0.08;
      const offsets: [number, number][] = [
        [-sq - gap, -sq - gap], [gap, -sq - gap],
        [-sq - gap, gap],       [gap, gap],
      ];
      for (const [ox, oy] of offsets) ctx.strokeRect(x + ox, y + oy, sq, sq);
      break;
    }

    // ── Phone outline + home indicator ───────────────────────────────────────
    case 'phone': {
      const pw = s * 0.52, ph = s * 0.95, cr = s * 0.10;
      ctx.beginPath();
      ctx.moveTo(x - pw / 2 + cr, y - ph / 2);
      ctx.lineTo(x + pw / 2 - cr, y - ph / 2);
      ctx.arcTo(x + pw / 2, y - ph / 2, x + pw / 2, y - ph / 2 + cr, cr);
      ctx.lineTo(x + pw / 2, y + ph / 2 - cr);
      ctx.arcTo(x + pw / 2, y + ph / 2, x + pw / 2 - cr, y + ph / 2, cr);
      ctx.lineTo(x - pw / 2 + cr, y + ph / 2);
      ctx.arcTo(x - pw / 2, y + ph / 2, x - pw / 2, y + ph / 2 - cr, cr);
      ctx.lineTo(x - pw / 2, y - ph / 2 + cr);
      ctx.arcTo(x - pw / 2, y - ph / 2, x - pw / 2 + cr, y - ph / 2, cr);
      ctx.closePath();
      ctx.stroke();
      // Home button dot
      ctx.beginPath();
      ctx.arc(x, y + ph / 2 - s * 0.13, s * 0.07, 0, Math.PI * 2);
      ctx.fill();
      break;
    }

    // ── Laptop screen + base line ─────────────────────────────────────────────
    case 'laptop': {
      const lw2 = s * 0.95, lh2 = s * 0.65;
      const screenH = lh2 * 0.75;
      const sx = x - lw2 / 2, sy = y - lh2 / 2;
      ctx.strokeRect(sx, sy, lw2, screenH);
      ctx.beginPath();
      ctx.moveTo(x - lw2 * 0.62, sy + screenH);
      ctx.lineTo(x + lw2 * 0.62, sy + screenH);
      ctx.stroke();
      break;
    }

    // ── Printer body + paper ─────────────────────────────────────────────────
    case 'printer': {
      const bw = s * 0.88, bh = s * 0.45;
      const bx = x - bw / 2, by = y - bh / 2 + s * 0.06;
      ctx.strokeRect(bx, by, bw, bh);
      // Paper sheet emerging from top
      ctx.strokeRect(x - bw * 0.25, by - s * 0.26, bw * 0.50, s * 0.28);
      break;
    }

    // ── Camera body + lens ───────────────────────────────────────────────────
    case 'camera': {
      const cw = s * 0.92, ch = s * 0.60;
      const cx = x - cw / 2, cy = y - ch / 2 + s * 0.05;
      ctx.strokeRect(cx, cy, cw, ch);
      // Lens
      ctx.beginPath();
      ctx.arc(x, y + s * 0.05, s * 0.22, 0, Math.PI * 2);
      ctx.stroke();
      // Viewfinder bump
      ctx.fillRect(x - s * 0.17, cy - s * 0.10, s * 0.34, s * 0.12);
      break;
    }

    // ── Database cylinders (NAS / storage) ───────────────────────────────────
    case 'storage': {
      const dw = s * 0.44, dh = s * 0.13, spacing = s * 0.30;
      const sy = y - spacing;
      for (let i = 0; i < 3; i++) {
        ctx.beginPath();
        ctx.ellipse(x, sy + i * spacing, dw, dh, 0, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.moveTo(x - dw, sy);     ctx.lineTo(x - dw, sy + 2 * spacing);
      ctx.moveTo(x + dw, sy);     ctx.lineTo(x + dw, sy + 2 * spacing);
      ctx.stroke();
      break;
    }

    // ── Play triangle (media device) ─────────────────────────────────────────
    case 'media': {
      ctx.beginPath();
      ctx.moveTo(x - s * 0.32, y - s * 0.48);
      ctx.lineTo(x + s * 0.58, y);
      ctx.lineTo(x - s * 0.32, y + s * 0.48);
      ctx.closePath();
      ctx.fill();
      break;
    }

    // ── House outline (smart home / IoT) ─────────────────────────────────────
    case 'smart': {
      ctx.beginPath();
      ctx.moveTo(x,           y - s * 0.52);   // roof peak
      ctx.lineTo(x + s * 0.52, y - s * 0.05);  // right eave
      ctx.lineTo(x + s * 0.52, y + s * 0.48);  // right wall base
      ctx.lineTo(x - s * 0.52, y + s * 0.48);  // left wall base
      ctx.lineTo(x - s * 0.52, y - s * 0.05);  // left eave
      ctx.closePath();
      ctx.stroke();
      break;
    }

    default: break;
  }

  ctx.restore();
}
// ────────────────────────────────────────────────────────────────────────────

const GraphView = forwardRef<GraphViewHandle, GraphViewProps>(function GraphView(
  { data, onNodeRightClick, onBackgroundClick, animStateRef, gatewayId },
  ref
) {
  const fgRef = useRef<any>(null);

  useImperativeHandle(ref, () => ({
    initNodeAtGateway(nodeId: string, gatewayId: string) {
      const nodes = fgRef.current?.getGraphData()?.nodes as any[] | undefined;
      if (!nodes) return;
      const gw     = nodes.find(n => n.id === gatewayId);
      const target = nodes.find(n => n.id === nodeId);
      if (target) {
        target.x  = gw?.x  ?? 0;
        target.y  = gw?.y  ?? 0;
        target.vx = 0;
        target.vy = 0;
      }
    }
  }));

  return (
    <div className="w-full h-full min-h-0 min-w-0 overflow-hidden cursor-crosshair">
      <ForceGraph2D
        ref={fgRef}
        graphData={data}
        onNodeRightClick={(node, event) => onNodeRightClick(node as NetworkNode, event as unknown as MouseEvent)}
        onBackgroundClick={onBackgroundClick}
        nodeLabel={() => ``}
        nodeColor={(node) => (node as GraphNode).color}
        nodeRelSize={7}
        nodeCanvasObject={(node, ctx, globalScale) => {
          const g = node as GraphNode;
          const x = g.x ?? 0;
          const y = g.y ?? 0;

          // ── Subnet Ring (drawn on gateway canvas pass) ──────────────────────
          if (g.ip === gatewayId) {
            let maxDist = 50;
            data.nodes.forEach((n: GraphNode) => {
              if (n.id !== gatewayId && n.x != null && n.y != null) {
                const dx = (n.x ?? 0) - x;
                const dy = (n.y ?? 0) - y;
                maxDist = Math.max(maxDist, Math.sqrt(dx * dx + dy * dy));
              }
            });
            const ringRadius = maxDist + 14;

            ctx.save();

            const grad = ctx.createRadialGradient(x, y, ringRadius * 0.45, x, y, ringRadius);
            grad.addColorStop(0, 'rgba(59,130,246,0.00)');
            grad.addColorStop(1, 'rgba(59,130,246,0.04)');
            ctx.beginPath();
            ctx.arc(x, y, ringRadius, 0, 2 * Math.PI);
            ctx.fillStyle = grad;
            ctx.fill();

            ctx.beginPath();
            ctx.arc(x, y, ringRadius, 0, 2 * Math.PI);
            ctx.setLineDash([6 / globalScale, 4 / globalScale]);
            ctx.strokeStyle = 'rgba(59,130,246,0.20)';
            ctx.lineWidth = 1 / globalScale;
            ctx.stroke();
            ctx.setLineDash([]);

            const subnetLabel = gatewayId.replace(/\.\d+$/, '.0/24');
            const labelAlpha = Math.min(0.80, Math.max(0, (globalScale - 0.30) * 2.2));
            if (labelAlpha > 0.01) {
              const fontSize = 13 / globalScale;
              ctx.font = `bold ${fontSize}px "JetBrains Mono", monospace`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.globalAlpha = labelAlpha;
              ctx.shadowBlur  = 10 / globalScale;
              ctx.shadowColor = '#3b82f6';
              ctx.fillStyle   = '#93c5fd';
              ctx.fillText(subnetLabel, x, y - ringRadius - 14 / globalScale);
              ctx.shadowBlur  = 0;
            }

            ctx.restore();
          }
          // ───────────────────────────────────────────────────────────────────

          const entry = animStateRef.current?.get(g.ip);
          let scale = 1, alpha = 1, drawRing = false, ringT = 0;

          if (entry) {
            const elapsed = performance.now() - entry.startTime;
            if (entry.type === 'spawn') {
              const t = Math.min(Math.max(elapsed / 800, 0), 1);
              const eased = 1 - Math.pow(1 - t, 3);
              scale = eased;
              alpha = eased;
              drawRing = t < 1;
              ringT = t;
            } else if (entry.type === 'despawn') {
              const t = Math.min(Math.max(elapsed / 600, 0), 1);
              const eased = 1 - Math.pow(t, 3);
              scale = eased;
              alpha = eased;
            }
          }

          const r = 6 * Math.max(scale, 0.01);   // slightly larger radius for icon room

          ctx.save();
          ctx.globalAlpha = alpha;

          // Outer glow
          ctx.shadowBlur  = 10 / globalScale;
          ctx.shadowColor = g.color;

          // Filled circle
          ctx.beginPath();
          ctx.arc(x, y, r, 0, 2 * Math.PI);
          ctx.fillStyle = g.color;
          ctx.fill();
          ctx.shadowBlur = 0;

          // Subtle radial highlight — top-left bright, bottom-right dark
          const shine = ctx.createRadialGradient(
            x - r * 0.28, y - r * 0.28, 0,
            x, y, r,
          );
          shine.addColorStop(0,   'rgba(255,255,255,0.18)');
          shine.addColorStop(0.5, 'rgba(255,255,255,0.00)');
          shine.addColorStop(1,   'rgba(0,0,0,0.18)');
          ctx.beginPath();
          ctx.arc(x, y, r, 0, 2 * Math.PI);
          ctx.fillStyle = shine;
          ctx.fill();

          // Crisp rim
          ctx.beginPath();
          ctx.arc(x, y, r, 0, 2 * Math.PI);
          ctx.strokeStyle = 'rgba(255,255,255,0.22)';
          ctx.lineWidth   = Math.max(0.6 / globalScale, 0.25);
          ctx.stroke();

          // Expanding pulse ring on spawn
          if (drawRing) {
            const pulseR = 6 + (18 - 6) * ringT;
            ctx.beginPath();
            ctx.arc(x, y, pulseR, 0, 2 * Math.PI);
            ctx.strokeStyle = g.color;
            ctx.globalAlpha = (1 - ringT) * 0.7;
            ctx.lineWidth = 1.5 / globalScale;
            ctx.stroke();
          }

          // ── Device icon (visible at all zoom levels) ──────────────────────
          if (scale > 0.3) {
            const icon = resolveIcon(g, gatewayId);
            drawIcon(ctx, x, y, r * 0.88, icon, alpha);
          }

          // ── Node label ────────────────────────────────────────────────────
          if (globalScale > 0.75 && scale > 0.4) {
            const fadeIn    = Math.min(1, (globalScale - 0.75) * 4);
            const fontSize  = 11 / globalScale;
            ctx.globalAlpha = alpha * fadeIn;
            ctx.font        = `600 ${fontSize}px "JetBrains Mono", monospace`;
            ctx.textAlign   = 'center';
            ctx.textBaseline = 'middle';
            ctx.shadowBlur  = 5 / globalScale;
            ctx.shadowColor = 'rgba(0,0,0,0.95)';
            ctx.fillStyle   = '#ffffff';
            ctx.fillText(g.name, x, y + r + 8 / globalScale);
            ctx.shadowBlur  = 0;
          }

          ctx.restore();
        }}
        linkCanvasObjectMode={() => 'replace'}
        linkCanvasObject={(link, ctx, globalScale) => {
          const src = link.source as GraphNode;
          const tgt = link.target as GraphNode;
          if (src?.x == null || src?.y == null || tgt?.x == null || tgt?.y == null) return;
          const sx = src.x, sy = src.y;
          const tx = tgt.x, ty = tgt.y;
          const entry = animStateRef.current?.get((tgt as GraphNode).ip);

          ctx.save();
          ctx.lineWidth = 1.2 / globalScale;

          if (!entry) {
            ctx.beginPath();
            ctx.moveTo(sx, sy);
            ctx.lineTo(tx, ty);
            ctx.strokeStyle = 'rgba(130,130,145,0.55)';
            ctx.stroke();

          } else if (entry.type === 'spawn') {
            const t = Math.min(Math.max((performance.now() - entry.startTime) / 800, 0), 1);
            const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
            const bx = sx + (tx - sx) * e;
            const by = sy + (ty - sy) * e;
            ctx.shadowBlur = 6 / globalScale;
            ctx.shadowColor = '#60a5fa';
            ctx.globalAlpha = 0.9;
            ctx.beginPath();
            ctx.moveTo(sx, sy);
            ctx.lineTo(bx, by);
            ctx.strokeStyle = '#60a5fa';
            ctx.stroke();
            if (e < 1) {
              ctx.shadowBlur = 0;
              ctx.globalAlpha = 0.2;
              ctx.beginPath();
              ctx.moveTo(bx, by);
              ctx.lineTo(tx, ty);
              ctx.strokeStyle = '#444';
              ctx.stroke();
            }

          } else if (entry.type === 'despawn') {
            const t = Math.min(Math.max((performance.now() - entry.startTime) / 600, 0), 1);
            const e = t * t;
            const bx = tx + (sx - tx) * e;
            const by = ty + (sy - ty) * e;
            ctx.shadowBlur = 6 / globalScale;
            ctx.shadowColor = '#ef4444';
            ctx.globalAlpha = 1 - t * 0.5;
            ctx.beginPath();
            ctx.moveTo(sx, sy);
            ctx.lineTo(bx, by);
            ctx.strokeStyle = '#ef4444';
            ctx.stroke();
          }

          ctx.restore();
        }}
        linkDirectionalParticles={(link) => {
          const tgt = link.target as GraphNode;
          if (tgt?.ip && animStateRef.current?.get(tgt.ip)) return 0;
          return 3;
        }}
        linkDirectionalParticleSpeed={0.006}
        linkDirectionalParticleWidth={1.5}
        backgroundColor="rgba(0,0,0,0)"
        d3AlphaDecay={0.04}
        d3VelocityDecay={0.45}
      />
    </div>
  );
});

export default GraphView;
