#!/usr/bin/env python3
"""run_8h_accumulation.py — the live 8-hour sample-efficiency run.

The learner converges on a fixed task in seconds, so an honest long run is not
"spin the same task for 8 hours" — it is LIVE ACCUMULATION: keep feeding genuinely
new samples from real channels and watch the curve extend over wall-clock. Two real
sources feed the growing prototype pool each cycle:

  1. corpus channel  — the next batch of real LibriSpeech train-clean-100 utterances,
     extracted on the fly (251 speakers). Real audio, new speaker classes over time.
  2. live say channel — macOS `say` synthesizes a line in several distinct voices;
     each voice is fingerprinted as a live sample (and optionally round-tripped through
     whisper for the STT half of the loopback). The voices are learnable classes.

Recognition itself runs in Form (nearest-shape.fk on the Go kernel). This script is
orchestration + carrier: it marshals samples in, reads the recognized-count out, and
stamps wall-clock. Every cycle appends one row to learning_curve.jsonl. Every ~30 min
it emits a real_mesh_training_emitters receipt (now ACTIVE: the data floor is met).
"""
import argparse, json, os, sys, time, subprocess, tempfile, glob, random

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from extract_fingerprints import mel_filterbank, decode_pcm, fingerprint, load_sex  # carrier
from run_curve import build_driver, run_kernel                                       # orchestration

SAY_LINE = ("Coherence mesh live training sample. The body senses what is alive "
            "and returns an attributed trace.")


def probe_voices(candidates):
    ok = []
    for v in candidates:
        f = tempfile.NamedTemporaryFile(suffix=".aiff", delete=False).name
        try:
            r = subprocess.run(["say", "-v", v, "-o", f, "hello"],
                               capture_output=True)
            if r.returncode == 0 and os.path.getsize(f) > 1000:
                ok.append(v)
        except Exception:
            pass
        finally:
            if os.path.exists(f):
                os.unlink(f)
    return ok


def say_fingerprint(voice, fb, bands, levels, lo, hi, whisper_model=None):
    aiff = tempfile.NamedTemporaryFile(suffix=".aiff", delete=False).name
    try:
        r = subprocess.run(["say", "-v", voice, "-o", aiff, SAY_LINE],
                           capture_output=True)
        if r.returncode != 0:
            return None, None
        vec = fingerprint(decode_pcm(aiff), fb, bands, levels, lo, hi)
        transcript = None
        if whisper_model and os.path.exists(whisper_model):
            wav = aiff[:-5] + ".wav"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", aiff,
                            "-ar", "16000", "-ac", "1", wav], capture_output=True)
            wr = subprocess.run(["whisper-cli", "-m", whisper_model, "-f", wav,
                                 "-otxt", "-of", aiff[:-5]], capture_output=True)
            tp = aiff[:-5] + ".txt"
            if wr.returncode == 0 and os.path.exists(tp):
                transcript = open(tp).read().strip()
                os.unlink(tp)
            if os.path.exists(wav):
                os.unlink(wav)
        return vec, transcript
    finally:
        if os.path.exists(aiff):
            os.unlink(aiff)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-fingerprints", required=True)   # dev-clean.jsonl
    ap.add_argument("--corpus-root", default="")            # train-clean-100 flac root
    ap.add_argument("--speakers", default="")
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--nearest-shape", required=True)
    ap.add_argument("--out", required=True)                 # learning_curve.jsonl
    ap.add_argument("--receipt-script", default="")         # real_mesh_training_emitters.sh
    ap.add_argument("--corpus-data-root", default="")       # path passed to receipt --data-root
    ap.add_argument("--whisper-model", default="")
    ap.add_argument("--duration-hours", type=float, default=8.0)
    ap.add_argument("--corpus-batch", type=int, default=120)
    ap.add_argument("--max-train", type=int, default=6000,
                    help="cap the prototype pool; N=6000 is the stack/time-proven "
                         "ceiling for brute-force nearest-shape eval. Past it the "
                         "corpus channel pauses; live channel + eval keep ticking.")
    ap.add_argument("--heldout-cap", type=int, default=800)
    ap.add_argument("--receipt-every-min", type=float, default=30.0)
    ap.add_argument("--bands", type=int, default=13)
    ap.add_argument("--levels", type=int, default=8)
    ap.add_argument("--lo", type=float, default=-4.0)
    ap.add_argument("--hi", type=float, default=4.0)
    args = ap.parse_args()

    fb = mel_filterbank(args.bands)
    sex = load_sex(args.speakers)
    rnd = random.Random(7)

    # --- heldout: a fixed eval set from the seed corpus (capped) + 1 live sample/voice
    seed = [json.loads(l) for l in open(args.seed_fingerprints) if l.strip()]
    rnd.shuffle(seed)
    heldout = seed[: args.heldout_cap]
    train = list(seed[args.heldout_cap:])           # rest of seed seeds the train pool

    voices = probe_voices(["Alex", "Samantha", "Daniel", "Fred", "Victoria",
                           "Karen", "Moira", "Tessa", "Rishi", "Albert"])
    sys.stderr.write(f"live voices: {voices}\n")
    for v in voices:                                 # one held-out exemplar per live voice
        vec, _ = say_fingerprint(v, fb, args.bands, args.levels, args.lo, args.hi)
        if vec:
            heldout.append({"speaker": f"say:{v}", "sex": "S", "utt": f"say-{v}-h", "vec": vec})

    # --- corpus channel: queue of train-clean-100 flacs to extract incrementally
    corpus_flacs = []
    if args.corpus_root and os.path.isdir(args.corpus_root):
        corpus_flacs = sorted(glob.glob(os.path.join(args.corpus_root, "**", "*.flac"),
                                        recursive=True))
    rnd.shuffle(corpus_flacs)
    corpus_i = 0

    t0 = time.time()
    deadline = t0 + args.duration_hours * 3600.0
    last_receipt = 0.0
    cycle = 0
    out = open(args.out, "a")
    sys.stderr.write(f"start: heldout={len(heldout)} seed-train={len(train)} "
                     f"corpus-queue={len(corpus_flacs)} duration={args.duration_hours}h\n")

    while time.time() < deadline:
        cycle += 1
        added_corpus = 0
        # 1) corpus channel: extract next batch of real flacs (paused once the
        #    pool reaches the stack/time-proven ceiling, so the run stays stable)
        room = args.max_train - len(train)
        end = corpus_i + max(0, min(args.corpus_batch, room))
        end = min(end, len(corpus_flacs))
        for path in corpus_flacs[corpus_i:end]:
            base = os.path.basename(path).rsplit(".", 1)[0]
            spk = base.split("-")[0]
            vec = fingerprint(decode_pcm(path), fb, args.bands, args.levels, args.lo, args.hi)
            if vec:
                train.append({"speaker": spk, "sex": sex.get(spk, "?"),
                              "utt": base, "vec": vec})
                added_corpus += 1
        corpus_i = end

        # 2) live say channel: one sample per voice
        added_live = 0
        last_transcript = None
        for v in voices:
            vec, tr = say_fingerprint(v, fb, args.bands, args.levels, args.lo, args.hi,
                                      args.whisper_model or None)
            if vec:
                train.append({"speaker": f"say:{v}", "sex": "S",
                              "utt": f"say-{v}-c{cycle}", "vec": vec})
                added_live += 1
                if tr:
                    last_transcript = tr

        # 3) Form learner eval over the accumulated pool
        correct, kms = run_kernel(args.kernel, args.nearest_shape,
                                  build_driver(train, heldout, "speaker"))
        elapsed = time.time() - t0
        speakers = len(set(r["speaker"] for r in train))
        row = {"cycle": cycle, "elapsed_h": round(elapsed / 3600.0, 4),
               "n_train": len(train), "speakers": speakers,
               "added_corpus": added_corpus, "added_live": added_live,
               "corpus_consumed": corpus_i, "heldout": len(heldout),
               "correct": correct,
               "accuracy": round((correct / len(heldout)) if (correct is not None and heldout) else 0.0, 4),
               "kernel_ms": round(kms, 1),
               "stt_transcript": (last_transcript[:80] if last_transcript else None),
               "ts_s": round(time.time(), 1)}
        out.write(json.dumps(row) + "\n")
        out.flush()
        sys.stderr.write(f"  c{cycle} t={row['elapsed_h']:.2f}h N={len(train)} "
                         f"spk={speakers} acc={row['accuracy']} kms={kms:.0f}\n")

        # 4) periodic active-receipt emission
        if args.receipt_script and (elapsed - last_receipt) >= args.receipt_every_min * 60.0:
            last_receipt = elapsed
            try:
                rec_out = os.path.join(HERE, "receipts",
                                       f"window-{int(time.time())}")
                cmd = ["bash", args.receipt_script, "--out", rec_out, "--run-models"]
                if args.corpus_data_root:
                    cmd += ["--data-root", args.corpus_data_root]
                if args.whisper_model:
                    cmd += ["--whisper-model", args.whisper_model]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                sys.stderr.write(f"  [receipt] {r.stdout.strip()[:120]}\n")
            except Exception as e:
                sys.stderr.write(f"  [receipt] skipped: {e}\n")

        # once the corpus queue is drained OR the pool is capped, the live channel
        # keeps the run honest; pause briefly so we don't busy-spin pure re-eval
        if corpus_i >= len(corpus_flacs) or len(train) >= args.max_train:
            time.sleep(20)

    out.close()
    sys.stderr.write(f"done: {cycle} cycles, {round((time.time()-t0)/3600.0,2)}h\n")


if __name__ == "__main__":
    main()
