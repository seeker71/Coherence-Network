"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { ensureFingerprint, readIdentity } from "@/lib/identity";

const SESSION_KEY = "cc-anonymous-meeting-session";
const FLUSH_INTERVAL_MS = 30000;

function ensureSessionKey(): string {
  try {
    const existing = sessionStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const fresh = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    sessionStorage.setItem(SESSION_KEY, fresh);
    return fresh;
  } catch {
    return `session-${Math.random().toString(36).slice(2, 10)}`;
  }
}

export function AnonymousMeetingTrace() {
  const pathname = usePathname() || "/";
  const startedAtRef = useRef<number>(Date.now());
  const lastPathRef = useRef<string>(pathname);

  useEffect(() => {
    startedAtRef.current = Date.now();
    lastPathRef.current = pathname;

    const flush = (keepalive = false) => {
      const duration_ms = Math.max(0, Date.now() - startedAtRef.current);
      const { contributorId } = readIdentity();
      const payload: Record<string, string | number> = {
        visitor_key: ensureFingerprint(),
        session_key: ensureSessionKey(),
        surface: lastPathRef.current,
        duration_ms,
      };
      if (contributorId) payload.contributor_id = contributorId;

      try {
        void fetch(`${getApiBase()}/api/meetings/anonymous-traces`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          keepalive,
        });
      } catch {
        /* meeting traces are quiet; a missed breath should not disturb the surface */
      }
    };

    const initial = window.setTimeout(() => flush(), 1500);
    const interval = window.setInterval(() => flush(), FLUSH_INTERVAL_MS);
    const onVisibility = () => {
      if (document.visibilityState === "hidden") flush(true);
    };
    const onBeforeUnload = () => flush(true);

    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("beforeunload", onBeforeUnload);

    return () => {
      window.clearTimeout(initial);
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("beforeunload", onBeforeUnload);
      flush(true);
    };
  }, [pathname]);

  return null;
}
