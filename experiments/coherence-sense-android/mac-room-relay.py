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

ROOT = os.environ.get("COHERENCE_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Best multilingual oracle available — small > base (both multilingual: Brazilian Portuguese etc.,
# auto-detected) > english-only. small translates far better than base (the weak-oracle gap).
_sm = os.path.expanduser("~/.coherence-whisper/ggml-small.bin")
_mm = os.path.expanduser("~/.coherence-whisper/ggml-base.bin")
_en = os.path.expanduser("~/.coherence-whisper/ggml-base.en.bin")
def _best_model():
    for m in (_sm, _mm, _en):
        if os.path.exists(m):
            return m
    return _en
MODEL = os.environ.get("ROOM_EAR_MODEL", _best_model())
WHISPER = os.environ.get("ROOM_EAR_WHISPER", "whisper-cli")
ASK = os.path.join(ROOT, "scripts", "form_cli_ask.sh")
PORT = int(os.environ.get("ROOM_RELAY_PORT", "8910"))
DEFAULT_LANG = os.environ.get("ROOM_EAR_LANG", "auto")  # auto-detect; or force e.g. "pt" for Brazilian


def _is_noise(t):
    # whisper hallucinates on near-silence: blank markers, bracketed annotations, repeated tokens,
    # mostly-symbol strings. Drop those so the device shows REAL speech only.
    t = t.strip()
    if not t:
        return True
    if t[0] in "[(" or "BLANK_AUDIO" in t.upper():
        return True
    toks = t.split()
    if len(toks) >= 4 and len(set(w.strip(".,%/ ").lower() for w in toks)) <= 2:
        return True
    alpha = sum(c.isalpha() for c in t)
    if alpha < max(3, int(len(t) * 0.4)):
        return True
    return False


def transcribe(wav_path, lang="auto"):
    # -l auto detects the spoken language (English, Portuguese, ...); a forced lang sharpens accuracy.
    try:
        out = subprocess.run([WHISPER, "-m", MODEL, "-f", wav_path, "-nt", "-l", lang or "auto"],
                             capture_output=True, text=True, timeout=90).stdout
        text = " ".join(out.split()).strip()
        return "" if _is_noise(text) else text
    except Exception as e:
        return ""


def translate(wav_path):
    # whisper --translate renders any spoken language into English, so a non-English room is understandable.
    # Returns "" for English/near-silence (the source transcript already serves); a real translation else.
    try:
        out = subprocess.run([WHISPER, "-m", MODEL, "-f", wav_path, "-nt", "-tr"],
                             capture_output=True, text=True, timeout=90).stdout
        text = " ".join(out.split()).strip()
        return "" if _is_noise(text) else text
    except Exception:
        return ""


def _openrouter_key():
    import json as _j
    try:
        k = _j.load(open(os.path.expanduser("~/.coherence-network/keys.json")))
        o = k.get("openrouter")
        if isinstance(o, dict):
            o = o.get("api_key")
        return o or os.environ.get("OPENROUTER_API_KEY", "")
    except Exception:
        return os.environ.get("OPENROUTER_API_KEY", "")


EYE_MODEL = os.environ.get("ROOM_EYE_MODEL", "google/gemma-4-31b-it:free")  # remote fallback
EYE_LOCAL = os.environ.get("ROOM_EYE_LOCAL", "moondream")  # local ollama vision (sovereign, free)
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
EYE_PROMPT = ("Describe this room scene in ONE concise sentence, then on a second line prefixed "
              "'objects:' list the main concrete objects/people/animals as a comma-separated list. "
              "Be specific and grounded; only name what is actually visible.")


def _parse_scene(msg):
    msg = (msg or "").strip()
    scene, objects = msg, []
    for line in msg.splitlines():
        if line.lower().startswith("objects:"):
            objects = [o.strip() for o in line.split(":", 1)[1].split(",") if o.strip()]
            scene = msg.split(line)[0].strip() or scene
    return scene.replace("\n", " ").strip(), objects


def see_local(jpeg_bytes):
    # LOCAL sovereign vision — ollama VLM on the Mac (no key, no cost, no egress). Tried first.
    import base64, json as _j, urllib.request
    b64 = base64.b64encode(jpeg_bytes).decode()
    body = _j.dumps({"model": EYE_LOCAL, "prompt": EYE_PROMPT, "images": [b64], "stream": False}).encode()
    req = urllib.request.Request(OLLAMA + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = _j.load(r)
    scene, objects = _parse_scene(out.get("response", ""))
    return {"scene": scene, "objects": objects, "model": EYE_LOCAL, "where": "local"}


def see_remote(jpeg_bytes):
    # REMOTE oracle fallback — OpenRouter VLM (needs a key/credit; free tiers are throttled).
    import base64, json as _j, urllib.request
    key = _openrouter_key()
    if not key:
        return {"scene": "", "objects": [], "error": "no local vision + no openrouter key"}
    b64 = base64.b64encode(jpeg_bytes).decode()
    body = _j.dumps({"model": EYE_MODEL, "max_tokens": 200, "messages": [{"role": "user", "content": [
        {"type": "text", "text": EYE_PROMPT},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}]}]}).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            out = _j.load(r)
        scene, objects = _parse_scene(out["choices"][0]["message"]["content"])
        return {"scene": scene, "objects": objects, "model": EYE_MODEL, "where": "remote"}
    except Exception as e:
        return {"scene": "", "objects": [], "error": str(e)[:120]}


def see(jpeg_bytes):
    # The eye's oracle: a JPEG room frame → a grounded scene + object list, replacing ML Kit's scattered
    # low-confidence labels. Form-first: try the LOCAL sovereign VLM, escalate to the remote oracle only on
    # a miss. Carrier-last: the phone grabs pixels, the oracle grounds them; the form-native vision-percept
    # (learns the room's own shapes) is the destination, this is the good-enough oracle until then.
    try:
        r = see_local(jpeg_bytes)
        if r.get("scene"):
            return r
    except Exception:
        pass
    return see_remote(jpeg_bytes)


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
        path = self.path.split("?", 1)[0]
        if path == "/see":
            n = int(self.headers.get("Content-Length", 0) or 0)
            data = self.rfile.read(n) if n else b""
            if not data:
                return self._send(400, {"error": "empty body (POST a jpeg)"})
            return self._send(200, see(data))
        if path != "/hear":
            return self._send(404, {"error": "POST /hear[?lang=...] (wav) or /see (jpeg)"})
        # language: ?lang=pt (Brazilian), ?lang=en, or auto-detect (default)
        lang = DEFAULT_LANG
        if "?" in self.path:
            for kv in self.path.split("?", 1)[1].split("&"):
                if kv.startswith("lang="):
                    lang = kv.split("=", 1)[1] or DEFAULT_LANG
        n = int(self.headers.get("Content-Length", 0) or 0)
        data = self.rfile.read(n) if n else b""
        if not data:
            return self._send(400, {"error": "empty body"})
        wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        try:
            with open(wav, "wb") as f:
                f.write(data)
            text = transcribe(wav, lang)
            # translation: English rendering when the speech wasn't English; "" when it matches (English/silence)
            trans = translate(wav) if text else ""
            if trans and trans.strip().lower() == text.strip().lower():
                trans = ""
            ans = answer(text)
            return self._send(200, {"transcript": text, "translation": trans, "answer": ans, "lang": lang})
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
