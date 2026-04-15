import Link from "next/link";
import { frequencyColor } from "@/lib/vision-utils";
import type { LCConcept } from "@/lib/types/vision";

export function FrequencyDisplay({
  frequency,
  siblings,
  mode,
}: {
  frequency: { hz: number; quality: string };
  siblings: LCConcept[];
  mode: "sidebar" | "inline";
}) {
  if (mode === "inline") {
    return (
      <div className="flex items-center gap-4 p-4 rounded-xl border border-stone-800/30 bg-stone-900/20">
        <div className={`text-2xl font-extralight ${frequencyColor(frequency.hz)}`}>{frequency.hz} Hz</div>
        <p className="text-xs text-stone-500">{frequency.quality}</p>
        {siblings.length > 0 && (
          <div className="flex flex-wrap gap-2 ml-auto">
            {siblings.slice(0, 5).map((sib) => (
              <Link key={sib.id} href={`/vision/${sib.id}`}
                className="text-xs text-stone-600 hover:text-amber-300/60 transition-colors">
                {sib.name}
              </Link>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 space-y-4">
      <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Sacred Frequency</h2>
      <div className={`text-3xl font-extralight ${frequencyColor(frequency.hz)}`}>{frequency.hz} Hz</div>
      <p className="text-xs text-stone-500 leading-relaxed">{frequency.quality}</p>
      {siblings.length > 0 && (
        <div className="pt-2 border-t border-stone-800/30 space-y-2">
          <p className="text-xs text-stone-600">
            Resonates with {siblings.length} other concept{siblings.length === 1 ? "" : "s"} at this frequency:
          </p>
          <div className="space-y-1">
            {siblings.map((sib) => (
              <Link key={sib.id} href={`/vision/${sib.id}`}
                className="block text-xs text-stone-500 hover:text-amber-300/70 transition-colors truncate">
                {sib.name}
              </Link>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
