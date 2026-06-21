// Redirects to the release receipt JSON for the published Hati-OS assets.
// Tag comes from web/lib/hati-os-release.ts so the summary always describes the
// same release the download links serve.
import { NextResponse, type NextRequest } from "next/server";
import { HATI_OS_RELEASE_BASE } from "@/lib/hati-os-release";

export function GET(_request: NextRequest) {
  return NextResponse.redirect(
    `${HATI_OS_RELEASE_BASE}/hati-os-public-assets-summary.json`,
    307,
  );
}
