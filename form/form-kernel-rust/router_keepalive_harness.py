#!/usr/bin/env python3
"""Proof harness for the kernel-router's HTTP/1.1 KEEP-ALIVE.

Where router_body_harness.py proved one request per (HTTP/1.0, close) connection,
this proves the matured serve primitive: `cli_serve` now serves HTTP/1.1 with
keep-alive — MULTIPLE requests on ONE TCP connection, each Content-Length-framed
so the client knows exactly where one response ends and the next begins.

What it asserts (real sockets over loopback, the kernel-router in front of a mock
CPython upstream — touches NO production routing):

  1. N sequential requests on ONE connection: open a single socket, send N
     HTTP/1.1 requests WITHOUT closing between them, read N responses by their
     Content-Length. All N succeed with their OWN correct value (distinct inputs),
     and every response carries `Connection: keep-alive`. ONE connect, N
     request/response cycles — the keep-alive property.

  2. Pipelined requests (the leftover-bytes hazard): send two requests in a
     SINGLE send() — the server's read for request 1 pulls request 2's bytes too;
     it must NOT drop them. Both responses come back correct. This is the classic
     keep-alive byte-drop bug, proven absent.

  3. `Connection: close` honored: a request with `Connection: close` -> the
     response says `Connection: close` and the server closes the socket (the next
     recv returns EOF), no hang.

  4. HTTP/1.0 default-close (back-compat): an HTTP/1.0 request with no Connection
     header -> the server closes after responding (HTTP/1.0 default), so the
     existing HTTP/1.0 harness clients keep working.

  5. Idle timeout reaps the connection: open a connection, send one request, then
     sit IDLE (send nothing more). The server closes it after ~KEEPALIVE_IDLE
     seconds (recv returns EOF) — an idle keep-alive connection does NOT pin a
     worker forever.

  6. An idle keep-alive connection does NOT starve OTHER workers: with >1 worker,
     while connection A idles (holding one worker in its keep-alive loop), a fresh
     connection B is served IMMEDIATELY by another worker. (Honest tradeoff: a
     worker serving a keep-alive client is unavailable to others until close /
     idle-timeout; this proves the POOL still serves, not that it is free.)

  7. Keep-alive saves the TCP handshake: N requests on one connection vs N fresh
     connections — the reused connection is measurably faster (no per-request
     connect()).

Run from form/form-kernel-rust/:
    cargo build --release
    python3 router_keepalive_harness.py
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
# Mirrors KEEPALIVE_IDLE_TIMEOUT in form-kernel-rust src/main.rs (seconds).
KEEPALIVE_IDLE = 5.0


class _UpstreamHandler(http.server.BaseHTTPRequestHandler):
    """Mock CPython upstream (stands in for FastAPI; no production routing)."""

    def do_GET(self):  # noqa: N802
        text = f"{UPSTREAM_MARKER} GET {self.path}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(text)))
        self.end_headers()
        self.wfile.write(text)

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


class Conn:
    """A persistent client connection that frames responses by Content-Length.

    Unlike a read-until-close client, this reads EXACTLY one response (headers +
    Content-Length body) and leaves the socket open + any surplus bytes buffered
    for the next response — exactly what an HTTP/1.1 keep-alive client must do.
    """

    def __init__(self, port: int, timeout: float = 10.0):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.buf = b""

    def send(self, raw: bytes) -> None:
        self.sock.sendall(raw)

    def _fill(self) -> bool:
        b = self.sock.recv(65536)
        if not b:
            return False
        self.buf += b
        return True

    def read_response(self):
        """Read one HTTP response framed by Content-Length. Returns
        (status, headers_lower_dict, body_text)."""
        # Read until we have the full header block.
        while b"\r\n\r\n" not in self.buf:
            if not self._fill():
                raise EOFError("connection closed before full response headers")
        head_b, _, rest = self.buf.partition(b"\r\n\r\n")
        self.buf = rest
        head_txt = head_b.decode("utf-8", "replace")
        lines = head_txt.split("\r\n")
        status_line = lines[0]
        status = status_line.split(" ", 1)[1] if " " in status_line else status_line
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        n = int(headers.get("content-length", "0"))
        while len(self.buf) < n:
            if not self._fill():
                raise EOFError("connection closed before full response body")
        body = self.buf[:n].decode("utf-8", "replace")
        self.buf = self.buf[n:]
        return status, headers, body

    def recv_is_eof(self, timeout: float) -> bool:
        """Return True iff the peer closed (recv returns b'') within `timeout`."""
        self.sock.settimeout(timeout)
        try:
            b = self.sock.recv(1)
            return b == b""
        except socket.timeout:
            return False
        except OSError:
            return True

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def req(method: str, path: str, *, http_version="1.1",
        connection: str | None = None) -> bytes:
    lines = [f"{method} {path} HTTP/{http_version}", "Host: 127.0.0.1"]
    if connection is not None:
        lines.append(f"Connection: {connection}")
    return ("\r\n".join(lines) + "\r\n\r\n").encode()


def main() -> int:
    if not BIN.exists():
        print(f"build first: cargo build --release ({BIN} missing)", file=sys.stderr)
        return 2
    if not ROUTES.exists():
        print(f"missing routes file: {ROUTES}", file=sys.stderr)
        return 2

    up_port = free_port()
    httpd = http.server.HTTPServer(("127.0.0.1", up_port), _UpstreamHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    upstream_url = f"http://127.0.0.1:{up_port}"

    kport = free_port()
    # >1 worker so test 6 can prove an idle connection doesn't starve the pool.
    proc = subprocess.Popen(
        [str(BIN), "serve", "--port", str(kport), "--routes", str(ROUTES),
         "--upstream", upstream_url, "--workers", "4"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    failures = []
    try:
        wait_for_port(kport)

        # --- 1. N sequential requests on ONE connection ---
        c = Conn(kport)
        n = 8
        all_ok = True
        for i in range(n):
            a, b = i, i * 3  # distinct inputs each request
            c.send(req("GET", f"/sum?a={a}&b={b}"))
            status, headers, body = c.read_response()
            want = str(a + b)
            ok = (status == "200 OK" and body == want
                  and headers.get("connection") == "keep-alive"
                  and headers.get("x-form-router") == "native-kernel")
            all_ok = all_ok and ok
        c.close()
        print(f"  [1 conn x {n} reqs ] sequential on ONE connection, distinct "
              f"inputs -> all {'OK' if all_ok else 'FAIL'} "
              f"(each Connection: keep-alive, correct sum)")
        if not all_ok:
            failures.append(("N sequential on one connection",))

        # --- 2. PIPELINED: two requests in ONE send (leftover-bytes hazard) ---
        c = Conn(kport)
        pipelined = (req("GET", "/sum?a=10&b=5") + req("GET", "/sum?a=100&b=23"))
        c.send(pipelined)  # both requests in a single TCP write
        s1, h1, b1 = c.read_response()
        s2, h2, b2 = c.read_response()
        ok = (s1 == "200 OK" and b1 == "15" and s2 == "200 OK" and b2 == "123")
        c.close()
        print(f"  [pipelined 2-in-1 ] two reqs in ONE send -> {b1!r}, {b2!r} "
              f"(expect '15','123')  {'OK' if ok else 'FAIL'}  "
              f"(leftover bytes carried, none dropped)")
        if not ok:
            failures.append(("pipelined leftover-bytes", s1, b1, s2, b2))

        # --- 3. Connection: close honored ---
        c = Conn(kport)
        c.send(req("GET", "/health", connection="close"))
        status, headers, body = c.read_response()
        closed = c.recv_is_eof(timeout=2.0)
        ok = (status == "200 OK" and body == "ok"
              and headers.get("connection") == "close" and closed)
        print(f"  [Connection close ] /health Connection: close -> {body!r} "
              f"resp-conn={headers.get('connection')!r} server-closed={closed}  "
              f"{'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("Connection: close honored", status, body,
                             headers.get("connection"), closed))

        # --- 4. HTTP/1.0 default-close (back-compat) ---
        c = Conn(kport)
        c.send(req("GET", "/health", http_version="1.0"))  # no Connection header
        status, headers, body = c.read_response()
        closed = c.recv_is_eof(timeout=2.0)
        ok = (status == "200 OK" and body == "ok"
              and headers.get("connection") == "close" and closed)
        print(f"  [HTTP/1.0 default ] /health (1.0, no Conn hdr) -> {body!r} "
              f"resp-conn={headers.get('connection')!r} server-closed={closed}  "
              f"{'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("HTTP/1.0 default-close", status, body,
                             headers.get("connection"), closed))

        # --- 6. (run before 5, sharing the idle wait) An idle keep-alive conn
        #         does NOT starve other workers: open A, send one req, leave A
        #         IDLE (its worker now loops waiting); immediately serve B on a
        #         fresh connection — another worker must serve it at once. ---
        a_conn = Conn(kport)
        a_conn.send(req("GET", "/sum?a=1&b=1"))  # A's first (and only) request
        _ = a_conn.read_response()               # A now idles in its keep-alive loop
        t0 = time.monotonic()
        b_conn = Conn(kport)
        b_conn.send(req("GET", "/sum?a=7&b=8", connection="close"))
        sB, hB, bB = b_conn.read_response()
        b_serve_ms = (time.monotonic() - t0) * 1000.0
        b_conn.close()
        # B served fast (well under the idle timeout) -> A's idle conn did not
        # block the pool; another worker took B.
        ok = (sB == "200 OK" and bB == "15" and b_serve_ms < KEEPALIVE_IDLE * 1000 / 2)
        print(f"  [no-starve pool   ] B served in {b_serve_ms:.1f} ms while A "
              f"idles -> {bB!r} (expect '15')  {'OK' if ok else 'FAIL'}  "
              f"(idle keep-alive conn did not starve other workers)")
        if not ok:
            failures.append(("idle does not starve pool", sB, bB, b_serve_ms))

        # --- 5. Idle timeout reaps the connection: A (still open, idle since its
        #         one request above) must be closed by the server after the idle
        #         timeout — recv returns EOF. Prove it does NOT pin forever. ---
        elapsed_since_a = time.monotonic() - t0
        # Wait out the remainder of the idle window plus a margin.
        wait_left = max(0.0, KEEPALIVE_IDLE - elapsed_since_a) + 2.0
        a_closed = a_conn.recv_is_eof(timeout=wait_left)
        a_conn.close()
        print(f"  [idle timeout reap] idle conn A closed by server after "
              f"~{KEEPALIVE_IDLE:.0f}s idle (waited {wait_left:.1f}s) -> "
              f"server-closed={a_closed}  {'OK' if a_closed else 'FAIL'}")
        if not a_closed:
            failures.append(("idle timeout reap", a_closed))

        # --- 7. keep-alive saves the TCP handshake (N reused vs N fresh) ---
        reps = 30
        # N requests on ONE reused connection.
        c = Conn(kport)
        t0 = time.monotonic()
        for i in range(reps):
            c.send(req("GET", f"/sum?a={i}&b={i}"))
            _ = c.read_response()
        reuse_ms = (time.monotonic() - t0) * 1000.0
        c.close()
        # N requests, each a FRESH connection (pays connect() every time).
        t0 = time.monotonic()
        for i in range(reps):
            cc = Conn(kport)
            cc.send(req("GET", f"/sum?a={i}&b={i}", connection="close"))
            _ = cc.read_response()
            cc.close()
        fresh_ms = (time.monotonic() - t0) * 1000.0
        saved = fresh_ms - reuse_ms
        faster = reuse_ms < fresh_ms
        print(f"  [handshake saving ] {reps} reqs: reused-conn={reuse_ms:.1f} ms "
              f"vs fresh-conn-each={fresh_ms:.1f} ms -> keep-alive saved "
              f"{saved:.1f} ms ({'faster' if faster else 'NOT faster'})  "
              f"{'OK' if faster else 'WARN'}")
        # This is a performance observation, not a hard gate (loopback connect is
        # cheap; the saving is real but small over localhost). Only warn.

        if failures:
            print(f"\nFAIL: {len(failures)} case(s) did not match", file=sys.stderr)
            for f in failures:
                print(f"   {f}", file=sys.stderr)
            return 1
        print("\nok — kernel-router HTTP/1.1 KEEP-ALIVE: multiple requests served "
              "on ONE connection (Content-Length framed), pipelined leftover bytes "
              "carried (none dropped), Connection: close honored, HTTP/1.0 "
              "default-close back-compat, idle connection reaped after the idle "
              "timeout (worker freed), and an idle keep-alive conn did not starve "
              "the pool.")
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
