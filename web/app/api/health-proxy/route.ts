import { NextResponse } from "next/server";
import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";

const API_URL = getApiBase();
const WEB_STARTED_AT = new Date();
const WEB_UPDATED_AT = process.env.WEB_UPDATED_AT || process.env.VERCEL_GIT_COMMIT_SHA || "unknown";
const UPSTREAM_TIMEOUT_MS = 15000;
const HEALTH_PROXY_FAILURE_THRESHOLD = Math.max(
  1,
  Number.parseInt(process.env.HEALTH_PROXY_FAILURE_THRESHOLD || "2", 10) || 2,
);
const HEALTH_PROXY_COOLDOWN_MS = Math.max(
  1000,
  Number.parseInt(process.env.HEALTH_PROXY_COOLDOWN_MS || "30000", 10) || 30000,
);

let healthProxyConsecutiveFailures = 0;
let healthProxyCooldownUntilMs = 0;

function uptimeSeconds() {
  return Math.max(0, Math.floor((Date.now() - WEB_STARTED_AT.getTime()) / 1000));
}

function uptimeHuman(seconds: number) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins > 0) {
    return `${mins}m ${secs}s`;
  }
  return `${secs}s`;
}

function healthProxyRetryAfterSeconds(nowMs: number): number {
  if (healthProxyCooldownUntilMs <= nowMs) {
    return 0;
  }
  return Math.ceil((healthProxyCooldownUntilMs - nowMs) / 1000);
}

function markHealthProxySuccess() {
  healthProxyConsecutiveFailures = 0;
  healthProxyCooldownUntilMs = 0;
}

function markHealthProxyFailure() {
  healthProxyConsecutiveFailures += 1;
  if (healthProxyConsecutiveFailures >= HEALTH_PROXY_FAILURE_THRESHOLD) {
    healthProxyCooldownUntilMs = Date.now() + HEALTH_PROXY_COOLDOWN_MS;
    healthProxyConsecutiveFailures = 0;
  }
}

function emitHealthProxyRuntimeEvent(
  statusCode: number,
  runtimeMs: number,
  metadata: Record<string, string | number | boolean> = {},
) {
  void fetch(`${API_URL}/api/runtime/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source: "web_api",
      endpoint: "/api/health-proxy",
      method: "GET",
      status_code: statusCode,
      runtime_ms: Number(runtimeMs.toFixed(4)),
      metadata,
    }),
    cache: "no-store",
  }).catch(() => {});
}

export async function GET() {
  const started = performance.now();
  const nowMs = Date.now();
  if (healthProxyCooldownUntilMs > nowMs) {
    const retryAfterSeconds = healthProxyRetryAfterSeconds(nowMs);
    const response = NextResponse.json(
      {
        error: "Upstream API cooldown active",
        api_url: API_URL,
        web: {
          status: "degraded",
          started_at: WEB_STARTED_AT.toISOString(),
          uptime_seconds: uptimeSeconds(),
          updated_at: WEB_UPDATED_AT,
        },
        retry_after_seconds: retryAfterSeconds,
      },
      { status: 503 },
    );
    const runtimeMs = Math.max(0.1, performance.now() - started);
    emitHealthProxyRuntimeEvent(response.status, runtimeMs, {
      health_proxy_mode: "cooldown",
      retry_after_seconds: retryAfterSeconds,
    });
    return response;
  }

  try {
    const upstreamJson = await fetchJsonOrNull<Record<string, unknown>>(
      `${API_URL}/api/health`,
      { cache: "no-store" },
      UPSTREAM_TIMEOUT_MS,
    );
    if (!upstreamJson) {
      throw new Error("Upstream health payload unavailable");
    }
    markHealthProxySuccess();
    const up = uptimeSeconds();
    const response = NextResponse.json({
      api: upstreamJson,
      web: {
        status: "ok",
        started_at: WEB_STARTED_AT.toISOString(),
        uptime_seconds: up,
        uptime_human: uptimeHuman(up),
        updated_at: WEB_UPDATED_AT,
      },
      checked_at: new Date().toISOString(),
    });
    const runtimeMs = Math.max(0.1, performance.now() - started);
    emitHealthProxyRuntimeEvent(response.status, runtimeMs, {
      health_proxy_mode: "live",
    });
    return response;
  } catch (error) {
    markHealthProxyFailure();
    const retryAfterSeconds = healthProxyRetryAfterSeconds(Date.now());
    const response = NextResponse.json(
      {
        error: "Upstream API unreachable",
        api_url: API_URL,
        web: {
          status: "degraded",
          started_at: WEB_STARTED_AT.toISOString(),
          uptime_seconds: uptimeSeconds(),
          updated_at: WEB_UPDATED_AT,
        },
        details: String(error),
        retry_after_seconds: retryAfterSeconds,
      },
      { status: 502 },
    );
    const runtimeMs = Math.max(0.1, performance.now() - started);
    emitHealthProxyRuntimeEvent(response.status, runtimeMs, {
      health_proxy_mode: "upstream_failure",
      retry_after_seconds: retryAfterSeconds,
    });
    return response;
  }
}
