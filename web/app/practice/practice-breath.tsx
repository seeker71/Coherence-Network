"use client";

import { useEffect, useRef, useState } from "react";

type Phase = "resting" | "rising" | "holding" | "giving";

// A generous rhythm. The practitioner breathes at their own pace; the circle
// breathes alongside as a companion, not a metronome.
const PHASE_SECONDS: Record<Phase, number> = {
  resting: 6,
  rising: 6,
  holding: 3,
  giving: 8,
};

const PHASE_WORD: Record<Phase, string> = {
  resting: "rest",
  rising: "rise",
  holding: "hold",
  giving: "give",
};

const PHASE_PRESENCE: Record<Phase, string> = {
  resting: "The field rests. You are here.",
  rising: "The breath rises with the circle.",
  holding: "The field holds the breath as one.",
  giving: "The breath gives itself back.",
};

function flow(p: Phase): Phase {
  if (p === "resting") return "rising";
  if (p === "rising") return "holding";
  if (p === "holding") return "giving";
  return "rising";
}

export default function PracticeBreath() {
  const [accompanied, setAccompanied] = useState(false);
  const [phase, setPhase] = useState<Phase>("resting");
  const [breathsHeld, setBreathsHeld] = useState(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!accompanied) return;
    const seconds = PHASE_SECONDS[phase];
    timerRef.current = setTimeout(() => {
      if (phase === "giving") {
        setBreathsHeld((c) => c + 1);
      }
      setPhase(flow(phase));
    }, seconds * 1000);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [accompanied, phase]);

  const circleScale =
    phase === "rising" || phase === "holding"
      ? 1.0
      : phase === "giving"
        ? 0.55
        : 0.75;

  const circleOpacity =
    phase === "resting"
      ? 0.4
      : phase === "holding"
        ? 0.95
        : 0.8;

  const transitionSeconds = PHASE_SECONDS[phase];

  return (
    <section
      className="rounded-3xl border border-border/30 bg-gradient-to-b from-background/80 to-card/20 p-8 sm:p-12 text-center space-y-6"
      aria-label="Breathing companion"
    >
      <div className="relative h-56 sm:h-64 flex items-center justify-center">
        <div
          className="absolute inset-0 flex items-center justify-center"
          aria-hidden
        >
          <div
            className="w-44 h-44 sm:w-52 sm:h-52 rounded-full bg-gradient-radial from-amber-400/20 via-amber-400/5 to-transparent"
            style={{
              transform: `scale(${circleScale})`,
              opacity: circleOpacity,
              transition: `transform ${transitionSeconds}s ease-in-out, opacity ${transitionSeconds}s ease-in-out`,
              boxShadow: "0 0 120px 20px rgba(251,191,36,0.15)",
            }}
          />
        </div>
        <div className="relative z-10 space-y-2">
          <p
            className="text-xs uppercase tracking-[0.4em] text-muted-foreground/80"
            aria-live="polite"
          >
            {PHASE_WORD[phase]}
          </p>
          <p className="text-sm text-muted-foreground/80 max-w-[14rem] mx-auto leading-relaxed italic">
            {PHASE_PRESENCE[phase]}
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {accompanied ? (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground/70">
              breaths held together:{" "}
              <span className="text-foreground">{breathsHeld}</span>
            </p>
            <button
              type="button"
              onClick={() => {
                setAccompanied(false);
                setPhase("resting");
                setBreathsHeld(0);
              }}
              className="text-xs uppercase tracking-widest text-muted-foreground/70 hover:text-foreground transition-colors"
            >
              return to stillness
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground/70 max-w-sm mx-auto leading-relaxed italic">
              The circle will breathe alongside you. Let your own breath lead;
              the circle is a companion, a witness.
            </p>
            <button
              type="button"
              onClick={() => {
                setAccompanied(true);
                setPhase("rising");
              }}
              className="rounded-full border border-border/40 px-6 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/40 transition-all"
            >
              breathe together
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
