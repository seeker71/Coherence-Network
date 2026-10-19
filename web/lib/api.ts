import { readPublicWebConfig } from "@/lib/public-config";

export const DEV_API_URL = "http://localhost:8000";
const LEGACY_BLOCKED_API_HOSTS: string[] = [];

function _stripTrailingSlash(url: string): string {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

function _isLocalhostHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
}

function _resolveConfiguredApiUrl(value: string): string | null {
  const trimmed = value.trim();
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

function _loadServerConfiguredApiBase(): string | null {
  if (typeof window !== "undefined") return null;
  try {
    const req = Function("return require")() as NodeRequire;
    const { loadPublicWebConfig } = req("./app-config") as typeof import("./app-config");
    const config = loadPublicWebConfig();
    return config.localApiBaseUrl || config.apiBaseUrl || null;
  } catch {
    return null;
  }
}

export function getApiBase(): string {
  const isBrowser = typeof window !== "undefined";
  const config = readPublicWebConfig();
  const configured = isBrowser
    ? config.apiBaseUrl
    : (_loadServerConfiguredApiBase() || config.apiBaseUrl || config.localApiBaseUrl);
  const resolved = configured ? _resolveConfiguredApiUrl(configured) : null;
  if (resolved) {
    if (isBrowser && resolved !== DEV_API_URL) return "";
    return resolved;
  }
  if (isBrowser) return "";
  return DEV_API_URL;
}
