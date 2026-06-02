#!/usr/bin/env python3
"""Proof-of-shape harness for a BML-AUTHORED kernel-router manifest.

Sibling of router_proof_harness.py. That harness proves the kernel-as-router
topology against an S-EXPRESSION manifest (examples/router-proof.fk). This one
proves the runtime-share-aligned step Urs named: a route handler authored in BML
SURFACE syntax (`def name(args) = expr;`) serves through the kernel with NO
Python and NO hand-written S-expression — the BML manifest is SOURCE-COMPILED at
load via the body's own form-stdlib compiler (form-source-compile-file over the
form.bml dialect), then served exactly like a native S-expression manifest.

What it spins up:
  1. `form-kernel-rust serve --routes examples/router-bml-proof.bml
     --stdlib form-stdlib --upstream <mock>` — the BML manifest source-compiled
     AT LOAD, the kernel as the front door, fanning out the tail.
  2. (oracle) `form-kernel-rust serve --routes <temp S-expr manifest>` — the same
     three handlers authored in raw S-expression Form, on a second port. Its
     answers are the oracle the BML answers are checked EQUAL to.
  3. a tiny CPython upstream (mock FastAPI) — the fan-out target, so the proof
     touches NO production routing.

What it asserts:
  - the BML-authored native routes (/health, /weighted_sum, /coherence_weight,
    /count_signals) return the BML handler's value with header X-Form-Router:
    native-kernel — the kernel served them in Form, NO CPython hop, the handler
    authored in BML. /coherence_weight is a FLOAT route: its float literals and
    float result lower through the source compiler's .fkb artifact (which now
    carries float VALUES, not per-kernel overflow-table indices), so a BML
    float-literal handler serves the correct value (0.875) end-to-end.
  - the BML answer EQUALS the S-expression oracle's answer for the same route —
    BML surface syntax lowered to the same Form shape an S-expr handler is.
  - a non-native path FANS OUT to the CPython upstream (X-Form-Router:
    fanout-python) — the BML manifest's tail proxies to Python like any manifest.
  - the server's startup log NAMES the BML source-compile (the at-load lowering
    actually ran; the route was not secretly an S-expression file).
  - it MEASURES native-route latency (the BML-authored front door stays fast —
    once lowered at load, a BML route is the same value-walk as an S-expr one).

Run from form/form-kernel-rust/ (cwd must let --stdlib form-stdlib resolve, i.e.
run from form/form-kernel-rust with ../form-stdlib, or pass an absolute --stdlib):
    cargo build --release
    python3 router_bml_proof_harness.py
"""
from __future__ import annotations

import http.server
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE / "target" / "release" / "form-kernel-rust"
BML_ROUTES = HERE / "examples" / "router-bml-proof.bml"
# The form-stdlib dir the BML manifest is source-compiled through. The kernel's
# default --stdlib is "form-stdlib" relative to cwd; we pass the absolute path so
# the harness works regardless of the cwd it is launched from.
STDLIB_DIR = HERE.parent / "form-stdlib"

UPSTREAM_MARKER = "UPSTREAM-CPYTHON-FASTAPI-STANDIN"

# The S-expression ORACLE manifest: the SAME three handlers as the BML manifest,
# authored in raw S-expression Form. The harness serves this on its own port and
# checks the BML answers EQUAL these — proving the BML surface lowered to the same
# Form value an S-expr handler computes. route_weighted_sum is the multi-step
# integer aggregator (3*2)+(5*1)+(7*4)=39, identical to the BML handler.
ORACLE_SEXPR = """
(defn assoc (key pairs)
  (if (eq (len pairs) 0)
      ""
      (if (str_eq (head (head pairs)) key)
          (head (tail (head pairs)))
          (assoc key (tail pairs)))))

(defn route_health () "ok")

(defn route_weighted_sum ()
  (int_to_str (add (add (mul 3 2) (mul 5 1)) (mul 7 4))))

(defn route_coherence_weight ()
  (add (mul 0.5 0.25) (mul 1.0 0.75)))

(defn count_commas (s i n)
  (if (eq i (str_len s))
      n
      (count_commas s (add i 1)
                    (if (str_eq (char_at s i) ",") (add n 1) n))))

(defn route_count_signals (q)
  (if (eq (str_len (assoc "values" q)) 0)
      "0"
      (int_to_str (add (count_commas (assoc "values" q) 0 0) 1))))

(let routes
  (list
    (list "/health"          route_health)
    (list "/weighted_sum"    route_weighted_sum)
    (list "/count_signals"   route_count_signals)
    (list "/coherence_weight" route_coherence_weight)))
"""


class _UpstreamHandler(http.server.BaseHTTPRequestHandler):
    """The CPython upstream the kernel fans out to (mock FastAPI)."""

    def do_GET(self):  # noqa: N802
        body = f"{UPSTREAM_MARKER} served {self.path}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence per-request logging
        pass


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_port(port: int, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(0.2)
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(0.05)
    raise RuntimeError(f"listener never came up on 127.0.0.1:{port}")


def fetch(url: str):
    """Return (status, body, router-header) for a GET."""
    try:
        with urllib.request.urlopen(url, timeout=3.0) as r:
            return r.status, r.read().decode("utf-8"), r.headers.get("X-Form-Router")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), e.headers.get("X-Form-Router")


def serve_value(base: str, path: str) -> str:
    status, body, _ = fetch(base + path)
    if status != 200:
        raise RuntimeError(f"oracle {path} -> {status}")
    return body


def main() -> int:
    if not BIN.exists():
        print(f"build first: cargo build --release ({BIN} missing)", file=sys.stderr)
        return 2
    if not BML_ROUTES.exists():
        print(f"missing BML routes file: {BML_ROUTES}", file=sys.stderr)
        return 2
    if not STDLIB_DIR.exists():
        print(f"missing form-stdlib dir: {STDLIB_DIR}", file=sys.stderr)
        return 2

    # 1. CPython upstream (mock FastAPI) — the fan-out target.
    up_port = free_port()
    httpd = http.server.HTTPServer(("127.0.0.1", up_port), _UpstreamHandler)
    up_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    up_thread.start()
    upstream_url = f"http://127.0.0.1:{up_port}"

    # 2. The kernel as the front-door router, serving the BML-authored manifest
    #    (source-compiled at load) and fanning out the tail to the upstream.
    kport = free_port()
    bml_proc = subprocess.Popen(
        [
            str(BIN), "serve",
            "--port", str(kport),
            "--routes", str(BML_ROUTES),
            "--stdlib", str(STDLIB_DIR),
            "--upstream", upstream_url,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # 3. The S-expression ORACLE: the same handlers in raw Form, on its own port.
    oracle_file = tempfile.NamedTemporaryFile(
        "w", suffix=".fk", prefix="router-oracle-", delete=False
    )
    oracle_file.write(ORACLE_SEXPR)
    oracle_file.flush()
    oracle_file.close()
    oport = free_port()
    oracle_proc = subprocess.Popen(
        [str(BIN), "serve", "--port", str(oport), "--routes", oracle_file.name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    failures = []
    try:
        wait_for_port(kport)
        wait_for_port(oport)
        base = f"http://127.0.0.1:{kport}"
        oracle = f"http://127.0.0.1:{oport}"

        # --- NATIVE arm: BML-authored handlers, served in Form, no CPython ---
        #     each checked against the S-expression oracle's answer (EQUAL).
        cases = [
            "/health",
            "/weighted_sum",
            "/coherence_weight",  # FLOAT route: 0.5*0.25 + 1.0*0.75 = 0.875
            "/count_signals?values=0.5,0.75,1.0",
            "/count_signals?values=a",
            "/count_signals",  # no values -> "0"
        ]
        for path in cases:
            status, body, router = fetch(base + path)
            want = serve_value(oracle, path)  # the S-expr handler's answer
            ok = status == 200 and body == want and router == "native-kernel"
            print(f"  [bml-native] {path:<38} -> {status} {body!r} "
                  f"X-Form-Router={router}  ==oracle({want!r})  "
                  f"{'OK' if ok else 'FAIL'}")
            if not ok:
                failures.append(("native", path, status, body, router, want))

        # --- FAN-OUT arm: the BML manifest's tail proxies to CPython too ---
        for path in ("/api/ideas", "/api/whatever/deep/path"):
            status, body, router = fetch(base + path)
            ok = (
                status == 200
                and UPSTREAM_MARKER in body
                and path in body
                and router == "fanout-python"
            )
            print(f"  [bml-fanout] {path:<38} -> {status} via CPython "
                  f"X-Form-Router={router}  {'OK' if ok else 'FAIL'}")
            if not ok:
                failures.append(("fanout", path, status, body, router, None))

        # --- MEASURE native-route latency (the BML front door must stay fast) ---
        N = 200
        samples = []
        for _ in range(N):
            t0 = time.perf_counter()
            fetch(base + "/weighted_sum")
            samples.append((time.perf_counter() - t0) * 1000.0)
        samples.sort()
        p50 = statistics.median(samples)
        p99 = samples[int(0.99 * len(samples)) - 1]
        print(f"\n  BML-native /weighted_sum over {N} reqs: "
              f"p50={p50:.3f} ms  p99={p99:.3f} ms  min={samples[0]:.3f} ms")
        print("  (whole-request wall time incl. loopback socket; once lowered at "
              "load, a BML route is the same value-walk as an S-expr one.)")

        # --- the at-load source-compile must have actually run ---
        # Give the process a moment to flush its startup banner, then read it.
        time.sleep(0.1)
        bml_proc.terminate()
        try:
            _, stderr = bml_proc.communicate(timeout=2.0)
        except subprocess.TimeoutExpired:
            bml_proc.kill()
            _, stderr = bml_proc.communicate()
        compiled_named = "source-compiled" in (stderr or "") and "form.bml" in (stderr or "")
        print(f"\n  startup log named the BML source-compile: "
              f"{'OK' if compiled_named else 'FAIL'}")
        if not compiled_named:
            print("  --- server stderr ---", file=sys.stderr)
            print(stderr, file=sys.stderr)
            failures.append(("startup", "source-compile banner", None, None, None, None))

        if failures:
            print(f"\nFAIL: {len(failures)} case(s) did not match", file=sys.stderr)
            return 1
        print("\nok — a BML-AUTHORED route served through the kernel: native "
              "handlers written in BML surface syntax, source-compiled at load "
              "via form-stdlib, served in Form (no CPython, no hand S-expr), "
              "their answers EQUAL the S-expression oracle's; the tail fanned "
              "out to CPython.")
        return 0
    finally:
        for p in (bml_proc, oracle_proc):
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    p.kill()
        httpd.shutdown()
        try:
            Path(oracle_file.name).unlink()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
