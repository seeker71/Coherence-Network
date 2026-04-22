"use client";

/**
 * InspiredByRail — the editable rail on /me/inspired-by.
 *
 * Highlights the people, communities, and places that made you.
 * One input, one gesture: type a name or paste a URL. The resolver
 * returns a small subgraph (identity + presences + creations) and a
 * weighted ``inspired-by`` edge is recorded from you to them.
 *
 * Card rendering, types, and fetch logic live in
 * ``components/inspired-by/shared`` — this file only adds the input
 * and delete gestures.
 */

import { useCallback, useEffect, useState } from "react";
import {
  NAME_KEY,
  ensureContributorId,
  readIdentity,
} from "@/lib/identity";
import {
  InspiredByCard,
  useInspiredByList,
} from "@/components/inspired-by/shared";

export function InspiredByRail() {
  const [contributorId, setContributorId] = useState<string>("");
  const [name, setName] = useState<string>("");
  const [draftName, setDraftName] = useState<string>("");
  const [input, setInput] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ident = readIdentity();
    setName(ident.name);
    if (ident.contributorId) setContributorId(ident.contributorId);
  }, []);

  const { items, setItems, loaded, reload, apiBase } = useInspiredByList(contributorId);

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
      await reload();
    } finally {
      setBusy(false);
    }
  }, [input, busy, ensureName, contributorId, apiBase, reload]);

  const remove = useCallback(
    async (edgeId: string) => {
      setItems((prev) => prev.filter((it) => it.edge_id !== edgeId));
      try {
        await fetch(
          `${apiBase}/api/inspired-by/${encodeURIComponent(edgeId)}`,
          { method: "DELETE" },
        );
      } catch {
        reload();
      }
    },
    [apiBase, reload, setItems],
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
        {items.map((item) => (
          <InspiredByCard key={item.edge_id} item={item} onRemove={remove} />
        ))}
      </ul>
    </section>
  );
}
