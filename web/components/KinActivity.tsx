"use client";

/**
 * KinActivity — "Things near you" panel on /feed/you.
 *
 * Crosses the viewer's touched entities (from their personal feed)
 * with recent activity everywhere (recent voices + recent reactions).
 * Surfaces 3 items the viewer might care about because they already
 * touched those entities.
 *
 * Quiet when the viewer has no identity or no overlap.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useT, useLocale } from "@/components/MessagesProvider";

const CONTRIBUTOR_KEY = "cc-contributor-id";
const NAME_KEY = "cc-reaction-author-name";

interface PersonalItem {
  entity_type: string;
  entity_id: string;
  reason: string;
}

interface RecentVoice {
  id: string;
  concept_id: string;
  author_name: string;
  author_id: string | null;
  body: string;
  created_at: string | null;
}

interface RecentReaction {
  id: string;
  entity_type: string;
  entity_id: string;
  author_name: string;
  author_id: string | null;
  emoji: string | null;
  comment: string | null;
  created_at: string | null;
}

type Item =
  | { kind: "voice"; concept_id: string; actor: string; body: string; when: string | null }
  | { kind: "reaction"; entity_type: string; entity_id: string; actor: string; body: string; when: string | null };

function relTime(iso: string | null, lang: string): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const m = Math.round((Date.now() - t) / 60000);
  if (m < 1) return "now";
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.round(h / 24);
  return `${d}d`;
}

export function KinActivity() {
  const t = useT();
  const locale = useLocale();
  const [items, setItems] = useState<Item[] | null>(null);

  const load = useCallback(async () => {
    try {
      const contributor = localStorage.getItem(CONTRIBUTOR_KEY);
      const name = localStorage.getItem(NAME_KEY);
      if (!contributor && !name) {
        setItems([]);
        return;
      }
      const base = getApiBase();
      const [personalRes, voicesRes, reactionsRes] = await Promise.all([
        fetch(
          `${base}/api/feed/personal?${new URLSearchParams({
            limit: "50",
            lang: locale,
            ...(contributor ? { contributor_id: contributor } : {}),
            ...(name ? { author_name: name } : {}),
          })}`,
        ).catch(() => null),
        fetch(`${base}/api/concepts/voices/recent?limit=20`).catch(() => null),
        fetch(`${base}/api/reactions/recent?limit=30`).catch(() => null),
      ]);

      const personal: PersonalItem[] = personalRes?.ok
        ? ((await personalRes.json()).items || [])
        : [];
      const voices: RecentVoice[] = voicesRes?.ok
        ? ((await voicesRes.json()).voices || [])
        : [];
      const reactions: RecentReaction[] = reactionsRes?.ok
        ? ((await reactionsRes.json()).reactions || [])
        : [];

      // Set of entity keys the viewer has touched
      const touched = new Set(
        personal
          .filter((p) => p.reason !== "replied_to_me" && p.reason !== "reaction_on_my_voice")
          .map((p) => `${p.entity_type}:${p.entity_id}`),
      );
      // Also add concepts where the viewer voiced
      personal
        .filter((p) => p.reason === "i_voiced")
        .forEach((p) => touched.add(`concept:${p.entity_id}`));

      const out: Item[] = [];
      // Voices on concepts I touched, by others
      for (const v of voices) {
        const key = `concept:${v.concept_id}`;
        if (!touched.has(key)) continue;
        if (contributor && v.author_id === contributor) continue;
        if (!contributor && name && v.author_name === name) continue;
        out.push({
          kind: "voice",
          concept_id: v.concept_id,
          actor: v.author_name,
          body: v.body || "",
          when: v.created_at,
        });
      }
      // Reactions on entities I touched, by others, with a comment
      for (const r of reactions) {
        const key = `${r.entity_type}:${r.entity_id}`;
        if (!touched.has(key)) continue;
        if (contributor && r.author_id === contributor) continue;
        if (!contributor && name && r.author_name === name) continue;
        if (!r.comment) continue;  // keep it signal-rich
        out.push({
          kind: "reaction",
          entity_type: r.entity_type,
          entity_id: r.entity_id,
          actor: r.author_name,
          body: r.comment,
          when: r.created_at,
        });
      }
      out.sort((a, b) => {
        const at = a.when ? Date.parse(a.when) : 0;
        const bt = b.when ? Date.parse(b.when) : 0;
        return bt - at;
      });
      setItems(out.slice(0, 3));
    } catch {
      setItems([]);
    }
  }, [locale]);

  useEffect(() => {
    load();
  }, [load]);

  if (!items || items.length === 0) return null;

  return (
    <section className="rounded-xl border border-teal-800/30 bg-teal-950/10 p-5 space-y-3">
      <p className="text-xs uppercase tracking-widest text-teal-300/90">
        {t("kin.eyebrow")}
      </p>
      <h3 className="text-sm font-medium text-stone-100 leading-snug">
        {t("kin.headline")}
      </h3>
      <ul className="space-y-2">
        {items.map((it, i) => {
          const href =
            it.kind === "voice"
              ? `/vision/${encodeURIComponent(it.concept_id)}`
              : `/meet/${it.entity_type}/${encodeURIComponent(it.entity_id)}`;
          const target =
            it.kind === "voice" ? it.concept_id : `${it.entity_type}: ${it.entity_id}`;
          return (
            <li key={i} className="text-sm">
              <Link
                href={href}
                className="flex items-start gap-2 text-stone-300 hover:text-amber-200"
              >
                <span aria-hidden="true">
                  {it.kind === "voice" ? "🌱" : "💬"}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="truncate block">{it.body}</span>
                  <span className="text-xs text-stone-500">
                    {it.actor} · {target} · {relTime(it.when, locale)}
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
