#!/usr/bin/env python3
"""Proof harness for the kernel-router's UPSTREAM CONNECTION REUSE on the fan-out hop.

The client->router hop already reuses connections (HTTP/1.1 keep-alive, proven by
router_keepalive_harness.py). This proves the SYMMETRIC build: the router->upstream
hop now REUSES a per-worker keep-alive connection to the upstream instead of
opening a fresh TCP connection per fan-out. The handshake to the upstream is
amortized across requests — connections << requests.

The hard part this must get right is the classic keep-alive PROXY bug: with the
upstream connection held open (no `Connection: close`), the router can no longer
read the response with read-to-close. It MUST frame each response by its
Content-Length, reading EXACTLY one response, so the next request on the reused
connection is not corrupted by leftover bytes. If the framing is wrong, distinct
requests on a reused connection bleed into each other — this harness sends DISTINCT
requests on the reused connection and proves each gets its OWN correct response.

What it asserts (real sockets over loopback, the kernel-router with --workers 1 so
ALL fan-outs funnel through ONE worker's ONE pooled upstream connection — touches
NO production routing):

  1. Connections << requests (the handshake amortized): a connection-COUNTING mock
     upstream counts every TCP accept(). Fire N sequential fan-out requests through
     ONE worker. The upstream sees N requests but accepts FAR fewer connections
     (ideally 1) — the reused connection carried them all. The symmetric saving to
     the client-hop keep-alive, proven by counting the upstream's accepts.

  2. Correctness across the reused connection (no response-framing bleed): the N
     fan-out requests above each carry a DISTINCT path/marker; each response is the
     upstream's OWN correct answer for THAT request. The Content-Length framing read
     exactly one response each time — the classic proxy keep-alive bug, proven
     absent on a genuinely reused connection.

  3. Reuse is faster than fresh-connect-each: N fan-outs on the reused connection
     vs N fan-outs each forcing a fresh upstream connection (a counting upstream
     that sends `Connection: close`, so the router cannot pool it). Real p50/p99;
     the reused path saves the per-request upstream handshake.

  4. Stale pooled connection -> transparent reconnect+retry: the upstream serves a
     few requests on the reused connection, then CLOSES it from its side (an idle
     timeout on the upstream's side). The next fan-out finds the pooled connection
     dead; the router must transparently reconnect and retry ONCE, returning the
     correct response — never a client-facing error.

Run from form/form-kernel-rust/:
    cargo build --release
    python3 router_upstream_reuse_harness.py
"""
from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE / "target" / "release" / "form-kernel-rust"
ROUTES = HERE / "examples" / "router-body-proof.fk"


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


class CountingUpstream:
    """A raw-socket HTTP/1.1 upstream that COUNTS accepted TCP connections.

    This is the instrument the whole proof rests on: it makes connection REUSE
    directly observable. Each accept() increments `connections`; each request
    served increments `requests`. With reuse, connections << requests.

    It speaks HTTP/1.1 keep-alive: each response is Content-Length-framed and the
    socket is held open for the next request on it, so the router can pool it.

    Three modes shape the connection lifecycle:
      - default: every response is `Connection: keep-alive`; the socket stays open
        -> the router pools and reuses it (the reuse proof).
      - `connection_close=True`: every response carries `Connection: close`, so the
        router CANNOT pool it -> models fresh-connect-each (the latency baseline).
      - `stale_after=N`: responses stay `Connection: keep-alive` (the router DOES
        pool the connection), but after serving N requests the upstream SILENTLY
        closes the socket WITHOUT a `Connection: close` signal. This models a real
        upstream-side idle timeout: the pooled connection is now dead, but the
        router only learns that when it tries to REUSE it, so the next fan-out must
        transparently reconnect+retry. This is the GENUINE stale-pool path,
        distinct from a clean `Connection: close` (which the router never pools).

    """

    def __init__(self, *, connection_close: bool = False,
                 stale_after: int | None = None):
        self.connection_close = connection_close
        self.stale_after = stale_after
        self.connections = 0
        self.requests = 0
        self._lock = threading.Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(64)
        self.port = self.sock.getsockname()[1]
        self._stop = False
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def _serve(self):
        self.sock.settimeout(0.3)
        while not self._stop:
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self._lock:
                self.connections += 1
            threading.Thread(target=self._serve_conn, args=(conn,), daemon=True).start()

    def _serve_conn(self, conn: socket.socket):
        conn.settimeout(10.0)
        buf = b""
        served_on_this = 0
        try:
            while not self._stop:
                # Read one request: head, then exactly Content-Length body bytes.
                while b"\r\n\r\n" not in buf:
                    b = conn.recv(65536)
                    if not b:
                        return  # client closed the connection
                    buf += b
                head_b, _, rest = buf.partition(b"\r\n\r\n")
                buf = rest
                head = head_b.decode("latin-1")
                clen = 0
                path = "/"
                first = head.split("\r\n", 1)[0]
                parts = first.split(" ")
                if len(parts) >= 2:
                    path = parts[1]
                for line in head.split("\r\n")[1:]:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        if k.strip().lower() == "content-length":
                            clen = int(v.strip() or "0")
                while len(buf) < clen:
                    b = conn.recv(65536)
                    if not b:
                        return
                    buf += b
                _body = buf[:clen]
                buf = buf[clen:]

                with self._lock:
                    self.requests += 1
                served_on_this += 1

                # The response body echoes the request PATH so the harness can
                # prove each distinct request got its OWN correct response (the
                # no-framing-bleed property on a reused connection).
                payload = f"UPSTREAM path={path}".encode()
                # `connection_close` mode signals close on EVERY response (router
                # never pools). `stale_after` mode keeps the keep-alive SIGNAL
                # (router DOES pool) but silently drops the socket after N requests
                # (the genuine stale-pool path the router must reconnect through).
                signal_close = self.connection_close
                stale_drop = (
                    self.stale_after is not None and served_on_this >= self.stale_after
                )
                conn_hdr = "close" if signal_close else "keep-alive"
                resp = (
                    f"HTTP/1.1 200 OK\r\n"
                    f"Content-Type: text/plain; charset=utf-8\r\n"
                    f"Content-Length: {len(payload)}\r\n"
                    f"Connection: {conn_hdr}\r\n"
                    f"\r\n"
                ).encode() + payload
                conn.sendall(resp)
                if signal_close:
                    return  # clean close-each: router will not have pooled this
                if stale_drop:
                    # Keep-alive was SIGNALLED, so the router pooled this socket —
                    # now drop it silently. The router learns it's dead only on the
                    # next reuse attempt -> transparent reconnect+retry.
                    return
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def stop(self):
        self._stop = True
        try:
            self.sock.close()
        except OSError:
            pass


def fanout(kport: int, path: str, timeout: float = 10.0):
    """One fan-out request through the router on a FRESH client connection (so the
    CLIENT hop is not what's being reused — we are measuring the UPSTREAM hop).
    Returns (status, headers_lower, body_text)."""
    s = socket.create_connection(("127.0.0.1", kport), timeout=timeout)
    s.settimeout(timeout)
    try:
        # Connection: close on the CLIENT hop so each fan-out is its own client
        # connection — isolating the upstream-hop reuse as the thing under test.
        req = (f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
               f"Connection: close\r\n\r\n").encode()
        s.sendall(req)
        buf = b""
        while b"\r\n\r\n" not in buf:
            b = s.recv(65536)
            if not b:
                break
            buf += b
        head_b, _, rest = buf.partition(b"\r\n\r\n")
        head = head_b.decode("latin-1")
        lines = head.split("\r\n")
        status = lines[0].split(" ", 1)[1] if " " in lines[0] else lines[0]
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        n = int(headers.get("content-length", "0"))
        body = rest
        while len(body) < n:
            b = s.recv(65536)
            if not b:
                break
            body += b
        return status, headers, body[:n].decode("utf-8", "replace")
    finally:
        s.close()


def start_router(kport: int, upstream_url: str, workers: int = 1) -> subprocess.Popen:
    return subprocess.Popen(
        [str(BIN), "serve", "--port", str(kport), "--routes", str(ROUTES),
         "--upstream", upstream_url, "--workers", str(workers)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def main() -> int:
    if not BIN.exists():
        print(f"build first: cargo build --release ({BIN} missing)", file=sys.stderr)
        return 2
    if not ROUTES.exists():
        print(f"missing routes file: {ROUTES}", file=sys.stderr)
        return 2

    failures = []

    # ===================================================================
    # 1+2. Connections << requests AND correctness across the reused conn.
    # ONE worker -> ALL fan-outs funnel through ONE pooled upstream connection.
    # ===================================================================
    up = CountingUpstream()
    kport = free_port()
    proc = start_router(kport, up.url, workers=1)
    try:
        wait_for_port(kport)
        n = 20
        all_correct = True
        for i in range(n):
            # Each request a DISTINCT path -> the upstream echoes it back; a
            # framing bleed would return the WRONG path for some request.
            path = f"/api/reuse_probe_{i}"
            status, headers, body = fanout(kport, path)
            want = f"UPSTREAM path={path}"
            ok = (status == "200 OK" and body == want
                  and headers.get("x-form-router") == "fanout-python")
            all_correct = all_correct and ok
            if not ok:
                failures.append(("reuse correctness", i, status, body, want))
        time.sleep(0.1)
        conns = up.connections
        reqs = up.requests
        # The whole point: N requests, FAR fewer upstream connections.
        reuse_proven = conns < n and reqs >= n
        ideal = conns == 1
        print(f"  [conns<<reqs ] {reqs} fan-out requests through 1 worker -> "
              f"upstream accepted {conns} connection(s)  "
              f"{'OK' if reuse_proven else 'FAIL'}"
              f"{'  (ideal: ONE reused connection)' if ideal else ''}")
        print(f"  [no-bleed    ] each of {n} DISTINCT requests on the reused "
              f"connection got its OWN correct response -> "
              f"{'OK' if all_correct else 'FAIL'}  (Content-Length framing read "
              f"exactly one response each time — the classic proxy bug, absent)")
        if not reuse_proven:
            failures.append(("connections not << requests", conns, reqs, n))
        if not all_correct:
            failures.append(("response framing bleed on reused connection",))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()
        up.stop()

    # ===================================================================
    # 3. Reuse is faster than fresh-connect-each (the handshake amortized).
    # Compare: a keep-alive upstream (router pools it) vs a close-each upstream
    # (router must reconnect every fan-out). Same router code; the ONLY difference
    # is whether the upstream lets the connection be reused.
    # ===================================================================
    reps = 60

    def measure(connection_close: bool) -> tuple[float, float, float, int]:
        up = CountingUpstream(connection_close=connection_close)
        kport = free_port()
        proc = start_router(kport, up.url, workers=1)
        lats = []
        try:
            wait_for_port(kport)
            # warmup
            for _ in range(5):
                fanout(kport, "/api/warmup")
            for i in range(reps):
                t0 = time.perf_counter()
                fanout(kport, f"/api/perf_{i}")
                lats.append((time.perf_counter() - t0) * 1000.0)
            time.sleep(0.05)
            conns = up.connections
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
            up.stop()
        lats.sort()
        p50 = lats[len(lats) // 2]
        p99 = lats[min(len(lats) - 1, int(len(lats) * 0.99))]
        total = sum(lats)
        return p50, p99, total, conns

    reuse_p50, reuse_p99, reuse_total, reuse_conns = measure(connection_close=False)
    fresh_p50, fresh_p99, fresh_total, fresh_conns = measure(connection_close=True)
    faster = reuse_total < fresh_total
    print(f"  [reuse vs fresh] {reps} fan-outs each:")
    print(f"                   REUSED upstream conn ({reuse_conns} accept(s)):       "
          f"p50={reuse_p50:.3f} ms  p99={reuse_p99:.3f} ms  total={reuse_total:.1f} ms")
    print(f"                   FRESH conn each ({fresh_conns} accept(s), close-each): "
          f"p50={fresh_p50:.3f} ms  p99={fresh_p99:.3f} ms  total={fresh_total:.1f} ms")
    print(f"                   reuse saved {fresh_total - reuse_total:.1f} ms total "
          f"({'faster' if faster else 'NOT faster'}); fresh-each opened "
          f"{fresh_conns} connections vs reuse's {reuse_conns}  "
          f"{'OK' if faster else 'WARN'}")
    # The connection-count contrast is the HARD gate (proves reuse structurally);
    # the latency saving is real but small over loopback, so it only warns.
    if not (reuse_conns < fresh_conns and reuse_conns <= 2):
        failures.append(("reuse did not reduce upstream connections",
                         reuse_conns, fresh_conns))

    # ===================================================================
    # 4. Stale pooled connection -> transparent reconnect+retry (no client error).
    # The GENUINE stale path: the upstream SIGNALS keep-alive (so the router POOLS
    # the connection) but silently drops the socket after `stale_after` requests
    # (modeling an upstream-side idle timeout the router is not told about). The
    # router's pooled connection is now dead; the NEXT fan-out's reuse attempt
    # fails on the read, and the router must transparently reconnect+retry ONCE,
    # returning the correct response — never a client-facing error.
    # ===================================================================
    stale_after = 3
    up = CountingUpstream(stale_after=stale_after)
    kport = free_port()
    proc = start_router(kport, up.url, workers=1)
    try:
        wait_for_port(kport)
        all_ok = True
        results = []
        # Trace with stale_after=3: #1 opens conn1 (keep-alive signalled -> pooled);
        # #2,#3 reuse conn1; the upstream silently drops conn1 after #3. #4 finds
        # the pooled conn1 DEAD on reuse -> reconnect+retry on conn2 (served fresh
        # there); #5,#6 reuse conn2; dropped after #6; #7 stale again -> conn3;
        # #8 reuses conn3. Every client fan-out must succeed; the upstream is
        # reconnected once per stale cycle.
        total_reqs = 8
        for i in range(total_reqs):
            path = f"/api/stale_probe_{i}"
            status, headers, body = fanout(kport, path)
            want = f"UPSTREAM path={path}"
            ok = (status == "200 OK" and body == want
                  and headers.get("x-form-router") == "fanout-python")
            results.append((i, status, body == want))
            all_ok = all_ok and ok
        time.sleep(0.1)
        conns = up.connections
        reqs = up.requests
        # The client saw zero errors; the upstream was reconnected (conns > 1)
        # because the pooled connection went stale and the router transparently
        # opened a fresh one. Each client request was served exactly once
        # (a stale reuse failed on the READ before the upstream counted it, so the
        # retry on a fresh connection is that request's first served instance).
        print(f"  [stale-retry ] upstream silently drops the POOLED keep-alive conn "
              f"every {stale_after} reqs; {total_reqs} client fan-outs -> all "
              f"{'OK' if all_ok else 'FAIL'} "
              f"(upstream: {conns} connections, {reqs} requests served)")
        print(f"                 a stale POOLED connection triggered a transparent "
              f"reconnect+retry, never a client-facing error  "
              f"{'OK' if all_ok else 'FAIL'}")
        if not all_ok:
            failures.append(("stale-connection retry surfaced an error", results))
        # The upstream must have been reconnected (more than 1 connection) -> proof
        # the stale path actually fired, not that the connection never closed.
        if conns < 2:
            failures.append(("stale path did not fire (upstream never reconnected)",
                             conns))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()
        up.stop()

    if failures:
        print(f"\nFAIL: {len(failures)} case(s) did not match", file=sys.stderr)
        for f in failures:
            print(f"   {f}", file=sys.stderr)
        return 1
    print("\nok — kernel-router UPSTREAM CONNECTION REUSE: a per-worker keep-alive "
          "connection to the upstream is reused across fan-outs (connections << "
          "requests, the handshake amortized — the symmetric saving to the client "
          "hop); each response is Content-Length-framed so distinct requests on the "
          "reused connection never bleed (the classic proxy keep-alive bug, absent); "
          "and a stale pooled connection triggers a transparent reconnect+retry, "
          "never a client-facing error. NO production routing touched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
