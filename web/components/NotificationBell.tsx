"use client";

/**
 * NotificationBell — quiet witness of who spoke back.
 *
 * Polls /api/notifications with the viewer's identity (author_name from
 * localStorage, contributor_id if signed in) plus a "since" timestamp
 * tracked in localStorage. When events exist, a small dot appears on
 * the bell. Clicking reveals the list; opening the list marks them as
 * seen by bumping the since timestamp.
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useT, useLocale } from "@/components/MessagesProvider";

const NAME_KEY = "cc-reaction-author-name";
const CONTRIBUTOR_KEY = "cc-contributor-id";
const SINCE_KEY = "cc-notifications-since";

interface Event {
  kind:
    | "reply_to_me"
    | "reaction_to_my_voice"
    | "mention"
    | "proposal_lifted"
    | "lift_i_supported";
  entity_type: string;
  entity_id: string;
  body: string;
  actor_name: string;
  created_at: string | null;
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
    default:
      return `/meet/${entity_type}/${enc}`;
  }
}

export function NotificationBell() {
  const t = useT();
  const locale = useLocale();
  const [events, setEvents] = useState<Event[]>([]);
  const [open, setOpen] = useState(false);
  const [hasIdentity, setHasIdentity] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = useCallback(async () => {
    try {
      const name = localStorage.getItem(NAME_KEY);
      const contributor = localStorage.getItem(CONTRIBUTOR_KEY);
      if (!name && !contributor) {
        setHasIdentity(false);
        setEvents([]);
        return;
      }
      setHasIdentity(true);
      const since = localStorage.getItem(SINCE_KEY);
      const params = new URLSearchParams({ limit: "30", lang: locale });
      if (contributor) params.set("contributor_id", contributor);
      if (name) params.set("author_name", name);
      if (since) params.set("since", since);
      const base = getApiBase();
      const res = await fetch(`${base}/api/notifications?${params}`);
      if (!res.ok) return;
      const data = await res.json();
      setEvents(data.events || []);
    } catch {
      /* transient — try again next tick */
    }
  }, [locale]);

  useEffect(() => {
    poll();
    // Poll softly — once a minute while the tab is open.
    pollTimer.current = setInterval(poll, 60_000);
    function onFocus() {
      poll();
    }
    window.addEventListener("focus", onFocus);
    return () => {
      if (pollTimer.current) clearInterval(pollTimer.current);
      window.removeEventListener("focus", onFocus);
    };
  }, [poll]);

  function markSeen() {
    try {
      localStorage.setItem(SINCE_KEY, new Date().toISOString());
      setEvents([]);
    } catch {
      /* ignore */
    }
  }

  if (!hasIdentity) return null;

  const unseenCount = events.length;
  const relLabel = (iso: string | null): string => {
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
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => {
          setOpen((v) => !v);
        }}
        className="relative h-9 w-9 rounded-full hover:bg-stone-800/60 text-stone-300 flex items-center justify-center"
        aria-label={t("notifications.bellLabel")}
      >
        <span className="text-lg">🔔</span>
        {unseenCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 bg-amber-500 text-stone-950 text-[10px] font-medium rounded-full h-4 min-w-4 px-1 flex items-center justify-center">
            {unseenCount > 9 ? "9+" : unseenCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 max-h-96 overflow-y-auto rounded-md border border-stone-800 bg-stone-950/95 backdrop-blur shadow-2xl z-50">
          <header className="flex items-center justify-between px-4 py-2 border-b border-stone-800 text-xs text-stone-500 uppercase tracking-widest">
            <span>{t("notifications.heading")}</span>
            {events.length > 0 && (
              <button
                type="button"
                onClick={markSeen}
                className="text-stone-400 hover:text-amber-300/90 normal-case tracking-normal"
              >
                {t("notifications.markSeen")}
              </button>
            )}
          </header>

          {events.length === 0 ? (
            <p className="px-4 py-6 text-sm text-stone-400">
              {t("notifications.empty")}
            </p>
          ) : (
            <ul className="divide-y divide-stone-800/60">
              {events.map((e, i) => {
                const iconByKind =
                  e.kind === "reply_to_me"
                    ? "↩️"
                    : e.kind === "reaction_to_my_voice"
                    ? "💛"
                    : e.kind === "proposal_lifted"
                    ? "🌱"
                    : e.kind === "lift_i_supported"
                    ? "🌾"
                    : "@";
                return (
                  <li key={`${e.created_at}-${i}`} className="px-4 py-3 text-sm">
                    <Link
                      href={entityHref(e.entity_type, e.entity_id)}
                      onClick={() => setOpen(false)}
                      className="block hover:bg-stone-900 -mx-4 -my-3 px-4 py-3"
                    >
                      <div className="flex items-center gap-2 text-xs text-stone-500 mb-1">
                        <span>{iconByKind}</span>
                        <span className="text-amber-300/90 font-medium">
                          {e.actor_name}
                        </span>
                        <span className="ml-auto">{relLabel(e.created_at)}</span>
                      </div>
                      <p className="text-stone-200 leading-relaxed truncate">
                        {e.body}
                      </p>
                      <p className="text-xs text-stone-500 mt-1">
                        {e.entity_type} · {e.entity_id}
                      </p>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
