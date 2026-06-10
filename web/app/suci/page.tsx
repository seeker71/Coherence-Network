// suci.hati.earth — the door to Hati Suci, the resident-service nervous system
// (first Light Hub membrane). Today it opens the web experience; the android-native
// app (merging Coherence Sense with the resident/staff/friends flows) is the next phase.
"use client";

import { useEffect, useState } from "react";

const APK_SENSE =
  "https://github.com/seeker71/Coherence-Network/releases/download/coherence-sense-v0/coherence-sense-v0-debug.apk";

type OS = "android" | "other";

function detectOS(): OS {
  if (typeof navigator === "undefined") return "other";
  return /android/.test(navigator.userAgent.toLowerCase()) ? "android" : "other";
}

export default function SuciPage() {
  const [os, setOS] = useState<OS>("other");
  useEffect(() => setOS(detectOS()), []);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-6 py-16 text-neutral-200">
      <div className="text-xs uppercase tracking-[0.2em] text-amber-500">Hati · Suci</div>
      <h1 className="mt-3 text-3xl font-semibold text-neutral-50">The hub remembers you.</h1>
      <p className="mt-4 max-w-xl text-neutral-400">
        Hati Suci is the resident-service nervous system of the first Light Hub — residents, staff,
        and friends, each held by a light identity that a device token remembers. Seeing is open to
        any registered cell; asking, tending, and settling are vouched by a resident.
      </p>

      <div className="mt-10 grid gap-3">
        <a
          href="/hati-suci"
          className="block rounded-xl border border-amber-500/50 bg-amber-500/5 p-5 transition hover:border-amber-400/70"
        >
          <div className="text-xs uppercase tracking-wider text-neutral-500">Open now · web</div>
          <div className="mt-1 text-lg text-neutral-100">Enter Hati Suci →</div>
          <div className="mt-1 text-sm text-neutral-500">
            The living resident/staff/friends membrane, mobile-first and bilingual.
          </div>
        </a>

        <div className="block rounded-xl border border-white/10 bg-white/[0.02] p-5">
          <div className="text-xs uppercase tracking-wider text-neutral-500">
            Android app · next phase
          </div>
          <div className="mt-1 text-lg text-neutral-300">Hati Suci, native</div>
          <div className="mt-1 text-sm text-neutral-500">
            The web membrane is merging with Coherence Sense into one android-native app — the hub
            that both senses the field and holds its people. Coming next.
          </div>
          {os === "android" && (
            <a
              href={APK_SENSE}
              className="mt-3 inline-block text-sm text-emerald-400 underline decoration-emerald-500/30 hover:decoration-emerald-400"
            >
              Meanwhile, try Coherence Sense (the senses half) →
            </a>
          )}
        </div>
      </div>

      <div className="mt-10 border-t border-white/10 pt-6 text-sm text-neutral-500">
        A door of the same body as{" "}
        <a
          className="text-neutral-300 underline decoration-white/20 hover:decoration-white/60"
          href="https://sense.hati.earth"
        >
          sense.hati.earth
        </a>
        .
      </div>
    </main>
  );
}
