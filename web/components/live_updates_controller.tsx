"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { LIVE_REFRESH_EVENT } from "@/lib/live_refresh";
import { readPublicWebConfig } from "@/lib/public-config";
import { useT } from "@/components/MessagesProvider";

const DEFAULT_POLL_MS = 120000;
const MIN_POLL_MS = 30000;
const VERSION_CHECK_INTERVAL_TICKS = 6;
const DEFAULT_ROUTER_REFRESH_EVERY_TICKS = 8;
const LIVE_UPDATES_STORAGE_KEY = "coherence_live_updates_enabled";

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
  const t = useT();
  const [enabled, setEnabled] = useState(true);
  const [lastRefreshAt, setLastRefreshAt] = useState<string>("never");
  const webVersionRef = useRef<string>("");
  const changeTokenRef = useRef<string>("");
  const tickRef = useRef<number>(0);
  const webConfig = readPublicWebConfig();
  const pollMs = Math.max(MIN_POLL_MS, webConfig.liveUpdates.pollMs || DEFAULT_POLL_MS);
  const routerRefreshEveryTicks = Math.max(
    1,
    webConfig.liveUpdates.routerRefreshEveryTicks || DEFAULT_ROUTER_REFRESH_EVERY_TICKS,
  );
  const pollEverywhere = Boolean(webConfig.liveUpdates.global);
  const isEligiblePath =
    pollEverywhere ||
    webConfig.liveUpdates.activeRoutePrefixes.some((prefix) =>
      (pathname || "/").startsWith(prefix),
    );
  const skipRouterRefresh = webConfig.liveUpdates.routerRefreshSkipPrefixes.some((prefix) =>
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

  const statusLabel = enabled
    ? (isEligiblePath ? t("autoRefresh.statusOn") : t("autoRefresh.statusAvailable"))
    : t("autoRefresh.statusOff");

  return (
    // Hidden on mobile — it's developer-facing chrome, not the warmest
    // thing a first-time visitor from a phone should see. Desktop keeps
    // the affordance for contributors who want to pause live refresh.
    <div className="hidden md:block pointer-events-none fixed bottom-4 right-4 z-40">
      <details className="group pointer-events-auto">
        <summary className="list-none cursor-pointer rounded-full border border-border/70 bg-card/90 px-3 py-1.5 text-xs text-muted-foreground shadow-sm backdrop-blur">
          {t("autoRefresh.label")} <span className="font-semibold text-foreground">{statusLabel}</span>
        </summary>
        <div className="mt-2 w-64 rounded-2xl border border-border/70 bg-card/95 p-3 text-xs shadow-lg backdrop-blur">
          <p className="text-muted-foreground">
            {t("autoRefresh.body")}
          </p>
          <p className="mt-2 text-muted-foreground">
            {t("autoRefresh.pathLabel")} <code>{pathname || "/"}</code>
          </p>
          <p className="text-muted-foreground">
            {t("autoRefresh.lastRefresh")}{" "}
            <code>{lastRefreshAt === "never" ? t("autoRefresh.never") : new Date(lastRefreshAt).toLocaleTimeString()}</code>
          </p>
          <button
            type="button"
            onClick={() => setEnabled((prev) => !prev)}
            className="mt-3 w-full rounded-md border px-2 py-1.5 text-foreground hover:bg-accent"
          >
            {enabled ? t("autoRefresh.pauseNow") : t("autoRefresh.resume")}
          </button>
        </div>
      </details>
    </div>
  );
}
