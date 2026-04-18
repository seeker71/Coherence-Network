"use client";

/**
 * InspiredByRail — highlight the people, communities, and places
 * that made you who you are.
 *
 * One input, one gesture. Type a name ("Daniel Scranton", "Yaima",
 * "Unison Festival") or paste a URL. The resolver returns a small
 * subgraph: an identity, the presences it maintains across
 * platforms, and the creations we could find. A weighted
 * ``inspired-by`` edge records the relationship — the weight
 * emerges from what was discovered.
 *
 * Identity: uses the soft-identity pattern (ensureContributorId)
 * so a visitor with just a display name can add their first
 * inspiration without a signup form.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { getApiBase } from "@/lib/api";
import {
  NAME_KEY,
  ensureContributorId,
  readIdentity,
} from "@/lib/identity";

type Presence = { provider: string; url: string };

type Node = {
  id: string;
  name: string;
  description?: string;
  type: string;
  canonical_url?: string;
  image_url?: string | null;
  provider?: string;
  tagline?: string;
  claimable?: boolean;
  presences?: Presence[];
  creation_kind?: string;
};

type InspiredByItem = {
  edge_id: string;
  weight: number;
  node: Node;
  created_at: string | null;
};

const TYPE_LABEL: Record<string, string> = {
  contributor: "Person",
  community: "Community / Place",
  "network-org": "Project",
  asset: "Work",
};

function WeightDots({ weight }: { weight: number }) {
  // 0.4 → 2 dots, 0.7 → 4 dots, 1.0 → 5 dots.
  const filled = Math.max(1, Math.min(5, Math.round(weight * 5)));
  return (
    <span
      className="inline-flex items-center gap-0.5"
      aria-label={`weight ${weight.toFixed(2)}`}
      title={`weight ${weight.toFixed(2)} — from discovery signals`}
    >
      {Array.from({ length: 5 }).map((_, i) => (
        <span
          key={i}
          className={`w-1 h-1 rounded-full ${
            i < filled ? "bg-[hsl(var(--primary))]" : "bg-border"
          }`}
        />
      ))}
    </span>
  );
}

export function InspiredByRail() {
  const apiBase = getApiBase();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [items, setItems] = useState<InspiredByItem[]>([]);
  const [contributorId, setContributorId] = useState<string>("");
  const [name, setName] = useState<string>("");
  const [draftName, setDraftName] = useState<string>("");
  const [input, setInput] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const loadItems = useCallback(
    async (cid: string) => {
      try {
        const r = await fetch(
          `${apiBase}/api/inspired-by?contributor_id=${encodeURIComponent(cid)}`,
          { cache: "no-store" },
        );
        if (!r.ok) return;
        const body = await r.json();
        setItems(Array.isArray(body.items) ? body.items : []);
      } catch {
        /* transient */
      }
    },
    [apiBase],
  );

  useEffect(() => {
    const ident = readIdentity();
    setName(ident.name);
    if (ident.contributorId) {
      setContributorId(ident.contributorId);
      loadItems(ident.contributorId).finally(() => setLoaded(true));
    } else {
      setLoaded(true);
    }
  }, [loadItems]);

  const ensureName = useCallback((): string | null => {
    if (name.trim()) return name.trim();
    const trimmed = draftName.trim();
    if (!trimmed) return null;
    try {
      localStorage.setItem(NAME_KEY, trimmed);
    } catch {
      /* ignore */
    }
    setName(trimmed);
    return trimmed;
  }, [name, draftName]);

  const submit = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;
    if (!ensureName()) {
      setError("Tell me your name first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let cid = contributorId;
      if (!cid) {
        const fresh = await ensureContributorId(apiBase);
        if (!fresh) {
          setError("Couldn't claim a contributor id. Try again.");
          return;
        }
        cid = fresh;
        setContributorId(fresh);
      }
      const r = await fetch(`${apiBase}/api/inspired-by`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: text, source_contributor_id: cid }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setError(
          typeof body?.detail === "string" ? body.detail : "Couldn't resolve that.",
        );
        return;
      }
      setInput("");
      await loadItems(cid);
    } finally {
      setBusy(false);
    }
  }, [input, busy, ensureName, contributorId, apiBase, loadItems]);

  const remove = useCallback(
    async (edgeId: string) => {
      setItems((prev) => prev.filter((it) => it.edge_id !== edgeId));
      try {
        await fetch(
          `${apiBase}/api/inspired-by/${encodeURIComponent(edgeId)}`,
          { method: "DELETE" },
        );
      } catch {
        if (contributorId) loadItems(contributorId);
      }
    },
    [apiBase, contributorId, loadItems],
  );

  return (
    <section className="space-y-5">
      <header className="space-y-1">
        <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))]">
          Inspired by
        </p>
        <h2 className="text-xl md:text-2xl font-light tracking-tight text-foreground">
          The people, communities, and places that made me.
        </h2>
        <p className="text-sm text-muted-foreground">
          Name someone. The system finds them on the open web, highlights where
          they show up, what they've made — and remembers the thread between us.
        </p>
      </header>

      {!name.trim() && (
        <input
          aria-label="Your display name"
          type="text"
          placeholder="Your name (so the thread is attributed to you)"
          value={draftName}
          onChange={(e) => setDraftName(e.target.value)}
          className="w-full rounded-xl border border-border/40 bg-background/40 px-4 py-3 text-sm focus:outline-none focus:border-[hsl(var(--primary)/0.5)]"
        />
      )}

      <div className="flex gap-2">
        <input
          ref={inputRef}
          aria-label="A person, community, or place that inspired you"
          type="text"
          placeholder="Daniel Scranton  ·  Yaima  ·  Unison Festival  ·  https://…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
          disabled={busy}
          className="flex-1 rounded-xl border border-border/40 bg-background/40 px-4 py-3 text-sm focus:outline-none focus:border-[hsl(var(--primary)/0.5)] disabled:opacity-60"
        />
        <button
          type="button"
          onClick={submit}
          disabled={busy || !input.trim()}
          className="rounded-xl border border-[hsl(var(--primary)/0.4)] bg-[hsl(var(--primary)/0.08)] text-[hsl(var(--primary))] px-4 py-3 text-sm font-medium hover:bg-[hsl(var(--primary)/0.15)] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {busy ? "…" : "Add"}
        </button>
      </div>

      {error && (
        <p className="text-xs text-[hsl(var(--destructive))]">{error}</p>
      )}

      {loaded && items.length === 0 && !busy && (
        <p className="text-sm text-muted-foreground italic">
          Nothing yet. Begin with whoever first comes to mind — a teacher, an
          artist, a place that shaped you.
        </p>
      )}

      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {items.map((it) => {
          const presences = Array.isArray(it.node.presences) ? it.node.presences : [];
          return (
            <li
              key={it.edge_id}
              className="group relative rounded-2xl border border-border/30 bg-card/50 p-4 hover:bg-card/70 transition-colors"
            >
              <div className="flex gap-3 items-start">
                {it.node.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={it.node.image_url}
                    alt=""
                    className="w-12 h-12 rounded-lg object-cover shrink-0 border border-border/30"
                  />
                ) : (
                  <div className="w-12 h-12 rounded-lg bg-[hsl(var(--primary)/0.1)] text-[hsl(var(--primary))] flex items-center justify-center font-medium shrink-0">
                    {(it.node.name || "·").trim().charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      {TYPE_LABEL[it.node.type] || it.node.type}
                    </span>
                    {it.node.provider && (
                      <span className="text-[10px] text-muted-foreground/70">
                        · {it.node.provider}
                      </span>
                    )}
                    <span className="ml-auto">
                      <WeightDots weight={it.weight} />
                    </span>
                  </div>
                  <p className="font-medium text-foreground truncate">
                    {it.node.name}
                  </p>
                  {it.node.tagline || it.node.description ? (
                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                      {it.node.tagline || it.node.description}
                    </p>
                  ) : null}

                  {presences.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {presences.slice(0, 6).map((p) => (
                        <a
                          key={p.url}
                          href={p.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[10px] uppercase tracking-[0.12em] rounded-full border border-border/40 px-2 py-0.5 text-muted-foreground hover:text-foreground hover:border-border"
                        >
                          {p.provider}
                        </a>
                      ))}
                    </div>
                  )}

                  <div className="flex items-center gap-3 mt-2">
                    {it.node.canonical_url && (
                      <a
                        href={it.node.canonical_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-[hsl(var(--chart-2))] hover:opacity-80"
                      >
                        visit →
                      </a>
                    )}
                    {it.node.claimable && (
                      <span className="text-[10px] text-muted-foreground/70 italic">
                        claimable
                      </span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => remove(it.edge_id)}
                  aria-label={`Remove ${it.node.name}`}
                  className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground text-sm w-6 h-6 rounded-full flex items-center justify-center"
                >
                  ×
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
