import { NextRequest, NextResponse } from "next/server";

import { loadPublicWebConfig } from "@/lib/app-config";

const _config = loadPublicWebConfig();
const API_URL = _config.localApiBaseUrl || _config.apiBaseUrl || "http://api:8000";

const CONTRIBUTOR_KEY_COOKIE = "coh_contributor_key";
const CONTRIBUTOR_NAME_COOKIE = "coh_contributor_name";
const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

function sanitizeName(raw: unknown): string {
  if (typeof raw !== "string") return "";
  return raw.trim().slice(0, 80);
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  let payload: { name?: unknown };
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const name = sanitizeName(payload?.name);
  if (!name) {
    return NextResponse.json({ error: "name_required" }, { status: 400 });
  }

  const upstream = await fetch(`${API_URL}/api/onboard`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      provider: "name",
      provider_id: name,
      display_name: name,
    }),
    cache: "no-store",
  });

  if (!upstream.ok) {
    const detail = await upstream.text();
    return NextResponse.json(
      { error: "onboard_failed", status: upstream.status, detail },
      { status: 502 },
    );
  }

  const minted = (await upstream.json()) as {
    api_key?: string;
    contributor_id?: string;
  };

  const apiKey = String(minted.api_key || "").trim();
  const contributorId = String(minted.contributor_id || name).trim();
  if (!apiKey) {
    return NextResponse.json({ error: "no_key_returned" }, { status: 502 });
  }

  const response = NextResponse.json({
    contributor_id: contributorId,
    name,
  });

  const isProd = process.env.NODE_ENV === "production";
  response.cookies.set({
    name: CONTRIBUTOR_KEY_COOKIE,
    value: apiKey,
    httpOnly: true,
    sameSite: "lax",
    secure: isProd,
    path: "/",
    maxAge: ONE_YEAR_SECONDS,
  });
  response.cookies.set({
    name: CONTRIBUTOR_NAME_COOKIE,
    value: contributorId,
    httpOnly: false,
    sameSite: "lax",
    secure: isProd,
    path: "/",
    maxAge: ONE_YEAR_SECONDS,
  });

  return response;
}
