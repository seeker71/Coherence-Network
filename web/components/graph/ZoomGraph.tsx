"use client";

/**
 * ZoomGraph — Interactive graph view for technical users (Spec 182).
 *
 * Renders nodes sized by coherence score and edges colored by type.
 * Uses a simple SVG-based force layout (no external dependency required).
 * For production use, swap the layout engine for react-force-graph or vis-network.
 */

import { useEffect, useRef, useState } from "react";

interface GraphNode {
  id: string;
  name: string;
  coherence_score: number;
  node_type: string;
}

interface GraphEdge {
  from: string;
  to: string;
  edge_type: string;
}

interface ZoomGraphProps {
  rootNode: {
    id: string;
    name: string;
    coherence_score: number;
    node_type: string;
    children: Array<{
      id: string;
      name: string;
      coherence_score: number;
      node_type: string;
    }>;
    edges: GraphEdge[];
  };
  onNodeClick?: (nodeId: string) => void;
}

const EDGE_COLORS: Record<string, string> = {
  "parent-of": "#6366f1",
  "depends-on": "#f59e0b",
  implements: "#10b981",
};

function nodeRadius(score: number): number {
  return 18 + score * 20;
}

export function ZoomGraph({ rootNode, onNodeClick }: ZoomGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ w: 600, h: 400 });

  useEffect(() => {
    if (!containerRef.current) return;
    const { width, height } = containerRef.current.getBoundingClientRect();
    if (width > 0) setDims({ w: width, h: Math.max(height, 300) });
  }, []);

  const allNodes: GraphNode[] = [
    {
      id: rootNode.id,
      name: rootNode.name,
      coherence_score: rootNode.coherence_score,
      node_type: rootNode.node_type,
    },
    ...rootNode.children.map((c) => ({
      id: c.id,
      name: c.name,
      coherence_score: c.coherence_score,
      node_type: c.node_type,
    })),
  ];

  // Simple radial layout: root in center, children on a circle
  const cx = dims.w / 2;
  const cy = dims.h / 2;
  const radius = Math.min(cx, cy) * 0.65;

  const positions: Record<string, { x: number; y: number }> = {};
  positions[rootNode.id] = { x: cx, y: cy };

  const children = rootNode.children;
  children.forEach((child, i) => {
    const angle = (2 * Math.PI * i) / Math.max(children.length, 1) - Math.PI / 2;
    positions[child.id] = {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    };
  });

  return (
    <div ref={containerRef} className="w-full" style={{ minHeight: 320 }}>
      <svg
        width={dims.w}
        height={dims.h}
        className="overflow-visible"
        aria-label={`Graph view of ${rootNode.name} and its children`}
      >
        {/* Edges */}
        {rootNode.edges.map((edge, i) => {
          const from = positions[edge.from];
          const to = positions[edge.to];
          if (!from || !to) return null;
          const color = EDGE_COLORS[edge.edge_type] ?? "#9ca3af";
          return (
            <g key={i}>
              <line
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={color}
                strokeWidth={2}
                strokeOpacity={0.7}
              />
              <text
                x={(from.x + to.x) / 2}
                y={(from.y + to.y) / 2 - 4}
                fontSize={9}
                fill={color}
                textAnchor="middle"
                className="select-none"
              >
                {edge.edge_type}
              </text>
            </g>
          );
        })}

        {/* Nodes */}
        {allNodes.map((node) => {
          const pos = positions[node.id];
          if (!pos) return null;
          const r = nodeRadius(node.coherence_score);
          const isRoot = node.id === rootNode.id;
          const fill = isRoot ? "#6366f1" : "#818cf8";
          const textColor = "#fff";
          return (
            <g
              key={node.id}
              transform={`translate(${pos.x},${pos.y})`}
              className="cursor-pointer"
              onClick={() => onNodeClick?.(node.id)}
              role="button"
              aria-label={`${node.name} — coherence ${Math.round(node.coherence_score * 100)}%`}
            >
              <circle
                r={r}
                fill={fill}
                stroke={isRoot ? "#4338ca" : "#6366f1"}
                strokeWidth={2}
              />
              <text
                textAnchor="middle"
                dy="0.35em"
                fontSize={isRoot ? 11 : 9}
                fill={textColor}
                className="select-none pointer-events-none"
              >
                {node.name.length > 12 ? node.name.slice(0, 11) + "…" : node.name}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mt-2 text-xs text-gray-500">
        {Object.entries(EDGE_COLORS).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1">
            <span
              className="inline-block w-4 h-0.5 rounded"
              style={{ backgroundColor: color }}
            />
            {type}
          </span>
        ))}
        <span className="text-gray-400">Node size = coherence score</span>
      </div>
    </div>
  );
}
