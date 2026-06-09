#!/usr/bin/env python3
"""mac-witness-server.py — the Mac end of Coherence Sense v0. A thin CARRIER, nothing more.

The phone is a sense organ; this is the Mac it streams to. v0's job is honest and small: WITNESS
the phone's senses (receive each snapshot, count it, hold the latest field) and share that back, so
the loop closes and the two synchronize in real time. It does NOT put the body in Python — there is
no recognition logic here. The BODY is the Form recipes (recognition-router, perception-pipeline,
self-grounding, cell-sync), proven three-way under form/form-stdlib. v0.1 wires those in via a
persistent kernel eval server (the recipes run per-frame on the kernel, not re-implemented here);
v1 moves the kernel onto the phone itself (the aarch64 cross-compile is already proven —
form/form-kernel-rust/build-android.sh).

Run:  python3 mac-witness-server.py            # binds 0.0.0.0:8800
Then point the phone app at  http://<this-mac-LAN-IP>:8800  (find it: ipconfig getifaddr en0)
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8800

# the shared field state the two bodies synchronize on — pure witness, not a decision.
field = {"witnessed": 0, "senses_seen": set(), "latest": {}}


class Witness(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # a glance at the shared field (open this in a browser on the Mac)
        self._send(200, {"witnessed": field["witnessed"],
                          "senses_seen": sorted(field["senses_seen"]),
                          "latest": field["latest"]})

    def do_POST(self):
        if self.path != "/sense":
            return self._send(404, {"error": "only /sense"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            snap = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._send(400, {"error": str(e)})

        # WITNESS: record what arrived. No recognition logic — that is the Form body's job (v0.1).
        present = [k for k in ("accel", "gyro", "light", "mag") if k in snap]
        field["witnessed"] += 1
        field["senses_seen"].update(present)
        field["latest"] = snap
        # echo the field back so the phone sees the sync. "recognized"/"predicted" stay honest
        # placeholders until the Form recipes are wired through the kernel.
        self._send(200, {
            "synced": True,
            "witnessed": field["witnessed"],
            "recognized": "+".join(present) if present else "quiet",
            "predicted": "—",
        })

    def log_message(self, *a):  # keep the console quiet; the phone is the surface
        pass


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Witness)
    print(f"Coherence Sense — Mac witness listening on 0.0.0.0:{PORT}")
    print("point the phone app at  http://<this-mac-LAN-IP>:%d   (ipconfig getifaddr en0)" % PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print(f"\nwitnessed {field['witnessed']} frames; senses seen: {sorted(field['senses_seen'])}")
