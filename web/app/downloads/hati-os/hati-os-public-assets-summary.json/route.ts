import { NextResponse, type NextRequest } from "next/server";

const RELEASE_TAG = "hati-os-v0.1.0-20260613";
const RELEASE_BASE = `https://github.com/seeker71/Coherence-Network/releases/download/${RELEASE_TAG}`;

export function GET(_request: NextRequest) {
  return NextResponse.redirect(
    `${RELEASE_BASE}/hati-os-public-assets-summary.json`,
    307,
  );
}
