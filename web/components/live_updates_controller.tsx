"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { LIVE_REFRESH_EVENT } from "@/lib/live_refresh";

const POLL_MS = 20000;

type HealthProxyResponse = {
  web?: {
    updated_at?: string;
  };
};

export default function LiveUpdatesController() {
  const router = useRouter();
  const pathname = usePathname();
  const [enabled, setEnabled] = useState(true);
  const [lastRefreshAt, setLastRefreshAt] = useState<string>("never");
  const webVersionRef = useRef<string>("");
  const tickRef = useRef<number>(0);

  useEffect(() => {
    const stored = window.localStorage.getItem("coherence_live_updates_enabled");
    if (stored === "0") {
      setEnabled(false);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem("coherence_live_updates_enabled", enabled ? "1" : "0");
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;

    const runTick = async () => {
      if (cancelled || document.visibilityState !== "visible") return;

      tickRef.current += 1;
      const now = new Date().toISOString();
      setLastRefreshAt(now);

      window.dispatchEvent(new Event(LIVE_REFRESH_EVENT));
      router.refresh();

      if (tickRef.current % 3 !== 0) return;
      try {
        const res = await fetch("/api/health-proxy", { cache: "no-store" });
        if (!res.ok) return;
        const json = (await res.json()) as HealthProxyResponse;
        const nextVersion = json.web?.updated_at ?? "";
        if (!nextVersion) return;
        if (!webVersionRef.current) {
          webVersionRef.current = nextVersion;
          return;
        }
        if (webVersionRef.current !== nextVersion) {
          webVersionRef.current = nextVersion;
          window.location.reload();
        }
      } catch {
        // Ignore transient proxy failures; next cycle retries.
      }
    };

    const timer = window.setInterval(() => {
      void runTick();
    }, POLL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [enabled, router]);

  return (
    <div className="border-b bg-muted/20">
      <div className="mx-auto max-w-6xl px-4 md:px-8 py-1.5 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <p>
          Live updates <strong>{enabled ? "ON" : "OFF"}</strong> | path <code>{pathname || "/"}</code> | last refresh{" "}
          <code>{lastRefreshAt === "never" ? "never" : new Date(lastRefreshAt).toLocaleTimeString()}</code>
        </p>
        <button
          type="button"
          onClick={() => setEnabled((prev) => !prev)}
          className="rounded border px-2 py-1 hover:bg-accent hover:text-foreground"
        >
          {enabled ? "Pause live updates" : "Resume live updates"}
        </button>
      </div>
    </div>
  );
}
