"use client";

/**
 * ExplorePager — walk through a queue of entities, one full-screen
 * meeting at a time. Reuses MeetingSurface as the inner view; adds
 * queue fetching, swipe/keyboard navigation, and a lazy refetch so
 * the walk never hits a wall.
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { getApiBase } from "@/lib/api";
import { MeetingSurface } from "@/components/MeetingSurface";

const CONTRIBUTOR_KEY = "cc-contributor-id";
const SESSION_KEY = "cc-explore-session-key";

interface QueueItem {
  entity_type: string;
  entity_id: string;
  title: string;
  description: string;
  image_url: string | null;
}

interface Props {
  entityType: string;
  strings: {
    empty: string;
    exploreMore: string;
    loading: string;
    walkDone: string;
    restart: string;
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
  };
}

export function ExplorePager({ entityType, strings }: Props) {
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [done, setDone] = useState(false);
  const contributorRef = useRef<string | null>(null);
  const sessionRef = useRef<string>("");

  useEffect(() => {
    try {
      contributorRef.current = localStorage.getItem(CONTRIBUTOR_KEY);
      let sk = localStorage.getItem(SESSION_KEY);
      if (!sk) {
        sk = Math.random().toString(36).slice(2);
        localStorage.setItem(SESSION_KEY, sk);
      }
      sessionRef.current = sk;
    } catch {
      sessionRef.current = Math.random().toString(36).slice(2);
    }
  }, []);

  const fetchQueue = useCallback(async () => {
    try {
      setLoading(true);
      const base = getApiBase();
      const params = new URLSearchParams({ limit: "12" });
      if (contributorRef.current) params.set("contributor_id", contributorRef.current);
      if (sessionRef.current) params.set("session_key", sessionRef.current);
      const res = await fetch(`${base}/api/explore/${entityType}?${params}`);
      if (!res.ok) {
        setQueue([]);
        return;
      }
      const data = await res.json();
      setQueue(data.queue || []);
      setIndex(0);
      setDone(false);
    } catch {
      setQueue([]);
    } finally {
      setLoading(false);
    }
  }, [entityType]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const advance = useCallback(() => {
    setIndex((i) => {
      const next = i + 1;
      if (next >= queue.length) {
        setDone(true);
        return i;
      }
      return next;
    });
  }, [queue.length]);

  // Keyboard nav: space, right-arrow, down-arrow all advance.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowRight" || e.key === "ArrowDown" || e.key === " ") {
        e.preventDefault();
        advance();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [advance]);

  if (loading && queue.length === 0) {
    return (
      <main className="min-h-[100svh] flex items-center justify-center bg-stone-950 text-stone-400 text-sm">
        {strings.loading}
      </main>
    );
  }

  if (queue.length === 0) {
    return (
      <main className="min-h-[100svh] flex flex-col items-center justify-center gap-4 bg-stone-950 text-stone-300 px-6 text-center">
        <p>{strings.empty}</p>
        <Link
          href={`/${entityType === "concept" ? "vision" : entityType === "idea" ? "ideas" : "contributors"}`}
          className="rounded-md bg-amber-700/80 hover:bg-amber-600/90 text-stone-950 px-4 py-2 text-sm font-medium"
        >
          {strings.exploreMore}
        </Link>
      </main>
    );
  }

  if (done) {
    return (
      <main className="min-h-[100svh] flex flex-col items-center justify-center gap-4 bg-stone-950 text-stone-300 px-6 text-center">
        <p className="text-lg">{strings.walkDone}</p>
        <button
          type="button"
          onClick={fetchQueue}
          className="rounded-md bg-amber-700/80 hover:bg-amber-600/90 text-stone-950 px-4 py-2 text-sm font-medium"
        >
          {strings.restart}
        </button>
        <Link
          href="/feed"
          className="text-xs text-stone-500 hover:text-amber-300/90"
        >
          {strings.exploreMore}
        </Link>
      </main>
    );
  }

  const item = queue[index];

  return (
    <div className="relative">
      <MeetingSurface
        key={`${item.entity_type}-${item.entity_id}`}
        entityType={item.entity_type}
        entityId={item.entity_id}
        title={item.title}
        description={item.description}
        imageUrl={item.image_url}
        strings={{
          viewerPulse: strings.viewerPulse,
          contentPulse: strings.contentPulse,
          firstMeeting: strings.firstMeeting,
          familiar: strings.familiar,
          resonant: strings.resonant,
          quiet: strings.quiet,
          offer: strings.offer,
          dismiss: strings.dismiss,
          amplify: strings.amplify,
          inviteHint: strings.inviteHint,
          othersHereOne: strings.othersHereOne,
          othersHereMany: strings.othersHereMany,
          sayHeading: strings.sayHeading,
          sayNamePlaceholder: strings.sayNamePlaceholder,
          sayPlaceholder: strings.sayPlaceholder,
          saySubmit: strings.saySubmit,
          saySending: strings.saySending,
          saySent: strings.saySent,
          sayDismiss: strings.sayDismiss,
        }}
      />

      {/* Floating "next" affordance — also triggered by keyboard / react */}
      <button
        type="button"
        onClick={advance}
        className="fixed right-4 top-1/2 -translate-y-1/2 h-14 w-14 rounded-full bg-stone-900/70 backdrop-blur hover:bg-amber-900/60 active:scale-95 ring-1 ring-stone-700 text-2xl text-stone-200 shadow-xl"
        aria-label="next"
      >
        →
      </button>

      {/* Progress strip */}
      <div className="fixed top-0 left-0 right-0 h-0.5 bg-stone-800">
        <div
          className="h-full bg-amber-500/80 transition-all"
          style={{ width: `${Math.round(((index + 1) / queue.length) * 100)}%` }}
        />
      </div>

      {/* Index label */}
      <div className="fixed top-2 left-1/2 -translate-x-1/2 text-xs text-stone-500 tabular-nums">
        {index + 1} / {queue.length}
      </div>
    </div>
  );
}

