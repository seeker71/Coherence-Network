export const PROD_API_URL = "https://coherence-network-production.up.railway.app";
export const DEV_API_URL = "http://localhost:8000";
const LEGACY_BLOCKED_API_HOSTS = ["api.coherencycoin.com"];

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

export function getApiBase(): string {
  const env = process.env.NEXT_PUBLIC_API_URL;
  const resolved = env ? _resolveApiEnvUrl(env) : null;
  if (resolved) return resolved;
  if (process.env.NODE_ENV === "production") return PROD_API_URL;
  return DEV_API_URL;
}
