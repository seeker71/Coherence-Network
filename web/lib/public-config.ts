import type { PublicWebConfig } from "./app-config";

declare global {
  interface Window {
    __COHERENCE_PUBLIC_CONFIG__?: PublicWebConfig;
  }
}

export const PUBLIC_WEB_DEFAULTS: PublicWebConfig = {
  apiBaseUrl: "https://api.coherencycoin.com",
  localApiBaseUrl: "http://localhost:8000",
  liveUpdates: {
    pollMs: 120000,
    routerRefreshEveryTicks: 8,
    global: false,
    activeRoutePrefixes: ["/tasks", "/remote-ops", "/api-health", "/gates"],
    routerRefreshSkipPrefixes: ["/automation"],
  },
  runtimeBeacon: {
    sampleRate: 0.2,
    upstreamTimeoutMs: 5000,
    failureThreshold: 3,
    cooldownMs: 30000,
  },
  healthProxy: {
    failureThreshold: 2,
    cooldownMs: 30000,
  },
  deployedSha: "unknown",
  updatedAt: "unknown",
};

export function readPublicWebConfig(): PublicWebConfig {
  if (typeof window === "undefined") {
    return PUBLIC_WEB_DEFAULTS;
  }
  return window.__COHERENCE_PUBLIC_CONFIG__ || PUBLIC_WEB_DEFAULTS;
}
