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
    sayHeading?: string;
    sayNamePlaceholder?: string;
    sayPlaceholder?: string;
    saySubmit?: string;
    saySending?: string;
    saySent?: string;
    sayDismiss?: string;
    /** Three warm one-tap phrases a visitor can offer without typing.
     *  Each phrase, when tapped, fills the voice body and enables the
     *  submit button — so "offering" is as easy as tapping an emoji. */
    quickPhrase1?: string;
    quickPhrase2?: string;
    quickPhrase3?: string;
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
  const [sayOpen, setSayOpen] = useState(false);
  const [sayText, setSayText] = useState("");
  const [sayingName, setSayingName] = useState("");
  const [sayState, setSayState] = useState<"idle" | "sending" | "sent">("idle");
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
      // After the first warm gesture, invite a sentence. The panel opens
      // only if the viewer hasn't already sent a voice this session.
      if (emoji !== "➡️" && sayState !== "sent") {
        setSayOpen(true);
        setSayingName(authorName);
      }
    } catch { /* transient */ }
  }

  async function saySomething() {
    const name = sayingName.trim();
    const body = sayText.trim();
    if (!name || !body) return;
    setSayState("sending");
    try {
      // Store the name in localStorage for future visits
      try {
        localStorage.setItem(NAME_KEY, name);
      } catch {
        /* ignore */
      }
      setAuthorName(name);
      const base = getApiBase();
      const fingerprint = ensureFingerprint();
      // For concepts, store as a voice (richer shape + ripens into proposals
      // later). For any other entity, store as a reaction with a comment.
      //
      // Auto-graduation: if the viewer doesn't have a contributor_id yet,
      // the server mints one keyed by her name + device fingerprint and
      // returns it in the voice payload. We persist it to localStorage so
      // every subsequent surface (reactions, profile, feed) attributes
      // her correctly. No signup screen, no private key — contribution
      // IS the registration.
      if (entityType === "concept") {
        const res = await fetch(`${base}/api/concepts/${encodeURIComponent(entityId)}/voices`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            author_name: name,
            body,
            locale,
            author_id: contributorId,
            device_fingerprint: fingerprint,
          }),
        });
        try {
          if (res.ok) {
            const voice = await res.json();
            const newId = voice?.author_id;
            if (newId && !contributorId) {
              localStorage.setItem(CONTRIBUTOR_KEY, newId);
              setContributorId(newId);
            }
          }
        } catch { /* non-critical */ }
      } else {
        await fetch(`${base}/api/reactions/${entityType}/${entityId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            author_name: name,
            comment: body,
            locale,
            author_id: contributorId,
          }),
        });
      }
      setSayState("sent");
      setSayText("");
      triggerPulse();
      loadMeeting();
      setTimeout(() => {
        setSayOpen(false);
        setSayState("idle");
      }, 2400);
    } catch {
      setSayState("idle");
    }
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

      {/* Inline voice/comment — opens after a warm reaction.
          For concepts, stores as a voice; elsewhere as a commented
          reaction. Same gesture surface, different shape underneath. */}
      {sayOpen && (
        <section className="px-5 pb-4 border-t border-stone-800/60 bg-stone-900/40">
          <div className="max-w-md mx-auto pt-4 space-y-2">
            {sayState === "sent" ? (
              <p className="text-sm text-emerald-300 text-center py-3">
                {strings.saySent || "Thank you — your voice is here."}
              </p>
            ) : (
              <>
                <label className="text-xs uppercase tracking-widest text-amber-300/90">
                  {strings.sayHeading || "Say something?"}
                </label>
                <input
                  type="text"
                  value={sayingName}
                  onChange={(e) => setSayingName(e.target.value)}
                  placeholder={strings.sayNamePlaceholder || "Your name"}
                  className="w-full rounded-md bg-stone-950/60 border border-stone-800 px-3 py-2 text-sm text-stone-200 placeholder-stone-600 focus:outline-none focus:border-amber-600/60"
                  maxLength={80}
                />
                <textarea
                  value={sayText}
                  onChange={(e) => setSayText(e.target.value)}
                  placeholder={strings.sayPlaceholder || "Two sentences is enough."}
                  rows={2}
                  maxLength={1000}
                  className="w-full rounded-md bg-stone-950/60 border border-stone-800 px-3 py-2 text-sm text-stone-200 placeholder-stone-600 focus:outline-none focus:border-amber-600/60 resize-y"
                  autoFocus
                />
                {/* One-tap phrases — for when words are hard or time is
                    short. Tapping fills the textarea and the visitor can
                    submit immediately, or keep typing to deepen it. */}
                {(strings.quickPhrase1 || strings.quickPhrase2 || strings.quickPhrase3) && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {[strings.quickPhrase1, strings.quickPhrase2, strings.quickPhrase3]
                      .filter((p): p is string => !!p && p.length > 0)
                      .map((phrase) => (
                        <button
                          key={phrase}
                          type="button"
                          onClick={() => setSayText(phrase)}
                          className="rounded-full border border-amber-700/40 bg-amber-950/20 hover:bg-amber-900/30 text-amber-100/90 text-xs px-3 py-1 transition-colors"
                        >
                          {phrase}
                        </button>
                      ))}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={saySomething}
                    disabled={
                      sayState === "sending" ||
                      !sayingName.trim() ||
                      !sayText.trim()
                    }
                    className="rounded-full bg-amber-700/80 hover:bg-amber-600/90 disabled:bg-stone-800 disabled:text-stone-600 text-stone-950 px-4 py-1.5 text-sm font-medium transition-colors"
                  >
                    {sayState === "sending"
                      ? strings.saySending || "Sending…"
                      : strings.saySubmit || "Offer this"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSayOpen(false);
                      setSayText("");
                    }}
                    className="text-xs text-stone-500 hover:text-stone-300"
                  >
                    {strings.sayDismiss || "later"}
                  </button>
                </div>
              </>
            )}
          </div>
        </section>
      )}

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
