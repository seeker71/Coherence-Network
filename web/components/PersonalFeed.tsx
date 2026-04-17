"use client";

/**
 * PersonalFeed — the client-rendered stream of items the viewer has
 * touched or been touched by. Identity comes from localStorage (same
 * keys as ReactionBar / NotificationBell) so the server stays
 * identity-oblivious.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useLocale } from "@/components/MessagesProvider";
import { Panel } from "@/components/Panel";

const NAME_KEY = "cc-reaction-author-name";
const CONTRIBUTOR_KEY = "cc-contributor-id";

interface Item {
  entity_type: string;
  entity_id: string;
  kind: string;
  title: string;
  snippet: string;
  actor_name: string | null;
  reason: string;
  reason_label: string;
  created_at: string | null;
}

interface Props {
  strings: {
    empty: string;
    emptyCta: string;
    noIdentity: string;
    noIdentityCta: string;
    loading: string;
  };
}

function entityHref(entity_type: string, entity_id: string): string {
  const enc = encodeURIComponent(entity_id);
  switch (entity_type) {
    case "concept":
      return `/vision/${enc}`;
    case "idea":
      return `/ideas/${enc}`;
    case "spec":
      return `/specs/${enc}`;
    case "contributor":
      return `/contributors/${enc}/portfolio`;
    case "proposal":
      return `/meet/proposal/${enc}`;
    default:
      return `/meet/${entity_type}/${enc}`;
  }
}

function relLabel(iso: string | null, locale: string): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const delta = Math.max(0, Date.now() - t);
  const m = Math.round(delta / 60000);
  if (m < 1) return "now";
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.round(h / 24);
  if (d < 30) return `${d}d`;
  return new Date(t).toLocaleDateString(locale);
}

function iconForReason(reason: string): string {
  switch (reason) {
    case "i_voiced":
      return "🌱";
    case "i_reacted":
      return "💬";
    case "i_proposed":
      return "📜";
    case "i_supported":
      return "💛";
    case "replied_to_me":
      return "↩️";
    case "reaction_on_my_voice":
      return "✨";
    case "lifted_from_my_proposal":
      return "🌾";
    case "lifted_from_proposal_i_supported":
      return "🌾";
    default:
      return "•";
  }
}

export function PersonalFeed({ strings }: Props) {
  const locale = useLocale();
  const [items, setItems] = useState<Item[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasIdentity, setHasIdentity] = useState<boolean | null>(null);

  const load = useCallback(async () => {
    try {
      const contributor = localStorage.getItem(CONTRIBUTOR_KEY);
      const name = localStorage.getItem(NAME_KEY);
      if (!contributor && !name) {
        setHasIdentity(false);
        setItems([]);
        return;
      }
      setHasIdentity(true);
      const params = new URLSearchParams({ limit: "40", lang: locale });
      if (contributor) params.set("contributor_id", contributor);
      if (name) params.set("author_name", name);
      const base = getApiBase();
      const res = await fetch(`${base}/api/feed/personal?${params}`);
      if (!res.ok) {
        setItems([]);
        return;
      }
      const data = await res.json();
      setItems(data.items || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [locale]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return <p className="text-sm text-stone-500 italic">{strings.loading}</p>;
  }

  if (hasIdentity === false) {
    return (
      <Panel
        variant="empty"
        heading={strings.noIdentity}
        cta={
          <Link
            href="/vision/join"
            className="inline-block rounded-full bg-teal-600/90 hover:bg-teal-500/90 text-stone-950 px-4 py-2 text-sm font-medium transition-colors"
          >
            {strings.noIdentityCta}
          </Link>
        }
      />
    );
  }

  if (!items || items.length === 0) {
    return (
      <Panel
        variant="empty"
        heading={strings.empty}
        cta={
          <Link
            href="/vision"
            className="inline-block rounded-full bg-amber-600/90 hover:bg-amber-500/90 text-stone-950 px-4 py-2 text-sm font-medium transition-colors"
          >
            {strings.emptyCta}
          </Link>
        }
      />
    );
  }

  return (
    <ul className="space-y-3">
      {items.map((it, i) => (
        <li
          key={`${it.reason}-${it.entity_type}-${it.entity_id}-${it.created_at}-${i}`}
          className="rounded-lg border border-stone-800/50 bg-stone-900/40"
        >
          <Link
            href={entityHref(it.entity_type, it.entity_id)}
            className="flex items-start gap-3 p-4 hover:bg-stone-900 rounded-lg"
          >
            <div className="text-2xl leading-none shrink-0 w-10 text-center">
              {iconForReason(it.reason)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-xs text-stone-500 mb-1 flex-wrap">
                <span className="text-teal-300/90 font-medium">
                  {it.reason_label}
                </span>
                <span>·</span>
                <span className="text-stone-400">
                  {it.entity_type}: {it.entity_id}
                </span>
                <span className="ml-auto">{relLabel(it.created_at, locale)}</span>
              </div>
              {it.snippet && (
                <p className="text-stone-200 leading-relaxed break-words truncate">
                  {it.snippet}
                </p>
              )}
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
