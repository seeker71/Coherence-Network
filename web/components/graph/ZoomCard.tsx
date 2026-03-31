"use client";

/**
 * ZoomCard — Card layout for garden/card view (Spec 182).
 *
 * Non-technical users see each child node as a card showing:
 * name, coherence score, child_count, top open question.
 */

import Link from "next/link";

export interface ZoomNodeSummary {
  id: string;
  name: string;
  node_type: string;
  coherence_score: number;
  lifecycle_state: string;
  view_hint: string;
  open_questions: Array<{
    id: string;
    question: string;
    resolved: boolean;
  }>;
  children: ZoomNodeSummary[];
}

interface ZoomCardProps {
  node: ZoomNodeSummary;
  showLink?: boolean;
}

function CoherenceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.7 ? "bg-green-500" : score >= 0.4 ? "bg-yellow-500" : "bg-red-400";
  return (
    <div className="w-full bg-gray-200 rounded-full h-2 mt-1" title={`Coherence: ${pct}%`}>
      <div className={`${color} h-2 rounded-full`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function ZoomCard({ node, showLink = true }: ZoomCardProps) {
  const topQuestion = node.open_questions.find((q) => !q.resolved);
  const childCount = node.children.length;
  const lifecycleColor =
    node.lifecycle_state === "water"
      ? "bg-blue-100 text-blue-800"
      : node.lifecycle_state === "ice"
      ? "bg-cyan-100 text-cyan-800"
      : "bg-orange-100 text-orange-800";

  const card = (
    <div className="border rounded-xl p-4 bg-white shadow-sm hover:shadow-md transition-shadow flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-base leading-tight">{node.name}</h3>
        <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${lifecycleColor}`}>
          {node.lifecycle_state}
        </span>
      </div>

      <div>
        <div className="flex justify-between text-xs text-gray-500">
          <span>Coherence</span>
          <span>{Math.round(node.coherence_score * 100)}%</span>
        </div>
        <CoherenceBar score={node.coherence_score} />
      </div>

      {childCount > 0 && (
        <p className="text-xs text-gray-500">
          {childCount} child{childCount !== 1 ? "ren" : ""}
        </p>
      )}

      {topQuestion && (
        <p className="text-xs text-gray-600 italic line-clamp-2">
          Q: {topQuestion.question}
        </p>
      )}
    </div>
  );

  if (!showLink) return card;

  return (
    <Link href={`/graph/zoom/${node.id}`} className="block">
      {card}
    </Link>
  );
}

interface ZoomCardGridProps {
  nodes: ZoomNodeSummary[];
}

export function ZoomCardGrid({ nodes }: ZoomCardGridProps) {
  if (!nodes.length) {
    return (
      <p className="text-sm text-gray-500 text-center py-8">
        No child nodes found.
      </p>
    );
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {nodes.map((n) => (
        <ZoomCard key={n.id} node={n} />
      ))}
    </div>
  );
}
