#!/usr/bin/env python3
"""coherence-sense-eval.py — the Mac end with LIVE RECOGNITION through the kernel.

The witness server (mac-witness-server.py) only watched. This one RECOGNIZES and LEARNS: the phone's
accelerometer stream is fed, per frame, through the proven Form recipes RUN BY THE KERNEL —
signal-derivative says still vs moving, sequence-predictor calls the next state, and the mismatch
between the call and the actual next state is the INFERENCE ERROR (the learning signal). It also runs
the learning-arc.fk MECHANISM live: a nearest-shape CHALLENGER interns the signal-derivative CHAMPION's
labels and recognizes the nearest exemplar, agreement shown on the dashboard. HONEST SCOPE: this is the
mechanism (intern -> recognize-nearest), not learning that generalizes — still/moving is a single
threshold the champion already computes, and there is no held-out test. Measured on the real UCI-HAR
benchmark (../har-benchmark/), nearest-shape is a weak non-parametric memorizer (~81% vs ~96% SOTA). All
of it is the body (Form recipes); this server is only the thin carrier that marshals numbers in and reads
the label out. ~5ms per recognition through the kernel.

Run from the repo (it needs the kernel binary + form-stdlib):
    cd experiments/coherence-sense-android && python3 coherence-sense-eval.py
Open the dashboard:  http://localhost:8800
The Android app discovers this Mac over _hati-witness._tcp; the dashboard also shows fallback URLs.
"""
import json
import os
import re
import subprocess
import tempfile
import time
from argparse import ArgumentParser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from hati_witness_discovery import start_mdns_advertisement, witness_descriptor

DEFAULT_PORT = 8800
# the kernel binary + the form-stdlib live in the repo, three dirs up from here.
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FORM = os.path.join(REPO, "form")
KERNEL = os.path.join(FORM, "form-kernel-rust", "target", "release", "form-kernel-rust")
SD = "form-stdlib/signal-derivative.fk"          # still vs moving (rate of change) — the CHAMPION/reference
SP = "form-stdlib/sequence-predictor.fk"          # predict the next state
FV = "form-stdlib/feature-vector.fk"              # bin the window into a feature — the challenger's input
NS = "form-stdlib/nearest-shape.fk"               # the body's own classifier — the CHALLENGER
WINDOW = 8                                        # frames of accel held for the derivative
ACTIVITY_FLOOR = 3                                # >= this many rises+falls in the window = moving
CHAL_THRESHOLDS = "15 25 35"                      # magnitude bins for the challenger's feature
CHAL_NBINS = 4
PROTO_MAX = 60                                    # bounded exemplar memory (the learned model)

state = {
    "device": None, "frames": 0, "first_ts": None, "last_ts": None,
    "organs": [], "latest": {}, "events": [], "present": False,
    "recognized": "—", "predicted": "—", "errors": 0, "checks": 0, "kernel_ok": os.path.exists(KERNEL),
    "challenger": "—", "chal_agree": 0, "chal_checks": 0, "protos": 0,   # the live learning arc
    "witness": {},
}
accel_window = deque(maxlen=WINDOW)   # rounded vertical-ish accel magnitude per frame
state_history = deque(maxlen=12)       # recent still/moving labels (oldest -> newest)
_pending_prediction = {"next": None}   # what we predicted the next state would be
proto_set = []                          # the challenger's learned exemplars: [(champion_label, feature), ...]


def _event(kind, detail):
    state["events"].insert(0, {"t": round(time.time(), 1), "kind": kind, "detail": detail})
    del state["events"][60:]


def _merge_snapshot(snap):
    if isinstance(snap.get("capability_heartbeat"), dict):
        merged = dict(state["latest"] or {})
        merged.update(snap)
        return merged
    return snap


def kernel_eval(recipes, expr):
    """Run one Form expression through the kernel against one or more recipes. Returns the printed value (str)."""
    if not state["kernel_ok"]:
        return None
    if isinstance(recipes, str):
        recipes = [recipes]
    with tempfile.NamedTemporaryFile("w", suffix=".fk", dir="/tmp", delete=False) as f:
        f.write(expr)
        drv = f.name
    try:
        out = subprocess.run([KERNEL, *recipes, drv], cwd=FORM, capture_output=True, text=True, timeout=3)
        line = (out.stdout or out.stderr).strip().splitlines()
        return line[-1].strip() if line else None
    except Exception:
        return None
    finally:
        os.unlink(drv)


def kernel_feature(window):
    """Bin the window into a feature-vector via the kernel (fv-histogram). Returns a list of ints."""
    win = " ".join(str(v) for v in window)
    out = kernel_eval(FV, f"(do (fv-histogram (list {win}) (list {CHAL_THRESHOLDS}) {CHAL_NBINS}))")
    nums = re.findall(r"-?\d+", out) if out else None
    return [int(n) for n in nums] if nums else None


def _proto_literal(protos):
    """Build the Form prototype-set literal: (list (list "still" (list 3 2 0 1)) ...)."""
    items = " ".join(
        f'(list "{lbl}" (list {" ".join(str(x) for x in feat)}))' for lbl, feat in protos
    )
    return f"(list {items})"


def kernel_challenger(feature, protos):
    """The challenger's call (Form, via kernel): ns-label the feature against the learned prototypes."""
    feat = " ".join(str(x) for x in feature)
    return kernel_eval(NS, f"(do (ns-label (list {feat}) {_proto_literal(protos)}))")


def recognize(snap):
    """The body recognizes — via the kernel, not in Python. Returns (recognized, predicted)."""
    acc = snap.get("accel")
    if not isinstance(acc, list) or len(acc) < 3:
        return state["recognized"], state["predicted"]
    # marshal: one integer per frame ~ the phone's tilt/shake magnitude (a readout, not a decision)
    mag = int(round(abs(acc[0]) + abs(acc[1]) + abs(acc[2])))
    accel_window.append(mag)
    if len(accel_window) < 3:
        return "warming", "—"

    # RECOGNIZE (Form, via kernel): still vs moving from the rate of change of the window
    win = " ".join(str(v) for v in accel_window)
    moving = kernel_eval(SD, f"(do (sd-moving? (list {win}) {ACTIVITY_FLOOR}))")
    recognized = ("moving" if moving == "1" else "still") if moving in ("0", "1") else "?"

    # INFERENCE ERROR: was the last prediction right? (predict -> observe -> error -> learn)
    if _pending_prediction["next"] is not None:
        state["checks"] += 1
        if _pending_prediction["next"] != recognized:
            state["errors"] += 1
            _event("surprise", f"predicted {_pending_prediction['next']}, got {recognized}")

    state_history.append(recognized)

    # PREDICT (Form, via kernel): the next state from the history, via sequence-predictor
    predicted = "—"
    if len(state_history) >= 3:
        hist = " ".join(f'"{s}"' for s in state_history)
        last = f'"{state_history[-1]}"'
        predicted = kernel_eval(SP, f'(do (sp-predict (list {hist}) {last} (list "still" "moving")))')
        predicted = predicted.strip('"') if predicted else "—"
    _pending_prediction["next"] = predicted if predicted in ("still", "moving") else None

    # THE LEARNING ARC, LIVE (learning-arc.fk made real on the stream): a nearest-shape CHALLENGER
    # learns to match the signal-derivative CHAMPION. Each frame: the challenger predicts from what it
    # has interned (cold = no guess), we score it against the champion, THEN it learns this frame. Its
    # agreement climbing IS the body learning online — the Form-native arm reaching the reference.
    if recognized in ("still", "moving"):
        feature = kernel_feature(accel_window)
        if feature:
            if proto_set:
                chal = kernel_challenger(feature, proto_set)
                if chal in ("still", "moving"):
                    state["challenger"] = chal
                    state["chal_checks"] += 1
                    if chal == recognized:
                        state["chal_agree"] += 1
            # learn: intern this (champion-label, feature) — the smallest act (nearest-shape's teaching)
            proto_set.append((recognized, feature))
            if len(proto_set) > PROTO_MAX:
                proto_set.pop(0)
            state["protos"] = len(proto_set)
    return recognized, predicted


class Server(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/state"):
            now = time.time()
            was = state["present"]
            state["present"] = bool(state["last_ts"] and (now - state["last_ts"] < 4.0))
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
        merged = _merge_snapshot(snap)
        present = [k for k in ("accel", "gyro", "light", "mag") if k in merged]
        if state["device"] is None:
            state["device"] = "phone"; state["first_ts"] = now; _event("peer", "a body connected")
        for o in present:
            if o not in state["organs"]:
                _event("organ", f"{o} came online")
        state["organs"] = present; state["latest"] = merged
        state["frames"] += 1; state["last_ts"] = now; state["present"] = True

        recognized, predicted = recognize(merged)
        state["recognized"] = recognized
        state["predicted"] = predicted

        self._send(200, json.dumps({
            "synced": True, "witnessed": state["frames"],
            "recognized": recognized, "predicted": predicted,
        }))

    def log_message(self, *a):
        pass


DASHBOARD = """<!doctype html><html><head><meta charset=utf-8><title>Coherence Sense — live</title>
<style>
 body{background:#0b0d10;color:#cdd6e0;font:13px/1.5 ui-monospace,Menlo,monospace;margin:0;padding:18px}
 h1{font-size:18px;margin:0 0 2px;color:#eaf0f6} .sub{color:#7a8696;margin:0 0 16px}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:940px}
 .card{background:#12161b;border:1px solid #1e252d;border-radius:10px;padding:14px}
 .card h2{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#7a8696;margin:0 0 10px}
 .big{font-size:26px;color:#eaf0f6} .dim{color:#7a8696} .accent{color:#86efac}
 .organ{display:inline-block;background:#1b2a1f;color:#86efac;border:1px solid #2c4a35;border-radius:6px;padding:2px 9px;margin:2px 4px 2px 0}
 .organ.off{background:#1a1d22;color:#566;border-color:#262b32}
 .pill{display:inline-block;background:#182430;color:#9ad6ca;border:1px solid #28475c;border-radius:999px;padding:2px 9px;margin:2px 4px 2px 0}
 .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;vertical-align:middle}
 .on{background:#34d399;box-shadow:0 0 8px #34d399} .gone{background:#5b6470}
 table{width:100%;border-collapse:collapse} td{padding:2px 0} td.k{color:#7a8696;width:64px}
 .ev{border-left:2px solid #2a3340;padding:1px 0 1px 10px;margin:2px 0;color:#aeb9c6}
 .ev .t{color:#566} .ev.organ{border-color:#2c4a35} .ev.peer{border-color:#3a4a66} .ev.surprise{border-color:#7c5cff;color:#cdbcff}
</style></head><body>
<h1>Coherence Sense — live</h1>
<p class=sub>the phone senses; the Mac's kernel recognizes through proven Form recipes</p>
<div class=grid>
 <div class=card><h2>presence</h2><div class=big id=presence>&mdash;</div><div class=dim id=frames></div></div>
 <div class=card><h2>recognition (kernel)</h2><div class=big id=recog>&mdash;</div><div class=dim>predicts next: <span class=accent id=pred>&mdash;</span></div><div class=dim id=err></div></div>
 <div class=card><h2>learning — challenger vs champion</h2><div class=big id=chal>&mdash;</div><div class=dim id=chalrate></div></div>
 <div class=card><h2>organs active</h2><div id=organs></div></div>
 <div class=card><h2>nearby discovery</h2><div id=discovery></div><div class=dim>Android listens for _hati-witness._tcp; fallback URLs stay visible here.</div></div>
 <div class=card><h2>events / surprises</h2><div id=events></div></div>
 <div class=card style="grid-column:1/3"><h2>field (latest)</h2><table id=field></table></div>
</div>
<script>
const ALL=["accel","gyro","light","mag"];
function vec(v){return Array.isArray(v)?v.map(x=>(+x).toFixed(2)).join("  "):(+v).toFixed(2)}
async function tick(){
 let s; try{ s=await (await fetch("/state")).json() }catch(e){ document.getElementById("presence").textContent="server offline"; return }
 const pres=document.getElementById("presence");
 pres.innerHTML='<span class="dot '+(s.present?"on":"gone")+'"></span>'+(s.present?((s.device||"a body")+" present"):"quiet");
 const dur=s.first_ts&&s.last_ts?Math.round(s.last_ts-s.first_ts):0;
 document.getElementById("frames").textContent=(s.frames||0)+" frames · "+dur+"s alive"+(s.kernel_ok?"":"  (kernel not built)");
 document.getElementById("recog").textContent=s.recognized||"—";
 document.getElementById("pred").textContent=s.predicted||"—";
 const rate=s.checks?Math.round(100*(s.checks-s.errors)/s.checks):0;
 document.getElementById("err").textContent=s.checks?("prediction right "+rate+"%  ("+(s.checks-s.errors)+"/"+s.checks+")  — error is the learning signal"):"learning…";
 const crate=s.chal_checks?Math.round(100*s.chal_agree/s.chal_checks):0;
 document.getElementById("chal").textContent=s.challenger||"—";
 document.getElementById("chalrate").textContent=s.chal_checks?("agrees with champion "+crate+"%  ("+s.chal_agree+"/"+s.chal_checks+")  · "+(s.protos||0)+" exemplars learned"):("learning… ("+(s.protos||0)+" exemplars)");
 document.getElementById("organs").innerHTML=ALL.map(o=>'<span class="organ'+(s.organs&&s.organs.includes(o)?"":" off")+'">'+o+'</span>').join("");
 const w=s.witness||{};
 document.getElementById("discovery").innerHTML='<div class=dim>'+((w.service_type||"_hati-witness._tcp")+" · "+(w.mode||"recognition"))+'</div>'+((w.urls||[]).map(u=>'<span class=pill>'+u+'</span>').join("")||'<span class=dim>waiting for LAN address</span>');
 const f=s.latest||{}; document.getElementById("field").innerHTML=ALL.filter(o=>o in f).map(o=>'<tr><td class=k>'+o+'</td><td>'+vec(f[o])+'</td></tr>').join("")||'<tr><td class=dim>no field yet</td></tr>';
 document.getElementById("events").innerHTML=(s.events||[]).map(e=>'<div class="ev '+e.kind+'"><span class=t>'+e.t+'</span> '+e.detail+'</div>').join("")||'<div class=dim>waiting…</div>';
}
setInterval(tick,800); tick();
</script></body></html>"""


if __name__ == "__main__":
    parser = ArgumentParser(description="Run the Coherence Sense Mac recognition witness.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    if not state["kernel_ok"]:
        print(f"NOTE: kernel binary not built at {KERNEL}")
        print("  build it once:  cd form && ./validate.sh form-stdlib/core.fk form-stdlib/signal-derivative.fk form-stdlib/tests/signal-derivative-band.fk")
    state["witness"] = witness_descriptor(args.port, "recognition")
    mdns = start_mdns_advertisement(args.port, "recognition")
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Server)
    print(f"Coherence Sense — LIVE RECOGNITION on 0.0.0.0:{args.port}  (kernel: {'ready' if state['kernel_ok'] else 'MISSING'})")
    print(f"  open the dashboard:  http://localhost:{args.port}")
    print(f"  Android auto-discovers: {state['witness']['service_type']} ({'active' if mdns.active else mdns.reason})")
    for url in state["witness"]["urls"]:
        print(f"  fallback URL: {url}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{state['frames']} frames; last recognized {state['recognized']}; prediction {state['checks']-state['errors']}/{state['checks']} right")
    finally:
        mdns.stop()
