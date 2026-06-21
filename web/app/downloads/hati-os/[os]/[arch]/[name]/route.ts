// Redirects /downloads/hati-os/<os>/<arch>/<name> to the matching asset in the
// published GitHub release. Tag + allowlist come from the single source of
// truth in web/lib/hati-os-release.ts so this route can never serve a stale
// release tag or surface an asset the page does not know about.
import { NextResponse, type NextRequest } from "next/server";
import {
  HATI_OS_PROXY_ASSETS,
  HATI_OS_RELEASE_BASE,
} from "@/lib/hati-os-release";

type Params = {
  os: string;
  arch: string;
  name: string;
};

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<Params> },
) {
  const resolved = await params;
  const key = `${resolved.os}/${resolved.arch}/${resolved.name}`;
  const asset = HATI_OS_PROXY_ASSETS[key];
  if (!asset) {
    return NextResponse.json(
      { error: "unknown Hati-OS asset", key },
      { status: 404 },
    );
  }

  return NextResponse.redirect(`${HATI_OS_RELEASE_BASE}/${asset}`, 307);
}
