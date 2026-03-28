"use client";

/**
 * ConceptTagCloud — displays interest_tags and concept_resonances sized by weight.
 * spec-169 (belief-system-interface)
 */

import React from "react";
import Link from "next/link";

export type ConceptResonance = {
  concept_id: string;
  weight: number;
};

interface Props {
  interestTags: string[];
  conceptResonances: ConceptResonance[];
}

export function ConceptTagCloud({ interestTags, conceptResonances }: Props) {
  // Merge tags and resonances; resonances carry weight, tags default to 0.5
  const tagMap = new Map<string, number>();
  for (const tag of interestTags) {
    tagMap.set(tag, tagMap.get(tag) ?? 0.5);
  }
  for (const r of conceptResonances) {
    tagMap.set(r.concept_id, Math.max(tagMap.get(r.concept_id) ?? 0, r.weight));
  }

  const entries = Array.from(tagMap.entries()).sort((a, b) => b[1] - a[1]);

  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">
        No concept tags yet. Add some using the worldview selector below.
      </p>
    );
  }

  function fontSize(weight: number): number {
    // Map weight [0, 1] → font-size [11, 22]px
    return Math.round(11 + weight * 11);
  }

  function opacity(weight: number): number {
    return 0.5 + weight * 0.5;
  }

  return (
    <div className="flex flex-wrap gap-2 leading-relaxed" aria-label="Concept tag cloud">
      {entries.map(([tag, weight]) => (
        <Link
          key={tag}
          href={`/concepts/${encodeURIComponent(tag)}`}
          style={{ fontSize: fontSize(weight), opacity: opacity(weight) }}
          className="text-indigo-600 dark:text-indigo-400 hover:underline transition-opacity"
          title={`Weight: ${weight.toFixed(2)}`}
        >
          #{tag}
        </Link>
      ))}
    </div>
  );
}
