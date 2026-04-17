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

interface WarmthEvent {
  emoji: string | null;
  actorName: string | null;
  bodyPreview: string | null;
}

interface Digest {
  voices: number;
  newVoicesPreview: string | null;
  ideas: number;
  news: { title: string; url: string } | null;
  // The warmth she received back on her own voice(s) since she last
  // visited. Each event is one reaction another reader laid on
  // something she said. Rendered before everything else because it
  // is the closing of her contribution loop.
  warmth: WarmthEvent[];
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
      // Build the personal-feed URL from whichever identity she holds.
      // Cycle O auto-graduates her to a contributor on first voice, so
      // contributorId is the common case. We still pass author_name so
      // voices recorded before she had a contributor_id still match.
      const personalParams = new URLSearchParams({ limit: "20", lang });
      if (contributorId) personalParams.set("contributor_id", contributorId);
      if (storedName) personalParams.set("author_name", storedName);

      const [voicesRes, ideasRes, newsRes, personalRes] = await Promise.allSettled([
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
        // The personal feed surfaces reactions on her voices, replies
        // to her reactions, proposals she supported becoming ideas —
        // the full shape of "the organism received you". We filter it
        // down to what happened *since her last visit*.
        fetch(`${base}/api/feed/personal?${personalParams}`, { cache: "no-store" })
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

      // Reactions/replies that landed on what she contributed — the
      // shape that turns "you spoke" into "you were heard."
      const warmth: WarmthEvent[] = [];
      if (personalRes.status === "fulfilled" && personalRes.value) {
        interface FeedItem {
          reason?: string;
          actor_name?: string | null;
          snippet?: string | null;
          created_at?: string | null;
        }
        const items = (personalRes.value.items || []) as FeedItem[];
        const warmthReasons = new Set([
          "reaction_on_my_voice",
          "replied_to_me",
          "lifted_from_my_proposal",
          "lifted_from_proposal_i_supported",
        ]);
        for (const it of items) {
          if (!it.reason || !warmthReasons.has(it.reason)) continue;
          if (!it.created_at || Date.parse(it.created_at) <= lastVisitMs) continue;
          // snippet shape depends on the reason — for reactions, the
          // snippet is the emoji. For replies, it's the reply text.
          const raw = (it.snippet || "").trim();
          const emoji = raw.length > 0 && raw.length <= 6 ? raw : null;
          warmth.push({
            emoji,
            actorName: it.actor_name || null,
            bodyPreview: emoji ? null : raw.slice(0, 80),
          });
          if (warmth.length >= 3) break;
        }
      }

      const anythingWorthShowing =
        voices > 0 || ideas > 0 || !!news || warmth.length > 0;
      if (!anythingWorthShowing || cancelled) return;

      setName(storedName.trim());
      setDigest({ voices, newVoicesPreview, ideas, news, warmth });
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
      {/* Warmth-she-received comes first — the closing of her own
          contribution loop takes precedence over network-wide updates. */}
      {digest.warmth.length > 0 && (
        <div className="space-y-1.5">
          {digest.warmth.map((w, idx) => (
            <p key={idx} className="text-foreground/90">
              {w.emoji && (
                <span className="text-lg mr-1.5" aria-hidden="true">{w.emoji}</span>
              )}
              <span>
                {(w.actorName || t("morningNudge.someone"))}{" "}
                <span className="text-muted-foreground">
                  {w.emoji
                    ? t("morningNudge.reactedToYourVoice")
                    : t("morningNudge.repliedToYou")}
                </span>
              </span>
              {w.bodyPreview && (
                <span className="block text-sm italic text-muted-foreground mt-0.5 pl-6">
                  {w.bodyPreview}
                </span>
              )}
            </p>
          ))}
        </div>
      )}
      {parts.length > 0 && <p>{parts.join(" · ")}</p>}
      {digest.newVoicesPreview && (
        <VoiceQuote>{digest.newVoicesPreview}</VoiceQuote>
      )}
      {digest.news && (
        <p>
          <span className="text-muted-foreground mr-1">{t("morningNudge.newsLead")}</span>
          <a
            href={digest.news.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[hsl(var(--chart-2))] hover:opacity-80 underline underline-offset-2 decoration-[hsl(var(--chart-2)/0.4)]"
          >
            {digest.news.title}
          </a>
        </p>
      )}
    </Panel>
  );
}
