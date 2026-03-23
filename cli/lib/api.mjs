/**
 * HTTP client for the Coherence Network API.
 * Zero deps — uses native fetch (Node 18+).
 */

import { getHubUrl } from "./config.mjs";

const TIMEOUT_MS = 12_000;

function buildUrl(path, params) {
  const base = getHubUrl().replace(/\/$/, "");
  const url = new URL(path, base);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v != null) url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

export async function get(path, params) {
  try {
    const res = await fetch(buildUrl(path, params), {
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error(`\x1b[2m  network error: ${err.message}\x1b[0m`);
    return null;
  }
}

export async function post(path, body) {
  try {
    const res = await fetch(buildUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      console.error(`\x1b[2m  ${res.status}: ${err.detail || "request failed"}\x1b[0m`);
      return null;
    }
    return await res.json();
  } catch (err) {
    console.error(`\x1b[2m  network error: ${err.message}\x1b[0m`);
    return null;
  }
}

export async function del(path) {
  try {
    const res = await fetch(buildUrl(path), {
      method: "DELETE",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    return res.ok;
  } catch {
    return false;
  }
}
