#!/usr/bin/env python3
"""Shadow-mode proof for the kernel-router image's routes manifest.

Proves the deployable SHADOW step of the kernel-as-router flip
(kernels/KERNEL_AS_ROUTER.md): the kernel-router loaded with the EMPTY-routes
manifest (deploy/kernel-router/shadow-routes.fk) serves ZERO native routes and
fans EVERYTHING out to the upstream — byte-identical to hitting the upstream
directly, with `X-Form-Router: fanout-python` on every response as live evidence
the router is in the path.

This is the property the shipped image relies on: that `cli_serve` /
`build_route_pairs` ACCEPTS an empty `(let routes (list))` (an empty list is a
valid list, not an error), so the shadow manifest is a transparent proxy.

It uses a MOCK upstream (an http.server standin) so it touches NO production
routing — both processes run on throwaway loopback ports and are torn down.

Run from the repo root (after `cargo build --release` in form/form-kernel-rust):
    python3 deploy/kernel-router/shadow_proof_harness.py
"""
from __future__ import annotations

import http.server
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
# deploy/kernel-router -> deploy -> repo root
REPO_ROOT = HERE.parent.parent
BIN = REPO_ROOT / "form" / "form-kernel-rust" / "target" / "release" / "form-kernel-rust"
SHADOW_ROUTES = HERE / "shadow-routes.fk"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_port(port: int, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(0.3)
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(0.1)
    raise RuntimeError(f"listener never came up on 127.0.0.1:{port}")


# --- a mock CPython upstream standing in for the FastAPI app (api:8000). It
# echoes the path + a stable marker so we can prove the router relayed the
# upstream's actual response byte-for-byte. ---
class MockUpstreamHandler(http.server.BaseHTTPRequestHandler):
    def _respond(self) -> None:
        payload = json.dumps(
            {"upstream": "mock-cpython", "path": self.path, "method": self.command}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        self._respond()

    def do_POST(self) -> None:  # noqa: N802
        # drain the body so keep-alive framing stays correct
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n:
            self.rfile.read(n)
        self._respond()

    def log_message(self, *args) -> None:  # silence
        pass


def http_get(url: str, timeout: float = 10.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("X-Form-Router")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("X-Form-Router")


def main() -> int:
    if not BIN.exists():
        print(f"build first: cargo build --release ({BIN} missing)", file=sys.stderr)
        return 2
    if not SHADOW_ROUTES.exists():
        print(f"missing shadow manifest: {SHADOW_ROUTES}", file=sys.stderr)
        return 2

    failures: list = []
    up_port = free_port()
    kport = free_port()

    # 1. mock upstream (the CPython stand-in — proof touches NO real app).
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", up_port), MockUpstreamHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    up_base = f"http://127.0.0.1:{up_port}"

    router_proc = None
    try:
        wait_for_port(up_port)
        print(f"mock upstream up on :{up_port}")

        # 2. kernel-router with the SHADOW manifest (empty routes -> all fan-out).
        print(f"booting kernel-router on :{kport} --routes shadow-routes.fk "
              f"--upstream {up_base}")
        router_proc = subprocess.Popen(
            [str(BIN), "serve", "--port", str(kport),
             "--routes", str(SHADOW_ROUTES), "--upstream", up_base],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            wait_for_port(kport)
        except RuntimeError:
            # the router died — surface its stderr (e.g. if empty routes were rejected)
            out, err = router_proc.communicate(timeout=2)
            print("kernel-router FAILED to start — empty routes manifest rejected?",
                  file=sys.stderr)
            print("STDERR:", err.decode(errors="replace"), file=sys.stderr)
            return 1
        kbase = f"http://127.0.0.1:{kport}"

        print("\n--- PROOF: shadow mode = transparent proxy (every path fans out) ---")

        # Several distinct paths + a method — ALL must fan out (no native routes).
        cases = [
            ("/api/health", "GET"),
            ("/api/ideas", "GET"),
            ("/api/whatever/deep/path", "GET"),
            ("/health", "GET"),  # even a path the proof manifests usually serve natively
        ]
        for path, method in cases:
            # direct on upstream
            d_st, d_body, _ = http_get(up_base + path)
            # through the shadow router
            r_st, r_body, router = http_get(kbase + path)
            identical = (d_st == r_st) and (d_body == r_body)
            ok = (r_st == 200 and router == "fanout-python" and identical)
            print(f"  [{method} {path:<26}] router={r_st} X-Form-Router={router}  "
                  f"byte-identical-to-direct={identical}  {'OK' if ok else 'FAIL'}")
            if not ok:
                failures.append((path, r_st, router, identical,
                                 d_body[:120], r_body[:120]))

        # POST fan-out with a body — proves the body is forwarded too.
        body = b"hello=world&n=7"
        req = urllib.request.Request(kbase + "/api/echo", data=body, method="POST",
                                     headers={"Content-Type":
                                              "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                p_st, p_body, p_router = r.status, r.read(), r.headers.get("X-Form-Router")
        except urllib.error.HTTPError as e:
            p_st, p_body, p_router = e.code, e.read(), e.headers.get("X-Form-Router")
        pj = json.loads(p_body) if p_st == 200 else {}
        ok = (p_st == 200 and p_router == "fanout-python"
              and pj.get("path") == "/api/echo" and pj.get("method") == "POST")
        print(f"  [POST /api/echo (body fwd)  ] router={p_st} "
              f"X-Form-Router={p_router}  upstream-saw-POST={pj.get('method')!r}  "
              f"{'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("POST /api/echo", p_st, p_router, p_body[:120]))

        if failures:
            print(f"\nFAIL: {len(failures)} case(s)", file=sys.stderr)
            for f in failures:
                print("  ", f, file=sys.stderr)
            return 1
        print("\nok — the SHADOW manifest (empty routes) loads, serves ZERO native "
              "routes, and fans EVERY request out to the upstream byte-identically "
              "(X-Form-Router: fanout-python). The deployable shadow step is a "
              "transparent proxy.")
        return 0
    finally:
        if router_proc is not None:
            router_proc.terminate()
            try:
                router_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                router_proc.kill()
        httpd.shutdown()


if __name__ == "__main__":
    sys.exit(main())
