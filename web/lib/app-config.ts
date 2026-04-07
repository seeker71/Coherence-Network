import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";

export type PublicWebConfig = {
  apiBaseUrl: string;
  localApiBaseUrl: string;
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
  return {
    apiBaseUrl: String(
      getNested(config, ["web", "api_base_url"], "")
      || getNested(config, ["agent_providers", "api_base_url"], "https://api.coherencycoin.com"),
    ),
    localApiBaseUrl: String(
      process.env.API_URL
      || getNested(config, ["web", "local_api_base_url"], "http://localhost:8000"),
    ),
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
