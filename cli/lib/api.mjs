/**
 * HTTP client for the Coherence Network API.
 * Zero deps — uses native fetch (Node 18+).
 */

import { getHubUrl, getApiKey } from "./config.mjs";

const TIMEOUT_MS = 12_000;
/** Delay before a single retry after timeout (Contribution Recognition Loop). */
const RETRY_AFTER_TIMEOUT_MS = 500;
const CONTRIBUTION_POST_MAX_ATTEMPTS = 2;

function _isTimeoutError(err) {
  if (!err) return false;
  if (err.name === "AbortError" || err.name === "TimeoutError") return true;
  const msg = String(err.message || "").toLowerCase();
  return msg.includes("timeout") || msg.includes("aborted");
}

function authHeaders(extra = {}) {
  const key = getApiKey();
  const headers = { ...extra };
  if (key) headers["X-API-Key"] = key;
  return headers;
}

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
      headers: authHeaders(),
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
      headers: authHeaders({ "Content-Type": "application/json" }),
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

/**
 * POST with one retry on client timeout only (simplified Contribution Recognition Loop).
 * Does not retry HTTP error responses — only transport/timeout failures.
 */
export async function postWithRetryOnTimeout(path, body, maxAttempts = CONTRIBUTION_POST_MAX_ATTEMPTS) {
  let lastErr;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const res = await fetch(buildUrl(path), {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
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
      lastErr = err;
      if (attempt < maxAttempts && _isTimeoutError(err)) {
        console.error(`\x1b[2m  network error: ${err.message} — retrying once...\x1b[0m`);
        await new Promise((r) => setTimeout(r, RETRY_AFTER_TIMEOUT_MS));
        continue;
      }
      console.error(`\x1b[2m  network error: ${err.message}\x1b[0m`);
      return null;
    }
  }
  console.error(`\x1b[2m  network error: ${lastErr?.message || "unknown"}\x1b[0m`);
  return null;
}

export async function patch(path, body) {
  try {
    const res = await fetch(buildUrl(path), {
      method: "PATCH",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function del(path) {
  try {
    const res = await fetch(buildUrl(path), {
      method: "DELETE",
      headers: authHeaders(),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    return res.ok;
  } catch {
    return false;
  }
}
