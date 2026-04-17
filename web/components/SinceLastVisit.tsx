"use client";

/**
 * SinceLastVisit — the come-back promise.
 *
 * On every visit to /feed/you, checks `cc-last-visit-at` in localStorage.
 * If set, fetches /api/notifications?since=<that>&contributor_id=...
 * and /api/feed/personal to summarize: "Since you last visited, X new
 * voices on concepts you touched, Y replies, Z proposals lifted."
 *
 * Then writes the current time to cc-last-visit-at so the next visit
 * counts from now.
 *
 * Quiet when there's nothing new, or when the viewer has no identity.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useT, useLocale } from "@/components/MessagesProvider";

const LAST_VISIT_KEY = "cc-last-visit-at";
const CONTRIBUTOR_KEY = "cc-contributor-id";
const NAME_KEY = "cc-reaction-author-name";

interface Event {
  kind: string;
  entity_type: string;
  entity_id: string;
  body: string;
  actor_name: string;
  created_at: string | null;
}

function bucketOf(kind: string): "reply" | "reaction" | "lift" | "mention" | "other" {
  if (kind === "reply_to_me") return "reply";
  if (kind === "reaction_to_my_voice") return "reaction";
  if (kind === "proposal_lifted" || kind === "lift_i_supported") return "lift";
  if (kind === "mention") return "mention";
  return "other";
}

function humanDaysAgo(iso: string | null, lang: string): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const delta = Date.now() - t;
  const days = Math.round(delta / 86400000);
  if (days < 1) return new Date(t).toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" });
  if (days === 1) return "1d";
  return `${days}d`;
}

export function SinceLastVisit() {
  const t = useT();
  const locale = useLocale();
  const [events, setEvents] = useState<Event[] | null>(null);
  const [since, setSince] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const contributor = localStorage.getItem(CONTRIBUTOR_KEY);
        const name = localStorage.getItem(NAME_KEY);
        if (!contributor && !name) {
          setEvents([]);
          setLoading(false);
          return;
        }
        const lastVisit = localStorage.getItem(LAST_VISIT_KEY);
        if (!lastVisit) {
          // First visit — nothing to summarize yet, but mark now as the anchor
          try {
            localStorage.setItem(LAST_VISIT_KEY, new Date().toISOString());
          } catch { /* ignore */ }
          setEvents([]);
          setLoading(false);
          return;
        }
        setSince(lastVisit);
        const params = new URLSearchParams({ limit: "50", lang: locale });
        if (contributor) params.set("contributor_id", contributor);
        if (name) params.set("author_name", name);
        params.set("since", lastVisit);
        const res = await fetch(`${getApiBase()}/api/notifications?${params}`);
        if (!res.ok || cancelled) return;
        const data = await res.json();
        if (cancelled) return;
        setEvents(data.events || []);
        // Bump the anchor only after the user sees this panel (not on fetch)
      } catch {
        if (!cancelled) setEvents([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [locale]);

  // On unmount (or page transition), update the "last visit" so next
  // time we only show things newer than now.
  useEffect(() => {
    return () => {
      try {
        localStorage.setItem(LAST_VISIT_KEY, new Date().toISOString());
      } catch { /* ignore */ }
    };
  }, []);

  if (loading || !events || events.length === 0) return null;

  const buckets = events.reduce<Record<string, number>>((acc, e) => {
    const b = bucketOf(e.kind);
    acc[b] = (acc[b] || 0) + 1;
    return acc;
  }, {});
  const summary: string[] = [];
  if (buckets.reply) summary.push(t("sinceLast.replies").replace("{n}", String(buckets.reply)));
  if (buckets.reaction) summary.push(t("sinceLast.reactions").replace("{n}", String(buckets.reaction)));
  if (buckets.lift) summary.push(t("sinceLast.lifts").replace("{n}", String(buckets.lift)));
  if (buckets.mention) summary.push(t("sinceLast.mentions").replace("{n}", String(buckets.mention)));

  const latest = events.slice(0, 3);
  const sinceLabel = since ? humanDaysAgo(since, locale) : "";

  return (
    <section className="rounded-xl border border-amber-800/30 bg-amber-950/10 p-5 space-y-3">
      <p className="text-xs uppercase tracking-widest text-amber-300/90">
        {t("sinceLast.eyebrow").replace("{when}", sinceLabel)}
      </p>
      <h3 className="text-base font-medium text-stone-100 leading-snug">
        {summary.join(" · ") || t("sinceLast.generic")}
      </h3>
      <ul className="space-y-1.5 text-sm">
        {latest.map((e, i) => (
          <li
            key={`${e.created_at}-${i}`}
            className="flex items-start gap-2 text-stone-300"
          >
            <span className="shrink-0" aria-hidden="true">
              {bucketOf(e.kind) === "reply"
                ? "↩️"
                : bucketOf(e.kind) === "reaction"
                ? "💛"
                : bucketOf(e.kind) === "lift"
                ? "🌱"
                : bucketOf(e.kind) === "mention"
                ? "@"
                : "•"}
            </span>
            <span className="min-w-0 flex-1 truncate">
              <Link
                href={`/meet/${e.entity_type}/${encodeURIComponent(e.entity_id)}`}
                className="hover:text-amber-300"
              >
                {e.body || `${e.entity_type}: ${e.entity_id}`}
              </Link>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
