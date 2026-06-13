import { NextResponse, type NextRequest } from "next/server";

const RELEASE_TAG = "hati-os-v0.1.0-20260613";
const RELEASE_BASE = `https://github.com/seeker71/Coherence-Network/releases/download/${RELEASE_TAG}`;

const ASSETS: Record<string, string> = {
  "macos/arm64/hati-os-macos-arm64.tar.zst": "hati-os-macos-arm64.tar.zst",
  "macos/arm64/hati-os-macos-arm64.tar.zst.sha256": "hati-os-macos-arm64.tar.zst.sha256",
  "android/arm64/hati-os-android-arm64.tar.zst": "hati-os-android-arm64.tar.zst",
  "android/arm64/hati-os-android-arm64.tar.zst.sha256": "hati-os-android-arm64.tar.zst.sha256",
  "android/arm64/coherence-sense-hati-mesh-debug.apk": "coherence-sense-hati-mesh-debug.apk",
  "android/arm64/coherence-sense-hati-mesh-debug.apk.sha256": "coherence-sense-hati-mesh-debug.apk.sha256",
};

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
  const asset = ASSETS[key];
  if (!asset) {
    return NextResponse.json(
      { error: "unknown Hati-OS asset", key },
      { status: 404 },
    );
  }

  return NextResponse.redirect(`${RELEASE_BASE}/${asset}`, 307);
}
