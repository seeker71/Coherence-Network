// sense.hati.earth — the download door for Coherence Sense. Detects the visitor's
// device and offers the right artifact or entry lane for each platform.
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const APK =
  "https://github.com/seeker71/Coherence-Network/releases/download/coherence-sense-v0/coherence-sense-v0-debug.apk";
const MAC =
  "https://github.com/seeker71/Coherence-Network/releases/download/coherence-sense-v0/coherence-sense-mac.zip";

type OS = "mac" | "android" | "ios" | "other";

function detectOS(): OS {
  if (typeof navigator === "undefined") return "other";
  const ua = navigator.userAgent.toLowerCase();
  if (/android/.test(ua)) return "android";
  if (/iphone|ipad|ipod/.test(ua)) return "ios";
  if (/macintosh|mac os x/.test(ua)) return "mac";
  return "other";
}

function Card({
  kind,
  href,
  primary,
}: {
  kind: "android" | "ios" | "mac";
  href: string;
  primary: boolean;
}) {
  const isAndroid = kind === "android";
  const isIOS = kind === "ios";
  return (
    <a
      href={href}
      className={[
        "block rounded-xl border p-5 transition",
        primary
          ? "border-emerald-500/60 bg-emerald-500/5 shadow-[0_0_30px_-12px] shadow-emerald-500/40"
          : "border-white/10 bg-white/[0.02] hover:border-white/20",
      ].join(" ")}
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-neutral-500">
            {isAndroid ? "Android" : isIOS ? "iPhone" : "macOS"}
            {primary && <span className="ml-2 text-emerald-400">· your device</span>}
          </div>
          <div className="mt-1 text-lg text-neutral-100">
            {isAndroid
              ? "Coherence Sense (.apk)"
              : isIOS
                ? "iPhone presence — web + calls"
                : "Mac sense — kernel + launcher"}
          </div>
          <div className="mt-1 text-sm text-neutral-500">
            {isAndroid
              ? "The phone as a sense organ — streams its senses to the network."
              : isIOS
                ? "A first iPhone door: remembered context, mic/camera when granted, and trusted-call tel/CallKit lanes."
              : "Recognizes the stream through the Form kernel. Needs Python 3."}
          </div>
        </div>
        <div className="ml-4 text-2xl text-neutral-400">↓</div>
      </div>
    </a>
  );
}

export default function SensePage() {
  const [os, setOS] = useState<OS>("other");
  useEffect(() => setOS(detectOS()), []);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-6 py-16 text-neutral-200">
      <div className="text-xs uppercase tracking-[0.2em] text-emerald-500">Coherence · Sense</div>
      <h1 className="mt-3 text-3xl font-semibold text-neutral-50">Become a sense organ of the network.</h1>
      <p className="mt-4 max-w-xl text-neutral-400">
        Your phone becomes a trusted carried presence: it senses, remembers, informs, contributes,
        and touches the physical or digital surfaces it knows. Phone calls are the first action
        lane: relationship context before, live support during, exchange memory after.
      </p>

      <div className="mt-10 grid gap-3">
        <Card kind="android" href={APK} primary={os === "android"} />
        <Card kind="ios" href="/sense/surface" primary={os === "ios"} />
        <Card kind="mac" href={MAC} primary={os === "mac"} />
      </div>

      {os === "other" && (
        <p className="mt-4 text-sm text-neutral-500">
          On a phone? Android can install the native sense organ; iPhone can enter through the web
          presence door while the native CallKit lane lands. On a Mac? Grab the kernel + launcher above.
        </p>
      )}

      <Link
        href="/sense/surface"
        className="mt-6 inline-flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/5 px-4 py-2.5 text-sm text-emerald-200 transition-colors hover:border-emerald-400/60 hover:bg-emerald-500/10"
      >
        See what a node perceives — the live surface
        <span className="text-emerald-400/60">→</span>
      </Link>
      <p className="mt-2 text-xs text-neutral-600">
        Heard text + translation, who-can-hear-whom, the room&apos;s echo, place, what&apos;s
        playing, and the trusted-call floor — computed from proven Form recipes where the body
        already carries them.
      </p>

      <div className="mt-10 border-t border-white/10 pt-6 text-sm text-neutral-500">
        <p>
          The Android build is debug-signed — your phone will ask you to allow installing from your
          browser (Settings → unknown sources). iPhone starts with the web door and the system
          phone/CallKit lanes; the native iOS app is the next packaging step. The Mac bundle is the
          kernel binary + the proven recipes + a one-tap launcher.
        </p>
        <p className="mt-3">
          Source &amp; honest scope:{" "}
          <a
            className="text-neutral-300 underline decoration-white/20 hover:decoration-white/60"
            href="https://github.com/seeker71/Coherence-Network/tree/main/experiments/coherence-sense-android"
          >
            experiments/coherence-sense-android
          </a>
        </p>
      </div>
    </main>
  );
}
