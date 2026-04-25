import { getApiBase } from "@/lib/api";
import type { JsonResult } from "./types";

export const API_BASE = getApiBase();

export const REQUIRED_QUERY_OVERRIDES: Record<string, string> = {
  "/gates/pr-to-public": "branch=main",
};

export const SKIP_GET_PROBE: Record<string, string> = {
  "/gates/merged-contract": "Requires a known merged commit SHA query parameter.",
};

export async function fetchJson<T>(url: string): Promise<JsonResult<T>> {
  try {
    const res = await fetch(url, { cache: "no-store" });
    const text = await res.text();
    let parsed: unknown = null;
    try {
      parsed = text ? JSON.parse(text) : null;
    } catch {
      parsed = null;
    }

    if (!res.ok) {
      const errMsg =
        (parsed && typeof parsed === "object" && "detail" in parsed && typeof parsed.detail === "string"
          ? parsed.detail
          : text.slice(0, 240)) || `HTTP ${res.status}`;
      return { ok: false, status: res.status, error: errMsg };
    }
    return { ok: true, status: res.status, data: parsed as T };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

export function isStaticPath(path: string): boolean {
  return !path.includes("{") && !path.includes("}");
}

export function buildProbeUrl(path: string): string {
  const apiPath = path.startsWith("/api/") ? path : `/api${path}`;
  const qs = REQUIRED_QUERY_OVERRIDES[path];
  if (!qs) return `${API_BASE}${apiPath}`;
  return `${API_BASE}${apiPath}?${qs}`;
}

export function endpointHref(path: string): string {
  if (isStaticPath(path)) return `${API_BASE}${path}`;
  return `${API_BASE}/docs`;
}

export function scoreClass(status: "pass" | "fail" | "skipped"): string {
  if (status === "pass") return "text-emerald-700";
  if (status === "fail") return "text-destructive";
  return "text-muted-foreground";
}
