"use client";

/**
 * MorningNudge — the warm-back-tomorrow panel.
 *
 * Shown on /feed/you and / home when all of:
 *   • The viewer has a stored name (soft identity — from invite or
 *     direct name entry).
 *   • Her local time is between 06:00 and 11:00.
 *   • She has been here at least once before (cc-last-visit-at set).
 *   • At least 8 hours have passed since her last visit (so this is
 *     actually a new morning, not the same session).
 *   • She hasn't dismissed today's nudge yet.
 *
 * When all are true, fetches a lightweight "since last visit"
 * digest: new voices on concepts she touched + new ideas near
 * her interests + one resonant news item if available. Summarizes
 * in one sentence with a soft link to /feed/you.
 *
 * This is the in-app version of the "morning push" the user asked
 * for. True web-push (VAPID + service worker) is the next cycle —
 * this first surfaces the content shape and the warmth of tone
 * so we know what a push notification body should even say.
 */

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useT, useLocale } from "@/components/MessagesProvider";
import { Panel, PanelLink, VoiceQuote } from "@/components/Panel";

const NAME_KEY = "cc-reaction-author-name";
const CONTRIBUTOR_KEY = "cc-contributor-id";
const LAST_VISIT_KEY = "cc-last-visit-at";
const DISMISS_KEY = "cc-morning-nudge-dismissed";

const MORNING_START_HOUR = 6;
const MORNING_END_HOUR = 11;
const MIN_HOURS_BETWEEN_VISITS = 8;

interface Digest {
  voices: number;
  newVoicesPreview: string | null;
  ideas: number;
  news: { title: string; url: string } | null;
}

function localMorningWindow(): boolean {
  const h = new Date().getHours();
  return h >= MORNING_START_HOUR && h < MORNING_END_HOUR;
}

function hoursSince(iso: string | null): number {
  if (!iso) return Infinity;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return Infinity;
  return (Date.now() - t) / 3600_000;
}

function todayKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function MorningNudge() {
  const t = useT();
  const locale = useLocale();
  const [name, setName] = useState<string>("");
  const [digest, setDigest] = useState<Digest | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let storedName = "";
      let contributorId = "";
      let lastVisit: string | null = null;
      let dismissedToday = "";
      try {
        storedName = localStorage.getItem(NAME_KEY) || "";
        contributorId = localStorage.getItem(CONTRIBUTOR_KEY) || "";
        lastVisit = localStorage.getItem(LAST_VISIT_KEY);
        dismissedToday = localStorage.getItem(DISMISS_KEY) || "";
      } catch {
        /* ignore */
      }

      // Gate 1: she has a name we can greet by
      if (!storedName.trim()) return;
      // Gate 2: local morning window
      if (!localMorningWindow()) return;
      // Gate 3: has been here before
      if (!lastVisit) return;
      // Gate 4: it's actually a new day/session
      if (hoursSince(lastVisit) < MIN_HOURS_BETWEEN_VISITS) return;
      // Gate 5: already dismissed today
      if (dismissedToday === todayKey()) return;

      // Fetch the digest — keep it cheap, a single Promise.allSettled
      // of small endpoints. For news we query only the living-collective-
      // aligned sources so the morning greeting feels like it belongs
      // to the same world as the concepts she has been exploring, not a
      // generic tech-news feed. News is also translated into her locale
      // server-side (?lang=).
      const base = getApiBase();
      const lang = locale || "en";
      const [voicesRes, ideasRes, newsRes] = await Promise.allSettled([
        fetch(`${base}/api/concepts/voices/recent?limit=3`, { cache: "no-store" })
          .then((r) => (r.ok ? r.json() : null))
          .catch(() => null),
        fetch(`${base}/api/ideas/resonance?window_hours=36&limit=5&lang=${lang}`, { cache: "no-store" })
          .then((r) => (r.ok ? r.json() : null))
          .catch(() => null),
        // Prefer living-collective-aligned sources. Resilience.org is
        // most likely to match nourishing/community/regeneration themes.
        fetch(`${base}/api/news/feed?source=resilience&limit=3&lang=${lang}`, { cache: "no-store" })
          .then((r) => (r.ok ? r.json() : null))
          .catch(() => null),
      ]);

      const lastVisitMs = Date.parse(lastVisit);
      let voices = 0;
      let newVoicesPreview: string | null = null;
      if (voicesRes.status === "fulfilled" && voicesRes.value?.voices) {
        const fresh = (voicesRes.value.voices as Array<{ created_at: string | null; body: string }>)
          .filter((v) => v.created_at && Date.parse(v.created_at) > lastVisitMs);
        voices = fresh.length;
        if (fresh[0]?.body) {
          newVoicesPreview = fresh[0].body.slice(0, 120);
        }
      }

      let ideas = 0;
      if (ideasRes.status === "fulfilled" && ideasRes.value) {
        const arr = Array.isArray(ideasRes.value)
          ? ideasRes.value
          : ideasRes.value.ideas || [];
        ideas = arr.filter((i: { last_activity_at?: string }) => {
          if (!i.last_activity_at) return false;
          return Date.parse(i.last_activity_at) > lastVisitMs;
        }).length;
      }

      let news: Digest["news"] = null;
      if (newsRes.status === "fulfilled" && newsRes.value?.items?.length) {
        const first = newsRes.value.items[0];
        if (first?.title && first?.url) {
          news = { title: first.title, url: first.url };
        }
      }

      const anythingWorthShowing = voices > 0 || ideas > 0 || !!news;
      if (!anythingWorthShowing || cancelled) return;

      setName(storedName.trim());
      setDigest({ voices, newVoicesPreview, ideas, news });
      setVisible(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [locale]);

  function dismiss() {
    try {
      localStorage.setItem(DISMISS_KEY, todayKey());
    } catch {
      /* ignore */
    }
    setVisible(false);
  }

  if (!visible || !digest) return null;

  const parts: string[] = [];
  if (digest.voices > 0) {
    parts.push(
      t(digest.voices === 1 ? "morningNudge.voicesOne" : "morningNudge.voicesMany").replace(
        "{count}",
        String(digest.voices),
      ),
    );
  }
  if (digest.ideas > 0) {
    parts.push(
      t(digest.ideas === 1 ? "morningNudge.ideasOne" : "morningNudge.ideasMany").replace(
        "{count}",
        String(digest.ideas),
      ),
    );
  }

  // Every panel on every screen uses the same Panel primitive so the
  // visual language stays one language. MorningNudge is the canonical
  // "warm" panel — the viewer's own moment, held.
  return (
    <Panel
      variant="warm"
      ariaLabel={t("morningNudge.ariaLabel")}
      eyebrow={t("morningNudge.eyebrow")}
      heading={t("morningNudge.heading").replace("{name}", name)}
      onDismiss={dismiss}
      dismissLabel={t("morningNudge.dismiss")}
      cta={
        <PanelLink href="/feed/you" tone="warm">
          {t("morningNudge.openCorner")} →
        </PanelLink>
      }
      className="mt-3"
    >
      {parts.length > 0 && <p>{parts.join(" · ")}</p>}
      {digest.newVoicesPreview && (
        <VoiceQuote>{digest.newVoicesPreview}</VoiceQuote>
      )}
      {digest.news && (
        <p>
          <span className="text-stone-500 mr-1">{t("morningNudge.newsLead")}</span>
          <a
            href={digest.news.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-teal-300 hover:text-teal-200 underline underline-offset-2 decoration-teal-700/40"
          >
            {digest.news.title}
          </a>
        </p>
      )}
    </Panel>
  );
}
