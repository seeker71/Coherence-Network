import { NextResponse } from "next/server";
import { loadPublicWebConfig } from "@/lib/app-config";

const WEB_CONFIG = loadPublicWebConfig();
const WEB_UPDATED_AT = WEB_CONFIG.updatedAt || WEB_CONFIG.deployedSha || "unknown";

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
