import { NextRequest, NextResponse } from "next/server";
import { getApiBase } from "@/lib/api";

const API_URL = getApiBase();

async function recordBeaconRuntime(statusCode: number, runtimeMs: number): Promise<void> {
  try {
    // Track beacon endpoint usage itself so web API routes are visible in runtime coverage.
    await fetch(`${API_URL}/api/runtime/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: "web_api",
        endpoint: "/api/runtime-beacon",
        method: "POST",
        status_code: statusCode,
        runtime_ms: Number(Math.max(0.1, runtimeMs).toFixed(4)),
      }),
      cache: "no-store",
    });
  } catch {
    // Usage telemetry must never break the endpoint.
  }
}

export async function POST(request: NextRequest) {
  const started = performance.now();
  try {
    const payload = await request.json();
    const upstream = await fetch(`${API_URL}/api/runtime/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const body = await upstream.json();
    await recordBeaconRuntime(upstream.status, performance.now() - started);
    return NextResponse.json(body, { status: upstream.status });
  } catch (error) {
    await recordBeaconRuntime(502, performance.now() - started);
    return NextResponse.json(
      {
        error: "runtime_beacon_failed",
        details: String(error),
      },
      { status: 502 },
    );
  }
}
