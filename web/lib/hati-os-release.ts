// Single source of truth for the published Hati-OS native release.
// The /hati-os page renders the surfaced rows; the download proxy route builds
// its allowlist from the same list; the summary route redirects to the same
// tag. One cell, three readers — they cannot drift to different releases.

export const HATI_OS_RELEASE_TAG = "hati-os-v0.2.0-20260614";
export const HATI_OS_RELEASE_BASE = `https://github.com/seeker71/Coherence-Network/releases/download/${HATI_OS_RELEASE_TAG}`;

export type HatiOsAsset = {
  /** Display name of the target, e.g. "macOS arm64". */
  target: string;
  /** Proxy-path OS segment, e.g. "macos". */
  os: string;
  /** Proxy-path arch segment, e.g. "arm64". */
  arch: string;
  /** Asset filename in the GitHub release. */
  name: string;
  /** Short artifact label shown on the page. */
  artifact: string;
  /** The proof lane behind the artifact, shown on the page. */
  proof: string;
  /** Whether the row is shown on the /hati-os page (debug builds stay downloadable but unsurfaced). */
  surfaced: boolean;
};

export const HATI_OS_ASSETS: HatiOsAsset[] = [
  {
    target: "macOS arm64",
    os: "macos",
    arch: "arm64",
    name: "hati-os-macos-arm64.tar.zst",
    artifact: "Native CLI tarball",
    proof: "Form-emitted C compiled to Mach-O arm64 and executed locally for fib, sum, and ack parity.",
    surfaced: true,
  },
  {
    target: "Android arm64",
    os: "android",
    arch: "arm64",
    name: "hati-os-android-arm64.tar.zst",
    artifact: "Native kernel package",
    proof: "Android ARM64 ELF executable and C-ABI shared library cross-compiled with local file and symbol proof.",
    surfaced: true,
  },
  {
    target: "Android app",
    os: "android",
    arch: "arm64",
    name: "coherence-sense-hati-mesh-release.apk",
    artifact: "Hati mesh sensing-organ release APK",
    proof: "Release APK is signed with the Hati mesh app key, verified by apksigner, announces to hati.mesh, and checks signed update metadata.",
    surfaced: true,
  },
  {
    target: "Android app (debug)",
    os: "android",
    arch: "arm64",
    name: "coherence-sense-hati-mesh-debug.apk",
    artifact: "Hati mesh sensing-organ debug APK",
    proof: "Debug-key build for sideload testing; same mesh announce path as the release APK.",
    surfaced: false,
  },
];

/** Local proxy path for an asset, e.g. /downloads/hati-os/macos/arm64/<name>. */
export function hatiOsHref(asset: HatiOsAsset): string {
  return `/downloads/hati-os/${asset.os}/${asset.arch}/${asset.name}`;
}

/** Allowlist of proxy keys → release filenames, including each asset's .sha256. */
export const HATI_OS_PROXY_ASSETS: Record<string, string> = Object.fromEntries(
  HATI_OS_ASSETS.flatMap((a) => {
    const key = `${a.os}/${a.arch}/${a.name}`;
    return [
      [key, a.name],
      [`${key}.sha256`, `${a.name}.sha256`],
    ];
  }),
);
