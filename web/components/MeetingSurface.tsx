"use client";

/**
 * MeetingSurface — the full-screen experience of a viewer meeting an entity.
 *
 * Shows two vitality pulses (yours + theirs), a hero, and three gestures:
 *   · offer (💛): care, amplifies both pulses
 *   · dismiss (→): defer, records a light no-harm signal
 *   · amplify (🔥): strong care, bigger pulse lift
 *
 * No swipe lib — the page renders thumb-sized buttons at the bottom so
 * it works on mobile, desktop, and keyboard alike. The surface breathes
 * via a short animated pulse ring on each vitality number.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useLocale } from "@/components/MessagesProvider";

const CONTRIBUTOR_KEY = "cc-contributor-id";
const NAME_KEY = "cc-reaction-author-name";
const FINGERPRINT_KEY = "cc-presence-fingerprint";

function ensureFingerprint(): string {
  try {
    const existing = localStorage.getItem(FINGERPRINT_KEY);
    if (existing) return existing;
    const fresh = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem(FINGERPRINT_KEY, fresh);
    return fresh;
  } catch {
    return `anon-${Math.random().toString(36).slice(2, 10)}`;
  }
}

interface MeetingData {
  content: { vitality: number; reactions: number; voices: number; first_meeting: boolean };
  viewer: { vitality: number; reactions_given: number; voices_given: number; is_contributor: boolean };
  shared: { pulse: "resonant" | "familiar" | "first_meeting" | "quiet"; hint: string };
}

interface Props {
  entityType: string;
  entityId: string;
  title: string;
  description: string;
  imageUrl: string | null;
  strings: {
    viewerPulse: string;
    contentPulse: string;
    firstMeeting: string;
    familiar: string;
    resonant: string;
    quiet: string;
    offer: string;
    dismiss: string;
    amplify: string;
    inviteHint: string;
    othersHereOne?: string;
    othersHereMany?: string;
  };
}

export function MeetingSurface({
  entityType,
  entityId,
  title,
  description,
  imageUrl,
  strings,
}: Props) {
  const locale = useLocale();

  const [meeting, setMeeting] = useState<MeetingData | null>(null);
  const [authorName, setAuthorName] = useState<string>("");
  const [contributorId, setContributorId] = useState<string | null>(null);
  const [pulse, setPulse] = useState(false);
  const [othersHere, setOthersHere] = useState(0);
  const fingerprintRef = useRef<string>("");
  const heartbeat = useRef<ReturnType<typeof setInterval> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    try {
      setAuthorName(localStorage.getItem(NAME_KEY) || "");
      setContributorId(localStorage.getItem(CONTRIBUTOR_KEY));
    } catch { /* ignore */ }
    fingerprintRef.current = ensureFingerprint();
  }, []);

  // Heartbeat + presence poll — every 30s the viewer says "I'm here" and
  // reads how many others are too. Cleans up on unmount / entity change.
  useEffect(() => {
    let cancelled = false;
    const base = getApiBase();
    const fp = fingerprintRef.current || ensureFingerprint();
    fingerprintRef.current = fp;

    async function tick() {
      try {
        const res = await fetch(
          `${base}/api/presence/${entityType}/${encodeURIComponent(entityId)}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ fingerprint: fp }),
          },
        );
        if (!res.ok || cancelled) return;
        // Read an "others" count — the service subtracts myself
        const cnt = await fetch(
          `${base}/api/presence/${entityType}/${encodeURIComponent(entityId)}?fingerprint=${encodeURIComponent(fp)}`,
        );
        if (!cnt.ok || cancelled) return;
        const data = await cnt.json();
        if (!cancelled) setOthersHere(Math.max(0, data.others || 0));
      } catch {
        /* transient */
      }
    }
    tick();
    heartbeat.current = setInterval(tick, 30_000);
    function onVisible() {
      if (document.visibilityState === "visible") tick();
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      if (heartbeat.current) clearInterval(heartbeat.current);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [entityType, entityId]);

  async function loadMeeting() {
    try {
      const base = getApiBase();
      const cid = contributorId ? `?contributor_id=${encodeURIComponent(contributorId)}` : "";
      const res = await fetch(`${base}/api/meeting/${entityType}/${entityId}${cid}`);
      if (res.ok) setMeeting(await res.json());
    } catch { /* transient */ }
  }

  useEffect(() => {
    loadMeeting();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityType, entityId, contributorId]);

  function triggerPulse() {
    setPulse(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setPulse(false), 1200);
  }

  async function react(emoji: string) {
    const name = authorName.trim() || "friend";
    try {
      const base = getApiBase();
      await fetch(`${base}/api/reactions/${entityType}/${entityId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ author_name: name, emoji, locale, author_id: contributorId }),
      });
      triggerPulse();
      loadMeeting();
    } catch { /* transient */ }
  }

  const pulseLabel =
    meeting?.shared.pulse === "resonant"
      ? strings.resonant
      : meeting?.shared.pulse === "familiar"
      ? strings.familiar
      : meeting?.shared.pulse === "quiet"
      ? strings.quiet
      : strings.firstMeeting;

  return (
    <main className="min-h-[100svh] flex flex-col bg-stone-950 text-stone-100">
      {/* Top vitality strip */}
      <header className="flex items-center justify-between gap-4 px-5 pt-5 pb-3">
        <VitalityPulse
          label={strings.viewerPulse}
          value={meeting?.viewer.vitality ?? 0}
          pulse={pulse}
          tint="teal"
        />
        <div className="text-center text-xs uppercase tracking-widest text-stone-500 flex flex-col items-center gap-0.5">
          <span>{pulseLabel}</span>
          {othersHere > 0 && (
            <span
              className="text-[10px] normal-case tracking-normal text-teal-300/90"
              aria-live="polite"
            >
              {othersHere === 1
                ? (strings.othersHereOne || "1 other here")
                : (strings.othersHereMany || `${othersHere} others here`).replace(
                    "{count}",
                    String(othersHere),
                  )}
            </span>
          )}
        </div>
        <VitalityPulse
          label={strings.contentPulse}
          value={meeting?.content.vitality ?? 0}
          pulse={pulse}
          tint="amber"
        />
      </header>

      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center px-6 py-6 text-center">
        {imageUrl && (
          // Plain <img> so the meeting screen works without next/image config
          // for any image source; size-cover keeps it responsive.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt={title}
            className="w-48 h-48 md:w-64 md:h-64 object-cover rounded-2xl mb-6 shadow-2xl"
          />
        )}
        <h1 className="text-3xl md:text-4xl font-light tracking-tight mb-3">{title}</h1>
        {description && (
          <p className="text-base md:text-lg text-stone-300 max-w-xl w-full leading-relaxed break-words whitespace-normal px-1">{description}</p>
        )}
      </section>

      {/* Bottom gesture row */}
      <footer className="px-5 pb-6 pt-4 border-t border-stone-800/60">
        <div className="flex items-center justify-around gap-4 max-w-md mx-auto">
          <GestureButton emoji="➡️" label={strings.dismiss} onClick={() => react("➡️")} tint="stone" />
          <GestureButton emoji="💛" label={strings.offer} onClick={() => react("💛")} tint="amber" large />
          <GestureButton emoji="🔥" label={strings.amplify} onClick={() => react("🔥")} tint="rose" />
        </div>

        {meeting && !meeting.viewer.is_contributor && meeting.viewer.reactions_given > 0 && (
          <p className="mt-4 text-center text-xs text-teal-200/80">
            {strings.inviteHint}{" "}
            <Link href="/vision/join" className="underline text-teal-300">
              →
            </Link>
          </p>
        )}
      </footer>
    </main>
  );
}

function VitalityPulse({
  label,
  value,
  pulse,
  tint,
}: {
  label: string;
  value: number;
  pulse: boolean;
  tint: "teal" | "amber";
}) {
  const colour =
    tint === "teal"
      ? "text-teal-300 bg-teal-500/10 ring-teal-400/40"
      : "text-amber-300 bg-amber-500/10 ring-amber-400/40";
  return (
    <div className="flex flex-col items-center gap-1">
      <div
        className={`relative flex items-center justify-center rounded-full h-14 w-14 ring-2 ${colour} ${pulse ? "animate-pulse" : ""}`}
      >
        <span className="text-lg font-light tabular-nums">{value}</span>
      </div>
      <span className="text-[10px] uppercase tracking-widest text-stone-500">{label}</span>
    </div>
  );
}

function GestureButton({
  emoji,
  label,
  onClick,
  tint,
  large = false,
}: {
  emoji: string;
  label: string;
  onClick: () => void;
  tint: "amber" | "rose" | "stone";
  large?: boolean;
}) {
  const colour =
    tint === "amber"
      ? "bg-amber-700/30 hover:bg-amber-600/40 ring-amber-500/50 text-amber-100"
      : tint === "rose"
      ? "bg-rose-800/30 hover:bg-rose-700/40 ring-rose-500/50 text-rose-100"
      : "bg-stone-800/40 hover:bg-stone-700/50 ring-stone-500/40 text-stone-200";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex flex-col items-center gap-1 ${large ? "h-20 w-20 text-3xl" : "h-16 w-16 text-2xl"} rounded-full ring-1 active:scale-95 transition-transform ${colour}`}
      aria-label={label}
    >
      <span>{emoji}</span>
    </button>
  );
}
