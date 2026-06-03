#!/usr/bin/env python3
"""Proof harness for the kernel-router's REQUEST BODY parsing.

Where router_proof_harness.py proved GET routing, this proves the matured serve
primitive: `cli_serve` now reads the FULL request honoring Content-Length, parses
the body by Content-Type, and marshals it into the handler frame.

What it asserts (real POSTs over a loopback socket):
  - a native POST handler reads form-urlencoded body fields through the SAME
    alist a GET handler reads query params from: POST /sum (a=40&b=2) -> "42".
  - a native POST handler sees a JSON body captured raw under "__body__":
    POST /echo_len ({...}) -> the JSON body's character length.
  - a body LARGER than the kernel's initial 8 KiB read is fully captured
    (Content-Length honored across multiple reads): POST /payload_len with an
    >8 KiB field value -> that exact length. This is the correctness property
    the old single 8 KiB buffer read failed.
  - GET is unchanged: GET /health -> "ok" (native), and a non-native GET fans
    out to the CPython upstream.
  - a non-native POST FANS OUT with its body forwarded: the upstream echoes the
    received body, proving the kernel relayed method + body to Python.

Touches NO production routing — a mock CPython upstream stands in for FastAPI.

Run from form/form-kernel-rust/:
    cargo build --release
    python3 router_body_harness.py
"""
from __future__ import annotations

import http.server
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE / "target" / "release" / "form-kernel-rust"
ROUTES = HERE / "examples" / "router-body-proof.fk"

UPSTREAM_MARKER = "UPSTREAM-CPYTHON-FASTAPI-STANDIN"
# The router's request shape-threshold (form-kernel-rust src/main.rs): a generous
# 64 MiB default, changeable via COH_ROUTER_REQUEST_SHAPE_BYTES. The inherited
# fear-cap was 1 MiB; this harness proves a body past that OLD cap now FLOWS
# (circulation welcomed under the generous default) and a shape past the CURRENT
# threshold gets an OBSERVABLE, NAMED "no" — awareness, not prevention.
OLD_REQUEST_CAP = 1024 * 1024
DEFAULT_REQUEST_SHAPE = 64 * 1024 * 1024


class _UpstreamHandler(http.server.BaseHTTPRequestHandler):
    """The CPython upstream the kernel fans out to (mock FastAPI).

    GET returns a marker + path. POST/PUT/PATCH read the forwarded body and
    echo it back, so the harness can prove the kernel relayed method + body.
    """

    def _reply(self, text: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(text)))
        self.end_headers()
        self.wfile.write(text)

    def do_GET(self):  # noqa: N802
        self._reply(f"{UPSTREAM_MARKER} GET {self.path}\n".encode())

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n else b""
        ctype = self.headers.get("Content-Type", "<none>")
        body = (
            f"{UPSTREAM_MARKER} POST {self.path} ctype={ctype} "
            f"body={raw.decode('utf-8', 'replace')}\n"
        ).encode()
        self._reply(body)

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


def raw_request(port: int, method: str, path: str,
                body: bytes = b"", content_type: str | None = None,
                timeout: float = 5.0):
    """Send one HTTP/1.0 request over a fresh socket; return (status, body, router)."""
    lines = [f"{method} {path} HTTP/1.0", "Host: 127.0.0.1"]
    if body:
        if content_type:
            lines.append(f"Content-Type: {content_type}")
        lines.append(f"Content-Length: {len(body)}")
    lines.append("Connection: close")
    head = ("\r\n".join(lines) + "\r\n\r\n").encode()
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
        s.sendall(head + body)
        chunks = []
        while True:
            b = s.recv(65536)
            if not b:
                break
            chunks.append(b)
    resp = b"".join(chunks)
    head_b, _, body_b = resp.partition(b"\r\n\r\n")
    head_txt = head_b.decode("utf-8", "replace")
    status_line = head_txt.splitlines()[0] if head_txt else ""
    status = status_line.split(" ", 1)[1] if " " in status_line else status_line
    router = None
    for line in head_txt.splitlines()[1:]:
        if line.lower().startswith("x-form-router:"):
            router = line.split(":", 1)[1].strip()
    return status, body_b.decode("utf-8", "replace"), router


def oversize_probe(port: int, declared: int, timeout: float = 5.0):
    """Advertise a Content-Length past the threshold, send only a tiny prefix.

    The shape is sensed on the header alone — the server must not block waiting
    for a body it will never read — and answered observably (413, with a body
    that NAMES the bytes seen, the threshold we hold now, and the changeable
    recipe). Returns (status_line, body) so the caller can check the "no" is
    named, not just statused. Tolerates the reset that can follow a mid-send close.
    """
    head = (
        f"POST /payload_len HTTP/1.0\r\nHost: 127.0.0.1\r\n"
        f"Content-Type: application/x-www-form-urlencoded\r\n"
        f"Content-Length: {declared}\r\nConnection: close\r\n\r\n"
    ).encode()
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    try:
        s.sendall(head + b"payload=" + b"y" * 100)  # tiny prefix only
        try:
            s.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        s.settimeout(timeout)
        resp = b""
        try:
            while True:
                b = s.recv(65536)
                if not b:
                    break
                resp += b
        except (ConnectionResetError, socket.timeout):
            pass
    finally:
        s.close()
    txt = resp.decode("utf-8", "replace")
    status_line = txt.splitlines()[0] if txt else "<empty>"
    body = txt.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in txt else ""
    return status_line, body


def main() -> int:
    if not BIN.exists():
        print(f"build first: cargo build --release ({BIN} missing)", file=sys.stderr)
        return 2
    if not ROUTES.exists():
        print(f"missing routes file: {ROUTES}", file=sys.stderr)
        return 2

    up_port = free_port()
    httpd = http.server.HTTPServer(("127.0.0.1", up_port), _UpstreamHandler)
    up_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    up_thread.start()
    upstream_url = f"http://127.0.0.1:{up_port}"

    kport = free_port()
    proc = subprocess.Popen(
        [str(BIN), "serve", "--port", str(kport),
         "--routes", str(ROUTES), "--upstream", upstream_url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    failures = []
    try:
        wait_for_port(kport)

        # --- 1. native POST form-urlencoded: body fields summed ---
        status, body, router = raw_request(
            kport, "POST", "/sum", b"a=40&b=2",
            "application/x-www-form-urlencoded")
        ok = status == "200 OK" and body == "42" and router == "native-kernel"
        print(f"  [native POST form ] /sum a=40&b=2 -> {status} {body!r} "
              f"router={router}  {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("POST /sum", status, body, router))

        # --- 2. native POST JSON: raw body captured under __body__ ---
        json_body = b'{"name":"coherence","weight":0.8125}'
        status, body, router = raw_request(
            kport, "POST", "/echo_len", json_body, "application/json")
        ok = (status == "200 OK" and body == str(len(json_body))
              and router == "native-kernel")
        print(f"  [native POST json ] /echo_len ({len(json_body)}B JSON) -> "
              f"{status} {body!r} (expect {len(json_body)}) router={router}  "
              f"{'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("POST /echo_len", status, body, router))

        # --- 3. >8 KiB body fully captured (Content-Length across reads) ---
        big_n = 20000  # well past the 8192-byte initial read
        big_val = "x" * big_n
        big_body = ("payload=" + big_val).encode()
        status, body, router = raw_request(
            kport, "POST", "/payload_len", big_body,
            "application/x-www-form-urlencoded")
        ok = (status == "200 OK" and body == str(big_n)
              and router == "native-kernel")
        print(f"  [native POST >8KiB] /payload_len ({len(big_body)}B body) -> "
              f"{status} field-len={body} (expect {big_n}) router={router}  "
              f"{'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("POST /payload_len >8KiB", status, body, router))

        # --- 4. GET unchanged: native ---
        status, body, router = raw_request(kport, "GET", "/health")
        ok = status == "200 OK" and body == "ok" and router == "native-kernel"
        print(f"  [native GET       ] /health -> {status} {body!r} "
              f"router={router}  {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("GET /health", status, body, router))

        # --- 5. GET unchanged: fan-out to CPython upstream ---
        status, body, router = raw_request(kport, "GET", "/api/whatever")
        ok = (status == "200 OK" and UPSTREAM_MARKER in body
              and "GET /api/whatever" in body and router == "fanout-python")
        print(f"  [fanout GET       ] /api/whatever -> {status} via CPython "
              f"router={router}  {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("GET /api/whatever", status, body, router))

        # --- 6. POST fan-out: method + body forwarded to CPython upstream ---
        fan_body = b"hello=world&n=7"
        status, body, router = raw_request(
            kport, "POST", "/api/echo", fan_body,
            "application/x-www-form-urlencoded")
        ok = (status == "200 OK" and UPSTREAM_MARKER in body
              and "POST /api/echo" in body
              and "body=hello=world&n=7" in body
              and router == "fanout-python")
        print(f"  [fanout POST body ] /api/echo (body forwarded) -> {status} "
              f"router={router}  {'OK' if ok else 'FAIL'}")
        print(f"       upstream saw: {body.strip()!r}")
        if not ok:
            failures.append(("POST /api/echo fanout", status, body, router))

        # --- 7a. a body PAST THE OLD 1 MiB cap now FLOWS — observed and welcomed
        #          under the generous default shape, not prevented at an old wall ---
        past_old = OLD_REQUEST_CAP + 200_000  # ~1.2 MiB: over the OLD cap, under default
        flow_val = "y" * (past_old - len("payload="))
        flow_body = ("payload=" + flow_val).encode()
        status, body, router = raw_request(
            kport, "POST", "/payload_len", flow_body,
            "application/x-www-form-urlencoded")
        ok = (status == "200 OK" and body == str(len(flow_val))
              and router == "native-kernel")
        print(f"  [flows past old cap] /payload_len ({len(flow_body)}B, > {OLD_REQUEST_CAP} "
              f"old cap) -> {status} len={body}  {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("body past old cap flows", status, body, router))

        # --- 7b. a shape PAST THE CURRENT threshold gets an OBSERVABLE, NAMED "no",
        #          sensed on the Content-Length header alone (the body never sent):
        #          the response names the bytes seen, names the changeable recipe
        #          (COH_ROUTER_REQUEST_SHAPE_BYTES), and invites a change — not a
        #          silent wall and not a bare status code ---
        declared = DEFAULT_REQUEST_SHAPE + 5_000_000  # ~69 MiB declared, body never sent
        status_line, no_body = oversize_probe(kport, declared)
        names_shape = (
            "413" in status_line
            and str(declared) in no_body
            and "COH_ROUTER_REQUEST_SHAPE_BYTES" in no_body
            and "change" in no_body.lower()
        )
        print(f"  [shape > recipe   ] declared CL={declared} -> {status_line!r}, "
              f"names shape+recipe={names_shape}  {'OK' if names_shape else 'FAIL'}")
        if not names_shape:
            failures.append(("observable named no", status_line, no_body[:160], None))

        if failures:
            print(f"\nFAIL: {len(failures)} case(s) did not match", file=sys.stderr)
            for f in failures:
                print(f"   {f}", file=sys.stderr)
            return 1
        print("\nok — kernel-router READ REQUEST BODIES: form-urlencoded fields "
              "merged into the handler alist, JSON captured raw, a >8 KiB body "
              "fully captured (Content-Length honored), GET unchanged, POST "
              "fan-out forwarded its body to CPython; a body past the OLD 1 MiB "
              "cap now FLOWS under the generous default shape, and a shape past "
              "the current threshold gets an OBSERVABLE, NAMED no (the bytes seen "
              "+ the changeable COH_ROUTER_REQUEST_SHAPE_BYTES recipe) — awareness, "
              "not prevention.")
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
