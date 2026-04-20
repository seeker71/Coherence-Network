"use client";

/**
 * UpcomingGatherings — the living edge of a presence page.
 *
 * A ceremony is where the music actually happens; a workshop is
 * where the teaching lands in bodies. Those moments are time-charged
 * and co-held: a workshop is rarely one person's alone — it has
 * co-leaders and a hosting collective, and every presence involved
 * should carry the same gathering on their own page. Anyone who
 * knows can add one, no gate.
 *
 * When the identity itself walks in and claims the page, the
 * gatherings held by the community are already waiting for them —
 * gratitude placed on the shrine before they arrive.
 *
 * Storage shape (orchestrated by POST /api/presences/{id}/gatherings):
 *   · event node — type="event", properties {when, where, url, note,
 *     added_by, added_by_name, added_at}
 *   · edges — one contributes-to per host (primary + co-leaders +
 *     hosting collective), each with role="primary"|"co-leading"|"hosting"
 *
 * Because every host carries the same edge type to the event, every
 * host's /people/[id] page surfaces the gathering through the same
 * fetch path. No special-casing.
 */

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getApiBase } from "@/lib/api";
import {
  currentContributorName,
  ensureVisitorContributor,
} from "@/lib/visitor";
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
  added_at?: string;
};

type HostChip = { id: string; name: string; role: string };

type EdgeRow = {
  id: string;
  from_id: string;
  to_id: string;
  type: string;
  to_node?: { id: string; name: string; type: string };
  from_node?: { id: string; name: string; type: string };
  properties?: { kind?: string; role?: string };
};

function relativeTime(iso: string | undefined): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const deltaSec = Math.floor((Date.now() - t) / 1000);
  if (deltaSec < 60) return "just now";
  if (deltaSec < 3600) return `${Math.floor(deltaSec / 60)}m ago`;
  if (deltaSec < 86400) return `${Math.floor(deltaSec / 3600)}h ago`;
  if (deltaSec < 86400 * 7) return `${Math.floor(deltaSec / 86400)}d ago`;
  return new Date(t).toLocaleDateString();
}

/**
 * Is this gathering already past? The `when` field is free text —
 * "May 9 2026", "summer 2025", "next full moon". Chrome's Date.parse
 * is too lenient for season words ("summer 2026" → Dec 31 2025), so
 * the tiered heuristic is:
 *   1. If the string carries a 4-digit year and that year differs
 *      from the current year, the comparison is unambiguous.
 *   2. Otherwise (same year or no year), only trust Date.parse when
 *      the string contains a month name or digit-separated date.
 *   3. Anything else defaults to upcoming — a held-open date is more
 *      alive surfaced than tucked into a lineage list.
 */
function isPast(when: string | undefined): boolean {
  if (!when) return false;
  const yearMatch = when.match(/\b(19|20)\d{2}\b/);
  const currentYear = new Date().getFullYear();
  if (yearMatch) {
    const year = parseInt(yearMatch[0], 10);
    if (year < currentYear) return true;
    if (year > currentYear) return false;
  }
  const hasMonthOrDay = /\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}[/-])/i.test(when);
  if (hasMonthOrDay) {
    const parsed = Date.parse(when);
    if (!Number.isNaN(parsed)) return parsed < Date.now();
  }
  return false;
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
  const [hostsByEvent, setHostsByEvent] = useState<Record<string, HostChip[]>>({});
  const [loaded, setLoaded] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState("");
  const [when, setWhen] = useState("");
  const [where, setWhere] = useState("");
  const [url, setUrl] = useState("");
  const [note, setNote] = useState("");
  const [hostedBy, setHostedBy] = useState("");
  const [coLedWith, setCoLedWith] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      // Every presence this identity is linked to via contributes-to;
      // keep only the event-typed endpoints.
      const r = await fetch(
        `${apiBase}/api/edges?from_id=${encodeURIComponent(identityId)}&type=contributes-to&limit=100`,
        { cache: "no-store" },
      );
      if (!r.ok) return;
      const body: { items: EdgeRow[] } = await r.json();
      const eventEdges = (body.items || []).filter(
        (e) => e.to_node?.type === "event",
      );
      // Full event nodes for the cards + every contributes-to edge
      // pointing at each event, so we can render co-leader / hosting
      // chips drawn from the graph itself rather than any client guess.
      const [fullEvents, hostMap] = await Promise.all([
        Promise.all(
          eventEdges.map(async (e) => {
            const res = await fetch(
              `${apiBase}/api/graph/nodes/${encodeURIComponent(e.to_id)}`,
              { cache: "no-store" },
            );
            if (!res.ok) return null;
            return (await res.json()) as EventNode;
          }),
        ),
        Promise.all(
          eventEdges.map(async (e) => {
            const eres = await fetch(
              `${apiBase}/api/edges?to_id=${encodeURIComponent(e.to_id)}&type=contributes-to&limit=20`,
              { cache: "no-store" },
            );
            if (!eres.ok) return [e.to_id, [] as HostChip[]] as const;
            const ebody: { items: EdgeRow[] } = await eres.json();
            const chips = (ebody.items || [])
              .filter((row) => row.from_node && row.from_id !== identityId)
              .map((row) => ({
                id: row.from_id,
                name: row.from_node!.name,
                role: row.properties?.role || "with",
              }));
            return [e.to_id, chips] as const;
          }),
        ),
      ]);
      setEvents(fullEvents.filter((x): x is EventNode => x !== null));
      setHostsByEvent(Object.fromEntries(hostMap));
    } catch {
      /* transient */
    }
  }, [apiBase, identityId]);

  useEffect(() => {
    load().finally(() => setLoaded(true));
  }, [load]);

  const coLedList = useMemo(
    () =>
      coLedWith
        .split(/[,\n]/)
        .map((s) => s.trim())
        .filter(Boolean),
    [coLedWith],
  );

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
      // Every contribution is by a contributor. If the visitor hasn't
      // got one yet, mint a provisional one now — it's the same node
      // they'll claim when they name themselves via the stepIn door.
      const addedBy = await ensureVisitorContributor();
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
            added_by: addedBy,
            added_by_name: currentContributorName(),
            hosted_by: hostedBy.trim() || null,
            co_led_with: coLedList,
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
      setHostedBy("");
      setCoLedWith("");
      setShowForm(false);
      await load();
    } catch (err) {
      setError((err as Error).message || "Something slipped. Try again?");
    } finally {
      setSaving(false);
    }
  }

  if (!loaded && events.length === 0) return null;

  const upcoming = events.filter((e) => !isPast(e.when));
  const past = events.filter((e) => isPast(e.when));

  const renderCard = (e: EventNode, tone: "upcoming" | "past") => {
    const added = relativeTime(e.added_at);
    const chips = hostsByEvent[e.id] || [];
    const primary = chips.find((c) => c.role === "primary");
    const hosting = chips.find((c) => c.role === "hosting");
    const presenting = chips.filter((c) => c.role === "presenting");
    const coLeaders = chips.filter(
      (c) => c.role === "co-leading" || c.role === "co-creating",
    );
    const performers = chips.filter((c) => c.role === "performing");
    const cacaoFacilitators = chips.filter((c) => c.role === "cacao-facilitator");
    const videographers = chips.filter((c) => c.role === "videographer");
    const partners = chips.filter((c) => c.role === "partner");
    const cardClass =
      tone === "upcoming"
        ? "rounded-2xl border border-white/10 bg-white/[0.03] p-4"
        : "rounded-2xl border border-white/5 bg-white/[0.015] p-4";
    return (
      <li key={e.id} className={cardClass}>
        <p className="text-[15px] leading-snug text-white">{e.name}</p>
        {(e.when || e.where) && (
          <p className="mt-1 text-xs text-white/60">
            {e.when}
            {e.when && e.where && <span className="mx-1.5">·</span>}
            {e.where}
          </p>
        )}
        {primary && (
          <p className="mt-1.5 text-xs text-white/55">
            by{" "}
            <Link
              href={`/people/${encodeURIComponent(primary.id)}`}
              className="text-white/80 hover:text-white underline-offset-2 hover:underline"
            >
              {primary.name}
            </Link>
          </p>
        )}
        {hosting && (
          <p className="mt-1.5 text-xs text-white/55">
            held by{" "}
            <Link
              href={`/people/${encodeURIComponent(hosting.id)}`}
              className="text-white/80 hover:text-white underline-offset-2 hover:underline"
            >
              {hosting.name}
            </Link>
          </p>
        )}
        {presenting.length > 0 && (
          <p className="mt-1 text-xs text-white/55">
            presented by{" "}
            {presenting.map((c, i) => (
              <span key={c.id}>
                {i > 0 && (i === presenting.length - 1 ? " & " : ", ")}
                <Link
                  href={`/people/${encodeURIComponent(c.id)}`}
                  className="text-white/80 hover:text-white underline-offset-2 hover:underline"
                >
                  {c.name}
                </Link>
              </span>
            ))}
          </p>
        )}
        {coLeaders.length > 0 && (
          <p className="mt-1 text-xs text-white/55">
            co-led with{" "}
            {coLeaders.map((c, i) => (
              <span key={c.id}>
                {i > 0 && ", "}
                <Link
                  href={`/people/${encodeURIComponent(c.id)}`}
                  className="text-white/80 hover:text-white underline-offset-2 hover:underline"
                >
                  {c.name}
                </Link>
              </span>
            ))}
          </p>
        )}
        {performers.length > 0 && (
          <p className="mt-1 text-xs text-white/55">
            featuring{" "}
            {performers.map((c, i) => (
              <span key={c.id}>
                {i > 0 && ", "}
                <Link
                  href={`/people/${encodeURIComponent(c.id)}`}
                  className="text-white/80 hover:text-white underline-offset-2 hover:underline"
                >
                  {c.name}
                </Link>
              </span>
            ))}
          </p>
        )}
        {cacaoFacilitators.length > 0 && (
          <p className="mt-1 text-xs text-white/55">
            cacao by{" "}
            {cacaoFacilitators.map((c, i) => (
              <span key={c.id}>
                {i > 0 && ", "}
                <Link
                  href={`/people/${encodeURIComponent(c.id)}`}
                  className="text-white/80 hover:text-white underline-offset-2 hover:underline"
                >
                  {c.name}
                </Link>
              </span>
            ))}
          </p>
        )}
        {videographers.length > 0 && (
          <p className="mt-1 text-xs text-white/55">
            filmed by{" "}
            {videographers.map((c, i) => (
              <span key={c.id}>
                {i > 0 && ", "}
                <Link
                  href={`/people/${encodeURIComponent(c.id)}`}
                  className="text-white/80 hover:text-white underline-offset-2 hover:underline"
                >
                  {c.name}
                </Link>
              </span>
            ))}
          </p>
        )}
        {partners.length > 0 && (
          <p className="mt-1 text-xs text-white/55">
            in partnership with{" "}
            {partners.map((c, i) => (
              <span key={c.id}>
                {i > 0 && ", "}
                <Link
                  href={`/people/${encodeURIComponent(c.id)}`}
                  className="text-white/80 hover:text-white underline-offset-2 hover:underline"
                >
                  {c.name}
                </Link>
              </span>
            ))}
          </p>
        )}
        {e.note && (
          <p className="mt-2 text-sm italic text-white/75 leading-relaxed">
            {e.note}
          </p>
        )}
        <div className="mt-2 flex items-center gap-3 text-xs flex-wrap">
          {e.url && (
            <a
              href={e.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium"
              style={{ color: accent.bg }}
            >
              {tone === "past" ? "see it →" : "register →"}
            </a>
          )}
          {(e.added_by || added) && (
            <span className="text-white/40">
              ·{" "}
              {e.added_by ? (
                e.added_by_name ? (
                  <>
                    added by{" "}
                    <Link
                      href={`/people/${encodeURIComponent(e.added_by)}`}
                      className="hover:text-white/70 underline-offset-2 hover:underline"
                    >
                      {e.added_by_name}
                    </Link>
                  </>
                ) : (
                  <Link
                    href={`/people/${encodeURIComponent(e.added_by)}`}
                    className="hover:text-white/70 underline-offset-2 hover:underline"
                  >
                    added
                  </Link>
                )
              ) : (
                <>added</>
              )}
              {added && <> · {added}</>}
            </span>
          )}
        </div>
      </li>
    );
  };

  return (
    <section className="px-6 pt-8">
      {upcoming.length > 0 && (
        <>
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
            Upcoming
          </p>
          <ul className="space-y-3">
            {upcoming.map((e) => renderCard(e, "upcoming"))}
          </ul>
        </>
      )}

      {past.length > 0 && (
        <>
          <p className={`text-[10px] uppercase tracking-[0.18em] font-semibold text-white/40 mb-3 ${upcoming.length > 0 ? "mt-6" : ""}`}>
            Where the sound has traveled
          </p>
          <ul className="space-y-3">
            {past.map((e) => renderCard(e, "past"))}
          </ul>
        </>
      )}

      {upcoming.length === 0 && past.length === 0 && (
        <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
          Upcoming
        </p>
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
            Held by — a collective, a sanctuary, the land (optional)
            <input
              type="text"
              value={hostedBy}
              onChange={(e) => setHostedBy(e.target.value)}
              placeholder="paste the URL — e.g. ecstaticdance.org/…"
              className="mt-1 w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-sm text-white placeholder-white/30 focus:border-white/30 focus:outline-none"
            />
          </label>
          <label className="block text-[10px] uppercase tracking-[0.14em] text-white/50">
            Co-led with — URLs, comma-separated (optional)
            <input
              type="text"
              value={coLedWith}
              onChange={(e) => setCoLedWith(e.target.value)}
              placeholder="https://…, https://…"
              className="mt-1 w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-sm text-white placeholder-white/30 focus:border-white/30 focus:outline-none"
            />
            <span className="mt-1 block text-[10px] normal-case tracking-normal text-white/40 italic">
              A URL links to their real presence. A bare name becomes a
              held-open placeholder — the page surfaces it as unclaimed
              rather than binding an identity we haven't verified.
            </span>
          </label>
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
