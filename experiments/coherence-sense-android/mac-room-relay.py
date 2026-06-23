#!/usr/bin/env python3
# mac-room-relay.py — the persistent room-ear relay (Track B). The phone's fixed door: it POSTs a clip
# of room audio to /hear, the relay turns it into WORDS (whisper.cpp) and an ANSWER on the body-first
# path (scripts/form_cli_ask.sh — grounds in the body, escalates to the oracle only when local is not
# enough), and returns both. Thin CARRIER: the engines are the proven body, this only relays.
#
#   phone audio -> POST /hear -> whisper (audio->text) -> form_cli_ask (text->answer) -> {transcript, answer}
#
# Run:  python3 mac-room-relay.py [--port 8910]
# Test: curl --data-binary @clip.wav http://localhost:8910/hear
# Local only by default (binds 0.0.0.0 so the phone on the LAN can reach it); nothing leaves the Mac
# except the question the body-first agent already answers locally.
import json, os, subprocess, sys, tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODEL = os.environ.get("ROOM_EAR_MODEL", os.path.expanduser("~/.coherence-whisper/ggml-base.en.bin"))
WHISPER = os.environ.get("ROOM_EAR_WHISPER", "whisper-cli")
ASK = os.path.join(ROOT, "scripts", "form_cli_ask.sh")
PORT = int(os.environ.get("ROOM_RELAY_PORT", "8910"))


def transcribe(wav_path):
    try:
        out = subprocess.run([WHISPER, "-m", MODEL, "-f", wav_path, "-nt", "-l", "en"],
                             capture_output=True, text=True, timeout=60).stdout
        return " ".join(out.split()).strip()
    except Exception as e:
        return ""


def answer(text):
    if not text:
        return ""
    try:
        out = subprocess.run(["bash", ASK, text], capture_output=True, text=True, timeout=90).stdout
        # form_cli_ask prints a trust header line first; keep the body after it
        lines = [l for l in out.splitlines() if l.strip()]
        body = [l for l in lines if not l.startswith("trust ") and l.strip() != "?"]
        return "\n".join(body).strip()
    except Exception as e:
        return ""


class Relay(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._send(200, {"ok": True, "model": os.path.basename(MODEL), "agent": os.path.exists(ASK)})
        return self._send(404, {"error": "POST /hear or GET /health"})

    def do_POST(self):
        if self.path != "/hear":
            return self._send(404, {"error": "POST /hear with a wav body"})
        n = int(self.headers.get("Content-Length", 0) or 0)
        data = self.rfile.read(n) if n else b""
        if not data:
            return self._send(400, {"error": "empty body"})
        wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        try:
            with open(wav, "wb") as f:
                f.write(data)
            text = transcribe(wav)
            ans = answer(text)
            return self._send(200, {"transcript": text, "answer": ans})
        finally:
            try: os.remove(wav)
            except Exception: pass

    def log_message(self, *a):
        pass


def main():
    port = PORT
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    print(f"[room-relay] listening on 0.0.0.0:{port}  model={os.path.basename(MODEL)}  agent={os.path.exists(ASK)}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Relay).serve_forever()


if __name__ == "__main__":
    main()
