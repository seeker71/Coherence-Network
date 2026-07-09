#!/usr/bin/env python3
"""dialog-distill.py — the dialog domain's dataset builder. A dialog sample is a labelled
speaker TURN in a conversation: who spoke, what was said, and the turn before it (the context
that makes it a dialog and not a lone line). It reads the room transcripts the speech organ
already accumulates (~/Documents/Coherence-private/room-transcripts/room-YYYYMMDD.txt, lines
`[HH:MM:SS] speaker: text`) and folds each real turn into a store toward the 10k target.

The recognized STREAM for this domain is the set of speakers currently in dialog — which is
exactly the speaker book, seen through the lens of conversation.

  dialog-distill.py            # drain new transcript lines into the dialog store
  dialog-distill.py board      # emit the training-board line for `dialog`
"""
import json, os, sys, glob, hashlib, time

TDIR = os.path.expanduser("~/Documents/Coherence-private/room-transcripts")
STORE = os.path.expanduser("~/.coherence-network/dialog-training")
SAMPLES = os.path.join(STORE, "turns.jsonl")
SEEN = os.path.join(STORE, ".seen")
TARGET = 10000

def load_seen():
    return set(open(SEEN).read().split()) if os.path.exists(SEEN) else set()

def parse_line(line):
    # [HH:MM:SS] speaker: text
    line = line.rstrip("\n")
    if not line.startswith("["):
        return None
    try:
        ts_end = line.index("]")
        rest = line[ts_end + 1:].strip()
        speaker, text = rest.split(":", 1)
        return (line[1:ts_end], speaker.strip(), text.strip())
    except ValueError:
        return None

def distill():
    os.makedirs(STORE, exist_ok=True)
    seen = load_seen()
    new_seen, n = [], 0
    prev = None
    with open(SAMPLES, "a") as out:
        for path in sorted(glob.glob(os.path.join(TDIR, "room-*.txt"))):
            for raw in open(path):
                parsed = parse_line(raw)
                if not parsed:
                    continue
                ts, speaker, text = parsed
                if not text or speaker in ("", "unknown", "?"):
                    prev = (speaker, text); continue
                key = hashlib.sha1(f"{path}|{ts}|{speaker}|{text}".encode()).hexdigest()[:16]
                if key in seen:
                    prev = (speaker, text); continue
                rec = {"id": key, "ts": ts, "speaker": speaker, "text": text,
                       "prev_speaker": prev[0] if prev else None,
                       "prev_text": prev[1] if prev else None,
                       "source": os.path.basename(path), "distill_state": "turn-observed"}
                out.write(json.dumps(rec) + "\n")
                new_seen.append(key); n += 1
                prev = (speaker, text)
    if new_seen:
        with open(SEEN, "a") as s:
            s.write("\n".join(new_seen) + "\n")
    total = sum(1 for _ in open(SAMPLES)) if os.path.exists(SAMPLES) else 0
    print(f"[dialog-distill] +{n} turns this pass · {total}/{TARGET}")

def board():
    total = sum(1 for _ in open(SAMPLES)) if os.path.exists(SAMPLES) else 0
    speakers = []
    if os.path.exists(SAMPLES):
        seen = []
        for line in open(SAMPLES):
            sp = json.loads(line).get("speaker")
            if sp and sp not in seen:
                seen.append(sp)
        speakers = seen[-5:]
    state = "observing turns" if total else "pending — no transcript turns yet"
    # name|samples/target|parity|state|stream-csv
    print(f"dialog|{total}/{TARGET}|-|{state}|{','.join(speakers)}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "board":
        board()
    else:
        distill()
