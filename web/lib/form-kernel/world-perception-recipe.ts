// world-perception-recipe.ts — the proven world-perception engine, run in-browser.
//
// SOURCE OF TRUTH: form/form-stdlib/world-perception.fk (four-way 255, Go/Rust/TS/fkwu).
// This constant is the recipe TEXT verbatim — run as-is on the same TypeScript Form
// kernel that proves the band. It is NOT a reimplementation of the logic in TS; the
// surface computes every value by walking this recipe. Keep byte-identical to the .fk
// (the web container does not ship form/, so the text lives here; refresh on change).
import { Frame, Kernel, Trace, walk } from "./vendor/kernel.ts";
import { readAll } from "./vendor/reader.ts";
export const WORLD_PERCEPTION_RECIPE = String.raw`
; world-perception.fk — the node's surface as a projection over sensed channels.
;
; One engine, senses drop in as DATA (core-abstraction-first): every sense a node
; has — a transcript, its translation, who-can-hear-whom, the room's echo, where
; we are, what we're playing — is the SAME channel shape:
;     (kind value confidence source)
; The surface (wp-surface-of) is a salience projection over channels; adding a
; sense is adding a channel recipe, never a parallel path.
;
; Three threads land here as channels in one body:
;   1. transcript + translation — text spoken shown on the surface, a tongue away.
;      Translation crosses by content-address (channels-registry registry-translate,
;      cjk-channel readings): one cell, many tongues — the tap is structural.
;   2. on-device STT as a champion-challenger slot — oracle:whisper-cli holds the
;      transcript slot until form-native:whisper clears the floor AND costs no more
;      (the mind comes home). Native STT/TTS stay teacher-led until heldout receipts
;      cross (see oracle-distillation-learning.fk, speech-model-learning.fk); this
;      engine NAMES the slot the native recipe re-earns, never fakes it runs yet.
;   3. acoustic + place sensing — node-can-hear-node by inaudible ping, echo-location
;      room map by round-trip time-of-flight, travel/place change over a geo series,
;      and broadcast-what-I'm-playing so co-located audible nodes learn from it.
;
; Proven by: form-stdlib/tests/world-perception-band.fk

(do
    ;; --- the universal channel: every sense is this shape -----------------
    (defn wp-channel (kind value confidence source) (list kind value confidence source))
    (defn wp-kind (c) (nth c 0))
    (defn wp-value (c) (nth c 1))
    (defn wp-confidence (c) (nth c 2))
    (defn wp-source (c) (nth c 3))

    (defn wp-abs (n) (if (lt n 0) (sub 0 n) n))

    ;; --- the surface: salience projection over channels ------------------
    ;; what the surface shows for a kind is its most-confident channel.
    (defn wp-most-salient-loop (kind chans best)
        (if (eq (len chans) 0) best
            (if (str_eq (wp-kind (head chans)) kind)
                (if (eq (len best) 0)
                    (wp-most-salient-loop kind (tail chans) (head chans))
                    (if (gt (wp-confidence (head chans)) (wp-confidence best))
                        (wp-most-salient-loop kind (tail chans) (head chans))
                        (wp-most-salient-loop kind (tail chans) best)))
                (wp-most-salient-loop kind (tail chans) best))))
    (defn wp-surface-of (kind chans) (wp-most-salient-loop kind chans (empty)))

    ;; --- floor + north star ----------------------------------------------
    (defn wp-floor ()
        (list
            "every sense is one channel shape: (kind value confidence source)"
            "the surface is a salience projection; a new sense is a new channel, not a path"
            "the transcript shows on the surface and its translation is always one tap away"
            "on-device STT is a named champion-challenger slot, oracle-held until native crosses"
            "acoustic, echo, place, and broadcast senses are channels in the same body"))
    (defn wp-north-star ()
        (list
            "the node perceives, transcribes, translates, and speaks at home — no gated provider"
            "architecture and weights are recipe DATA; one engine emits proof and native alike"
            "nodes sense each other and the room by inaudible sound; what one hears, all may learn"))

    ;; === THREAD 1+2 — transcript + translation, champion-challenger STT ===
    ;; a transcript candidate carries cost so the cheaper sovereign path can win.
    (defn wp-tc (text confidence cost source) (list text confidence cost source))
    (defn wp-tc-text (c) (nth c 0))
    (defn wp-tc-conf (c) (nth c 1))
    (defn wp-tc-cost (c) (nth c 2))
    (defn wp-tc-source (c) (nth c 3))

    ;; the native challenger earns the slot only when it clears the floor AND is
    ;; no more costly than the oracle champion — else the oracle honestly holds.
    (defn wp-transcript-select (champion challenger floor)
        (if (lt (wp-tc-conf challenger) floor) champion
            (if (gt (wp-tc-cost challenger) (wp-tc-cost champion)) champion
                challenger)))
    (defn wp-tc->chan (chosen)
        (wp-channel "transcript" (wp-tc-text chosen) (wp-tc-conf chosen) (wp-tc-source chosen)))
    (defn wp-transcript-channel (champion challenger floor)
        (wp-tc->chan (wp-transcript-select champion challenger floor)))

    ;; translation is ALWAYS derivable from a transcript (the tap is structural,
    ;; not an optional field). it crosses by content-address — one cell, many tongues.
    (defn wp-translate (transcript-chan target-tongue)
        (wp-channel "translation"
            (list target-tongue (wp-value transcript-chan))
            (wp-confidence transcript-chan)
            "content-address"))
    (defn wp-translation-tongue (tc) (nth (wp-value tc) 0))
    (defn wp-translation-text (tc) (nth (wp-value tc) 1))
    ;; the affordance is present for any transcript channel — proof it's one tap away.
    (defn wp-can-translate? (chan) (if (str_eq (wp-kind chan) "transcript") 1 0))

    ;; === THREAD 3 — acoustic node-sensing, echo room-map, place, broadcast ==
    ;; node-can-hear-node: an inaudible ping from an emitter, heard by a listener
    ;; above a correlation threshold, is an audibility edge (strength = correlation).
    (defn wp-audible? (correlation threshold) (if (lt correlation threshold) 0 1))
    (defn wp-audibility-edge (listener emitter correlation threshold)
        (wp-channel "audibility"
            (list listener emitter (wp-audible? correlation threshold))
            correlation
            "acoustic-ping"))
    (defn wp-edge-listener (e) (nth (wp-value e) 0))
    (defn wp-edge-emitter (e) (nth (wp-value e) 1))
    (defn wp-edge-heard (e) (nth (wp-value e) 2))

    ;; echo-location: a ping's round-trip time-of-flight (microseconds) off a wall
    ;; maps to distance. sound = 343 mm/ms; the round trip halves it.
    ;;     dist_mm = tof_us * 343 / 2000
    (defn wp-echo-distance-mm (tof-us) (div (mul tof-us 343) 2000))
    (defn wp-echo-channel (tof-us)
        (wp-channel "echo" (wp-echo-distance-mm tof-us) tof-us "acoustic-ping"))

    ;; travel / place: a location series moved if any consecutive step exceeds a
    ;; threshold (manhattan over scaled lat/lon). confidence = the count of fixes.
    (defn wp-step (a b)
        (add (wp-abs (sub (nth a 0) (nth b 0)))
             (wp-abs (sub (nth a 1) (nth b 1)))))
    (defn wp-moved-loop (pts threshold)
        (if (lt (len pts) 2) 0
            (if (gt (wp-step (head pts) (head (tail pts))) threshold) 1
                (wp-moved-loop (tail pts) threshold))))
    (defn wp-place-channel (pts threshold)
        (wp-channel "place" (wp-moved-loop pts threshold) (len pts) "geo-series"))

    ;; broadcast-what-I'm-playing: a node offers its media so co-located nodes learn
    ;; from it. an audible co-located node RECEIVES the broadcast (the edge gates it).
    (defn wp-broadcast (media-id title)
        (wp-channel "broadcast" (list media-id title) 100 "self-play"))
    (defn wp-broadcast-reaches? (edge) (wp-edge-heard edge))
)
`;

// The recipe is one (do ...) of defns. To run a witness against it we wrap the
// inner defns with the witness expression as the last form in a fresh (do ...).
function wpInnerDefns(): string {
  const r = WORLD_PERCEPTION_RECIPE;
  const after = r.slice(r.indexOf("(do") + 3);
  return after.slice(0, after.lastIndexOf(")"));
}

export function wpProgram(witness: string): string {
  return `(do ${wpInnerDefns()}
${witness})`;
}

export type WpRun = { value: string; walks: number; ms: number };

// Walk one witness against the recipe on the in-browser TS Form kernel. Returns
// the rendered value (string-quotes stripped) plus the walk count + elapsed ms so
// the surface can show that the number was computed, not hard-coded.
export function wpRun(witness: string): WpRun {
  const kernel = new Kernel({ writeStdout: () => {}, writeStderr: () => {} });
  kernel.trace = new Trace();
  const start = performance.now();
  const root = readAll(kernel, wpProgram(witness));
  const rendered = kernel.render(walk(kernel, root, new Frame(null)));
  const ms = performance.now() - start;
  const trace = kernel.trace.toJSON() as { total_walks?: number };
  const value = rendered.replace(/^"(.*)"$/s, "$1");
  return { value, walks: trace.total_walks ?? 0, ms };
}
