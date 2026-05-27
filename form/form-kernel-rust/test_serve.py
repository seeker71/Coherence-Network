#!/usr/bin/env python3
"""Proof-of-shape test for `form-kernel-rust serve`.

Spawns the kernel binary as an HTTP listener, curls the two demo routes,
asserts the responses match what the Form recipes return. The point is
not coverage breadth — it is the body's own attestation that "kernel
listens on a port, dispatches via Form, replies with the recipe's value"
works end-to-end with no FastAPI in the path.

Run from this directory:
    cargo build --release
    python3 test_serve.py
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.request
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


def get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=2.0) as r:
        return r.read().decode("utf-8")


def main() -> int:
    if not BIN.exists():
        print(f"build first: cargo build --release ({BIN} missing)", file=sys.stderr)
        return 2
    if not ROUTES.exists():
        print(f"missing routes file: {ROUTES}", file=sys.stderr)
        return 2

    port = free_port()
    proc = subprocess.Popen(
        [str(BIN), "serve", "--port", str(port), "--routes", str(ROUTES)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        wait_for_port(port)

        hello = get(f"http://127.0.0.1:{port}/hello")
        assert hello == "Hello from the kernel", f"/hello → {hello!r}"

        echo = get(f"http://127.0.0.1:{port}/echo?msg=foo")
        assert echo == "foo", f"/echo → {echo!r}"

        echo_sp = get(f"http://127.0.0.1:{port}/echo?msg=hello+world")
        assert echo_sp == "hello world", f"/echo+space → {echo_sp!r}"

        # 404 path
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/missing", timeout=2.0)
            raise AssertionError("/missing should have 404'd")
        except urllib.error.HTTPError as e:
            assert e.code == 404, f"/missing → {e.code}"

        print(f"ok — kernel served /hello, /echo, 404 on 127.0.0.1:{port}")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
