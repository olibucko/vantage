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
        // Seed position at gateway so the physics simulation moves it
        // outward naturally instead of dropping it at a random far location
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
        // Using onNodeRightClick to avoid Drag competition [cite: 2026-02-20]
        onNodeRightClick={(node, event) => onNodeRightClick(node as NetworkNode, event as unknown as MouseEvent)}
        onBackgroundClick={onBackgroundClick}
        nodeLabel={() => ``}
        nodeColor={(node) => (node as GraphNode).color}
        nodeRelSize={7}
        nodeCanvasObject={(node, ctx, globalScale) => {
          const g = node as GraphNode;
          const x = g.x ?? 0;
          const y = g.y ?? 0;

          // ── Subnet Ring ────────────────────────────────────────────────────
          // Drawn on the gateway node's canvas pass so it sits behind all other
          // nodes (gateway is first in the nodes array, so it renders first).
          if (g.ip === gatewayId) {
            // Adaptive radius: max distance from gateway to any peer + padding.
            // Node draw radius = 5 graph units, so +14 leaves ~9 units of gap
            // between the outermost node edge and the ring — tight but legible.
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

            // Faint radial fill — inner transparent, outer blue tint
            const grad = ctx.createRadialGradient(x, y, ringRadius * 0.45, x, y, ringRadius);
            grad.addColorStop(0, 'rgba(59,130,246,0.00)');
            grad.addColorStop(1, 'rgba(59,130,246,0.04)');
            ctx.beginPath();
            ctx.arc(x, y, ringRadius, 0, 2 * Math.PI);
            ctx.fillStyle = grad;
            ctx.fill();

            // Dashed ring border
            ctx.beginPath();
            ctx.arc(x, y, ringRadius, 0, 2 * Math.PI);
            ctx.setLineDash([6 / globalScale, 4 / globalScale]);
            ctx.strokeStyle = 'rgba(59,130,246,0.20)';
            ctx.lineWidth = 1 / globalScale;
            ctx.stroke();
            ctx.setLineDash([]);

            // Subnet label — fades in as you zoom, anchored just outside the ring
            const subnetLabel = gatewayId.replace(/\.\d+$/, '.0/24');
            const labelAlpha = Math.min(0.40, Math.max(0, (globalScale - 0.55) * 1.6));
            if (labelAlpha > 0.01) {
              const fontSize = 9 / globalScale;
              ctx.font = `bold ${fontSize}px "JetBrains Mono", monospace`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.globalAlpha = labelAlpha;
              ctx.fillStyle = '#3b82f6';
              ctx.fillText(subnetLabel, x, y - ringRadius - 10 / globalScale);
            }

            ctx.restore();
          }
          // ──────────────────────────────────────────────────────────────────

          const entry = animStateRef.current?.get(g.ip);

          let scale = 1, alpha = 1, drawRing = false, ringT = 0;

          if (entry) {
            const elapsed = performance.now() - entry.startTime;
            if (entry.type === 'spawn') {
              const t = Math.min(elapsed / 800, 1);
              const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
              scale = eased;
              alpha = eased;
              drawRing = t < 1;
              ringT = t;
            } else if (entry.type === 'despawn') {
              const t = Math.min(elapsed / 600, 1);
              const eased = 1 - Math.pow(t, 3); // ease-in cubic (reversed)
              scale = eased;
              alpha = eased;
            }
          }

          ctx.save();
          ctx.globalAlpha = alpha;
          ctx.shadowBlur = 15 / globalScale;
          ctx.shadowColor = g.color;
          ctx.beginPath();
          ctx.arc(x, y, 5 * Math.max(scale, 0.01), 0, 2 * Math.PI);
          ctx.fillStyle = g.color;
          ctx.fill();
          ctx.shadowBlur = 0;

          // Expanding pulse ring on spawn
          if (drawRing) {
            const ringRadius = 5 + (15 - 5) * ringT;
            ctx.beginPath();
            ctx.arc(x, y, ringRadius, 0, 2 * Math.PI);
            ctx.strokeStyle = g.color;
            ctx.globalAlpha = (1 - ringT) * 0.7;
            ctx.lineWidth = 1.5 / globalScale;
            ctx.stroke();
          }

          // Labels only when zoomed in and node isn't nearly invisible
          if (globalScale > 1.2 && scale > 0.4) {
            const fontSize = 12 / globalScale;
            ctx.globalAlpha = alpha;
            ctx.font = `bold ${fontSize}px "JetBrains Mono", monospace`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#ddd';
            ctx.fillText(g.name, x, y + 14);
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
          ctx.lineWidth = 2 / globalScale;

          if (!entry) {
            ctx.beginPath();
            ctx.moveTo(sx, sy);
            ctx.lineTo(tx, ty);
            ctx.strokeStyle = '#666';
            ctx.stroke();

          } else if (entry.type === 'spawn') {
            const t = Math.min((performance.now() - entry.startTime) / 800, 1);
            // ease-in-out: beam extends from source toward target
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
            // Ghost trail for the undrawn remainder
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
            const t = Math.min((performance.now() - entry.startTime) / 600, 1);
            // ease-in: beam retracts from target back toward source
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
        linkDirectionalParticleWidth={2}
        backgroundColor="rgba(0,0,0,0)"
        // Higher alpha decay → simulation settles in ~2 s instead of the default ~5 s,
        // so the graph stabilises quickly after each node addition/removal.
        d3AlphaDecay={0.04}
        d3VelocityDecay={0.45}
      />
    </div>
  );
});

export default GraphView;
