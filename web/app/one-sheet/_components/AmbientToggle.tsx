"use client";

// Optional ambient drone for /one-sheet contemplation. Generated locally
// via Web Audio API — two slow sine oscillators with a gentle low-pass
// filter and a long-attack envelope. Default off; user opts in. Honors
// prefers-reduced-motion as a soft signal to default further muted.

import { useCallback, useEffect, useRef, useState } from "react";

export function AmbientToggle() {
  const [on, setOn] = useState(false);
  const ctxRef = useRef<AudioContext | null>(null);
  const masterRef = useRef<GainNode | null>(null);
  const oscRef = useRef<OscillatorNode[]>([]);

  const start = useCallback(() => {
    if (ctxRef.current) return;
    const Ctx =
      window.AudioContext ||
      // @ts-expect-error — webkit prefix for older Safari
      window.webkitAudioContext;
    if (!Ctx) return;
    const ctx: AudioContext = new Ctx();
    ctxRef.current = ctx;

    const master = ctx.createGain();
    master.gain.value = 0;
    master.connect(ctx.destination);
    masterRef.current = master;

    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 700;
    lp.Q.value = 0.4;
    lp.connect(master);

    // Two slow sines, slightly detuned, beating gently.
    const freqs = [55, 82.5];
    freqs.forEach((f) => {
      const osc = ctx.createOscillator();
      osc.type = "sine";
      osc.frequency.value = f;
      const g = ctx.createGain();
      g.gain.value = 0.5;
      // Slow LFO on amplitude for breath-like swell.
      const lfo = ctx.createOscillator();
      lfo.type = "sine";
      lfo.frequency.value = 0.07;
      const lfoGain = ctx.createGain();
      lfoGain.gain.value = 0.18;
      lfo.connect(lfoGain).connect(g.gain);
      osc.connect(g).connect(lp);
      osc.start();
      lfo.start();
      oscRef.current.push(osc, lfo);
    });

    // Slow fade-in over four seconds.
    master.gain.linearRampToValueAtTime(0.06, ctx.currentTime + 4);
  }, []);

  const stop = useCallback(() => {
    const ctx = ctxRef.current;
    const master = masterRef.current;
    if (!ctx || !master) return;
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.setValueAtTime(master.gain.value, ctx.currentTime);
    master.gain.linearRampToValueAtTime(0, ctx.currentTime + 1.2);
    setTimeout(() => {
      oscRef.current.forEach((o) => {
        try {
          o.stop();
          o.disconnect();
        } catch {}
      });
      oscRef.current = [];
      try {
        ctx.close();
      } catch {}
      ctxRef.current = null;
      masterRef.current = null;
    }, 1300);
  }, []);

  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  const toggle = () => {
    if (on) {
      stop();
      setOn(false);
    } else {
      start();
      setOn(true);
    }
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={on}
      className="fixed bottom-5 right-5 z-30 rounded-full border border-amber-500/40 bg-stone-950/85 backdrop-blur-sm px-4 py-2.5 text-xs uppercase tracking-widest text-amber-300 hover:bg-stone-900/95 transition-colors shadow-lg"
    >
      {on ? "Stop drone" : "Add drone"}
    </button>
  );
}
