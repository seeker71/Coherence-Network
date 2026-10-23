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
import { useEffect, useState } from "react";
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

type SearchState = {
  query: string;
  status: "idle" | "loading" | "success" | "error";
  result: ResolveResponse | null;
};

function isResolveResponse(value: unknown): value is ResolveResponse {
  if (!value || typeof value !== "object") return false;
  const body = value as Partial<ResolveResponse>;
  const validHit = (hit: ConceptHit | PresenceHit) =>
    hit && typeof hit.id === "string" && typeof hit.name === "string" &&
    typeof hit.type === "string" && typeof hit.score === "number" && Number.isFinite(hit.score) &&
    Array.isArray(hit.shared_tokens) && hit.shared_tokens.every((token) => typeof token === "string");
  const optionalText = (text: unknown) => text === null || typeof text === "string";
  return typeof body.query === "string" &&
    Array.isArray(body.concepts) && body.concepts.every((hit) => validHit(hit) && hit.type === "concept" && (hit.hz === null || (typeof hit.hz === "number" && Number.isFinite(hit.hz)))) &&
    Array.isArray(body.presences) && body.presences.every((hit) => validHit(hit) && optionalText(hit.image_url) && optionalText(hit.canonical_url)) &&
    Array.isArray(body.existing_edges);
}

function hzToHue(hz: number | null | undefined): number {
  if (typeof hz !== "number" || !Number.isFinite(hz)) return 175;
  const clamped = Math.max(300, Math.min(1000, hz));
  return Math.round(((clamped - 396) / (963 - 396)) * 280);
}

export function PeopleSearch() {
  const [query, setQuery] = useState("");
  const [retry, setRetry] = useState(0);
  const [search, setSearch] = useState<SearchState>({ query: "", status: "idle", result: null });
  const normalizedQuery = query.trim();

  useEffect(() => {
    if (normalizedQuery.length < 3) {
      setSearch({ query: normalizedQuery, status: "idle", result: null });
      return;
    }

    const controller = new AbortController();
    setSearch({ query: normalizedQuery, status: "loading", result: null });
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(`${getApiBase()}/api/resolve/query`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ query: normalizedQuery, limit: 12 }),
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Search request failed");
        const body: unknown = await response.json();
        if (!isResolveResponse(body)) throw new Error("Search response is invalid");
        if (!controller.signal.aborted) {
          setSearch({ query: normalizedQuery, status: "success", result: body });
        }
      } catch {
        if (!controller.signal.aborted) {
          setSearch({ query: normalizedQuery, status: "error", result: null });
        }
      }
    }, 350);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [normalizedQuery, retry]);

  // The input can render before its effect runs. Only its own response is
  // current, including during the debounce interval and after clearing it.
  const status = search.query === normalizedQuery
    ? search.status
    : normalizedQuery.length >= 3 ? "loading" : "idle";
  const result = status === "success" ? search.result : null;
  const loading = status === "loading";

  const hasResult =
    result && (result.concepts.length > 0 || result.presences.length > 0);

  return (
    <section className="space-y-4" aria-label="Explore concepts and presences" aria-busy={loading}>
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search concepts and presences"
          placeholder="Explore a shared interest, such as music and movement"
          className="w-full rounded-2xl border border-border/50 bg-card/40 hover:border-border focus:border-[hsl(var(--primary))] focus:outline-none pl-5 pr-28 py-4 text-base placeholder-muted-foreground/60 transition-colors"
          autoComplete="off"
          spellCheck="false"
        />
        {loading && (
          <span role="status" className="absolute right-5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground animate-pulse">
            Searching…
          </span>
        )}
      </div>

      {status === "success" && !hasResult && (
        <p role="status" className="text-sm text-muted-foreground px-1">
          Try another phrase or explore the directory below. This search returned no matches.
        </p>
      )}

      {status === "error" && (
        <div className="space-y-2 px-1">
          <p role="alert" className="text-sm text-muted-foreground">
            Search is temporarily unavailable. Try again.
          </p>
          <button
            type="button"
            onClick={() => {
              setSearch({ query: normalizedQuery, status: "loading", result: null });
              setRetry((attempt) => attempt + 1);
            }}
            className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            Retry search
          </button>
        </div>
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
                        className="inline-block rounded-full border px-3 py-1 text-xs text-foreground hover:bg-white/10 transition-colors"
                        style={{
                          borderColor: `hsl(${hue} 55% 45% / ${strength * 0.55})`,
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
