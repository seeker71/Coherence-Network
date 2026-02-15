import { NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WEB_STARTED_AT = new Date();
const WEB_UPDATED_AT = process.env.WEB_UPDATED_AT || process.env.VERCEL_GIT_COMMIT_SHA || "unknown";

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

export async function GET() {
  const started = performance.now();
  try {
    const upstream = await fetch(`${API_URL}/api/health`, {
      cache: "no-store",
    });
    const upstreamJson = await upstream.json();
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
    void fetch(`${API_URL}/api/runtime/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: "web_api",
        endpoint: "/api/health-proxy",
        method: "GET",
        status_code: response.status,
        runtime_ms: Number(runtimeMs.toFixed(4)),
      }),
      cache: "no-store",
    }).catch(() => {});
    return response;
  } catch (error) {
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
      },
      { status: 502 },
    );
    const runtimeMs = Math.max(0.1, performance.now() - started);
    void fetch(`${API_URL}/api/runtime/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: "web_api",
        endpoint: "/api/health-proxy",
        method: "GET",
        status_code: response.status,
        runtime_ms: Number(runtimeMs.toFixed(4)),
      }),
      cache: "no-store",
    }).catch(() => {});
    return response;
  }
}
