export const DEV_API_URL = "http://localhost:8000";
const LEGACY_BLOCKED_API_HOSTS: string[] = [];

function _stripTrailingSlash(url: string): string {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

function _isLocalhostHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
}

function _resolveApiEnvUrl(envValue: string): string | null {
  const trimmed = envValue.trim();
  if (!trimmed) return null;

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return null;
  }

  const hostname = parsed.hostname.toLowerCase();
  if (LEGACY_BLOCKED_API_HOSTS.includes(hostname)) {
    return null;
  }

  if (_isLocalhostHost(hostname) || parsed.protocol.startsWith("http")) {
    return _stripTrailingSlash(trimmed);
  }

  return null;
}

/** Map GET /api/agent/tasks/count `by_status` into list `counts` buckets (spec 156). */
export function aggregateTaskCountsFromByStatus(
  byStatus: Record<string, number> | undefined | null,
): {
  pending: number;
  running: number;
  completed: number;
  failed: number;
} {
  const by = byStatus || {};
  const n = (k: string) =>
    typeof by[k] === "number" && Number.isFinite(by[k]) ? Math.trunc(by[k]) : 0;
  return {
    pending: n("pending") + n("queued"),
    running: n("running") + n("claimed") + n("in_progress"),
    completed: n("completed"),
    failed: n("failed") + n("needs_decision") + n("timed_out"),
  };
}

export function getApiBase(): string {
  // In the browser, use the Next.js rewrite proxy (empty base = relative /api/* paths)
  // to avoid CORS issues. Server components can use the full URL directly.
  const isBrowser = typeof window !== "undefined";
  const env = process.env.NEXT_PUBLIC_API_URL || process.env.API_URL;
  const resolved = env ? _resolveApiEnvUrl(env) : null;
  if (resolved) {
    // If running in the browser and pointing at a remote API, use the proxy instead
    if (isBrowser && resolved !== DEV_API_URL) return "";
    return resolved;
  }
  // In dev with no env set, browser uses proxy, server uses localhost
  if (isBrowser) return "";
  return DEV_API_URL;
}
