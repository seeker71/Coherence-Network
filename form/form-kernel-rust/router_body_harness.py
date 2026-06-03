#!/usr/bin/env python3
"""Proof harness for the kernel-router's REQUEST BODY parsing + RESPONSE STREAMING.

Where router_proof_harness.py proved GET routing, this proves the matured serve
primitive: `cli_serve` now reads the FULL request honoring Content-Length, parses
the body by Content-Type, marshals it into the handler frame, and STREAMS the
fan-out response body straight back to the client — the body never held whole.

What it asserts (real requests over a loopback socket):
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

RESPONSE STREAMING (the body-buffer-dissolving proof):
  - a LARGE (16 MiB) Content-Length-framed fan-out response relays BYTE-IDENTICAL
    through the router (sha256 of the client body == sha256 of the upstream body,
    over all 256 byte values — proving the relay is binary-exact, not a lossy
    UTF-8 round-trip). The body that would have stressed the old whole-body buffer
    flows through a fixed 64 KiB pipe.
  - THE BUFFER IS GONE: with COH_ROUTER_RESPONSE_SHAPE_BYTES set to a SMALL 1 MiB
    threshold, a 16 MiB Content-Length body STILL relays 200 byte-identical. Under
    the old buffered code that exact threshold would have 502'd the body
    ("upstream response shape is N bytes — larger than we can hold"); streaming
    dissolves the gate — the size is no longer a memory ceiling because the body
    never occupies one buffer. This is the load-bearing proof that the whole-body
    Vec is gone, not merely larger.
  - a CHUNKED (Transfer-Encoding: chunked) fan-out response relays correctly: the
    router passes the raw chunk framing through to the terminating 0-length chunk;
    the de-chunked body matches the upstream's.
  - an UNFRAMED (no Content-Length, read-to-close) fan-out response relays
    correctly: the router pipes upstream→client until the upstream closes.

Touches NO production routing — a mock CPython upstream stands in for FastAPI.

Run from form/form-kernel-rust/:
    cargo build --release
    python3 router_body_harness.py
"""
from __future__ import annotations

import hashlib
import http.server
import os
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

# --- response-streaming proof fixtures ---
# A LARGE response body, deterministic and byte-known on both sides. Cycling all
# 256 byte values makes it BINARY (non-UTF-8 bytes present), so a byte-identical
# relay proves the router pipes raw bytes — not the old `String::from_utf8_lossy`
# round-trip that would have corrupted bytes >= 0x80. 16 MiB is far past any single
# read buffer and large enough that holding it whole would be the old behavior.
BIG_BODY_LEN = 16 * 1024 * 1024
_BIG_PATTERN = bytes(range(256))
BIG_BODY = (_BIG_PATTERN * (BIG_BODY_LEN // 256 + 1))[:BIG_BODY_LEN]
BIG_BODY_SHA = hashlib.sha256(BIG_BODY).hexdigest()

# The SMALL response shape-threshold the "buffer is gone" case runs the router
# under: a 16 MiB body STREAMS through it though the threshold is 1 MiB, because
# the body never occupies a buffer. Under the old buffered code this exact value
# would have 502'd the 16 MiB body.
SMALL_RESPONSE_SHAPE = 1024 * 1024

# Bodies for the chunked + unframed (read-to-close) framings — moderate size, also
# spanning all byte values so the relay is proven binary-exact on those paths too.
CHUNKED_BODY = (_BIG_PATTERN * 9000)[: 9000 * 256]      # ~2.2 MiB
UNFRAMED_BODY = (_BIG_PATTERN * 5000)[: 5000 * 256]     # ~1.2 MiB

# An ADVERSARIAL chunked body whose DATA literally contains the bytes `0\r\n\r\n`
# (the chunk-terminator byte run). A naive byte-scan for the terminator would
# truncate HERE; the router's chunk-BOUNDARY parser must skip these as data and
# stop only at the real 0-length chunk. The trap bytes sit in the middle of a chunk.
CHUNKED_TRAP_BODY = b"before-" + b"0\r\n\r\n" + b"-after-" + (b"x" * 100000) + b"-end"


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

    # The streaming-proof responses are written with RAW socket bytes so this mock
    # controls the EXACT framing per path (Content-Length / chunked / read-to-close)
    # without changing the handler's default protocol for the existing tests. Each
    # sends `Connection: close` and closes after — orthogonal to the body streaming
    # the router proves (the router frames by Content-Length / Transfer-Encoding /
    # absence, not by the connection lifecycle).
    def _raw_big(self):
        # Content-Length-framed LARGE body (16 MiB). The router must pipe exactly
        # this many bytes to the client, byte-identical, without buffering them.
        self.close_connection = True
        head = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/octet-stream\r\n"
            b"Content-Length: " + str(len(BIG_BODY)).encode() + b"\r\n"
            b"Connection: close\r\n\r\n"
        )
        self.wfile.write(head)
        self.wfile.write(BIG_BODY)

    def _raw_chunked(self):
        # Transfer-Encoding: chunked. Write several chunks then the terminating
        # 0-length chunk. The router relays the raw chunk framing through.
        self.close_connection = True
        head = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/octet-stream\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"Connection: close\r\n\r\n"
        )
        self.wfile.write(head)
        step = 64 * 1024
        for i in range(0, len(CHUNKED_BODY), step):
            piece = CHUNKED_BODY[i : i + step]
            self.wfile.write(f"{len(piece):X}\r\n".encode() + piece + b"\r\n")
        self.wfile.write(b"0\r\n\r\n")  # terminating 0-length chunk

    def _raw_chunked_trap(self):
        # A chunked response whose chunk DATA contains the terminator byte run
        # `0\r\n\r\n`. Emitted as ONE chunk so those bytes are data, not a boundary.
        # The router must relay the whole body and stop only at the real 0-chunk.
        self.close_connection = True
        head = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/octet-stream\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"Connection: close\r\n\r\n"
        )
        self.wfile.write(head)
        body = CHUNKED_TRAP_BODY
        self.wfile.write(f"{len(body):X}\r\n".encode() + body + b"\r\n")
        self.wfile.write(b"0\r\n\r\n")  # the REAL terminating 0-length chunk

    def _raw_unframed(self):
        # No Content-Length, no chunked: the body ends at connection close. The
        # router pipes upstream->client until EOF, then closes the client too.
        self.close_connection = True
        head = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/octet-stream\r\n"
            b"Connection: close\r\n\r\n"
        )
        self.wfile.write(head)
        self.wfile.write(UNFRAMED_BODY)
        # returning from the handler closes the socket (close_connection=True),
        # which is the body-end marker for a read-to-close response.

    def do_GET(self):  # noqa: N802
        if self.path == "/stream/big":
            return self._raw_big()
        if self.path == "/stream/chunked":
            return self._raw_chunked()
        if self.path == "/stream/chunked-trap":
            return self._raw_chunked_trap()
        if self.path == "/stream/unframed":
            return self._raw_unframed()
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


def raw_request_bytes(port: int, method: str, path: str, timeout: float = 30.0):
    """Send one HTTP/1.1 request and read the FULL raw response as BYTES.

    Returns (status, headers_lower_dict, raw_body_bytes). Reads to connection
    close (the client hop sends `Connection: close`, so the router closes after
    the response). The body is returned as exact bytes — never decoded — so a
    large/binary streamed response can be hashed and compared byte-for-byte. A
    generous timeout covers a multi-MiB stream over loopback.
    """
    head = (
        f"{method} {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n"
    ).encode()
    chunks = []
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
        s.sendall(head)
        s.settimeout(timeout)
        while True:
            b = s.recv(262144)
            if not b:
                break
            chunks.append(b)
    resp = b"".join(chunks)
    head_b, _, body_b = resp.partition(b"\r\n\r\n")
    head_txt = head_b.decode("utf-8", "replace")
    lines = head_txt.splitlines()
    status_line = lines[0] if lines else ""
    status = status_line.split(" ", 1)[1] if " " in status_line else status_line
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
    return status, headers, body_b


def dechunk(raw: bytes) -> bytes:
    """Decode an HTTP/1.1 chunked transfer-encoding body to its raw bytes.

    The router relays the chunk framing verbatim (it does NOT de-chunk), so the
    harness de-chunks here to recover the original body and compare it to the
    upstream's. Stops at the terminating 0-length chunk.
    """
    out = bytearray()
    i = 0
    n = len(raw)
    while i < n:
        j = raw.find(b"\r\n", i)
        if j < 0:
            break
        size = int(raw[i:j].split(b";", 1)[0], 16)  # ignore any chunk extensions
        if size == 0:
            break
        start = j + 2
        out += raw[start : start + size]
        i = start + size + 2  # skip the chunk's trailing CRLF
    return bytes(out)


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
    # ThreadingHTTPServer so a streaming relay (the router holds the upstream
    # connection open while piping a multi-MiB body) cannot serialize behind / wedge
    # another concurrent fan-out — a single-threaded upstream could deadlock a worker
    # pool mid-stream.
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", up_port), _UpstreamHandler)
    up_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    up_thread.start()
    upstream_url = f"http://127.0.0.1:{up_port}"

    kport = free_port()
    proc = subprocess.Popen(
        [str(BIN), "serve", "--port", str(kport),
         "--routes", str(ROUTES), "--upstream", upstream_url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    # A SECOND router under a deliberately SMALL response shape-threshold (1 MiB),
    # for the "buffer is gone" proof: a 16 MiB body STREAMS through it though the
    # threshold is 1 MiB. Under the OLD buffered code this exact env would have 502'd
    # the body ("upstream response shape is N bytes — larger than we can hold").
    small_port = free_port()
    small_env = dict(os.environ, COH_ROUTER_RESPONSE_SHAPE_BYTES=str(SMALL_RESPONSE_SHAPE))
    small_proc = subprocess.Popen(
        [str(BIN), "serve", "--port", str(small_port),
         "--routes", str(ROUTES), "--upstream", upstream_url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=small_env,
    )
    failures = []
    try:
        wait_for_port(kport)
        wait_for_port(small_port)

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

        # --- 8a. RESPONSE STREAMING — byte-identical LARGE response. A 16 MiB
        #          Content-Length-framed fan-out body relays BYTE-IDENTICAL through
        #          the router. Comparing the sha256 (over all 256 byte values)
        #          proves the relay is binary-exact — not a lossy UTF-8 round-trip —
        #          at a size that would have stressed the old whole-body buffer. ---
        status, headers, raw_body = raw_request_bytes(kport, "GET", "/stream/big")
        got_sha = hashlib.sha256(raw_body).hexdigest()
        ok = (
            status == "200 OK"
            and headers.get("x-form-router") == "fanout-python"
            and len(raw_body) == BIG_BODY_LEN
            and got_sha == BIG_BODY_SHA
            and headers.get("content-length") == str(BIG_BODY_LEN)
        )
        print(f"  [stream big 16MiB ] /stream/big -> {status} "
              f"{len(raw_body)}B (expect {BIG_BODY_LEN}) sha-match={got_sha == BIG_BODY_SHA} "
              f"CL-relayed={headers.get('content-length') == str(BIG_BODY_LEN)} "
              f"router={headers.get('x-form-router')}  {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("stream big byte-identical", status,
                             f"len={len(raw_body)} sha_ok={got_sha == BIG_BODY_SHA}", got_sha))

        # --- 8b. THE BUFFER IS GONE. The SAME 16 MiB body relays 200 byte-identical
        #          through a router whose response shape-threshold is only 1 MiB.
        #          Under the old buffered code this exact env 502'd the body
        #          ("upstream response shape is N bytes — larger than we can hold").
        #          It flowing proves the body never occupies a whole-body buffer —
        #          the size is no longer a memory gate, only the (small) head is. ---
        status, headers, raw_body = raw_request_bytes(small_port, "GET", "/stream/big")
        got_sha = hashlib.sha256(raw_body).hexdigest()
        ok = (
            status == "200 OK"
            and headers.get("x-form-router") == "fanout-python"
            and len(raw_body) == BIG_BODY_LEN
            and got_sha == BIG_BODY_SHA
        )
        print(f"  [buffer-gone 1MiB ] /stream/big through 1 MiB-shape router "
              f"({BIG_BODY_LEN} >> {SMALL_RESPONSE_SHAPE}) -> {status} "
              f"{len(raw_body)}B sha-match={got_sha == BIG_BODY_SHA}  "
              f"{'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("buffer-gone (16MiB through 1MiB shape)", status,
                             f"len={len(raw_body)} sha_ok={got_sha == BIG_BODY_SHA}", None))

        # --- 8c. CHUNKED response relayed. The upstream responds Transfer-Encoding:
        #          chunked; the router relays the raw chunk framing through to the
        #          terminating 0-length chunk. The client sees chunked framing; the
        #          de-chunked body matches the upstream's byte-for-byte. ---
        status, headers, raw_body = raw_request_bytes(kport, "GET", "/stream/chunked")
        is_chunked = headers.get("transfer-encoding", "").lower() == "chunked"
        decoded = dechunk(raw_body) if is_chunked else raw_body
        ok = (
            status == "200 OK"
            and headers.get("x-form-router") == "fanout-python"
            and is_chunked
            and "content-length" not in headers  # chunked has NO Content-Length
            and decoded == CHUNKED_BODY
        )
        print(f"  [stream chunked   ] /stream/chunked -> {status} "
              f"te-chunked={is_chunked} dechunked={len(decoded)}B "
              f"(expect {len(CHUNKED_BODY)}) match={decoded == CHUNKED_BODY} "
              f"router={headers.get('x-form-router')}  {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("stream chunked relay", status,
                             f"chunked={is_chunked} len={len(decoded)} "
                             f"match={decoded == CHUNKED_BODY}", None))

        # --- 8c-trap. CHUNKED with the terminator byte run `0\r\n\r\n` INSIDE chunk
        #          data. The router's chunk-BOUNDARY parser must skip it as data and
        #          stop only at the real 0-length chunk — a naive byte-scan would
        #          truncate the body here. The full de-chunked body must come back. ---
        status, headers, raw_body = raw_request_bytes(kport, "GET", "/stream/chunked-trap")
        is_chunked = headers.get("transfer-encoding", "").lower() == "chunked"
        decoded = dechunk(raw_body) if is_chunked else raw_body
        ok = (
            status == "200 OK"
            and headers.get("x-form-router") == "fanout-python"
            and is_chunked
            and decoded == CHUNKED_TRAP_BODY  # not truncated at the in-data terminator
        )
        print(f"  [chunked trap     ] /stream/chunked-trap (0CRLFCRLF in data) -> {status} "
              f"dechunked={len(decoded)}B (expect {len(CHUNKED_TRAP_BODY)}) "
              f"match={decoded == CHUNKED_TRAP_BODY}  {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("chunked in-data terminator not truncated", status,
                             f"len={len(decoded)} expect={len(CHUNKED_TRAP_BODY)} "
                             f"match={decoded == CHUNKED_TRAP_BODY}", None))

        # --- 8d. UNFRAMED (read-to-close) response relayed. The upstream sends no
        #          Content-Length and no chunked, then closes; the router pipes
        #          upstream->client until EOF and closes the client too. The body
        #          arrives byte-identical; the client response is close-framed. ---
        status, headers, raw_body = raw_request_bytes(kport, "GET", "/stream/unframed")
        ok = (
            status == "200 OK"
            and headers.get("x-form-router") == "fanout-python"
            and "content-length" not in headers      # no length: close-framed
            and headers.get("transfer-encoding", "").lower() != "chunked"
            and headers.get("connection", "").lower() == "close"
            and raw_body == UNFRAMED_BODY
        )
        print(f"  [stream unframed  ] /stream/unframed -> {status} "
              f"close-framed={headers.get('connection','').lower() == 'close'} "
              f"{len(raw_body)}B (expect {len(UNFRAMED_BODY)}) "
              f"match={raw_body == UNFRAMED_BODY} "
              f"router={headers.get('x-form-router')}  {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("stream unframed relay", status,
                             f"len={len(raw_body)} match={raw_body == UNFRAMED_BODY}", None))

        if failures:
            print(f"\nFAIL: {len(failures)} case(s) did not match", file=sys.stderr)
            for f in failures:
                print(f"   {f}", file=sys.stderr)
            return 1
        print("\nok — kernel-router READ REQUEST BODIES and STREAMS RESPONSES: "
              "form-urlencoded fields merged into the handler alist, JSON captured "
              "raw, a >8 KiB body fully captured (Content-Length honored), GET "
              "unchanged, POST fan-out forwarded its body to CPython; a body past "
              "the OLD 1 MiB cap now FLOWS under the generous default shape, and a "
              "shape past the current threshold gets an OBSERVABLE, NAMED no. "
              "RESPONSE STREAMING: a 16 MiB Content-Length fan-out body relays "
              "BYTE-IDENTICAL (sha256 over all 256 byte values); the SAME body "
              "relays 200 byte-identical through a router whose response shape is "
              "only 1 MiB (the whole-body buffer is GONE — size is no longer the "
              "gate); a chunked response relays its raw chunk framing through (the "
              "de-chunked body matches); an unframed read-to-close response pipes "
              "upstream->client to EOF byte-identical. The router never holds a "
              "response body whole — it observes circulation AS IT FLOWS.")
        return 0
    finally:
        proc.terminate()
        small_proc.terminate()
        for p in (proc, small_proc):
            try:
                p.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                p.kill()
        httpd.shutdown()


if __name__ == "__main__":
    sys.exit(main())
