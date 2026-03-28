"use client";

import Link from "next/link";

type ConceptResonance = {
  concept_id: string;
  weight: number;
};

interface Props {
  interestTags: string[];
  conceptResonances: ConceptResonance[];
}

export function ConceptTagCloud({ interestTags, conceptResonances }: Props) {
  // Merge interest_tags and concept_resonances into one unified set
  const tagWeights: Record<string, number> = {};
  for (const tag of interestTags) {
    tagWeights[tag] = tagWeights[tag] ?? 0.5;
  }
  for (const r of conceptResonances) {
    tagWeights[r.concept_id] = Math.max(tagWeights[r.concept_id] ?? 0, r.weight);
  }

  const entries = Object.entries(tagWeights).sort((a, b) => b[1] - a[1]);

  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">
        No concept tags yet. Add some below!
      </p>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {entries.map(([id, weight]) => {
        const size = weight >= 0.8 ? "text-base font-semibold" : weight >= 0.5 ? "text-sm font-medium" : "text-xs";
        const opacity = `opacity-${Math.max(40, Math.round(weight * 100))}`;
        return (
          <Link
            key={id}
            href={`/concepts/${encodeURIComponent(id)}`}
            className={`${size} px-2 py-1 rounded-full border border-primary/30 bg-primary/5 text-primary hover:bg-primary/10 transition-colors`}
            style={{ opacity: Math.max(0.4, weight) }}
            title={`resonance: ${(weight * 100).toFixed(0)}%`}
          >
            #{id}
          </Link>
        );
      })}
    </div>
  );
}
