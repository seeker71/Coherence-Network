"use client";

/**
 * Reader presence — shows how alive this concept is through attention.
 *
 * When someone reads a concept, their attention makes it more vital.
 * This component makes that visible — gently, as warmth rather than
 * a counter. The reader sees that others have sat with this too.
 */

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

interface ReaderPresenceProps {
  conceptId: string;
}

export function ReaderPresence({ conceptId }: ReaderPresenceProps) {
  const [views, setViews] = useState<number | null>(null);
  const [contributors, setContributors] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(
          `${getApiBase()}/api/views/stats/${encodeURIComponent(conceptId)}?days=365`
        );
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) {
          setViews(data.total_views ?? 0);
          setContributors(data.unique_contributors ?? 0);
        }
      } catch {
        // Presence is supplementary
      }
    }

    load();
    return () => { cancelled = true; };
  }, [conceptId]);

  if (views === null || views === 0) return null;

  // Language that honors the reader's attention
  const presenceText =
    contributors > 0
      ? `${views} ${views === 1 ? "person has" : "people have"} sat with this · ${contributors} ${contributors === 1 ? "contributor" : "contributors"}`
      : `${views} ${views === 1 ? "person has" : "people have"} sat with this`;

  return (
    <p className="text-xs text-stone-500/60 mt-2">
      {presenceText}
    </p>
  );
}
