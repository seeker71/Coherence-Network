#!/usr/bin/env python3
"""Proof-of-shape test for `form-kernel-rust serve`.

Spawns the kernel binary as an HTTP listener, curls the two demo routes,
asserts the responses match what the Form recipes return, then starts a
tiny Python upstream and proves unmatched routes fan out through the
kernel front door. The point is not coverage breadth — it is the body's
own attestation that "kernel listens on a port, dispatches via Form,
replies with the recipe's value, and can route the not-yet-native tail"
works end-to-end.

Run from this directory:
    cargo build --release
    python3 test_serve.py
"""
from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE / "target" / "release" / "form-kernel-rust"
ROUTES = HERE / "examples" / "routes.fk"


def free_port() -> int:
    """Ask the kernel for an unused port; close it before the kernel binds."""
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


class UpstreamHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/python-tail"):
            body = f"python upstream saw {self.path}".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = b"upstream missing"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def get_response(url: str) -> tuple[int, str, str]:
    with urllib.request.urlopen(url, timeout=2.0) as r:
        body = r.read().decode("utf-8")
        return r.status, r.headers.get("X-Form-Router", ""), body


def get(url: str) -> str:
    return get_response(url)[2]


def start_kernel(port: int, upstream: str | None = None) -> subprocess.Popen[bytes]:
    args = [str(BIN), "serve", "--port", str(port), "--routes", str(ROUTES)]
    if upstream is not None:
        args.extend(["--upstream", upstream])
    return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def start_upstream(port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), UpstreamHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main() -> int:
    if not BIN.exists():
        print(f"build first: cargo build --release ({BIN} missing)", file=sys.stderr)
        return 2
    if not ROUTES.exists():
        print(f"missing routes file: {ROUTES}", file=sys.stderr)
        return 2

    port = free_port()
    proc = start_kernel(port)
    try:
        wait_for_port(port)

        status, router, hello = get_response(f"http://127.0.0.1:{port}/hello")
        assert status == 200, f"/hello status -> {status}"
        assert router == "native-kernel", f"/hello router -> {router!r}"
        assert hello == "Hello from the kernel", f"/hello → {hello!r}"

        status, router, echo = get_response(f"http://127.0.0.1:{port}/echo?msg=foo")
        assert status == 200, f"/echo status -> {status}"
        assert router == "native-kernel", f"/echo router -> {router!r}"
        assert echo == "foo", f"/echo → {echo!r}"

        echo_sp = get(f"http://127.0.0.1:{port}/echo?msg=hello+world")
        assert echo_sp == "hello world", f"/echo+space → {echo_sp!r}"

        # 404 path
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/missing", timeout=2.0)
            raise AssertionError("/missing should have 404'd")
        except urllib.error.HTTPError as e:
            assert e.code == 404, f"/missing → {e.code}"
            assert e.headers.get("X-Form-Router") == "local-control"

        print(f"ok — kernel served /hello, /echo, 404 on 127.0.0.1:{port}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()

    upstream_port = free_port()
    upstream = start_upstream(upstream_port)
    router_port = free_port()
    proc = start_kernel(router_port, f"http://127.0.0.1:{upstream_port}")
    try:
        wait_for_port(router_port)

        status, router, hello = get_response(f"http://127.0.0.1:{router_port}/hello")
        assert status == 200, f"fanout-mode /hello status -> {status}"
        assert router == "native-kernel", f"fanout-mode /hello router -> {router!r}"
        assert hello == "Hello from the kernel", f"fanout-mode /hello -> {hello!r}"

        status, router, tail = get_response(
            f"http://127.0.0.1:{router_port}/python-tail?msg=still+python"
        )
        assert status == 200, f"/python-tail status -> {status}"
        assert router == "fanout-python", f"/python-tail router -> {router!r}"
        assert tail == "python upstream saw /python-tail?msg=still+python", tail

        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{router_port}/upstream-missing",
                timeout=2.0,
            )
            raise AssertionError("/upstream-missing should have 404'd upstream")
        except urllib.error.HTTPError as e:
            assert e.code == 404, f"/upstream-missing -> {e.code}"
            assert e.headers.get("X-Form-Router") == "fanout-python"
            assert e.read().decode("utf-8") == "upstream missing"

        print(
            "ok — kernel stayed native for /hello and fanned out "
            f"/python-tail on 127.0.0.1:{router_port}"
        )
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()
        upstream.shutdown()


if __name__ == "__main__":
    sys.exit(main())
