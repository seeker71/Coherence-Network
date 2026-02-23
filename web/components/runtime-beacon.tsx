"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { getApiBase } from "@/lib/api";

type ViewTracker = {
  id: string;
  route: string;
  startedAt: number;
  apiCallCount: number;
  apiEndpoints: Set<string>;
  apiRuntimeMs: number;
  apiRuntimeCostEstimate: number;
  activeApiRequests: number;
  idleTimer: number | null;
  hardTimeoutTimer: number | null;
  finalized: boolean;
};

const VIEW_IDLE_SETTLE_MS = 700;
const VIEW_MAX_WAIT_MS = 20000;

let currentView: ViewTracker | null = null;
let fetchPatched = false;
let currentApiHost = "";
let initialViewMeasured = false;

function randomViewId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const seed = Math.random().toString(16).slice(2);
  return `view_${Date.now().toString(36)}_${seed}`;
}

function parseUrl(input: RequestInfo | URL): URL | null {
  try {
    if (input instanceof URL) return input;
    if (typeof input === "string") return new URL(input, window.location.origin);
    if (typeof Request !== "undefined" && input instanceof Request) {
      return new URL(input.url, window.location.origin);
    }
    return null;
  } catch {
    return null;
  }
}

function normalizeEndpoint(url: URL): string {
  const path = (url.pathname || "/").trim();
  return path.startsWith("/") ? path : `/${path}`;
}

function shouldTrackApiRequest(url: URL): boolean {
  const endpoint = normalizeEndpoint(url);
  if (!endpoint.startsWith("/api")) return false;
  if (endpoint === "/api/runtime-beacon") return false;
  if (url.host === window.location.host) return true;
  if (currentApiHost && url.host === currentApiHost) return true;
  return false;
}

function round(value: number, digits: number): number {
  const scale = 10 ** digits;
  return Math.round(value * scale) / scale;
}

function emitRuntime(
  endpoint: string,
  runtimeMs: number,
  metadata: Record<string, string | number | boolean>,
) {
  const payload = {
    source: "web",
    endpoint,
    method: "GET",
    status_code: 200,
    runtime_ms: Math.max(0.1, round(runtimeMs, 4)),
    metadata,
  };
  const body = JSON.stringify(payload);
  if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
    const blob = new Blob([body], { type: "application/json" });
    navigator.sendBeacon("/api/runtime-beacon", blob);
    return;
  }
  void fetch("/api/runtime-beacon", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  });
}

function clearViewTimers(view: ViewTracker): void {
  if (view.idleTimer !== null) {
    window.clearTimeout(view.idleTimer);
    view.idleTimer = null;
  }
  if (view.hardTimeoutTimer !== null) {
    window.clearTimeout(view.hardTimeoutTimer);
    view.hardTimeoutTimer = null;
  }
}

function finalizeView(view: ViewTracker, reason: string): void {
  if (view.finalized) return;
  view.finalized = true;
  clearViewTimers(view);
  const runtimeMs = performance.now() - view.startedAt;
  emitRuntime(view.route, runtimeMs, {
    tracking_kind: "web_view_complete",
    page_view_id: view.id,
    page_route: view.route,
    completion_reason: reason,
    api_call_count: view.apiCallCount,
    api_endpoint_count: view.apiEndpoints.size,
    api_runtime_ms: round(view.apiRuntimeMs, 4),
    api_runtime_cost_estimate: round(view.apiRuntimeCostEstimate, 8),
  });
  if (currentView?.id === view.id) {
    currentView = null;
  }
}

function scheduleIdleFinalize(view: ViewTracker): void {
  if (view.finalized) return;
  if (view.idleTimer !== null) {
    window.clearTimeout(view.idleTimer);
  }
  view.idleTimer = window.setTimeout(() => {
    if (view.finalized || currentView?.id !== view.id) return;
    if (document.readyState !== "complete" || view.activeApiRequests > 0) {
      scheduleIdleFinalize(view);
      return;
    }
    finalizeView(view, "idle");
  }, VIEW_IDLE_SETTLE_MS);
}

function patchFetchOnce(): void {
  if (fetchPatched || typeof window === "undefined" || typeof window.fetch !== "function") {
    return;
  }
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const parsedUrl = parseUrl(input);
    const view = currentView;
    const isApiCall = Boolean(parsedUrl && shouldTrackApiRequest(parsedUrl));

    let nextInit = init;
    if (isApiCall && view) {
      const headers = new Headers();
      if (typeof Request !== "undefined" && input instanceof Request) {
        input.headers.forEach((value, key) => headers.set(key, value));
      }
      if (init?.headers) {
        new Headers(init.headers).forEach((value, key) => headers.set(key, value));
      }
      headers.set("x-page-view-id", view.id);
      headers.set("x-page-route", view.route);
      nextInit = { ...init, headers };
    }

    if (!isApiCall || !view) {
      return nativeFetch(input, nextInit);
    }

    const endpoint = parsedUrl ? normalizeEndpoint(parsedUrl) : "unknown";
    const startedAt = performance.now();
    view.apiCallCount += 1;
    view.apiEndpoints.add(endpoint);
    view.activeApiRequests += 1;

    try {
      const response = await nativeFetch(input, nextInit);
      const runtimeHeader = Number.parseFloat(response.headers.get("x-coherence-runtime-ms") || "");
      const costHeader = Number.parseFloat(response.headers.get("x-coherence-runtime-cost-estimate") || "");
      const fallbackRuntime = Math.max(0, performance.now() - startedAt);
      view.apiRuntimeMs += Number.isFinite(runtimeHeader) ? runtimeHeader : fallbackRuntime;
      if (Number.isFinite(costHeader)) {
        view.apiRuntimeCostEstimate += costHeader;
      }
      return response;
    } catch (error) {
      view.apiRuntimeMs += Math.max(0, performance.now() - startedAt);
      throw error;
    } finally {
      view.activeApiRequests = Math.max(0, view.activeApiRequests - 1);
      scheduleIdleFinalize(view);
    }
  };
  fetchPatched = true;
}

export default function RuntimeBeacon() {
  const pathname = usePathname();
  const parsedSampleRate = Number.parseFloat(process.env.NEXT_PUBLIC_RUNTIME_BEACON_SAMPLE_RATE || "");
  const sampleRate = Number.isFinite(parsedSampleRate) ? Math.min(1, Math.max(0, parsedSampleRate)) : 0.2;

  useEffect(() => {
    if (!pathname) return;

    try {
      currentApiHost = new URL(getApiBase()).host;
    } catch {
      currentApiHost = "";
    }

    patchFetchOnce();

    if (currentView && !currentView.finalized) {
      finalizeView(currentView, "route_change");
    }

    if (Math.random() > sampleRate) {
      currentView = null;
      return;
    }

    const view: ViewTracker = {
      id: randomViewId(),
      route: pathname,
      startedAt: (() => {
        if (initialViewMeasured) return performance.now();
        const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
        if (nav && Number.isFinite(nav.startTime)) {
          return Math.max(0, nav.startTime);
        }
        return performance.now();
      })(),
      apiCallCount: 0,
      apiEndpoints: new Set<string>(),
      apiRuntimeMs: 0,
      apiRuntimeCostEstimate: 0,
      activeApiRequests: 0,
      idleTimer: null,
      hardTimeoutTimer: null,
      finalized: false,
    };
    currentView = view;
    if (!initialViewMeasured) {
      initialViewMeasured = true;
    }
    view.hardTimeoutTimer = window.setTimeout(() => {
      if (!view.finalized) {
        finalizeView(view, "max_wait");
      }
    }, VIEW_MAX_WAIT_MS);
    scheduleIdleFinalize(view);

    return () => {
      if (currentView?.id === view.id && !view.finalized) {
        finalizeView(view, "unmount");
      }
    };
  }, [pathname, sampleRate]);

  return null;
}
