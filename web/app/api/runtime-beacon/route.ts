import { NextRequest, NextResponse } from "next/server";
import { getApiBase } from "@/lib/api";

const API_URL = getApiBase();
const RUNTIME_BEACON_UPSTREAM_TIMEOUT_MS = Number.parseInt(
  process.env.RUNTIME_BEACON_UPSTREAM_TIMEOUT_MS || "5000",
  10,
);
const RUNTIME_BEACON_FAILURE_THRESHOLD = Math.max(
  1,
  Number.parseInt(process.env.RUNTIME_BEACON_FAILURE_THRESHOLD || "3", 10) || 3,
);
const RUNTIME_BEACON_COOLDOWN_MS = Math.max(
  1000,
  Number.parseInt(process.env.RUNTIME_BEACON_COOLDOWN_MS || "30000", 10) || 30000,
);

let runtimeBeaconConsecutiveFailures = 0;
let runtimeBeaconCooldownUntilMs = 0;

function runtimeBeaconCooldownRemainingSeconds(nowMs: number): number {
  if (runtimeBeaconCooldownUntilMs <= nowMs) {
    return 0;
  }
  return Math.ceil((runtimeBeaconCooldownUntilMs - nowMs) / 1000);
}

function markRuntimeBeaconSuccess() {
  runtimeBeaconConsecutiveFailures = 0;
  runtimeBeaconCooldownUntilMs = 0;
}

function markRuntimeBeaconFailure() {
  runtimeBeaconConsecutiveFailures += 1;
  if (runtimeBeaconConsecutiveFailures >= RUNTIME_BEACON_FAILURE_THRESHOLD) {
    runtimeBeaconCooldownUntilMs = Date.now() + RUNTIME_BEACON_COOLDOWN_MS;
    runtimeBeaconConsecutiveFailures = 0;
  }
}

async function postRuntimeEvent(payload: unknown): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => {
    controller.abort(new DOMException("Request timed out", "TimeoutError"));
  }, RUNTIME_BEACON_UPSTREAM_TIMEOUT_MS);

async function recordBeaconRuntime(statusCode: number, runtimeMs: number): Promise<void> {
  try {
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
    return await fetch(`${API_URL}/api/runtime/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
      signal: controller.signal,
    });
    const body = await upstream.json();
    await recordBeaconRuntime(upstream.status, performance.now() - started);
    return NextResponse.json(body, { status: upstream.status });
  } catch (error) {
    await recordBeaconRuntime(502, performance.now() - started);
    return NextResponse.json(
      {
        status: "skipped",
        reason: "cooldown_active",
        retry_after_seconds: runtimeBeaconCooldownRemainingSeconds(nowMs),
      },
      { status: 202 },
    );
  }

  try {
    const payload = await request.json();
    const upstream = await postRuntimeEvent(payload);

    let body: unknown = null;
    try {
      body = await upstream.json();
    } catch {
      body = null;
    }

    if (upstream.status >= 500) {
      markRuntimeBeaconFailure();
      return NextResponse.json(
        {
          status: "degraded",
          error: "runtime_beacon_upstream_5xx",
          upstream_status: upstream.status,
          retry_after_seconds: runtimeBeaconCooldownRemainingSeconds(Date.now()),
        },
        { status: 202 },
      );
    }

    markRuntimeBeaconSuccess();
    if (body === null) {
      return new NextResponse(null, { status: upstream.status });
    }
    return NextResponse.json(body, { status: upstream.status });
  } catch (error) {
    markRuntimeBeaconFailure();
    return NextResponse.json(
      {
        status: "degraded",
        error: "runtime_beacon_failed",
        details: String(error),
        retry_after_seconds: runtimeBeaconCooldownRemainingSeconds(Date.now()),
      },
      { status: 202 },
    );
  }
}
