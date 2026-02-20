import ForceGraph2D from 'react-force-graph-2d';
import type { NetworkNode, GraphNode, GraphData } from './types';

interface GraphViewProps {
  data: GraphData;
  onNodeRightClick: (node: NetworkNode, event: MouseEvent) => void;
  onBackgroundClick: () => void;
}

export default function GraphView({ data, onNodeRightClick, onBackgroundClick }: GraphViewProps) {
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
          const graphNode = node as GraphNode;
          const label = graphNode.name;
          const fontSize = 12 / globalScale;

          ctx.font = `bold ${fontSize}px "JetBrains Mono", monospace`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';

          // Glow Logic [cite: 2026-02-20]
          ctx.shadowBlur = 15 / globalScale;
          ctx.shadowColor = graphNode.color;

          ctx.beginPath();
          ctx.arc(graphNode.x || 0, graphNode.y || 0, 5, 0, 2 * Math.PI, false);
          ctx.fillStyle = graphNode.color;
          ctx.fill();

          ctx.shadowBlur = 0;

          // High-Visibility Labels
          if (globalScale > 1.2) {
            ctx.fillStyle = '#ddd';
            ctx.fillText(label, graphNode.x || 0, (graphNode.y || 0) + 14);
          }
        }}
        linkDirectionalParticles={3}
        linkDirectionalParticleSpeed={0.006}
        linkDirectionalParticleWidth={2}
        backgroundColor="rgba(0,0,0,0)"
        linkColor={() => '#666'}
        linkWidth={2}
        d3VelocityDecay={0.45}
      />
    </div>
  );
}