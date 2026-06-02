#!/usr/bin/env python3
"""Proof-of-shape harness for the kernel-as-router REVERSAL.

Proves the inverted topology at small scale: the Form kernel is the front-door
ROUTER. It owns the listening socket, serves NATIVE routes entirely in Form
(no CPython in the path), and FANS OUT every other path to a CPython upstream.

What it spins up:
  1. a tiny CPython HTTP upstream (stands in for the real FastAPI app) on one
     port — every kernel-served route in production today (763 of them) would
     live behind this. The harness mocks it so the proof touches NO production
     routing.
  2. `form-kernel-rust serve --routes examples/router-proof.fk --upstream <mock>`
     on another port — the kernel as the front door.

What it asserts:
  - native routes (/health, /coherence_weight, /count_signals) return the Form
    handler's value with header X-Form-Router: native-kernel — proving the
    kernel served them in Form with NO CPython hop.
  - a non-native path (/api/whatever) is FANNED OUT to the CPython upstream:
    the response carries the upstream's marker AND header X-Form-Router:
    fanout-python — proving the kernel owns the routing decision and forwards
    the not-yet-native tail to Python.
  - it MEASURES native-route latency (the inverted front door must stay fast).

Run from form/form-kernel-rust/:
    cargo build --release
    python3 router_proof_harness.py
"""
from __future__ import annotations

import http.server
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE / "target" / "release" / "form-kernel-rust"
ROUTES = HERE / "examples" / "router-proof.fk"

UPSTREAM_MARKER = "UPSTREAM-CPYTHON-FASTAPI-STANDIN"


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


def wait_for_port(port: int, timeout: float = 5.0) -> None:
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


def main() -> int:
    if not BIN.exists():
        print(f"build first: cargo build --release ({BIN} missing)", file=sys.stderr)
        return 2
    if not ROUTES.exists():
        print(f"missing routes file: {ROUTES}", file=sys.stderr)
        return 2

    # 1. CPython upstream (mock FastAPI) — the fan-out target.
    up_port = free_port()
    httpd = http.server.HTTPServer(("127.0.0.1", up_port), _UpstreamHandler)
    up_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    up_thread.start()
    upstream_url = f"http://127.0.0.1:{up_port}"

    # 2. The kernel as the front-door router, fanning out to the upstream.
    kport = free_port()
    proc = subprocess.Popen(
        [
            str(BIN), "serve",
            "--port", str(kport),
            "--routes", str(ROUTES),
            "--upstream", upstream_url,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    failures = []
    try:
        wait_for_port(kport)
        base = f"http://127.0.0.1:{kport}"

        # --- NATIVE arm: served in Form, no CPython in the path ---
        cases = [
            ("/health", "ok"),
            ("/coherence_weight", "0.8125"),
            ("/count_signals?values=0.5,0.75,1.0", "3"),
            ("/count_signals?values=a", "1"),
        ]
        for path, expect in cases:
            status, body, router = fetch(base + path)
            ok = status == 200 and body == expect and router == "native-kernel"
            print(f"  [native ] {path:<38} -> {status} {body!r} "
                  f"X-Form-Router={router}  {'OK' if ok else 'FAIL'}")
            if not ok:
                failures.append((path, status, body, router))

        # --- FAN-OUT arm: forwarded to the CPython upstream ---
        for path in ("/api/ideas", "/api/whatever/deep/path"):
            status, body, router = fetch(base + path)
            ok = (
                status == 200
                and UPSTREAM_MARKER in body
                and path in body
                and router == "fanout-python"
            )
            print(f"  [fanout ] {path:<38} -> {status} via CPython "
                  f"X-Form-Router={router}  {'OK' if ok else 'FAIL'}")
            if not ok:
                failures.append((path, status, body, router))

        # --- MEASURE native-route latency (the front door must stay fast) ---
        N = 200
        samples = []
        for _ in range(N):
            t0 = time.perf_counter()
            fetch(base + "/coherence_weight")
            samples.append((time.perf_counter() - t0) * 1000.0)
        samples.sort()
        p50 = statistics.median(samples)
        p99 = samples[int(0.99 * len(samples)) - 1]
        print(f"\n  native /coherence_weight over {N} reqs: "
              f"p50={p50:.3f} ms  p99={p99:.3f} ms  min={samples[0]:.3f} ms")
        print("  (whole-request wall time incl. loopback socket; the Form "
              "value-walk is the sub-fraction.)")

        if failures:
            print(f"\nFAIL: {len(failures)} case(s) did not match", file=sys.stderr)
            return 1
        print("\nok — kernel OWNED the front door: native routes served in "
              "Form (no CPython), tail fanned out to CPython upstream.")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()
        httpd.shutdown()


if __name__ == "__main__":
    sys.exit(main())
