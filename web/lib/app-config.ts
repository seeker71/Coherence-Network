import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";

export type PublicWebConfig = {
  apiBaseUrl: string;
  localApiBaseUrl: string;
  // Canonical user-facing origin (for OG/Twitter tags, share links,
  // canonical URLs). Env override: NEXT_PUBLIC_BASE_URL.
  webUiBaseUrl: string;
  // Pulse Monitor — the external witness that records the breath of the
  // network. Served from a different origin than the API (see pulse/ in the
  // repo). Env override: NEXT_PUBLIC_PULSE_URL. Empty string is allowed and
  // means "the witness is unavailable" — the /pulse page renders a muted
  // "witness is quiet" state in that case.
  pulseBaseUrl: string;
  // Public repo browse base (for spec/source file permalinks). Env
  // override: NEXT_PUBLIC_REPO_URL. Defaults to the `main` branch blob.
  repoUrl: string;
  // Shared fetch defaults for pages that don't have a specific need.
  // Individual pages may still override by passing options directly.
  fetchDefaults: {
    timeoutMs: number;
    retryAttempts: number;
    healthTimeoutMs: number;
  };
  // Default pagination shape for list pages that don't have a specific need.
  pagination: {
    defaultLimit: number;
    maxLimit: number;
  };
  liveUpdates: {
    pollMs: number;
    routerRefreshEveryTicks: number;
    global: boolean;
    activeRoutePrefixes: string[];
    routerRefreshSkipPrefixes: string[];
  };
  runtimeBeacon: {
    sampleRate: number;
    upstreamTimeoutMs: number;
    failureThreshold: number;
    cooldownMs: number;
  };
  healthProxy: {
    failureThreshold: number;
    cooldownMs: number;
  };
  deployedSha: string;
  updatedAt: string;
};

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function deepMerge(base: Record<string, unknown>, override: Record<string, unknown>): Record<string, unknown> {
  const merged: Record<string, unknown> = { ...base };
  for (const [key, value] of Object.entries(override)) {
    if (String(key).startsWith("_")) continue;
    if (isObject(merged[key]) && isObject(value)) {
      merged[key] = deepMerge(merged[key] as Record<string, unknown>, value);
      continue;
    }
    merged[key] = value;
  }
  return merged;
}

function loadJson(path: string): Record<string, unknown> {
  if (!existsSync(path)) return {};
  try {
    const parsed = JSON.parse(readFileSync(path, "utf-8"));
    return isObject(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function repoConfigPath(): string {
  const cwd = process.cwd();
  const candidates = [
    resolve(cwd, "../api/config/api.json"),
    resolve(cwd, "api/config/api.json"),
  ];
  return candidates.find((candidate) => existsSync(candidate)) || candidates[0];
}

function userConfigPath(): string {
  return join(homedir(), ".coherence-network", "config.json");
}

function defaultConfig(): Record<string, unknown> {
  return {
    agent_providers: {
      api_base_url: "https://api.coherencycoin.com",
      web_ui_base_url: "https://coherencycoin.com",
    },
    web: {
      api_base_url: "https://api.coherencycoin.com",
      local_api_base_url: "http://localhost:8000",
      web_ui_base_url: "https://coherencycoin.com",
      pulse_base_url: "https://pulse.coherencycoin.com",
      repo_url: "https://github.com/seeker71/Coherence-Network/blob/main",
      fetch_defaults: {
        timeout_ms: 7000,
        retry_attempts: 3,
        health_timeout_ms: 10000,
      },
      pagination: {
        default_limit: 50,
        max_limit: 500,
      },
      deployed_sha: "unknown",
      updated_at: "unknown",
    },
    live_updates: {
      poll_ms: 120000,
      router_refresh_every_ticks: 8,
      global: false,
      active_route_prefixes: ["/tasks", "/remote-ops", "/api-health", "/gates"],
      router_refresh_skip_prefixes: ["/automation"],
    },
    runtime_beacon: {
      sample_rate: 0.2,
      upstream_timeout_ms: 5000,
      failure_threshold: 3,
      cooldown_ms: 30000,
    },
    health_proxy: {
      failure_threshold: 2,
      cooldown_ms: 30000,
    },
    deployed_sha: "unknown",
  };
}

function getNested<T>(config: Record<string, unknown>, path: string[], fallback: T): T {
  let current: unknown = config;
  for (const key of path) {
    if (!isObject(current) || !(key in current)) return fallback;
    current = current[key];
  }
  return (current as T) ?? fallback;
}

export function loadMergedAppConfig(): Record<string, unknown> {
  return deepMerge(
    deepMerge(defaultConfig(), loadJson(repoConfigPath())),
    loadJson(userConfigPath()),
  );
}

export function loadPublicWebConfig(): PublicWebConfig {
  const config = loadMergedAppConfig();
  // Env var overrides take precedence over merged config. This lets
  // deploys (Docker, Vercel, etc.) tune values without editing files.
  const fromEnv = <T>(name: string, fallback: T, parse: (s: string) => T = ((s) => s as unknown as T)): T => {
    const v = process.env[name];
    if (v === undefined || v === null || v === "") return fallback;
    try {
      return parse(String(v));
    } catch {
      return fallback;
    }
  };
  return {
    apiBaseUrl: String(
      process.env.NEXT_PUBLIC_API_URL
      || getNested(config, ["web", "api_base_url"], "")
      || getNested(config, ["agent_providers", "api_base_url"], "https://api.coherencycoin.com"),
    ),
    localApiBaseUrl: String(
      process.env.API_URL
      || getNested(config, ["web", "local_api_base_url"], "http://localhost:8000"),
    ),
    webUiBaseUrl: String(
      process.env.NEXT_PUBLIC_BASE_URL
      || getNested(config, ["web", "web_ui_base_url"], "")
      || getNested(config, ["agent_providers", "web_ui_base_url"], "https://coherencycoin.com"),
    ),
    pulseBaseUrl: String(
      process.env.NEXT_PUBLIC_PULSE_URL
      || getNested(config, ["web", "pulse_base_url"], "")
      || "https://pulse.coherencycoin.com",
    ),
    repoUrl: String(
      process.env.NEXT_PUBLIC_REPO_URL
      || getNested(config, ["web", "repo_url"], "https://github.com/seeker71/Coherence-Network/blob/main"),
    ),
    fetchDefaults: {
      timeoutMs: Math.max(
        1000,
        fromEnv("NEXT_PUBLIC_FETCH_TIMEOUT_MS", Number(getNested(config, ["web", "fetch_defaults", "timeout_ms"], 7000)) || 7000, Number),
      ),
      retryAttempts: Math.max(
        0,
        fromEnv("NEXT_PUBLIC_FETCH_RETRY_ATTEMPTS", Number(getNested(config, ["web", "fetch_defaults", "retry_attempts"], 3)) || 3, Number),
      ),
      healthTimeoutMs: Math.max(
        1000,
        fromEnv("NEXT_PUBLIC_HEALTH_TIMEOUT_MS", Number(getNested(config, ["web", "fetch_defaults", "health_timeout_ms"], 10000)) || 10000, Number),
      ),
    },
    pagination: {
      defaultLimit: Math.max(
        1,
        Number(getNested(config, ["web", "pagination", "default_limit"], 50)) || 50,
      ),
      maxLimit: Math.max(
        1,
        Number(getNested(config, ["web", "pagination", "max_limit"], 500)) || 500,
      ),
    },
    liveUpdates: {
      pollMs: Math.max(30000, Number(getNested(config, ["live_updates", "poll_ms"], 120000)) || 120000),
      routerRefreshEveryTicks: Math.max(
        1,
        Number(getNested(config, ["live_updates", "router_refresh_every_ticks"], 8)) || 8,
      ),
      global: Boolean(getNested(config, ["live_updates", "global"], false)),
      activeRoutePrefixes: getNested(config, ["live_updates", "active_route_prefixes"], ["/tasks", "/remote-ops", "/api-health", "/gates"]),
      routerRefreshSkipPrefixes: getNested(config, ["live_updates", "router_refresh_skip_prefixes"], ["/automation"]),
    },
    runtimeBeacon: {
      sampleRate: Math.max(0, Math.min(1, Number(getNested(config, ["runtime_beacon", "sample_rate"], 0.2)) || 0.2)),
      upstreamTimeoutMs: Math.max(1000, Number(getNested(config, ["runtime_beacon", "upstream_timeout_ms"], 5000)) || 5000),
      failureThreshold: Math.max(1, Number(getNested(config, ["runtime_beacon", "failure_threshold"], 3)) || 3),
      cooldownMs: Math.max(1000, Number(getNested(config, ["runtime_beacon", "cooldown_ms"], 30000)) || 30000),
    },
    healthProxy: {
      failureThreshold: Math.max(1, Number(getNested(config, ["health_proxy", "failure_threshold"], 2)) || 2),
      cooldownMs: Math.max(1000, Number(getNested(config, ["health_proxy", "cooldown_ms"], 30000)) || 30000),
    },
    deployedSha: String(
      getNested(config, ["web", "deployed_sha"], "")
      || getNested(config, ["deployed_sha"], "unknown")
      || "unknown",
    ),
    updatedAt: String(
      getNested(config, ["web", "updated_at"], "")
      || getNested(config, ["web", "deployed_sha"], "")
      || getNested(config, ["deployed_sha"], "unknown")
      || "unknown",
    ),
  };
}
