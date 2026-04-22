"use client";

/**
 * PeopleSearch — free-text resonance query for the /people directory.
 *
 * Types anything (a phrase, a feeling, a fragment) and calls
 * /api/resolve/query. Shows back:
 *   · concepts whose story overlaps (with their hz colour)
 *   · presences in the network whose spectrum overlaps
 *   · a count of existing edges between the returned nodes
 *
 * Nothing is written. The user picks threads to follow (click any
 * chip). When we wire the "integrate as my inspired-by" flow, it'll
 * build on top of this same preview result.
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { getApiBase } from "@/lib/api";

type ConceptHit = {
  id: string;
  name: string;
  type: "concept";
  hz: number | null;
  score: number;
  shared_tokens: string[];
};

type PresenceHit = {
  id: string;
  name: string;
  type: string;
  image_url: string | null;
  canonical_url: string | null;
  score: number;
  shared_tokens: string[];
};

type ResolveResponse = {
  query: string;
  concepts: ConceptHit[];
  presences: PresenceHit[];
  existing_edges: Array<{ from_id: string; to_id: string; type: string; role?: string | null }>;
};

function hzToHue(hz: number | null | undefined): number {
  if (typeof hz !== "number" || !Number.isFinite(hz)) return 175;
  const clamped = Math.max(300, Math.min(1000, hz));
  return Math.round(((clamped - 396) / (963 - 396)) * 280);
}

export function PeopleSearch() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<ResolveResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runQuery = useCallback(async (q: string) => {
    if (q.trim().length < 3) {
      setResult(null);
      return;
    }
    setLoading(true);
    try {
      const r = await fetch(`${getApiBase()}/api/resolve/query`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ query: q.trim(), limit: 12 }),
      });
      if (!r.ok) {
        setResult(null);
        return;
      }
      const body: ResolveResponse = await r.json();
      setResult(body);
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runQuery(query), 350);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, runQuery]);

  const hasResult =
    result && (result.concepts.length > 0 || result.presences.length > 0);

  return (
    <section className="space-y-4">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Type what's alive — a phrase, a feeling, a fragment"
          className="w-full rounded-2xl border border-border/50 bg-card/40 hover:border-border focus:border-[hsl(var(--primary))] focus:outline-none px-5 py-4 text-base placeholder-muted-foreground/60 transition-colors"
          autoComplete="off"
          spellCheck="false"
        />
        {loading && (
          <span className="absolute right-5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground animate-pulse">
            listening…
          </span>
        )}
      </div>

      {query.trim().length >= 3 && !loading && !hasResult && (
        <p className="text-sm text-muted-foreground italic px-1">
          The field doesn't carry that frequency yet — try a different phrasing.
        </p>
      )}

      {hasResult && (
        <div className="rounded-2xl border border-[hsl(var(--primary)/0.25)] bg-[hsl(var(--primary)/0.04)] p-5 space-y-5">
          <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))]">
            Resonating weave · {result!.existing_edges.length} existing threads
          </p>

          {result!.concepts.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground/70 mb-2">
                Concepts
              </p>
              <ul className="flex flex-wrap gap-1.5">
                {result!.concepts.map((c) => {
                  const hue = hzToHue(c.hz);
                  const strength = Math.min(0.95, 0.4 + c.score * 1.5);
                  return (
                    <li key={c.id}>
                      <Link
                        href={`/vision/${encodeURIComponent(c.id)}`}
                        title={c.shared_tokens.join(" · ")}
                        className="inline-block rounded-full border px-3 py-1 text-xs hover:bg-white/10 transition-colors"
                        style={{
                          borderColor: `hsl(${hue} 55% 45% / ${strength * 0.55})`,
                          color: `hsl(${hue} 70% 78% / ${strength})`,
                          background: `hsl(${hue} 45% 22% / ${strength * 0.16})`,
                        }}
                      >
                        {c.name}
                        {c.hz && (
                          <span className="ml-1.5 opacity-60">
                            {c.hz}Hz
                          </span>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {result!.presences.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground/70 mb-2">
                Presences
              </p>
              <ul className="flex flex-wrap gap-2">
                {result!.presences.map((p) => (
                  <li key={p.id}>
                    <Link
                      href={`/people/${encodeURIComponent(p.id)}`}
                      title={p.shared_tokens.join(" · ")}
                      className="inline-flex items-center gap-2 rounded-full border border-border/40 bg-background/40 hover:bg-accent/40 hover:border-border px-3 py-1.5 transition-colors"
                    >
                      {p.image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={p.image_url}
                          alt=""
                          className="w-5 h-5 rounded-full object-cover border border-border/30"
                        />
                      ) : (
                        <span className="w-5 h-5 rounded-full bg-accent/40 text-[10px] flex items-center justify-center">
                          {p.name.charAt(0).toUpperCase()}
                        </span>
                      )}
                      <span className="text-sm text-foreground/90">
                        {p.name}
                      </span>
                      <span className="text-[10px] text-muted-foreground/60">
                        {p.type}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
