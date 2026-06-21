"use client";

// PerceptionSurface — the node's world-perception surface, rendered from the
// proven world-perception.fk recipe (four-way 255) walked live in this browser.
//
// Every value on the surface (which transcript source wins, who can hear whom,
// the room's echo distance, are we moving, does a broadcast reach a neighbour) is
// computed by walking the recipe on the in-browser TS Form kernel — the SAME
// kernel that proves the band. The scene is a sensed snapshot standing in for the
// phone's microphone / radios / camera until those carriers are wired; the LOGIC
// is the body's, not a TypeScript reimplementation.

import { useMemo, useState } from "react";
import {
  Cpu,
  Ear,
  Home,
  Languages,
  MapPin,
  Mic,
  Radio,
  Ruler,
  ScanSearch,
  Cloud,
} from "lucide-react";
import { wpRun, type WpRun } from "@/lib/form-kernel/world-perception-recipe";
import { recRun } from "@/lib/form-kernel/recognition-recipe";

// Sanitize a string for embedding inside a Form double-quoted literal.
const q = (s: string) => s.replace(/["()\\]/g, "").trim();

type Ping = { emitter: string; correlation: number; threshold: number };

type Scene = {
  id: string;
  label: string;
  note: string;
  transcript: string;
  oracleConf: number;
  oracleCost: number;
  nativeConf: number;
  nativeCost: number;
  floor: number;
  pings: Ping[];
  echoTofUs: number[];
  geo: Array<[number, number]>;
  geoThreshold: number;
  broadcastMedia: string;
  broadcastTitle: string;
};

// Three sensed snapshots. Costs encode the sovereignty gradient: the oracle
// (rented frontier mind) is dear; the native path is cheap, so it earns the slot
// the moment it clears the confidence floor.
const SCENES: Scene[] = [
  {
    id: "quiet-room",
    label: "Quiet room",
    note: "One neighbour nearby, no movement. The native ear has learned this voice — it holds the slot.",
    transcript: "the source is native",
    oracleConf: 90,
    oracleCost: 100,
    nativeConf: 88,
    nativeCost: 5,
    floor: 80,
    pings: [{ emitter: "node-aria", correlation: 78, threshold: 50 }],
    echoTofUs: [2000, 5200],
    geo: [
      [0, 0],
      [0, 0],
      [1, 1],
    ],
    geoThreshold: 10,
    broadcastMedia: "",
    broadcastTitle: "",
  },
  {
    id: "in-the-car",
    label: "In the car",
    note: "Travelling — the location series jumps. A podcast is playing; the signal is offered to any node that can hear.",
    transcript: "the kernel is native",
    oracleConf: 90,
    oracleCost: 100,
    nativeConf: 86,
    nativeCost: 5,
    floor: 80,
    pings: [{ emitter: "node-phone-2", correlation: 64, threshold: 50 }],
    echoTofUs: [900],
    geo: [
      [0, 0],
      [40, 12],
      [120, 60],
    ],
    geoThreshold: 10,
    broadcastMedia: "yt:podcast-7f3",
    broadcastTitle: "a podcast, playing aloud",
  },
  {
    id: "gathering",
    label: "A gathering",
    note: "Many voices, a large room, music in the air — the kind of scene the phone met at the gathering. The native ear is still learning the crowd, so the oracle is asked to hold this one.",
    transcript: "many voices speaking at once",
    oracleConf: 92,
    oracleCost: 100,
    nativeConf: 61,
    nativeCost: 5,
    floor: 80,
    pings: [
      { emitter: "node-aria", correlation: 71, threshold: 50 },
      { emitter: "node-kai", correlation: 58, threshold: 50 },
      { emitter: "node-far", correlation: 22, threshold: 50 },
    ],
    echoTofUs: [12000, 28000, 41000],
    geo: [
      [0, 0],
      [1, 0],
      [0, 1],
    ],
    geoThreshold: 10,
    broadcastMedia: "yt:drum-circle",
    broadcastTitle: "live drums, in the room",
  },
];

const TONGUES = [
  { id: "en", label: "English" },
  { id: "id", label: "Indonesian" },
  { id: "de", label: "Deutsch" },
  { id: "es", label: "Español" },
];

// Recognition — one recipe, four libraries. A reading vector (a quantized
// fingerprint) matched against a library of known signatures. The recipe never
// changes; only the library differs per sense. Readings here are sample
// fingerprints, the way the scenes are sample snapshots — the logic is the
// proven body's (nearest-shape + recognition, four-way 63).
const REC_SENSES = [
  { kind: "place", label: "Place", from: "wifi fingerprint", reading: "(list 5 5 5 5)",
    library: '(list (list "home" (list 5 5 5 5)) (list "cafe" (list 1 8 1 8)) (list "office" (list 9 1 9 1)))' },
  { kind: "room", label: "Room", from: "echo signature", reading: "(list 2 7 2 7)",
    library: '(list (list "kitchen" (list 2 7 2 7)) (list "hall" (list 9 9 1 1)))' },
  { kind: "who", label: "Who", from: "face · voice", reading: "(list 3 1 4 1)",
    library: '(list (list "aria" (list 3 1 4 1)) (list "kai" (list 8 8 8 8)))' },
  { kind: "what", label: "What", from: "sound · vision", reading: "(list 6 2 6 2)",
    library: '(list (list "dog" (list 6 2 6 2)) (list "cat" (list 1 1 9 9)) (list "bird" (list 7 7 7 1)))' },
] as const;

type Surface = {
  transcript: { text: string; source: string; isHome: boolean; conf: string };
  audibility: Array<{ emitter: string; heard: boolean; strength: number }>;
  walls: number[]; // distances in mm
  moving: boolean;
  broadcast: { media: string; title: string; reaches: number } | null;
  proof: { walks: number; ms: number; calls: number };
};

function accumulate(acc: { walks: number; ms: number; calls: number }, r: WpRun) {
  acc.walks += r.walks;
  acc.ms += r.ms;
  acc.calls += 1;
  return r.value;
}

export function PerceptionSurface() {
  const [sceneId, setSceneId] = useState(SCENES[0].id);
  const [transcript, setTranscript] = useState(SCENES[0].transcript);
  const [tongue, setTongue] = useState<string | null>(null);

  const scene = SCENES.find((s) => s.id === sceneId) ?? SCENES[0];

  const pickScene = (s: Scene) => {
    setSceneId(s.id);
    setTranscript(s.transcript);
    setTongue(null);
  };

  const surface: Surface = useMemo(() => {
    const proof = { walks: 0, ms: 0, calls: 0 };
    const text = q(transcript) || "(silence)";

    const oracle = `(wp-tc "${text}" ${scene.oracleConf} ${scene.oracleCost} "oracle:whisper-cli")`;
    const native = `(wp-tc "${text}" ${scene.nativeConf} ${scene.nativeCost} "form-native:whisper")`;
    const chosen = `(wp-transcript-select ${oracle} ${native} ${scene.floor})`;

    const source = accumulate(proof, wpRun(`(wp-source (wp-transcript-channel ${oracle} ${native} ${scene.floor}))`));
    const conf = accumulate(proof, wpRun(`(wp-tc-conf ${chosen})`));

    const audibility = scene.pings.map((p) => {
      const edge = `(wp-audibility-edge "me" "${p.emitter}" ${p.correlation} ${p.threshold})`;
      const heard = accumulate(proof, wpRun(`(wp-edge-heard ${edge})`));
      return { emitter: p.emitter, heard: heard === "1", strength: p.correlation };
    });

    const walls = scene.echoTofUs.map((tof) =>
      Number(accumulate(proof, wpRun(`(wp-echo-distance-mm ${tof})`))),
    );

    const geoList = `(list ${scene.geo.map(([a, b]) => `(list ${a} ${b})`).join(" ")})`;
    const moved = accumulate(proof, wpRun(`(wp-value (wp-place-channel ${geoList} ${scene.geoThreshold}))`));

    let broadcast: Surface["broadcast"] = null;
    if (scene.broadcastMedia) {
      // a broadcast reaches each neighbour whose audibility edge can hear us
      let reaches = 0;
      for (const p of scene.pings) {
        const edge = `(wp-audibility-edge "me" "${p.emitter}" ${p.correlation} ${p.threshold})`;
        const r = accumulate(proof, wpRun(`(wp-broadcast-reaches? ${edge})`));
        if (r === "1") reaches += 1;
      }
      broadcast = { media: scene.broadcastMedia, title: scene.broadcastTitle, reaches };
    }

    return {
      transcript: { text, source, isHome: source === "form-native:whisper", conf },
      audibility,
      walls,
      moving: moved === "1",
      broadcast,
      proof,
    };
  }, [scene, transcript]);

  // Translation is structurally one tap away (wp-can-translate? proves it on any
  // transcript channel). Computed live when a tongue is chosen.
  const translation = useMemo(() => {
    if (!tongue) return null;
    const text = q(transcript) || "(silence)";
    const chan = `(wp-channel "transcript" "${text}" 88 "form-native:whisper")`;
    const can = wpRun(`(wp-can-translate? ${chan})`).value === "1";
    const tongueOut = wpRun(`(wp-translation-tongue (wp-translate ${chan} "${tongue}"))`).value;
    return { can, tongueOut };
  }, [tongue, transcript]);

  // Recognition — one recipe, four libraries, all walked on the same kernel.
  const recognized = useMemo(
    () =>
      REC_SENSES.map((s) => ({
        label: s.label,
        from: s.from,
        result: recRun(
          `(rec-label (recognize "${s.kind}" ${s.reading} ${s.library} "${s.from}"))`,
        ).value,
      })),
    [],
  );

  const mm = (v: number) => (v / 1000).toFixed(2);

  return (
    <div className="grid gap-6 lg:grid-cols-[0.82fr_1.18fr]">
      {/* Controls + proof */}
      <div className="space-y-4">
        <div className="space-y-3 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
          <p className="text-xs uppercase tracking-[0.22em] text-amber-300/75">Sensed scene</p>
          <div className="grid gap-2">
            {SCENES.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => pickScene(s)}
                className={`rounded-lg border px-3 py-2.5 text-left transition-colors ${
                  sceneId === s.id
                    ? "border-amber-400/50 bg-amber-500/10 text-amber-100"
                    : "border-stone-800/50 bg-stone-950/35 text-stone-300 hover:border-amber-500/35 hover:text-amber-200"
                }`}
              >
                <span className="text-sm font-medium">{s.label}</span>
                <span className="mt-1 block text-xs leading-relaxed text-stone-500">{s.note}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2 rounded-xl border border-stone-800/50 bg-stone-950/35 p-4">
          <label htmlFor="heard-text" className="text-xs uppercase tracking-[0.18em] text-stone-500">
            What was heard
          </label>
          <textarea
            id="heard-text"
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            rows={2}
            className="w-full resize-y rounded-xl border border-stone-800/50 bg-stone-950/80 p-3 text-sm text-stone-200 transition-colors focus:border-amber-500/40 focus:outline-none"
            spellCheck={false}
          />
          <p className="text-xs leading-relaxed text-stone-500">
            Edit the heard text and the surface re-decides live — which source wins, what the
            translation channel carries.
          </p>
        </div>

        <div className="rounded-xl border border-teal-500/20 bg-teal-500/5 p-4 text-xs leading-relaxed text-teal-100/80">
          <div className="flex items-center gap-2 text-teal-200">
            <Cpu className="h-4 w-4" aria-hidden="true" />
            <span className="font-medium">Computed, not claimed</span>
          </div>
          <p className="mt-2 text-stone-400">
            Every value on the surface was just walked through{" "}
            <code className="text-teal-300/80">world-perception.fk</code> on the in-browser
            TypeScript Form kernel — the same kernel that proves the band{" "}
            <span className="text-teal-200">four-way (255)</span>.
          </p>
          <div className="mt-2 grid grid-cols-3 gap-2 font-mono">
            <div>
              <div className="text-stone-500">calls</div>
              <div className="text-teal-200">{surface.proof.calls}</div>
            </div>
            <div>
              <div className="text-stone-500">walks</div>
              <div className="text-teal-200">{surface.proof.walks}</div>
            </div>
            <div>
              <div className="text-stone-500">time</div>
              <div className="text-teal-200">{surface.proof.ms.toFixed(1)}ms</div>
            </div>
          </div>
        </div>
      </div>

      {/* The surface */}
      <div className="space-y-3 rounded-2xl border border-stone-800/60 bg-stone-950/40 p-4">
        {/* Transcript + translate */}
        <article className="rounded-xl border border-stone-800/50 bg-stone-900/40 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-stone-500">
              <Mic className="h-3.5 w-3.5 text-amber-300/75" aria-hidden="true" />
              Heard
            </div>
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                surface.transcript.isHome
                  ? "bg-emerald-500/10 text-emerald-300"
                  : "bg-stone-700/30 text-stone-300"
              }`}
              title={
                surface.transcript.isHome
                  ? "The native (on-device) transcript cleared the floor and cost less — the mind is home."
                  : "The native ear has not cleared the floor here, so the rented oracle holds the slot. Honest floor."
              }
            >
              {surface.transcript.isHome ? (
                <>
                  <Home className="h-3 w-3" aria-hidden="true" /> home · form-native
                </>
              ) : (
                <>
                  <Cloud className="h-3 w-3" aria-hidden="true" /> rented · oracle
                </>
              )}
            </span>
          </div>
          <p className="mt-2 text-lg text-stone-100">{surface.transcript.text}</p>
          <div className="mt-1 font-mono text-xs text-stone-500">
            source {surface.transcript.source} · confidence {surface.transcript.conf}
          </div>

          <div className="mt-3 border-t border-stone-800/50 pt-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 text-xs text-stone-400">
                <Languages className="h-3.5 w-3.5 text-sky-300/75" aria-hidden="true" /> Translate:
              </span>
              {TONGUES.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTongue(t.id === tongue ? null : t.id)}
                  className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                    tongue === t.id
                      ? "border-sky-400/50 bg-sky-500/10 text-sky-200"
                      : "border-stone-800/50 bg-stone-950/40 text-stone-400 hover:border-sky-500/35 hover:text-sky-200"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
            {translation && (
              <div className="mt-2 space-y-1 rounded-lg border border-sky-500/15 bg-sky-500/5 p-3 text-xs">
                <div className="text-sky-200">
                  one tap away {translation.can ? "✓" : "✗"} · translation channel ·{" "}
                  <span className="font-mono">tongue={translation.tongueOut}</span>
                </div>
                {(tongue === "id" || tongue === "en") && (
                  <div className="text-stone-400">
                    real cross-tongue render (proven four-way in{" "}
                    <code className="text-sky-300/70">nl-translate</code>): “the source is native”
                    ⇄ “sumber adalah asli”, through the language-neutral pivot.
                  </div>
                )}
                {tongue !== "id" && tongue !== "en" && (
                  <div className="text-stone-500">
                    the affordance is proven; the word-render for this tongue is the next lane to
                    wire (a grammar + lexicon onto the same pivot).
                  </div>
                )}
              </div>
            )}
          </div>
        </article>

        {/* Who can hear whom */}
        <article className="rounded-xl border border-stone-800/50 bg-stone-900/40 p-4">
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-stone-500">
            <Ear className="h-3.5 w-3.5 text-violet-300/75" aria-hidden="true" />
            Who can hear whom — inaudible ping
          </div>
          <div className="mt-2 space-y-1.5">
            {surface.audibility.map((e) => (
              <div key={e.emitter} className="flex items-center justify-between text-sm">
                <span className="font-mono text-stone-300">me ← {e.emitter}</span>
                <span className={e.heard ? "text-emerald-300" : "text-stone-600"}>
                  {e.heard ? "heard" : "out of range"} · {e.strength}
                </span>
              </div>
            ))}
          </div>
        </article>

        {/* Room — echo-location */}
        <div className="grid gap-3 sm:grid-cols-2">
          <article className="rounded-xl border border-stone-800/50 bg-stone-900/40 p-4">
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-stone-500">
              <Ruler className="h-3.5 w-3.5 text-amber-300/75" aria-hidden="true" />
              Room — echo
            </div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-stone-200">
              {surface.walls.map((d, i) => (
                <span key={i} className="font-mono">
                  ~{mm(d)} m
                </span>
              ))}
            </div>
            <div className="mt-1 text-xs text-stone-500">surfaces, from round-trip time-of-flight</div>
          </article>

          {/* Place — travel */}
          <article className="rounded-xl border border-stone-800/50 bg-stone-900/40 p-4">
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-stone-500">
              <MapPin className="h-3.5 w-3.5 text-sky-300/75" aria-hidden="true" />
              Place
            </div>
            <p className="mt-2 text-lg text-stone-100">
              {surface.moving ? "moving" : "here, settled"}
            </p>
            <div className="mt-1 text-xs text-stone-500">
              {surface.moving ? "the location series jumped" : "the location series held still"}
            </div>
          </article>
        </div>

        {/* Broadcast */}
        {surface.broadcast && (
          <article className="rounded-xl border border-stone-800/50 bg-stone-900/40 p-4">
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-stone-500">
              <Radio className="h-3.5 w-3.5 text-rose-300/75" aria-hidden="true" />
              Playing — offered to the room
            </div>
            <p className="mt-2 text-stone-200">{surface.broadcast.title}</p>
            <div className="mt-1 font-mono text-xs text-stone-500">
              {surface.broadcast.media} · reaches {surface.broadcast.reaches}{" "}
              {surface.broadcast.reaches === 1 ? "node" : "nodes"} that can hear us
            </div>
          </article>
        )}

        {/* Recognized — one recipe, four senses */}
        <article className="rounded-xl border border-stone-800/50 bg-stone-900/40 p-4">
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-stone-500">
            <ScanSearch className="h-3.5 w-3.5 text-green-300/75" aria-hidden="true" />
            Recognized — one recipe, four senses
          </div>
          <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5">
            {recognized.map((r) => (
              <div key={r.label} className="flex items-baseline justify-between gap-2 text-sm">
                <span className="text-stone-500">{r.label}</span>
                <span className="font-mono text-stone-200">{r.result}</span>
              </div>
            ))}
          </div>
          <div className="mt-2 text-xs text-stone-500">
            place by wifi · room by echo · who by face/voice · what by sound/vision — the same{" "}
            <code className="text-green-300/70">recognize</code> recipe; only the library differs.
          </div>
        </article>
      </div>
    </div>
  );
}
