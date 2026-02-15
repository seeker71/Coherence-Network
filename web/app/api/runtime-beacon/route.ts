import { NextRequest, NextResponse } from "next/server";
import { getApiBase } from "@/lib/api";

const API_URL = getApiBase();

export async function POST(request: NextRequest) {
  try {
    const payload = await request.json();
    const upstream = await fetch(`${API_URL}/api/runtime/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const body = await upstream.json();
    return NextResponse.json(body, { status: upstream.status });
  } catch (error) {
    return NextResponse.json(
      {
        error: "runtime_beacon_failed",
        details: String(error),
      },
      { status: 502 },
    );
  }
}
