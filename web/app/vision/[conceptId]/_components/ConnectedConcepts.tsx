import Link from "next/link";
import { displayName, EDGE_LABELS } from "@/lib/vision-utils";
import type { Edge } from "@/lib/types/vision";

export function ConnectedConcepts({
  outgoing,
  incoming,
  nameMap,
  mode,
}: {
  outgoing: Edge[];
  incoming: Edge[];
  nameMap: Record<string, string>;
  mode: "full" | "compact";
}) {
  if (outgoing.length === 0 && incoming.length === 0) return null;

  if (mode === "compact") {
    return (
      <div className="flex flex-wrap gap-2 p-4 rounded-xl border border-stone-800/30 bg-stone-900/20">
        <span className="text-xs text-stone-600 mr-2">Connected:</span>
        {outgoing.map((e) => (
          <Link key={e.id} href={`/vision/${e.to}`}
            className="text-xs px-2 py-1 rounded-full border border-stone-700/30 text-stone-500 hover:text-amber-300/70 hover:border-amber-500/20 transition-colors">
            {displayName(e.to, nameMap)}
          </Link>
        ))}
        {incoming.map((e) => (
          <Link key={e.id} href={`/vision/${e.from}`}
            className="text-xs px-2 py-1 rounded-full border border-stone-700/30 text-stone-500 hover:text-teal-300/70 hover:border-teal-500/20 transition-colors">
            {displayName(e.from, nameMap)}
          </Link>
        ))}
      </div>
    );
  }

  return (
    <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
      <h2 className="text-lg font-light text-stone-300">Connected Frequencies</h2>
      <div className="space-y-2">
        {outgoing.map((e) => (
          <Link key={e.id} href={`/vision/${e.to}`}
            className="flex items-center gap-3 py-2 px-3 rounded-xl hover:bg-stone-800/40 transition-colors group">
            <span className="text-xs text-amber-400/60 font-medium min-w-[120px]">
              {EDGE_LABELS[e.type] || e.type}
            </span>
            <span className="text-stone-300 group-hover:text-amber-300/80 transition-colors">
              {displayName(e.to, nameMap)}
            </span>
            <span className="text-stone-700 ml-auto">&rarr;</span>
          </Link>
        ))}
        {incoming.map((e) => (
          <Link key={e.id} href={`/vision/${e.from}`}
            className="flex items-center gap-3 py-2 px-3 rounded-xl hover:bg-stone-800/40 transition-colors group">
            <span className="text-xs text-teal-400/60 font-medium min-w-[120px]">
              {EDGE_LABELS[e.type] || e.type}
            </span>
            <span className="text-stone-300 group-hover:text-teal-300/80 transition-colors">
              {displayName(e.from, nameMap)}
            </span>
            <span className="text-stone-700 ml-auto">&larr;</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
