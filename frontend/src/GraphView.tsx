import React from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { NetworkNode, GraphNode, GraphData, AnimEntry } from './types';

interface GraphViewProps {
  data: GraphData;
  onNodeRightClick: (node: NetworkNode, event: MouseEvent) => void;
  onBackgroundClick: () => void;
  animStateRef: React.RefObject<Map<string, AnimEntry>>;
}

export default function GraphView({ data, onNodeRightClick, onBackgroundClick, animStateRef }: GraphViewProps) {
  return (
    <div className="w-full h-full min-h-0 min-w-0 overflow-hidden cursor-crosshair">
      <ForceGraph2D
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
        d3VelocityDecay={0.45}
      />
    </div>
  );
}
