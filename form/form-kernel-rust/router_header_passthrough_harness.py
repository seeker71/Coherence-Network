#!/usr/bin/env python3
"""Proof harness for the kernel-router's BIDIRECTIONAL HEADER PASSTHROUGH.

Where router_real_app_harness.py proved the reversed topology fans out method +
body to the REAL FastAPI app and relays status + body, this proves the matured
fan-out arm carries HEADERS both ways with reverse-proxy hop-by-hop hygiene:

  UP   — the client's end-to-end REQUEST headers (Authorization, Cookie, Accept*,
         User-Agent, X-*, Content-Type) reach the upstream, so the fan-out can
         front an authenticated / content-typed route truthfully. Host is
         rewritten to the upstream; the client's Content-Length is dropped (the
         router re-derives it from the body it captured); hop-by-hop headers
         (Connection, Keep-Alive, Transfer-Encoding, Upgrade, Proxy-*, TE,
         Trailer) are stripped — the router owns its upstream-hop framing.
  DOWN — the upstream's RESPONSE headers (Content-Type, Set-Cookie,
         Cache-Control, Location, ETag, X-*) reach the client, so a JSON/HTML
         route survives the proxy instead of being flattened to text/plain and a
         cookie/redirect/cache directive is not lost. The router still owns its
         own client-hop framing (Content-Length, Connection); the upstream's
         hop-by-hop + framing headers are NOT relayed.

TWO upstreams, each proving what it is best placed to prove (honest split):

  • the REAL FastAPI app (app.main:app, dev sqlite, throwaway port) — proves the
    DOWN direction against a genuine route: GET /api/health relayed with
    Content-Type: application/json (the real upstream's), NOT text/plain. Also
    the no-regression checks: a native route still serves in Form, a fan-out GET
    still returns the real app's JSON body.

  • a mock ECHO upstream (http.server) — proves what no fixed real route cleanly
    exposes: (1) the UP direction — it echoes every request header it RECEIVED
    back in the response body, so the harness can assert the client's
    Authorization / Cookie / X-Probe arrived and the hop-by-hop Connection /
    client Content-Length / original Host did NOT; (2) Set-Cookie + Cache-Control
    relay DOWN; (3) the upstream's own hop-by-hop response headers (a bogus
    Transfer-Encoding / Connection it emits) are NOT relayed — the router owns
    that framing.

This is a LOCAL side-by-side proof. It touches NO production routing — the real
app runs on a throwaway test port against the dev sqlite DB; the production front
door is untouched.

Run from form/form-kernel-rust/ (after `cargo build --release`):
    python3 router_header_passthrough_harness.py
"""
from __future__ import annotations

import json
import os
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
# One native route (/sum) + everything else fans out — the body-proof manifest.
ROUTES = HERE / "examples" / "router-body-proof.fk"
REAL_ROUTES = HERE / "examples" / "router-real-app-proof.fk"
# form/form-kernel-rust -> form -> repo root -> api
API_DIR = HERE.parent.parent / "api"

# A distinctive request header the harness sets and the echo upstream reflects.
PROBE_AUTH = "Bearer test123"
PROBE_COOKIE = "session=abc; theme=dark"
PROBE_X = "hello-upstream"

FANOUT_GET_PATH = "/api/health"  # real app -> application/json


# ── echo upstream: reflects the request headers it RECEIVED, sets a cookie ──
class _EchoHandler(BaseHTTPRequestHandler):
    """Mock upstream that makes the UP direction observable: it serializes every
    request header it received into the JSON body, so the harness can assert
    which client headers arrived and which were (correctly) stripped. It also
    sets a Set-Cookie + Cache-Control to prove DOWN relay, and emits a bogus
    hop-by-hop response header to prove the router does NOT relay it."""

    def _echo(self):
        received = {k.lower(): v for k, v in self.headers.items()}
        payload = json.dumps({"received_headers": received, "path": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        # DOWN-relay probes (end-to-end response headers):
        self.send_header("Set-Cookie", "echosession=xyz789; Path=/; HttpOnly")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Echo-Custom", "relayed-ok")
        # A hop-by-hop response header the router must NOT relay (it owns framing):
        self.send_header("Transfer-Encoding", "chunked-but-not-really")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        self._echo()

    def do_POST(self):  # noqa: N802
        # drain any body so the connection frames cleanly
        n = int(self.headers.get("Content-Length", "0") or "0")
        if n:
            self.rfile.read(n)
        self._echo()

    def log_message(self, *args):  # silence per-request logging
        pass


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_port(port: int, timeout: float = 40.0) -> None:
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


def wait_for_http(url: str, timeout: float = 40.0) -> None:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as r:
                r.read()
                return
        except urllib.error.HTTPError:
            return
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            last = e
            time.sleep(0.25)
    raise RuntimeError(f"app never answered at {url}: {last}")


def raw_request(port: int, raw: bytes, timeout: float = 10.0):
    """Send a fully hand-built request over a raw socket and return
    (status_line, headers_lower_dict_with_multivalue, body_text). Set-Cookie can
    appear multiple times, so headers map name -> list[str]."""
    sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    sock.settimeout(timeout)
    try:
        sock.sendall(raw)
        buf = b""
        while b"\r\n\r\n" not in buf:
            b = sock.recv(65536)
            if not b:
                break
            buf += b
        head_b, _, rest = buf.partition(b"\r\n\r\n")
        head_txt = head_b.decode("utf-8", "replace")
        lines = head_txt.split("\r\n")
        status_line = lines[0]
        headers: dict[str, list[str]] = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers.setdefault(k.strip().lower(), []).append(v.strip())
        n = 0
        if "content-length" in headers:
            n = int(headers["content-length"][0])
        body = rest
        while len(body) < n:
            b = sock.recv(65536)
            if not b:
                break
            body += b
        body = body[:n]
        return status_line, headers, body.decode("utf-8", "replace")
    finally:
        sock.close()


def get_real(url: str, timeout: float = 10.0):
    """Return (status, content_type, body) via urllib against the real app."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type"), r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read().decode("utf-8")


def first(headers: dict, name: str):
    vals = headers.get(name.lower())
    return vals[0] if vals else None


def main() -> int:
    if not BIN.exists():
        print(f"build first: cargo build --release ({BIN} missing)", file=sys.stderr)
        return 2
    if not ROUTES.exists() or not REAL_ROUTES.exists():
        print("missing routes file(s)", file=sys.stderr)
        return 2
    if not (API_DIR / "app" / "main.py").exists():
        print(f"cannot find the real app at {API_DIR}/app/main.py", file=sys.stderr)
        return 2

    failures: list[tuple] = []

    # ── 1) echo upstream + router: prove UP, Set-Cookie/Cache DOWN, hop-by-hop ──
    echo_port = free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", echo_port), _EchoHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    echo_url = f"http://127.0.0.1:{echo_port}"

    kport = free_port()
    router_proc = subprocess.Popen(
        [str(BIN), "serve", "--port", str(kport), "--routes", str(ROUTES),
         "--upstream", echo_url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    real_proc = None
    real_router_proc = None
    try:
        wait_for_port(kport)
        print("=== UP + DOWN against the ECHO upstream (header observability) ===")

        # Hand-build a request with end-to-end headers AND hop-by-hop noise the
        # router must strip on the way up. /echo is not native -> fans out.
        raw = (
            f"GET /echo/probe HTTP/1.1\r\n"
            f"Host: client-sent-host.example\r\n"
            f"Authorization: {PROBE_AUTH}\r\n"
            f"Cookie: {PROBE_COOKIE}\r\n"
            f"Accept: application/json\r\n"
            f"X-Probe: {PROBE_X}\r\n"
            f"User-Agent: header-passthrough-harness\r\n"
            f"Connection: keep-alive\r\n"        # hop-by-hop -> must NOT reach upstream
            f"Content-Length: 999\r\n"           # bogus framing -> router re-derives (0 here)
            f"\r\n"
        ).encode()
        status_line, rheaders, body = raw_request(kport, raw)
        try:
            echoed = json.loads(body).get("received_headers", {})
        except Exception:
            echoed = {}

        # UP: end-to-end headers arrived at the upstream
        up_auth = echoed.get("authorization") == PROBE_AUTH
        up_cookie = echoed.get("cookie") == PROBE_COOKIE
        up_accept = echoed.get("accept") == "application/json"
        up_xprobe = echoed.get("x-probe") == PROBE_X
        up_ua = echoed.get("user-agent") == "header-passthrough-harness"
        # UP hygiene: Host rewritten to upstream, client Content-Length NOT
        # forwarded (no body -> router sends none), Connection NOT forwarded
        host_rewritten = echoed.get("host", "").startswith("127.0.0.1")
        no_client_cl = echoed.get("content-length") in (None, "0")
        no_conn_up = "connection" not in echoed or echoed.get("connection", "").lower() != "keep-alive"
        ok_up = all([up_auth, up_cookie, up_accept, up_xprobe, up_ua,
                     host_rewritten, no_client_cl, no_conn_up])
        print(f"  [UP request hdrs ] upstream RECEIVED: "
              f"Authorization={up_auth} Cookie={up_cookie} Accept={up_accept} "
              f"X-Probe={up_xprobe} UA={up_ua}")
        print(f"                     hygiene: Host->upstream={host_rewritten} "
              f"client-Content-Length-dropped={no_client_cl} "
              f"Connection-stripped={no_conn_up}  {'OK' if ok_up else 'FAIL'}")
        print(f"                     (upstream saw Host={echoed.get('host')!r} "
              f"Content-Length={echoed.get('content-length')!r})")
        if not ok_up:
            failures.append(("UP request headers", echoed))

        # DOWN: Set-Cookie + Cache-Control + custom header relayed; Content-Type
        # is the upstream's application/json; hop-by-hop NOT relayed.
        down_cookie = first(rheaders, "set-cookie") == "echosession=xyz789; Path=/; HttpOnly"
        down_cache = first(rheaders, "cache-control") == "no-store"
        down_custom = first(rheaders, "x-echo-custom") == "relayed-ok"
        down_ct = (first(rheaders, "content-type") or "").startswith("application/json")
        # The upstream emitted Transfer-Encoding (hop-by-hop) — router must NOT relay it.
        no_te_down = "transfer-encoding" not in rheaders
        # Router owns its client-hop framing.
        router_framing = (first(rheaders, "connection") in ("keep-alive", "close")
                          and "content-length" in rheaders
                          and first(rheaders, "x-form-router") == "fanout-python")
        ok_down = all([down_cookie, down_cache, down_custom, down_ct,
                       no_te_down, router_framing])
        print(f"  [DOWN resp hdrs  ] client RECEIVED: Set-Cookie={down_cookie} "
              f"Cache-Control={down_cache} X-Echo-Custom={down_custom} "
              f"Content-Type=json:{down_ct}")
        print(f"                     hygiene: upstream-Transfer-Encoding-NOT-relayed="
              f"{no_te_down} router-owns-framing={router_framing}  "
              f"{'OK' if ok_down else 'FAIL'}")
        if not ok_down:
            failures.append(("DOWN response headers", dict(rheaders)))

        # POST with a real body + Content-Type -> body forwarded, Content-Type up.
        post_body = json.dumps({"hello": "upstream"}).encode()
        raw_post = (
            f"POST /echo/post HTTP/1.1\r\n"
            f"Host: client.example\r\n"
            f"Content-Type: application/json\r\n"
            f"X-Probe: {PROBE_X}\r\n"
            f"Content-Length: {len(post_body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode() + post_body
        _, _, pbody = raw_request(kport, raw_post)
        try:
            pe = json.loads(pbody).get("received_headers", {})
        except Exception:
            pe = {}
        post_ct = pe.get("content-type") == "application/json"
        post_cl = pe.get("content-length") == str(len(post_body))
        post_x = pe.get("x-probe") == PROBE_X
        ok_post = post_ct and post_cl and post_x
        print(f"  [POST body+hdrs  ] upstream saw Content-Type={post_ct} "
              f"Content-Length(re-derived={len(post_body)})={post_cl} "
              f"X-Probe={post_x}  {'OK' if ok_post else 'FAIL'}")
        if not ok_post:
            failures.append(("POST body + headers up", pe))

    finally:
        router_proc.terminate()
        try:
            router_proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            router_proc.kill()
        httpd.shutdown()

    # ── 2) REAL FastAPI app: prove DOWN Content-Type relay + no-regression ──
    app_port = free_port()
    env = dict(os.environ)
    env["COH_ENV"] = "dev"
    (API_DIR / "data").mkdir(exist_ok=True)
    real_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(app_port), "--log-level", "warning"],
        cwd=str(API_DIR), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    app_base = f"http://127.0.0.1:{app_port}"
    try:
        print("\n=== DOWN Content-Type relay against the REAL FastAPI app ===")
        wait_for_port(app_port)
        wait_for_http(app_base + FANOUT_GET_PATH)
        # Confirm it's genuinely the real app AND note its real content-type.
        st, app_ct, abody = get_real(app_base + FANOUT_GET_PATH)
        try:
            hj = json.loads(abody)
        except Exception:
            hj = {}
        is_real = st == 200 and "version" in hj and "kernel_runtime" in hj
        real_ct_json = (app_ct or "").startswith("application/json")
        print(f"  real app {FANOUT_GET_PATH} -> {st} Content-Type={app_ct!r} "
              f"{'REAL FastAPI (json)' if is_real and real_ct_json else 'UNEXPECTED'}")
        if not (is_real and real_ct_json):
            failures.append(("real-app health probe", st, app_ct, abody[:120]))

        kport2 = free_port()
        real_router_proc = subprocess.Popen(
            [str(BIN), "serve", "--port", str(kport2),
             "--routes", str(REAL_ROUTES), "--upstream", app_base],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        wait_for_port(kport2)

        # DOWN through the router: the client must now see application/json (the
        # upstream's real type), NOT text/plain.
        raw = (
            f"GET {FANOUT_GET_PATH} HTTP/1.1\r\n"
            f"Host: client.example\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode()
        status_line, rheaders, body = raw_request(kport2, raw)
        router_ct = first(rheaders, "content-type")
        relayed_json = (router_ct or "").startswith("application/json")
        not_textplain = "text/plain" not in (router_ct or "")
        try:
            kj = json.loads(body)
        except Exception:
            kj = {}
        genuine = "version" in kj and "kernel_runtime" in kj
        is_fanout = first(rheaders, "x-form-router") == "fanout-python"
        ok = relayed_json and not_textplain and genuine and is_fanout and status_line.endswith("200 OK")
        print(f"  [DOWN real CT    ] {FANOUT_GET_PATH} through router -> "
              f"Content-Type={router_ct!r} (was text/plain before this build)")
        print(f"                     relayed-json={relayed_json} "
              f"not-text-plain={not_textplain} genuine-app-body={genuine} "
              f"X-Form-Router={first(rheaders, 'x-form-router')}  {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("real-app DOWN content-type relay", status_line, router_ct, body[:160]))

        # No-regression: native route still serves text/plain value in Form.
        raw_native = (
            "GET /api/utils/weighted_average?values=0.5,0.75,1.0&weights=0.25,0.25,0.5 HTTP/1.1\r\n"
            "Host: client.example\r\nConnection: close\r\n\r\n"
        ).encode()
        nstatus, nheaders, nbody = raw_request(kport2, raw_native)
        native_ok = (nstatus.endswith("200 OK")
                     and first(nheaders, "x-form-router") == "native-kernel"
                     and (first(nheaders, "content-type") or "").startswith("text/plain"))
        try:
            nval = float(nbody)
        except ValueError:
            nval = None
        native_ok = native_ok and nval is not None
        print(f"  [no-regress nat  ] native weighted_average -> value={nval} "
              f"Content-Type={first(nheaders, 'content-type')!r} "
              f"X-Form-Router={first(nheaders, 'x-form-router')}  "
              f"{'OK' if native_ok else 'FAIL'}")
        if not native_ok:
            failures.append(("no-regression native route", nstatus, nbody[:120]))

    finally:
        for p in (real_router_proc, real_proc):
            if p is None:
                continue
            p.terminate()
            try:
                p.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                p.kill()
                try:
                    p.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    pass

    if failures:
        print(f"\nFAIL: {len(failures)} case(s) did not match", file=sys.stderr)
        for f in failures:
            print(f"   {f}", file=sys.stderr)
        return 1
    print("\nok — bidirectional header passthrough with hop-by-hop hygiene: the "
          "client's end-to-end REQUEST headers (Authorization/Cookie/Accept/"
          "X-Probe/UA + Content-Type on POST) reached the upstream with Host "
          "rewritten and client Content-Length/Connection stripped; the "
          "upstream's RESPONSE headers (Set-Cookie/Cache-Control/X-Echo-Custom) "
          "and its real Content-Type (application/json from the REAL FastAPI "
          "app, not text/plain) reached the client; hop-by-hop headers were "
          "stripped both ways and the router kept ownership of its framing; "
          "native routes still serve in Form unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
