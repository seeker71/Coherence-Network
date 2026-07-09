#!/usr/bin/env python3
"""recognition-server.py — the recognition body's door for the phone. A small LAN HTTP server
(runs on the Mac, where the profile engines and the sample stores live) so the companion app can
do what the mac Speakers/Faces rooms do: see who is known, see the unassigned pool, HEAR a voice
clip or SEE a face, and assign / unassign / rename — full parity, from the pocket.

It announces its own LAN URL to the mesh (learning/recognition-endpoint) so the phone finds it by
reading the field, never a hardcoded address — an organ is not its address.

Run under the venv python (needs the engines). Endpoints:
  GET  /board                      -> {speakers:{known,pool}, faces:{known,pool}}
  GET  /voice/<id>.wav             -> the voice clip (to play)
  GET  /face/<id>.jpg              -> the face frame (to see)
  POST /assign   {domain,id,person}
  POST /unassign {domain,id}
  POST /rename   {domain,old,new}
"""
import json, os, socket, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable  # the venv python this server runs under (has numpy/resemblyzer)
SPEAKER = os.path.join(HERE, "speaker_profiles.py")
FACE = os.path.join(HERE, "face_profiles.py")
CN = os.path.expanduser("~/.coherence-network")
SPK_SAMPLES = os.path.join(CN, "speakers", "samples")
FACE_FRAMES = os.path.join(CN, "face-training", "frames")
PORT = int(os.environ.get("RECOG_PORT", "8788"))
API = os.environ.get("HATI_MESH", "https://api.coherencycoin.com/api") + "/hati/mesh"
FROM = "hati-organ-macos-77a05bc8f6c24"


def engine(script, *args):
    try:
        out = subprocess.run([PY, script, *args], capture_output=True, text=True, timeout=60)
        return out.stdout.strip()
    except Exception as e:
        return ""


def board():
    def dom(script):
        known = json.loads(engine(script, "json") or '{"profiles":[]}').get("profiles", [])
        pool = json.loads(engine(script, "unassigned") or "[]")
        return {"known": known, "pool": pool}
    return {"speakers": dom(SPEAKER), "faces": dom(FACE)}


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        if body:
            self.wfile.write(body)

    def _file(self, path, ctype):
        if not os.path.isfile(path):
            self._send(404, {"error": "not found"}); return
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self._send(200, "")

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/board":
            self._send(200, board())
        elif p.startswith("/voice/"):
            sid = os.path.basename(p)[:-4] if p.endswith(".wav") else os.path.basename(p)
            self._file(os.path.join(SPK_SAMPLES, sid + ".wav"), "audio/wav")
        elif p.startswith("/face/"):
            fid = os.path.basename(p)
            fid = fid[:-4] if fid.endswith(".jpg") else fid
            # a face sample id is <framehash>-<i>; its image is the kept frame <framehash>.jpg
            frame = fid.rsplit("-", 1)[0]
            self._file(os.path.join(FACE_FRAMES, frame + ".jpg"), "image/jpeg")
        elif p == "/" or p == "/health":
            self._send(200, {"ok": True, "service": "recognition", "ts": time.time()})
        else:
            self._send(404, {"error": "unknown"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0") or "0")
        try:
            body = json.loads(self.rfile.read(n) or "{}")
        except Exception:
            self._send(400, {"error": "bad json"}); return
        p = self.path.split("?")[0]
        domain = body.get("domain")
        script = SPEAKER if domain == "voice" else FACE if domain == "face" else None
        if not script:
            self._send(400, {"error": "domain must be voice|face"}); return
        if p == "/assign":
            engine(script, "assign", str(body.get("id", "")), str(body.get("person", "")))
        elif p == "/unassign":
            engine(script, "unassign", str(body.get("id", "")))
        elif p == "/release":
            engine(script, "release", str(body.get("person", "")))
        elif p == "/rename":
            engine(script, "rename", str(body.get("old", "")), str(body.get("new", "")))
        else:
            self._send(404, {"error": "unknown"}); return
        self._send(200, board())


def announce_loop(url):
    # tell the field where the recognition door is; re-post so it stays fresh and IP-change-proof.
    # curl, not urllib — the venv python's SSL trips on this host; curl is proven across the body.
    payload = json.dumps({
        "from_organ_id": FROM, "to_organ_id": "hati-suci", "protocol": "hati-mesh",
        "interface": "learning/recognition-endpoint", "capability": url[:120],
        "codec": "json", "data_type": "event", "direction": "presence", "status": "offered",
    })
    while True:
        try:
            subprocess.run(["curl", "-s", "-m", "8", "-X", "POST", API + "/channels/offer",
                            "-H", "Content-Type: application/json", "-d", payload],
                           capture_output=True, timeout=12)
        except Exception:
            pass
        time.sleep(120)


def main():
    url = f"http://{lan_ip()}:{PORT}"
    threading.Thread(target=announce_loop, args=(url,), daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[recognition-server] {url}  (announced to the mesh)", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
