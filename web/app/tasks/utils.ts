import { UI_RUNTIME_EVENTS_LIMIT } from "@/lib/egress";

export const REQUEST_TIMEOUT_MS = 12000;
export const EVENTS_TIMEOUT_MS = 8000;
export const EVENTS_LIMIT = UI_RUNTIME_EVENTS_LIMIT;
export const DEFAULT_PAGE_SIZE = 25;
export const MAX_PAGE_SIZE = 100;

export function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return value as Record<string, unknown>;
}

export function toInt(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return Math.trunc(value);
  if (typeof value === "string" && value.trim()) {
    const parsed = Number.parseInt(value.trim(), 10);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function formatTime(value?: string): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export function tailLines(value: string, maxLines: number): string {
  const rows = value.split("\n");
  return rows.slice(Math.max(0, rows.length - maxLines)).join("\n");
}

export function parsePositiveInt(value: string | null, fallback: number): number {
  const parsed = Number.parseInt((value || "").trim(), 10);
  if (!Number.isFinite(parsed) || parsed < 1) return fallback;
  return parsed;
}

export async function fetchWithTimeout(
  input: string,
  init: RequestInit = {},
  timeoutMs = REQUEST_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  let timeout: ReturnType<typeof setTimeout> | null = null;
  const timeoutPromise = new Promise<Response>((_, reject) => {
    timeout = setTimeout(() => {
      controller.abort(new DOMException("Request timed out", "TimeoutError"));
      reject(new Error(`Request timed out after ${timeoutMs}ms`));
    }, timeoutMs);
  });

  const fetchPromise = fetch(input, {
    ...init,
    signal: controller.signal,
    cache: init.cache ?? "no-store",
  });

  try {
    return await Promise.race([fetchPromise, timeoutPromise]);
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}
