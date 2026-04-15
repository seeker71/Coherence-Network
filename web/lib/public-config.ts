import type { PublicWebConfig } from "./app-config";

declare global {
  interface Window {
    __COHERENCE_PUBLIC_CONFIG__?: PublicWebConfig;
  }
}

export const PUBLIC_WEB_DEFAULTS: PublicWebConfig = {
  apiBaseUrl: "https://api.coherencycoin.com",
  localApiBaseUrl: "http://localhost:8000",
  webUiBaseUrl: "https://coherencycoin.com",
  pulseBaseUrl: "https://pulse.coherencycoin.com",
  repoUrl: "https://github.com/seeker71/Coherence-Network/blob/main",
  fetchDefaults: {
    timeoutMs: 7000,
    retryAttempts: 3,
    healthTimeoutMs: 10000,
  },
  pagination: {
    defaultLimit: 50,
    maxLimit: 500,
  },
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
    // On the server, let env vars (NEXT_PUBLIC_API_URL, API_URL,
    // NEXT_PUBLIC_BASE_URL, NEXT_PUBLIC_REPO_URL) override the built-in
    // defaults. This lets `.env.local` and deploy env vars set the URLs
    // without having to touch code or config files. Without this, the
    // server always returns PUBLIC_WEB_DEFAULTS (which point at prod) and
    // every dev preview hammers production even when a local API is up.
    const envApi = process.env.NEXT_PUBLIC_API_URL;
    const envLocalApi = process.env.API_URL;
    const envWebUi = process.env.NEXT_PUBLIC_BASE_URL;
    const envRepo = process.env.NEXT_PUBLIC_REPO_URL;
    return {
      ...PUBLIC_WEB_DEFAULTS,
      apiBaseUrl: envApi || PUBLIC_WEB_DEFAULTS.apiBaseUrl,
      localApiBaseUrl: envLocalApi || envApi || PUBLIC_WEB_DEFAULTS.localApiBaseUrl,
      webUiBaseUrl: envWebUi || PUBLIC_WEB_DEFAULTS.webUiBaseUrl,
      repoUrl: envRepo || PUBLIC_WEB_DEFAULTS.repoUrl,
    };
  }
  return window.__COHERENCE_PUBLIC_CONFIG__ || PUBLIC_WEB_DEFAULTS;
}
