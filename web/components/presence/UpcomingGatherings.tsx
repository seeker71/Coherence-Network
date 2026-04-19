"use client";

/**
 * UpcomingGatherings — the living edge of a presence page.
 *
 * A ceremony is where the music actually happens; a workshop is
 * where the teaching lands in bodies. Those moments are time-charged,
 * and the page should carry them. Anyone who knows about a gathering
 * can add it right here — no claim gate, no moderation queue. The
 * graph takes the offer; the next visitor sees it.
 *
 * When the identity itself walks in and claims the page, the
 * gatherings added by the community are already waiting for them,
 * which is itself a form of gratitude flowing back.
 *
 * Storage shape (everything through existing graph endpoints):
 *   · event node — type="event", properties {when, where, url, note, added_by}
 *   · edge — from identity → event, type="contributes-to",
 *            properties {kind:"event"}. Reuses the same pattern the
 *            resolver uses for albums, so the lineage stays consistent.
 */

import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import type { BrandTone } from "./brand";

type EventNode = {
  id: string;
  name: string;
  when?: string;
  where?: string;
  url?: string;
  note?: string;
  added_by?: string;
  added_by_name?: string;
};

type EdgeRow = {
  id: string;
  to_id: string;
  to_node?: { id: string; name: string; type: string };
  properties?: { kind?: string };
};

function currentContributorId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem("contributor_id");
  } catch {
    return null;
  }
}

function currentContributorName(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem("author_name") || null;
  } catch {
    return null;
  }
}

export function UpcomingGatherings({
  identityId,
  identityName,
  accent,
}: {
  identityId: string;
  identityName: string;
  accent: BrandTone;
}) {
  const apiBase = getApiBase();
  const [events, setEvents] = useState<EventNode[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState("");
  const [when, setWhen] = useState("");
  const [where, setWhere] = useState("");
  const [url, setUrl] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(
        `${apiBase}/api/edges?from_id=${encodeURIComponent(identityId)}&type=contributes-to&limit=50`,
        { cache: "no-store" },
      );
      if (!r.ok) return;
      const body: { items: EdgeRow[] } = await r.json();
      const eventEdges = (body.items || []).filter(
        (e) => e.to_node?.type === "event",
      );
      const full = await Promise.all(
        eventEdges.map(async (e) => {
          const res = await fetch(
            `${apiBase}/api/graph/nodes/${encodeURIComponent(e.to_id)}`,
            { cache: "no-store" },
          );
          if (!res.ok) return null;
          return (await res.json()) as EventNode;
        }),
      );
      setEvents(full.filter((x): x is EventNode => x !== null));
    } catch {
      /* transient */
    }
  }, [apiBase, identityId]);

  useEffect(() => {
    load().finally(() => setLoaded(true));
  }, [load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setError("A gathering needs at least a title.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(
        `${apiBase}/api/presences/${encodeURIComponent(identityId)}/gatherings`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            title: cleanTitle,
            when: when.trim() || null,
            where: where.trim() || null,
            url: url.trim() || null,
            note: note.trim() || null,
            added_by: currentContributorId(),
            added_by_name: currentContributorName(),
          }),
        },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `add gathering failed (${res.status})`);
      }
      setTitle("");
      setWhen("");
      setWhere("");
      setUrl("");
      setNote("");
      setShowForm(false);
      await load();
    } catch (err) {
      setError((err as Error).message || "Something slipped. Try again?");
    } finally {
      setSaving(false);
    }
  }

  if (!loaded && events.length === 0) return null;

  return (
    <section className="px-6 pt-8">
      <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
        Upcoming
      </p>

      {events.length > 0 && (
        <ul className="space-y-3">
          {events.map((e) => (
            <li
              key={e.id}
              className="rounded-2xl border border-white/10 bg-white/[0.03] p-4"
            >
              <p className="text-[15px] leading-snug text-white">{e.name}</p>
              {(e.when || e.where) && (
                <p className="mt-1 text-xs text-white/60">
                  {e.when}
                  {e.when && e.where && <span className="mx-1.5">·</span>}
                  {e.where}
                </p>
              )}
              {e.note && (
                <p className="mt-2 text-sm italic text-white/75 leading-relaxed">
                  {e.note}
                </p>
              )}
              <div className="mt-2 flex items-center gap-3 text-xs">
                {e.url && (
                  <a
                    href={e.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium"
                    style={{ color: accent.bg }}
                  >
                    register →
                  </a>
                )}
                {e.added_by_name && (
                  <span className="text-white/40">· added by {e.added_by_name}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {showForm ? (
        <form
          onSubmit={submit}
          className="mt-3 rounded-2xl border border-white/15 bg-white/[0.04] p-4 space-y-2"
        >
          <label className="block text-[10px] uppercase tracking-[0.14em] text-white/50">
            What's the gathering
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={`e.g. Breathwork with ${identityName}`}
              className="mt-1 w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-sm text-white placeholder-white/30 focus:border-white/30 focus:outline-none"
              autoFocus
            />
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="block text-[10px] uppercase tracking-[0.14em] text-white/50">
              When
              <input
                type="text"
                value={when}
                onChange={(e) => setWhen(e.target.value)}
                placeholder="summer 2026"
                className="mt-1 w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-sm text-white placeholder-white/30 focus:border-white/30 focus:outline-none"
              />
            </label>
            <label className="block text-[10px] uppercase tracking-[0.14em] text-white/50">
              Where
              <input
                type="text"
                value={where}
                onChange={(e) => setWhere(e.target.value)}
                placeholder="Boulder, CO"
                className="mt-1 w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-sm text-white placeholder-white/30 focus:border-white/30 focus:outline-none"
              />
            </label>
          </div>
          <label className="block text-[10px] uppercase tracking-[0.14em] text-white/50">
            Register / learn more (optional)
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://"
              className="mt-1 w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-sm text-white placeholder-white/30 focus:border-white/30 focus:outline-none"
            />
          </label>
          <label className="block text-[10px] uppercase tracking-[0.14em] text-white/50">
            A word about why it matters (optional)
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="he's returning to Colorado — more charged than usual"
              rows={2}
              className="mt-1 w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-sm text-white placeholder-white/30 focus:border-white/30 focus:outline-none resize-none"
            />
          </label>
          {error && <p className="text-xs text-red-300/80">{error}</p>}
          <div className="flex items-center gap-3 pt-1">
            <button
              type="submit"
              disabled={saving}
              className="rounded-full px-4 py-2 text-sm font-medium disabled:opacity-50"
              style={{ background: accent.bg, color: accent.fg }}
            >
              {saving ? "adding…" : "add gathering"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowForm(false);
                setError(null);
              }}
              className="text-sm text-white/50 hover:text-white/80"
            >
              cancel
            </button>
          </div>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => setShowForm(true)}
          className="mt-3 inline-flex items-center gap-1.5 text-sm text-white/60 hover:text-white/90 border border-dashed border-white/15 hover:border-white/30 rounded-full px-4 py-2"
        >
          + add a gathering you know about
        </button>
      )}
    </section>
  );
}
