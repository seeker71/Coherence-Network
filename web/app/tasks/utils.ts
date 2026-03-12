import { UI_RUNTIME_EVENTS_LIMIT } from "@/lib/egress";
import { humanizeStatus } from "@/lib/humanize";

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

export function humanizeTaskType(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "impl") return "Build step";
  if (normalized === "review") return "Check-in";
  if (normalized === "spec") return "Plan";
  if (!normalized) return "Work card";
  return humanizeStatus(normalized);
}

export function humanizeTaskStatus(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "pending") return "Ready to start";
  if (normalized === "running" || normalized === "in_progress" || normalized === "claimed") return "In progress";
  if (normalized === "queued") return "Waiting in line";
  if (normalized === "completed") return "Finished";
  if (normalized === "failed") return "Blocked";
  if (normalized === "needs_decision") return "Waiting for your decision";
  return humanizeStatus(normalized);
}

export function describeTaskStatus(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "pending") return "This work card is ready for someone to pick up.";
  if (normalized === "running" || normalized === "in_progress" || normalized === "claimed") return "Someone is actively moving this work forward.";
  if (normalized === "queued") return "This work is waiting behind something else right now.";
  if (normalized === "completed") return "This work is finished and ready for review or follow-up.";
  if (normalized === "failed") return "This work is blocked and needs attention before it can continue.";
  if (normalized === "needs_decision") return "This work is paused until someone makes a choice.";
  return "This work card exists, but its current state needs a quick review.";
}

export function humanizeIdeaName(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "Linked idea";
  if (/[_-]/.test(trimmed) && !trimmed.includes(" ")) {
    return trimmed
      .split(/[_-]+/)
      .filter(Boolean)
      .map((word) => `${word.slice(0, 1).toUpperCase()}${word.slice(1)}`)
      .join(" ");
  }
  return trimmed;
}
