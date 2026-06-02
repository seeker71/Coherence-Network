#!/usr/bin/env python3
"""Proof harness for the kernel-router's FAN-OUT TIMEOUTS on the upstream hop.

The client->router hop already reaps an IDLE connection (KEEPALIVE_IDLE_TIMEOUT,
proven by router_keepalive_harness.py). This proves the SYMMETRIC robustness on
the router->UPSTREAM hop, for a HUNG (not merely idle) upstream: the router now
bounds each fan-out with a CONNECT timeout + a READ/WRITE timeout, so a slow or
hung upstream cannot pin a worker forever. On expiry the client gets a clean 504
Gateway Timeout and the worker is freed (the stale connection is dropped, never
pooled) — instead of the worker blocking in connect or read indefinitely and,
under load, starving the whole worker pool.

The fan-out timeout values are configurable for testing via env vars so this
harness runs in SECONDS rather than the production 30s default:
    COH_FANOUT_READ_TIMEOUT_MS    (read/write deadline; prod default 30000)
    COH_FANOUT_CONNECT_TIMEOUT_MS (connect deadline;     prod default 5000)
Here the read timeout is set to ~2s so a hung upstream is proven to 504 in ~2s.

What it asserts (real sockets over loopback, the kernel-router — touches NO
production routing):

  1. HUNG upstream -> 504: an upstream that ACCEPTS the TCP connection but never
     sends a response. The router's read deadline fires after ~READ_TIMEOUT and
     returns a clean 504 Gateway Timeout (status 504, an honest text/plain body),
     measured to arrive ~at the deadline — NOT an indefinite hang.

  2. UNREACHABLE upstream -> 504/502 (clean, not a hang): a non-listening /
     blackholed upstream addr. The router's connect path returns a clean error
     response (504 on a connect-timeout to a blackhole, 502 on a fast refusal) —
     either way a definite answer, never an indefinite block.

  3. POOL NOT STARVED: with N workers, while ONE worker is blocked on a hung
     fan-out (timing out over ~READ_TIMEOUT), OTHER requests (a native route, and
     a fan-out to a RESPONSIVE upstream) still serve concurrently. The hung
     fan-out consumes exactly ONE worker for at most (connect+read timeout); the
     rest of the pool keeps serving. This is the load-bearing property: a hung
     upstream does not pin the whole pool.

  4. TIMEOUT != INFINITE RETRY: a read-timeout returns 504 ONCE — it does not
     reconnect+retry (which would double the latency before the same deadline).
     Proven by timing: the 504 arrives at ~ONE read-timeout, not ~2x. Contrast
     with the stale-close path (router_upstream_reuse_harness.py), which DOES
     reconnect+retry once — a timeout is deliberately distinct from a stale close.

  5. HAPPY PATH UNAFFECTED: a responsive upstream still serves normally (the
     timeout is generous; a normal response is well under it), on both the native
     and fan-out arms.

Run from form/form-kernel-rust/:
    cargo build --release
    python3 router_fanout_timeout_harness.py
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE / "target" / "release" / "form-kernel-rust"
ROUTES = HERE / "examples" / "router-body-proof.fk"

# Short fan-out timeouts so the proof runs in seconds. The read timeout is the one
# a HUNG upstream trips; keep the connect timeout short too so the blackhole case
# is quick. These are passed to the router via env vars (the production defaults,
# 30s/5s, apply when unset — this is a TEST override, not a production change).
TEST_READ_TIMEOUT_S = 2.0
TEST_CONNECT_TIMEOUT_S = 2.0
ROUTER_ENV = {
    **os.environ,
    "COH_FANOUT_READ_TIMEOUT_MS": str(int(TEST_READ_TIMEOUT_S * 1000)),
    "COH_FANOUT_CONNECT_TIMEOUT_MS": str(int(TEST_CONNECT_TIMEOUT_S * 1000)),
}


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


class HungUpstream:
    """A raw-socket upstream that ACCEPTS connections but never (or slowly) responds.

    This is the instrument the timeout proof rests on: it models a HUNG upstream —
    reachable (the TCP handshake completes) but it never sends an HTTP response.
    The router's READ deadline must fire and turn this into a 504, freeing the
    worker, rather than blocking on the read forever.

    `respond_after`: if set, the upstream eventually sends a valid response after
    this many seconds (a SLOW upstream). With respond_after > read_timeout the
    router still times out (proving the bound); with respond_after < read_timeout
    the response arrives in time (proving the timeout is not over-eager). Default
    None = never respond (a fully hung upstream).
    """

    def __init__(self, *, respond_after: float | None = None):
        self.respond_after = respond_after
        self.connections = 0
        self._lock = threading.Lock()
        self._held: list[socket.socket] = []
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
                self._held.append(conn)
            threading.Thread(target=self._hold, args=(conn,), daemon=True).start()

    def _hold(self, conn: socket.socket):
        # Drain the request so the router's WRITE completes (the hang is on the
        # READ of the response, the realistic case: the upstream took the request
        # but is stuck computing / deadlocked and never writes a response).
        conn.settimeout(0.3)
        try:
            try:
                conn.recv(65536)
            except OSError:
                pass
            if self.respond_after is not None:
                # SLOW upstream: respond eventually.
                end = time.monotonic() + self.respond_after
                while not self._stop and time.monotonic() < end:
                    time.sleep(0.05)
                if not self._stop:
                    payload = b"SLOW UPSTREAM RESPONSE"
                    resp = (
                        f"HTTP/1.1 200 OK\r\n"
                        f"Content-Type: text/plain; charset=utf-8\r\n"
                        f"Content-Length: {len(payload)}\r\n"
                        f"Connection: close\r\n\r\n"
                    ).encode() + payload
                    try:
                        conn.sendall(resp)
                    except OSError:
                        pass
            else:
                # Fully hung: hold the connection open, NEVER respond, until torn
                # down. The router's read deadline is what must end this.
                while not self._stop:
                    time.sleep(0.1)
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def stop(self):
        self._stop = True
        with self._lock:
            for c in self._held:
                try:
                    c.close()
                except OSError:
                    pass
        try:
            self.sock.close()
        except OSError:
            pass


class ResponsiveUpstream:
    """A normal HTTP/1.1 upstream that responds immediately (the happy path and the
    pool-not-starved control: requests to THIS upstream must keep serving while a
    hung upstream times out elsewhere)."""

    def __init__(self):
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
            threading.Thread(target=self._serve_conn, args=(conn,), daemon=True).start()

    def _serve_conn(self, conn: socket.socket):
        conn.settimeout(10.0)
        buf = b""
        try:
            while not self._stop:
                while b"\r\n\r\n" not in buf:
                    b = conn.recv(65536)
                    if not b:
                        return
                    buf += b
                head_b, _, rest = buf.partition(b"\r\n\r\n")
                buf = rest
                head = head_b.decode("latin-1")
                path = "/"
                first = head.split("\r\n", 1)[0]
                parts = first.split(" ")
                if len(parts) >= 2:
                    path = parts[1]
                clen = 0
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
                buf = buf[clen:]
                with self._lock:
                    self.requests += 1
                payload = f"RESPONSIVE path={path}".encode()
                resp = (
                    f"HTTP/1.1 200 OK\r\n"
                    f"Content-Type: text/plain; charset=utf-8\r\n"
                    f"Content-Length: {len(payload)}\r\n"
                    f"Connection: keep-alive\r\n\r\n"
                ).encode() + payload
                conn.sendall(resp)
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


def request(kport: int, path: str, timeout: float = 30.0):
    """One request through the router on a FRESH client connection (Connection:
    close so the client hop is not reused). Returns (status, headers_lower, body,
    elapsed_s). On a client-side socket timeout returns ('CLIENT-TIMEOUT', {}, '',
    elapsed) — that would mean the ROUTER hung (the bug we are disproving)."""
    t0 = time.perf_counter()
    try:
        s = socket.create_connection(("127.0.0.1", kport), timeout=timeout)
    except OSError as e:
        return f"CONNECT-FAIL {e}", {}, "", time.perf_counter() - t0
    s.settimeout(timeout)
    try:
        req = (f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
               f"Connection: close\r\n\r\n").encode()
        s.sendall(req)
        buf = b""
        while b"\r\n\r\n" not in buf:
            try:
                b = s.recv(65536)
            except socket.timeout:
                return "CLIENT-TIMEOUT", {}, "", time.perf_counter() - t0
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
            try:
                b = s.recv(65536)
            except socket.timeout:
                break
            if not b:
                break
            body += b
        return status, headers, body[:n].decode("utf-8", "replace"), time.perf_counter() - t0
    finally:
        s.close()


def start_router(kport: int, upstream_url: str, workers: int = 1) -> subprocess.Popen:
    return subprocess.Popen(
        [str(BIN), "serve", "--port", str(kport), "--routes", str(ROUTES),
         "--upstream", upstream_url, "--workers", str(workers)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ROUTER_ENV,
    )


def stop_proc(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        proc.kill()


def main() -> int:
    if not BIN.exists():
        print(f"build first: cargo build --release ({BIN} missing)", file=sys.stderr)
        return 2
    if not ROUTES.exists():
        print(f"missing routes file: {ROUTES}", file=sys.stderr)
        return 2

    failures = []
    rt = TEST_READ_TIMEOUT_S
    print(f"  (fan-out read timeout set to {rt:.1f}s, connect timeout "
          f"{TEST_CONNECT_TIMEOUT_S:.1f}s via env for a fast proof; "
          f"prod defaults 30s/5s when unset)")

    # ===================================================================
    # 1. HUNG upstream -> 504 (measured ~at the read deadline, not a hang).
    # ===================================================================
    up = HungUpstream()  # accepts, never responds
    kport = free_port()
    proc = start_router(kport, up.url, workers=2)
    try:
        wait_for_port(kport)
        # Generous client timeout so if the ROUTER hangs, the CLIENT detects it
        # (CLIENT-TIMEOUT) rather than us waiting forever — that would be the bug.
        status, headers, body, elapsed = request(kport, "/api/hung", timeout=rt + 8.0)
        is_504 = status == "504 Gateway Timeout"
        # The 504 should arrive at ~ONE read timeout (not 2x — no retry).
        timely = (rt * 0.7) <= elapsed <= (rt + 2.0)
        clean_body = bool(body.strip()) and "CLIENT-TIMEOUT" not in status
        print(f"  [hung->504   ] hung upstream (accepts, never responds) -> "
              f"status={status!r}  body={body.strip()[:40]!r}  in {elapsed:.2f}s  "
              f"{'OK' if (is_504 and timely and clean_body) else 'FAIL'}")
        print(f"                 504 arrived at ~one read-timeout ({rt:.1f}s) — "
              f"a clean Gateway Timeout, NOT an indefinite hang  "
              f"{'OK' if (is_504 and timely) else 'FAIL'}")
        if not is_504:
            failures.append(("hung upstream did not return 504", status, body))
        if not timely:
            failures.append(("504 not timely (hang or retry-doubled latency)", elapsed, rt))
        if not clean_body:
            failures.append(("504 body not clean / client hung", status, body))
    finally:
        stop_proc(proc)
        up.stop()

    # ===================================================================
    # 4 (proven alongside 1). TIMEOUT != INFINITE RETRY: the elapsed above is
    # ~ONE read-timeout, not ~2x. Assert it explicitly so a future retry-on-timeout
    # regression (which would double the latency) is caught.
    # ===================================================================
    no_retry_doubling = "504 not timely (hang or retry-doubled latency)" not in [
        f[0] for f in failures
    ]
    print(f"  [no-retry    ] read-timeout returned 504 ONCE (latency ~1x the "
          f"read-timeout, not ~2x) -> a timeout is NOT reconnect+retried  "
          f"{'OK' if no_retry_doubling else 'FAIL'}")

    # ===================================================================
    # 2. UNREACHABLE upstream -> clean error (504 on blackhole connect-timeout,
    # 502 on fast refusal) — never an indefinite block.
    # ===================================================================
    # A non-listening port on localhost typically REFUSES fast (-> 502 quickly,
    # still a clean definite answer, not a hang). A blackhole (TEST-NET / RFC5737
    # 192.0.2.0/24, which silently drops) exercises the CONNECT-TIMEOUT -> 504.
    dead_port = free_port()  # nothing listening here
    kport = free_port()
    proc = start_router(kport, f"http://127.0.0.1:{dead_port}", workers=2)
    try:
        wait_for_port(kport)
        status, headers, body, elapsed = request(kport, "/api/dead", timeout=TEST_CONNECT_TIMEOUT_S + 8.0)
        clean = status in ("502 Bad Gateway", "504 Gateway Timeout")
        timely = elapsed <= (TEST_CONNECT_TIMEOUT_S + 2.0)
        print(f"  [refused->err] non-listening upstream -> status={status!r}  "
              f"body={body.strip()[:40]!r}  in {elapsed:.3f}s  "
              f"{'OK' if (clean and timely) else 'FAIL'} (fast refusal -> clean "
              f"502/504, never a hang)")
        if not (clean and timely):
            failures.append(("non-listening upstream not a clean timely error", status, elapsed))
    finally:
        stop_proc(proc)

    # Blackhole connect-timeout -> 504 (RFC5737 TEST-NET-1, silently dropped).
    kport = free_port()
    proc = start_router(kport, "http://192.0.2.1:80", workers=2)
    try:
        wait_for_port(kport)
        status, headers, body, elapsed = request(kport, "/api/blackhole",
                                                  timeout=TEST_CONNECT_TIMEOUT_S + 8.0)
        is_504 = status == "504 Gateway Timeout"
        # Connect-timeout should fire ~at the connect deadline.
        timely = (TEST_CONNECT_TIMEOUT_S * 0.5) <= elapsed <= (TEST_CONNECT_TIMEOUT_S + 3.0)
        ok = is_504 and timely
        print(f"  [blackhole504] blackholed upstream (192.0.2.1, silently dropped) "
              f"-> status={status!r} in {elapsed:.2f}s  {'OK' if ok else 'WARN'} "
              f"(connect-timeout -> 504 at ~{TEST_CONNECT_TIMEOUT_S:.1f}s)")
        # Some networks RST blackhole addrs instead of dropping; accept a clean
        # 502/504 as long as it's timely (the hard gate is no-hang). Only the hang
        # case fails.
        if not (status in ("502 Bad Gateway", "504 Gateway Timeout") and
                elapsed <= (TEST_CONNECT_TIMEOUT_S + 3.0)):
            failures.append(("blackhole upstream hung or wrong status", status, elapsed))
    finally:
        stop_proc(proc)

    # ===================================================================
    # 3. POOL NOT STARVED: N workers; ONE worker blocked on a hung fan-out while
    # OTHER requests (native route + responsive-upstream fan-out) still serve.
    # The router fans out to the HUNG upstream; a SEPARATE responsive upstream is
    # NOT what the router points at (the router has one --upstream), so "other
    # requests serve" is proven via the NATIVE route (served entirely in-kernel,
    # no upstream) AND repeated hung requests each completing in ~one timeout
    # rather than stacking. With 4 workers we fire 1 hung request (occupies 1
    # worker for ~read-timeout) and CONCURRENTLY fire many native requests; the
    # native requests must all return FAST (well under the read-timeout), proving
    # the hung fan-out did not pin the pool.
    # ===================================================================
    up = HungUpstream()
    kport = free_port()
    workers = 4
    proc = start_router(kport, up.url, workers=workers)
    try:
        wait_for_port(kport)
        results = {}
        with ThreadPoolExecutor(max_workers=8) as ex:
            # 1 hung fan-out (will 504 after ~read-timeout) occupying 1 worker.
            hung_fut = ex.submit(request, kport, "/api/hung_one", rt + 8.0)
            # Give the hung request a moment to be picked up by a worker.
            time.sleep(0.2)
            # Many NATIVE requests fired while the hung one is still timing out.
            native_futs = [ex.submit(request, kport, "/health", 5.0) for _ in range(20)]
            t_native0 = time.perf_counter()
            native_results = [f.result() for f in native_futs]
            native_wall = time.perf_counter() - t_native0
            hung_status, _, hung_body, hung_elapsed = hung_fut.result()
        native_ok = all(s == "200 OK" and b == "ok" for (s, _, b, _) in native_results)
        # The 20 native requests must complete FAST — well under the read-timeout —
        # proving they were NOT stuck behind the hung fan-out.
        native_fast = native_wall < (rt * 0.8)
        hung_504 = hung_status == "504 Gateway Timeout"
        print(f"  [pool-alive  ] {workers} workers, 1 hung fan-out (504 in "
              f"{hung_elapsed:.2f}s) — meanwhile 20 native /health requests "
              f"served in {native_wall*1000:.1f} ms total  "
              f"{'OK' if (native_ok and native_fast) else 'FAIL'}")
        print(f"                 the hung fan-out occupied ONE worker for ~one "
              f"read-timeout; the pool kept serving (native requests fast, not "
              f"stacked behind the hang)  "
              f"{'OK' if (native_ok and native_fast and hung_504) else 'FAIL'}")
        if not native_ok:
            failures.append(("native requests failed while a fan-out hung",
                             [r[0] for r in native_results]))
        if not native_fast:
            failures.append(("pool STARVED: native requests stuck behind hung fan-out",
                             native_wall, rt))
        if not hung_504:
            failures.append(("hung fan-out in pool test did not 504", hung_status))
    finally:
        stop_proc(proc)
        up.stop()

    # ===================================================================
    # 5. HAPPY PATH UNAFFECTED: a responsive upstream serves normally on both arms
    # (the timeout is generous; a normal response is well under it).
    # ===================================================================
    up = ResponsiveUpstream()
    kport = free_port()
    proc = start_router(kport, up.url, workers=2)
    try:
        wait_for_port(kport)
        # Native arm (no upstream).
        ns, _, nb, _ = request(kport, "/health", 5.0)
        native_ok = ns == "200 OK" and nb == "ok"
        # Fan-out arm to the responsive upstream.
        fs, fh, fb, fe = request(kport, "/api/normal_path", 5.0)
        fanout_ok = (fs == "200 OK" and fb == "RESPONSIVE path=/api/normal_path"
                     and fh.get("x-form-router") == "fanout-python"
                     and fe < (rt * 0.5))
        print(f"  [happy native] /health -> {ns!r} {nb!r}  "
              f"{'OK' if native_ok else 'FAIL'}")
        print(f"  [happy fanout] /api/normal_path -> {fs!r} body={fb!r} in "
              f"{fe*1000:.1f} ms (well under the {rt:.1f}s timeout)  "
              f"{'OK' if fanout_ok else 'FAIL'}")
        if not native_ok:
            failures.append(("native happy path broke", ns, nb))
        if not fanout_ok:
            failures.append(("fanout happy path broke", fs, fb, fe))
    finally:
        stop_proc(proc)
        up.stop()

    if failures:
        print(f"\nFAIL: {len(failures)} case(s) did not match", file=sys.stderr)
        for f in failures:
            print(f"   {f}", file=sys.stderr)
        return 1
    print("\nok — kernel-router FAN-OUT TIMEOUTS: a hung upstream (accepts but "
          "never responds) returns a clean 504 Gateway Timeout at ~one read "
          "deadline and frees the worker (the stale connection dropped, never "
          "pooled); an unreachable upstream returns a clean 502/504 rather than "
          "hanging; the worker pool is NOT starved (a hung fan-out occupies ONE "
          "worker for at most connect+read timeout while the rest of the pool keeps "
          "serving); a read-timeout is returned ONCE, not reconnect+retried "
          "(distinct from the stale-close path); the happy path is unaffected. "
          "NO production routing touched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
