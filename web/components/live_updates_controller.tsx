"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { LIVE_REFRESH_EVENT } from "@/lib/live_refresh";

const DEFAULT_POLL_MS = 120000;
const MIN_POLL_MS = 30000;
const VERSION_CHECK_INTERVAL_TICKS = 6;
const DEFAULT_ROUTER_REFRESH_EVERY_TICKS = 8;
const LIVE_UPDATES_STORAGE_KEY = "coherence_live_updates_enabled";
const ROUTER_REFRESH_SKIP_PREFIXES = ["/automation"];
const DEFAULT_ACTIVE_ROUTE_PREFIXES = ["/tasks", "/remote-ops", "/api-health", "/gates"];

type WebVersionResponse = {
  web?: {
    updated_at?: string;
  };
};

type ChangeTokenResponse = {
  token?: string;
};

export default function LiveUpdatesController() {
  const router = useRouter();
  const pathname = usePathname();
  const [enabled, setEnabled] = useState(true);
  const [lastRefreshAt, setLastRefreshAt] = useState<string>("never");
  const webVersionRef = useRef<string>("");
  const changeTokenRef = useRef<string>("");
  const tickRef = useRef<number>(0);
  const parsedPollMs = Number.parseInt(process.env.NEXT_PUBLIC_LIVE_UPDATES_POLL_MS ?? "", 10);
  const pollMs = Number.isFinite(parsedPollMs) ? Math.max(MIN_POLL_MS, parsedPollMs) : DEFAULT_POLL_MS;
  const parsedRefreshEveryTicks = Number.parseInt(process.env.NEXT_PUBLIC_LIVE_UPDATES_ROUTER_REFRESH_EVERY_TICKS ?? "", 10);
  const routerRefreshEveryTicks = Number.isFinite(parsedRefreshEveryTicks)
    ? Math.max(1, parsedRefreshEveryTicks)
    : DEFAULT_ROUTER_REFRESH_EVERY_TICKS;
  const pollEverywhere = process.env.NEXT_PUBLIC_LIVE_UPDATES_GLOBAL === "1";
  const isEligiblePath =
    pollEverywhere ||
    DEFAULT_ACTIVE_ROUTE_PREFIXES.some((prefix) =>
      (pathname || "/").startsWith(prefix),
    );
  const skipRouterRefresh = ROUTER_REFRESH_SKIP_PREFIXES.some((prefix) =>
    (pathname || "/").startsWith(prefix)
  );

  useEffect(() => {
    const stored = window.localStorage.getItem(LIVE_UPDATES_STORAGE_KEY);
    if (stored === "0") {
      setEnabled(false);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(LIVE_UPDATES_STORAGE_KEY, enabled ? "1" : "0");
  }, [enabled]);

  useEffect(() => {
    if (!enabled || !isEligiblePath) return;

    let cancelled = false;

    const checkDataChange = async (): Promise<boolean> => {
      try {
        const res = await fetch("/api/runtime/change-token", { cache: "no-store" });
        if (!res.ok) return false;
        const json = (await res.json()) as ChangeTokenResponse;
        const nextToken = json.token ?? "";
        if (!nextToken) return false;
        if (!changeTokenRef.current) {
          changeTokenRef.current = nextToken;
          return false;
        }
        if (changeTokenRef.current === nextToken) {
          return false;
        }
        changeTokenRef.current = nextToken;
        return true;
      } catch {
        return false;
      }
    };

    const checkWebVersion = async () => {
      try {
        const res = await fetch("/api/web-version", { cache: "no-store" });
        if (!res.ok) return;
        const json = (await res.json()) as WebVersionResponse;
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

    const runTick = async () => {
      if (cancelled || document.visibilityState !== "visible") return;

      tickRef.current += 1;
      const changed = await checkDataChange();
      if (changed) {
        const now = new Date().toISOString();
        setLastRefreshAt(now);
        window.dispatchEvent(new Event(LIVE_REFRESH_EVENT));
        if (!skipRouterRefresh && tickRef.current % routerRefreshEveryTicks === 0) {
          router.refresh();
        }
      }

      if (tickRef.current % VERSION_CHECK_INTERVAL_TICKS === 0) {
        await checkWebVersion();
      }
    };

    const handleFocus = () => {
      void runTick();
    };
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        void runTick();
      }
    };

    void checkWebVersion();
    void runTick();

    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);

    const timer = window.setInterval(() => {
      void runTick();
    }, pollMs);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [enabled, isEligiblePath, pollMs, router, routerRefreshEveryTicks, skipRouterRefresh]);

  return (
    <div className="border-b bg-muted/20">
      <div className="mx-auto max-w-6xl px-4 md:px-8 py-1.5 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <p>
          Live updates <strong>{enabled && isEligiblePath ? "ON" : "OFF"}</strong> | path <code>{pathname || "/"}</code> | last refresh{" "}
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
