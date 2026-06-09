// sense.hati.earth — the download door for Coherence Sense. Detects the visitor's
// device and offers the right artifact: the Android .apk (phone as a sense organ)
// or the macOS kernel + launcher (the Mac that recognizes through the Form kernel).
"use client";

import { useEffect, useState } from "react";

const APK =
  "https://github.com/seeker71/Coherence-Network/releases/download/coherence-sense-v0/coherence-sense-v0-debug.apk";
const MAC =
  "https://github.com/seeker71/Coherence-Network/releases/download/coherence-sense-v0/coherence-sense-mac.zip";

type OS = "mac" | "android" | "other";

function detectOS(): OS {
  if (typeof navigator === "undefined") return "other";
  const ua = navigator.userAgent.toLowerCase();
  if (/android/.test(ua)) return "android";
  if (/iphone|ipad|ipod/.test(ua)) return "other"; // iOS: nothing to offer yet
  if (/macintosh|mac os x/.test(ua)) return "mac";
  return "other";
}

function Card({
  kind,
  href,
  primary,
}: {
  kind: "android" | "mac";
  href: string;
  primary: boolean;
}) {
  const isAndroid = kind === "android";
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
            {isAndroid ? "Android" : "macOS"}
            {primary && <span className="ml-2 text-emerald-400">· your device</span>}
          </div>
          <div className="mt-1 text-lg text-neutral-100">
            {isAndroid ? "Coherence Sense (.apk)" : "Mac sense — kernel + launcher"}
          </div>
          <div className="mt-1 text-sm text-neutral-500">
            {isAndroid
              ? "The phone as a sense organ — streams its senses to the network."
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
        Your phone reads its senses — motion, light, orientation — and streams them to a Mac that
        recognizes the field through the Form kernel: the two synchronizing, predicting, surfacing
        what is alive in the room. Nothing streams until you connect.
      </p>

      <div className="mt-10 grid gap-3">
        <Card kind="android" href={APK} primary={os === "android"} />
        <Card kind="mac" href={MAC} primary={os === "mac"} />
      </div>

      {os === "other" && (
        <p className="mt-4 text-sm text-neutral-500">
          On a phone? Open this on Android to install. On a Mac? Grab the kernel + launcher above.
        </p>
      )}

      <div className="mt-10 border-t border-white/10 pt-6 text-sm text-neutral-500">
        <p>
          The Android build is debug-signed — your phone will ask you to allow installing from your
          browser (Settings → unknown sources). The Mac bundle is the kernel binary + the proven
          recipes + a one-tap launcher.
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
