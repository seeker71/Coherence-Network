import { NextResponse } from "next/server";

const WEB_UPDATED_AT = process.env.WEB_UPDATED_AT || process.env.VERCEL_GIT_COMMIT_SHA || "unknown";

export async function GET() {
  return NextResponse.json(
    {
      web: {
        updated_at: WEB_UPDATED_AT,
      },
      checked_at: new Date().toISOString(),
    },
    {
      headers: {
        "cache-control": "no-store",
      },
    },
  );
}
