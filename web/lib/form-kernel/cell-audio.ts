// cell-audio.ts — every cell has a voice.
//
// A cell's pitch is keyed to its *blueprint*, so two cells that are
// structurally identical (same blueprintKey, by the substrate's
// content-addressing) ring the *same note*. The same coherence the
// blueprint-shader gives the eye — twins shimmer alike — the ear gets too:
// twins sound alike. Hearing a recipe play through its cells reveals its
// structure as melody and rhythm; repeated structure becomes a repeated motif.
//
// Vision concepts carry a real `hz` (the solfeggio frequencies), so they sound
// their literal frequency — lc-rest emits 174Hz, lc-love 528Hz. Recipe cells
// have no stated frequency, so their pitch is drawn from a major-pentatonic
// scale (any combination stays consonant) indexed by blueprint.

import type { SpaceCell } from "./space";

// major pentatonic — forgiving: any subset sounds musical together
const PENTATONIC = [0, 2, 4, 7, 9];
const BASE_HZ = 220; // A3

function hashKey(key: string): number {
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// The cell's voice — its literal hz if it has one, else a blueprint-keyed
// pentatonic pitch across three octaves. Pure + deterministic: same blueprint
// always returns the same frequency.
export function pitchForCell(cell: SpaceCell): number {
  if (cell.hz && cell.hz > 0) return cell.hz;
  const span = PENTATONIC.length * 3;
  const idx = hashKey(cell.blueprintKey) % span;
  const octave = Math.floor(idx / PENTATONIC.length);
  const semis = PENTATONIC[idx % PENTATONIC.length]! + octave * 12;
  return BASE_HZ * Math.pow(2, semis / 12);
}

// ---------------------------------------------------------------------------
// Audio engine — a lazily-created AudioContext, unlocked on first gesture.
// ---------------------------------------------------------------------------

let ctx: AudioContext | null = null;

function getCtx(): AudioContext | null {
  if (typeof window === "undefined") return null;
  if (!ctx) {
    const AC =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
  }
  return ctx;
}

// Resume the context inside a user gesture (browsers start it suspended).
export function unlockAudio(): void {
  const c = getCtx();
  if (c && c.state === "suspended") void c.resume();
}

export interface ToneOptions {
  dur?: number;
  gain?: number;
}

// A soft glassy bell: fundamental + octave + fifth harmonics, quick attack,
// exponential decay. Pleasant, non-fatiguing, lets many tones overlap.
export function playTone(freq: number, opts: ToneOptions = {}): void {
  const c = getCtx();
  if (!c) return;
  if (c.state === "suspended") void c.resume();
  const { dur = 1.1, gain = 0.16 } = opts;
  const t = c.currentTime;

  const master = c.createGain();
  master.gain.setValueAtTime(0.0001, t);
  master.gain.linearRampToValueAtTime(gain, t + 0.012);
  master.gain.exponentialRampToValueAtTime(0.0001, t + dur);

  const lp = c.createBiquadFilter();
  lp.type = "lowpass";
  lp.frequency.value = Math.min(8000, freq * 6);
  master.connect(lp);
  lp.connect(c.destination);

  for (const [mult, amp] of [
    [1, 1],
    [2, 0.38],
    [3, 0.16],
  ] as const) {
    const o = c.createOscillator();
    o.type = "sine";
    o.frequency.value = freq * mult;
    const g = c.createGain();
    g.gain.value = amp;
    o.connect(g);
    g.connect(master);
    o.start(t);
    o.stop(t + dur);
  }
}

let seqTimers: number[] = [];

// Play a list of cells in order — the recipe heard as a melody. Returns a
// stop() that cancels any pending notes.
export function playSequence(
  cells: SpaceCell[],
  interval = 0.17,
  cap = 64,
): () => void {
  unlockAudio();
  stopSequence();
  const voices = cells.slice(0, cap);
  voices.forEach((cell, i) => {
    const id = window.setTimeout(
      () => playTone(pitchForCell(cell), { dur: Math.max(0.45, interval * 2.4) }),
      i * interval * 1000,
    );
    seqTimers.push(id);
  });
  return stopSequence;
}

export function stopSequence(): void {
  for (const id of seqTimers) window.clearTimeout(id);
  seqTimers = [];
}
