#!/usr/bin/env python3
"""mac-witness-server.py — the Mac end of Coherence Sense. A thin CARRIER with a live window.

The phone is a sense organ; this is the Mac it streams to. This server WITNESSES the phone's senses
(receives each snapshot, tracks which organs are live, holds the latest field, logs field-change
events) and shows it all on a live dashboard you open in a browser — so you can SEE what the body is
doing, what state it is in, which organs are active, and the surprise events as they happen.

It puts NO body in Python: there is no recognition logic here. The BODY is the Form recipes proven
three-way under form/form-stdlib (recognition-router, perception-pipeline, active-inference,
device-heartbeat, body-state, ...). The recognition / prediction / inference-error panel is an honest
placeholder until those recipes are wired into the live loop through a persistent kernel eval server
(the recipes are done; the live data door is the next carrier step).

Run:  python3 mac-witness-server.py            # binds 0.0.0.0:8800
Open the dashboard on the Mac:  http://localhost:8800
The Android app discovers this Mac over _hati-witness._tcp; the dashboard also shows fallback URLs.
"""
import json
import time
from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from hati_witness_discovery import start_mdns_advertisement, witness_descriptor

DEFAULT_PORT = 8800
ORGAN_KEYS = ("accel", "gyro", "light", "mag")
STALE_SECONDS = 4.0          # no frame in this long -> the body went quiet (a liveness event)

# the shared field state the dashboard renders — pure witness, not a decision.
state = {
    "device": None,
    "frames": 0,
    "first_ts": None,
    "last_ts": None,
    "organs": [],            # which senses are live right now
    "latest": {},            # the most recent snapshot
    "events": [],            # field-change events (most recent first)
    "present": False,
    "witness": {},
}


def _event(kind, detail):
    state["events"].insert(0, {"t": round(time.time(), 1), "kind": kind, "detail": detail})
    del state["events"][60:]


class Witness(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/state"):
            now = time.time()
            was = state["present"]
            state["present"] = bool(state["last_ts"] and (now - state["last_ts"] < STALE_SECONDS))
            if was and not state["present"]:
                _event("peer", f"{state['device']} went quiet")
            return self._send(200, json.dumps(state))
        if self.path.startswith("/.well-known/hati-witness") or self.path.startswith("/discover"):
            return self._send(200, json.dumps(state["witness"]))
        return self._send(200, DASHBOARD, "text/html; charset=utf-8")

    def do_POST(self):
        if self.path != "/sense":
            return self._send(404, json.dumps({"error": "only /sense"}))
        try:
            n = int(self.headers.get("Content-Length", 0))
            snap = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._send(400, json.dumps({"error": str(e)}))

        now = time.time()
        present = [k for k in ORGAN_KEYS if k in snap]

        if state["device"] is None:
            state["device"] = "phone"
            state["first_ts"] = now
            _event("peer", "a body connected")
        # organ-change events (a sense appearing or going quiet IS a surprise the dashboard highlights)
        for o in present:
            if o not in state["organs"]:
                _event("organ", f"{o} came online")
        for o in state["organs"]:
            if o not in present:
                _event("organ", f"{o} went quiet")
        if not state["present"] and state["frames"] > 0:
            _event("peer", f"{state['device']} present again")

        state["organs"] = present
        state["latest"] = snap
        state["frames"] += 1
        state["last_ts"] = now
        state["present"] = True

        self._send(200, json.dumps({
            "synced": True,
            "witnessed": state["frames"],
            "recognized": "+".join(present) if present else "quiet",
            "predicted": "—",
        }))

    def log_message(self, *a):
        pass


DASHBOARD = """<!doctype html><html><head><meta charset=utf-8>
<title>Coherence Sense — live</title>
<style>
 body{background:#0b0d10;color:#cdd6e0;font:13px/1.5 ui-monospace,Menlo,monospace;margin:0;padding:18px}
 h1{font-size:18px;margin:0 0 2px;color:#eaf0f6} .sub{color:#7a8696;margin:0 0 16px}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:900px}
 .card{background:#12161b;border:1px solid #1e252d;border-radius:10px;padding:14px}
 .card h2{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#7a8696;margin:0 0 10px}
 .big{font-size:26px;color:#eaf0f6} .dim{color:#7a8696}
 .organ{display:inline-block;background:#1b2a1f;color:#86efac;border:1px solid #2c4a35;border-radius:6px;padding:2px 9px;margin:2px 4px 2px 0}
 .organ.off{background:#1a1d22;color:#566;border-color:#262b32}
 .pill{display:inline-block;background:#182430;color:#9ad6ca;border:1px solid #28475c;border-radius:999px;padding:2px 9px;margin:2px 4px 2px 0}
 .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;vertical-align:middle}
 .on{background:#34d399;box-shadow:0 0 8px #34d399} .gone{background:#5b6470}
 table{width:100%;border-collapse:collapse} td{padding:2px 0} td.k{color:#7a8696;width:64px}
 .ev{border-left:2px solid #2a3340;padding:1px 0 1px 10px;margin:2px 0;color:#aeb9c6}
 .ev .t{color:#566} .ev.organ{border-color:#2c4a35} .ev.peer{border-color:#3a4a66}
 .note{grid-column:1/3;background:#12161b;border:1px dashed #2a3340;border-radius:10px;padding:12px;color:#8a97a6}
</style></head><body>
<h1>Coherence Sense — live</h1>
<p class=sub>the phone is a sense organ of the network; this is the Mac witnessing it</p>
<div class=grid>
 <div class=card><h2>presence</h2><div class=big id=presence>&mdash;</div><div class=dim id=frames></div></div>
 <div class=card><h2>organs active</h2><div id=organs></div></div>
 <div class=card><h2>nearby discovery</h2><div id=discovery></div><div class=dim>Android listens for _hati-witness._tcp; fallback URLs stay visible here.</div></div>
 <div class=card><h2>field (latest)</h2><table id=field></table></div>
 <div class=card><h2>events / surprises</h2><div id=events></div></div>
 <div class=note id=note>recognition &middot; prediction &middot; inference-error &mdash; the Form recipes are proven three-way; wiring them into this live loop (a persistent kernel eval server) is the next carrier step. For now this window shows the senses and the sync, honestly.</div>
</div>
<script>
const ALL=["accel","gyro","light","mag"];
function vec(v){return Array.isArray(v)?v.map(x=>(+x).toFixed(2)).join("  "):(+v).toFixed(2)}
async function tick(){
 let s; try{ s=await (await fetch("/state")).json() }catch(e){ document.getElementById("presence").textContent="server offline"; return }
 const pres=document.getElementById("presence");
 pres.innerHTML='<span class="dot '+(s.present?"on":"gone")+'"></span>'+(s.present?((s.device||"a body")+" present"):"quiet");
 const dur=s.first_ts&&s.last_ts?Math.round(s.last_ts-s.first_ts):0;
 document.getElementById("frames").textContent=(s.frames||0)+" frames witnessed · "+dur+"s alive";
 document.getElementById("organs").innerHTML=ALL.map(o=>'<span class="organ'+(s.organs&&s.organs.includes(o)?"":" off")+'">'+o+'</span>').join("");
 const w=s.witness||{};
 document.getElementById("discovery").innerHTML='<div class=dim>'+((w.service_type||"_hati-witness._tcp")+" · "+(w.mode||"witness"))+'</div>'+((w.urls||[]).map(u=>'<span class=pill>'+u+'</span>').join("")||'<span class=dim>waiting for LAN address</span>');
 const f=s.latest||{}; document.getElementById("field").innerHTML=ALL.filter(o=>o in f).map(o=>'<tr><td class=k>'+o+'</td><td>'+vec(f[o])+'</td></tr>').join("")||'<tr><td class=dim>no field yet</td></tr>';
 document.getElementById("events").innerHTML=(s.events||[]).map(e=>'<div class="ev '+e.kind+'"><span class=t>'+e.t+'</span> '+e.detail+'</div>').join("")||'<div class=dim>waiting…</div>';
}
setInterval(tick,800); tick();
</script></body></html>"""


def main():
    parser = ArgumentParser(description="Run the Coherence Sense Mac witness server.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    state["witness"] = witness_descriptor(args.port, "witness")
    mdns = start_mdns_advertisement(args.port, "witness")
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Witness)
    print(f"Coherence Sense — Mac witness + dashboard on 0.0.0.0:{args.port}")
    print(f"  open the dashboard:  http://localhost:{args.port}")
    print(f"  Android auto-discovers: {state['witness']['service_type']} ({'active' if mdns.active else mdns.reason})")
    for url in state["witness"]["urls"]:
        print(f"  fallback URL: {url}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print(f"\nwitnessed {state['frames']} frames; last organs: {state['organs']}")
    finally:
        mdns.stop()


if __name__ == "__main__":
    main()
