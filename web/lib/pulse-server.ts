// Server-only helper for resolving the Pulse Monitor base URL.
//
// Lives in its own file (not lib/api.ts) because api.ts is imported by
// client components. `loadPublicWebConfig` reads from fs/os, which webpack
// cannot bundle into a client chunk. This module must only be imported
// from server components (see web/app/pulse/page.tsx).

import { loadPublicWebConfig } from "./app-config";

function stripTrailingSlash(url: string): string {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

/**
 * Resolve the base URL of the Pulse Monitor (the external witness) for use
 * from a server component. Reads NEXT_PUBLIC_PULSE_URL and the merged
 * public web config. Returns an empty string if nothing is configured, in
 * which case the /pulse page renders a "witness is quiet" state.
 */
export function getPulseBaseServer(): string {
  const cfg = loadPublicWebConfig();
  const url = (cfg.pulseBaseUrl || "").trim();
  if (!url) return "";
  return stripTrailingSlash(url);
}
