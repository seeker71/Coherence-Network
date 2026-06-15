#!/usr/bin/env bash
# live_audio_copresence_receipt.sh — live speaker→microphone FSK nonce receipt.
#
# The nonce stays local. The script keeps only a derived receipt and removes raw
# generated/captured audio after decoding.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

audio_device_index="${1:-1}"
bit_count="${2:-12}"

if ! command -v ffmpeg >/dev/null; then
    echo "FAIL missing ffmpeg"
    exit 1
fi
if ! command -v afplay >/dev/null; then
    echo "FAIL missing afplay"
    exit 1
fi
if ! command -v openssl >/dev/null; then
    echo "FAIL missing openssl"
    exit 1
fi
if ! command -v python3 >/dev/null; then
    echo "FAIL missing python3"
    exit 1
fi

ts="$(date -u +"%Y%m%dT%H%M%SZ")"
out_dir="$ROOT/.cache/live-audio-copresence/$ts"
mkdir -p "$out_dir"

nonce="$(openssl rand -hex 32)"
nonce_hash="$(printf '%s' "$nonce" | shasum -a 256 | awk '{print $1}')"
stimulus="$out_dir/stimulus.wav"
capture="$out_dir/capture.wav"
expected="$out_dir/expected.json"
receipt="$out_dir/live-audio-copresence-receipt.json"

python3 - "$stimulus" "$expected" "$nonce_hash" "$bit_count" <<'PY'
import json
import math
import struct
import sys
import wave

stimulus_path, expected_path, nonce_hash, bit_count_raw = sys.argv[1:5]
sample_rate = 48000
bit_count = max(8, min(int(bit_count_raw), 32))
bits = "".join(f"{int(ch, 16):04b}" for ch in nonce_hash)[:bit_count]
freq_zero = 1400.0
freq_one = 2200.0
bit_seconds = 0.08
preamble = [(1700.0, 0.18), (2500.0, 0.18), (1700.0, 0.12)]
lead_silence = 0.25
tail_silence = 0.25
amp = 0.42
samples: list[float] = []

def add_silence(seconds: float) -> None:
    samples.extend([0.0] * int(sample_rate * seconds))

def add_tone(freq: float, seconds: float) -> None:
    n = int(sample_rate * seconds)
    ramp = max(1, int(sample_rate * 0.008))
    for i in range(n):
        env = 1.0
        if i < ramp:
            env = i / ramp
        elif i > n - ramp:
            env = max(0.0, (n - i) / ramp)
        samples.append(amp * env * math.sin(2.0 * math.pi * freq * (i / sample_rate)))

add_silence(lead_silence)
for freq, seconds in preamble:
    add_tone(freq, seconds)
for bit in bits:
    add_tone(freq_one if bit == "1" else freq_zero, bit_seconds)
add_silence(tail_silence)

with wave.open(stimulus_path, "wb") as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(sample_rate)
    for sample in samples:
        wav.writeframesraw(struct.pack("<h", int(max(-1.0, min(1.0, sample)) * 32767)))

with open(expected_path, "w", encoding="utf-8") as f:
    json.dump(
        {
            "sample_rate": sample_rate,
            "nonce_hash": nonce_hash,
            "nonce_hash_len": len(nonce_hash),
            "bits": bits,
            "bit_count": bit_count,
            "bit_seconds": bit_seconds,
            "freq_zero": freq_zero,
            "freq_one": freq_one,
            "preamble_seconds": sum(seconds for _, seconds in preamble),
            "lead_silence_seconds": lead_silence,
        },
        f,
        indent=2,
    )
PY

record_seconds="$(
    python3 - "$expected" <<'PY'
import json
import math
import sys
with open(sys.argv[1], encoding="utf-8") as f:
    row = json.load(f)
duration = 1.2 + row["lead_silence_seconds"] + row["preamble_seconds"] + row["bit_count"] * row["bit_seconds"]
print(max(3, int(math.ceil(duration))))
PY
)"

start_ms="$(python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
)"

ffmpeg -hide_banner -nostdin -loglevel error -y \
    -f avfoundation -i ":$audio_device_index" \
    -t "$record_seconds" -ac 1 -ar 48000 "$capture" &
rec_pid=$!
sleep 0.45
afplay "$stimulus"
wait "$rec_pid"

end_ms="$(python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
)"
latency_ms=$((end_ms - start_ms))

python3 - "$capture" "$expected" "$receipt" "$latency_ms" <<'PY'
import json
import math
import sys
import wave

capture_path, expected_path, receipt_path, latency_ms_raw = sys.argv[1:5]
with open(expected_path, encoding="utf-8") as f:
    expected = json.load(f)
with wave.open(capture_path, "rb") as wav:
    sample_rate = wav.getframerate()
    channels = wav.getnchannels()
    width = wav.getsampwidth()
    frames = wav.readframes(wav.getnframes())

if sample_rate != expected["sample_rate"] or channels != 1 or width != 2:
    raise SystemExit("capture format mismatch")

samples = [
    int.from_bytes(frames[i:i + 2], "little", signed=True) / 32768.0
    for i in range(0, len(frames), 2)
]

bits = expected["bits"]
bit_n = int(round(expected["bit_seconds"] * sample_rate))
preamble_n = int(round(expected["preamble_seconds"] * sample_rate))
freq_zero = float(expected["freq_zero"])
freq_one = float(expected["freq_one"])
noise_freqs = [900.0, 3100.0, 3900.0]

def tone_power(segment: list[float], freq: float) -> float:
    if not segment:
        return 0.0
    s_cos = 0.0
    s_sin = 0.0
    step = 2.0 * math.pi * freq / sample_rate
    for i, sample in enumerate(segment):
        angle = step * i
        s_cos += sample * math.cos(angle)
        s_sin += sample * math.sin(angle)
    return (s_cos * s_cos + s_sin * s_sin) / max(1, len(segment))

best: dict[str, float | int | str] | None = None
scan_start = int(0.15 * sample_rate)
scan_stop = min(len(samples) - (preamble_n + len(bits) * bit_n), int(1.4 * sample_rate))
step_n = max(1, int(0.01 * sample_rate))
for offset in range(scan_start, max(scan_start, scan_stop), step_n):
    bit_start = offset + preamble_n
    decoded = []
    margins = []
    signal_power = 0.0
    noise_power = 0.0
    for idx, expected_bit in enumerate(bits):
        segment = samples[bit_start + idx * bit_n: bit_start + (idx + 1) * bit_n]
        p0 = tone_power(segment, freq_zero)
        p1 = tone_power(segment, freq_one)
        decoded_bit = "1" if p1 > p0 else "0"
        decoded.append(decoded_bit)
        high = max(p0, p1)
        low = max(1e-12, min(p0, p1))
        margins.append(10.0 * math.log10(max(1e-12, high) / low))
        signal_power += high
        noise_power += sum(tone_power(segment, f) for f in noise_freqs) / len(noise_freqs)
    decoded_s = "".join(decoded)
    matches = sum(1 for a, b in zip(decoded_s, bits) if a == b)
    avg_margin = sum(margins) / max(1, len(margins))
    snr = 10.0 * math.log10(max(1e-12, signal_power) / max(1e-12, noise_power))
    score = matches * 100.0 + avg_margin + snr
    if best is None or score > float(best["score"]):
        best = {
            "score": score,
            "offset_ms": int(offset * 1000 / sample_rate),
            "decoded_bits": decoded_s,
            "matches": matches,
            "avg_margin_db": round(avg_margin, 2),
            "snr_db": round(snr, 2),
        }

if best is None:
    raise SystemExit("no decodable audio window")

bit_count = len(bits)
matches = int(best["matches"])
snr_db = float(best["snr_db"])
avg_margin_db = float(best["avg_margin_db"])
confidence = min(99, int(round((matches / bit_count) * 85 + min(14.0, avg_margin_db) + max(0.0, min(10.0, snr_db)) / 10.0)))
status = "pass" if matches == bit_count and snr_db > 9.0 and confidence > 79 else "blocked"

receipt = {
    "protocol": "audio-audible-fsk",
    "direction": "mac-speaker-to-microphone",
    "nonce_hash": expected["nonce_hash"],
    "nonce_hash_len": expected["nonce_hash_len"],
    "bit_count": bit_count,
    "decoded_match_count": matches,
    "decoded_bits": best["decoded_bits"],
    "offset_ms": best["offset_ms"],
    "snr_db": snr_db,
    "confidence": confidence,
    "latency_ms": int(latency_ms_raw),
    "raw_audio_retained": 0,
    "status": status,
}
with open(receipt_path, "w", encoding="utf-8") as f:
    json.dump(receipt, f, indent=2, sort_keys=True)

if status != "pass":
    raise SystemExit(f"audio receipt blocked matches={matches}/{bit_count} snr_db={snr_db} confidence={confidence}")
PY

rm -f "$stimulus" "$capture"
cp "$receipt" "$ROOT/.cache/live-audio-copresence/latest.json"

python3 - "$receipt" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as f:
    row = json.load(f)
print(
    "PASS live-audio-copresence "
    f"protocol={row['protocol']} direction={row['direction']} "
    f"nonce_hash_len={row['nonce_hash_len']} bits={row['decoded_match_count']}/{row['bit_count']} "
    f"snr_db={row['snr_db']} confidence={row['confidence']} latency_ms={row['latency_ms']} "
    f"raw_audio_retained={row['raw_audio_retained']} cache={sys.argv[1]}"
)
PY
