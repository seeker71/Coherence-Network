#!/usr/bin/env python3
"""Real-app proof for the kernel-as-router REVERSAL — no mock upstream.

Where router_proof_harness.py / router_body_harness.py prove the reversed
topology against a MOCK CPython upstream (an http.server standin), this harness
proves it IN FRONT OF THE ACTUAL Coherence-Network FastAPI app: it boots the
real `app.main:app` under uvicorn on a test port, stands the kernel-router in
front of it, and exercises both arms end-to-end against the live app.

This is a LOCAL side-by-side proof. It touches NO production routing — the real
app runs on a throwaway test port against the dev sqlite DB; the production
front door is untouched.

What it boots:
  1. the REAL FastAPI app — `python -m uvicorn app.main:app` on a free port,
     COH_ENV=dev so it uses the sqlite fallback DB. This is the genuine app
     (816 routes), not a mock: /api/health returns the real health JSON,
     /api/utils/* run the app's serve_via_kernel guest path, /api/ideas reads
     the real DB.
  2. the kernel-router — `form-kernel-rust serve --routes router-real-app-proof.fk
     --upstream http://127.0.0.1:<app>` on another free port. ONE native route
     (/api/utils/weighted_average, served in Form); everything else fans out to
     the real app.

What it proves (all measured against the LIVE app, not asserted):
  - NATIVE: GET /api/utils/weighted_average -> served in Form, X-Form-Router:
    native-kernel, NO CPython in the path. Its value EQUALS what the real app
    returns for the same route (the app computes it via serve_via_kernel; the
    kernel-router computes the same arithmetic natively) — proving the router
    serves the SAME answer the app would.
  - FAN-OUT (GET): GET /api/health -> proxied to the real app, X-Form-Router:
    fanout-python, and the body is the REAL app's health JSON (status/version/
    uptime/kernel_runtime fields — genuinely FastAPI, not a marker).
  - FAN-OUT (POST): POST /api/cc/exchange/quote with a JSON body -> proxied to
    the real app with the body forwarded, X-Form-Router: fanout-python, and the
    body is the real app's quote response (a quote_id + rate from the live
    exchange route).
  - LATENCY (real numbers): native-route latency through the kernel-router; the
    same fan-out route hit (a) directly on FastAPI vs (b) through the router —
    the proxy-hop overhead; and the native route through the router vs the same
    computation through the app's own serve_via_kernel guest path. p50/p99.

Run from form/form-kernel-rust/ (after `cargo build --release`):
    python3 router_real_app_harness.py
"""
from __future__ import annotations

import json
import os
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE / "target" / "release" / "form-kernel-rust"
ROUTES = HERE / "examples" / "router-real-app-proof.fk"
# form/form-kernel-rust -> form -> repo root -> api
API_DIR = HERE.parent.parent / "api"

# The one native route the kernel-router serves in Form; the real app serves the
# same path via serve_via_kernel, so the two answers must agree.
NATIVE_PATH = "/api/utils/weighted_average"
NATIVE_QUERY = "values=0.5,0.75,1.0&weights=0.25,0.25,0.5"

# A GET route the router does NOT handle natively -> fans out to the real app.
FANOUT_GET_PATH = "/api/health"
# A real POST route -> fans out with its body forwarded to the real app.
FANOUT_POST_PATH = "/api/cc/exchange/quote"
FANOUT_POST_BODY = json.dumps(
    {"from_asset": "USD", "to_asset": "CC", "amount": 100}
).encode()


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
                time.sleep(0.15)
    raise RuntimeError(f"listener never came up on 127.0.0.1:{port}")


def wait_for_http(url: str, timeout: float = 40.0) -> None:
    """The real app's port opens before its routes are ready; poll until a
    request actually returns (uvicorn binds, then runs the lifespan)."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as r:
                r.read()
                return
        except urllib.error.HTTPError:
            return  # a 4xx/5xx still means the app is answering
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            last = e
            time.sleep(0.25)
    raise RuntimeError(f"app never answered at {url}: {last}")


def http_get(url: str, timeout: float = 10.0):
    """Return (status, body-text, X-Form-Router header)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8"), r.headers.get("X-Form-Router")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), e.headers.get("X-Form-Router")


def http_post(url: str, body: bytes, content_type: str = "application/json",
              timeout: float = 10.0):
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": content_type})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8"), r.headers.get("X-Form-Router")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), e.headers.get("X-Form-Router")


def percentiles(samples_ms: list[float]) -> tuple[float, float, float]:
    s = sorted(samples_ms)
    p50 = statistics.median(s)
    p99 = s[min(len(s) - 1, int(0.99 * len(s)))]
    return p50, p99, s[0]


def measure_get(url: str, n: int) -> list[float]:
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        http_get(url)
        out.append((time.perf_counter() - t0) * 1000.0)
    return out


def main() -> int:
    if not BIN.exists():
        print(f"build first: cargo build --release ({BIN} missing)", file=sys.stderr)
        return 2
    if not ROUTES.exists():
        print(f"missing routes file: {ROUTES}", file=sys.stderr)
        return 2
    if not (API_DIR / "app" / "main.py").exists():
        print(f"cannot find the real app at {API_DIR}/app/main.py", file=sys.stderr)
        return 2

    failures: list[tuple] = []
    app_port = free_port()
    kport = free_port()

    # 1. boot the REAL FastAPI app on the dev sqlite path.
    env = dict(os.environ)
    env["COH_ENV"] = "dev"
    (API_DIR / "data").mkdir(exist_ok=True)
    app_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(app_port), "--log-level", "warning"],
        cwd=str(API_DIR), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    app_base = f"http://127.0.0.1:{app_port}"

    router_proc = None
    try:
        print(f"booting the REAL FastAPI app (uvicorn app.main:app) on :{app_port} ...")
        wait_for_port(app_port)
        wait_for_http(app_base + FANOUT_GET_PATH)
        # Confirm it is genuinely the real app, not a stand-in.
        st, body, _ = http_get(app_base + FANOUT_GET_PATH)
        try:
            hj = json.loads(body)
        except Exception:
            hj = {}
        is_real = st == 200 and "version" in hj and "kernel_runtime" in hj
        print(f"  real app /api/health -> {st}  status={hj.get('status')!r} "
              f"version={hj.get('version')!r} kernel_runtime={hj.get('kernel_runtime')!r}  "
              f"{'REAL FastAPI' if is_real else 'UNEXPECTED'}")
        if not is_real:
            failures.append(("real-app health probe", st, body[:120]))

        # The app's own answer for the native route (its serve_via_kernel path) —
        # the oracle the kernel-router's native value must match.
        st, body, _ = http_get(app_base + NATIVE_PATH + "?" + NATIVE_QUERY)
        app_native = json.loads(body) if st == 200 else {}
        app_avg = app_native.get("average")
        print(f"  real app {NATIVE_PATH} -> {st}  average={app_avg} "
              f"runtime={app_native.get('runtime')!r}  (the oracle)")

        # 2. boot the kernel-router in front of the real app.
        print(f"booting the kernel-router on :{kport} --upstream {app_base} ...")
        router_proc = subprocess.Popen(
            [str(BIN), "serve", "--port", str(kport),
             "--routes", str(ROUTES), "--upstream", app_base],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        wait_for_port(kport)
        kbase = f"http://127.0.0.1:{kport}"

        print("\n--- PROOF: native in Form, fan-out to the REAL app ---")

        # --- NATIVE: served in Form, value must equal the real app's answer ---
        st, body, router = http_get(kbase + NATIVE_PATH + "?" + NATIVE_QUERY)
        kr_avg = None
        try:
            kr_avg = float(body)
        except ValueError:
            pass
        matches_app = (app_avg is not None and kr_avg is not None
                       and abs(kr_avg - float(app_avg)) < 1e-12)
        ok = st == 200 and router == "native-kernel" and matches_app
        print(f"  [native  ] {NATIVE_PATH} -> {st} body={body!r} "
              f"X-Form-Router={router}")
        print(f"             kernel-router native value={kr_avg}  ==  "
              f"real-app value={app_avg}  -> {'MATCH' if matches_app else 'MISMATCH'}  "
              f"{'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("native weighted_average", st, body, router))

        # --- FAN-OUT GET: the real app's health JSON, relayed by the router ---
        st, body, router = http_get(kbase + FANOUT_GET_PATH)
        try:
            hj = json.loads(body)
        except Exception:
            hj = {}
        genuine = "version" in hj and "kernel_runtime" in hj and "uptime_seconds" in hj
        ok = st == 200 and router == "fanout-python" and genuine
        print(f"  [fanout G] {FANOUT_GET_PATH} -> {st} X-Form-Router={router}  "
              f"(real health JSON: status={hj.get('status')!r} "
              f"version={hj.get('version')!r})  {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("fanout GET /api/health", st, body[:160], router))

        # --- FAN-OUT POST: body forwarded, the real app's quote response ---
        st, body, router = http_post(kbase + FANOUT_POST_PATH, FANOUT_POST_BODY)
        try:
            qj = json.loads(body)
        except Exception:
            qj = {}
        genuine_quote = "quote_id" in qj and "rate" in qj
        ok = st == 200 and router == "fanout-python" and genuine_quote
        print(f"  [fanout P] {FANOUT_POST_PATH} (JSON body) -> {st} "
              f"X-Form-Router={router}  (real quote: quote_id={qj.get('quote_id')!r} "
              f"rate={qj.get('rate')})  {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(("fanout POST /api/cc/exchange/quote", st, body[:160], router))

        # 3. MEASUREMENTS (real numbers, not asserted).
        print("\n--- MEASURED LATENCY (real app, real hops) ---")
        N = 300
        WARM = 30
        for _ in range(WARM):  # warm both paths
            http_get(kbase + NATIVE_PATH + "?" + NATIVE_QUERY)
            http_get(kbase + FANOUT_GET_PATH)
            http_get(app_base + FANOUT_GET_PATH)
            http_get(app_base + NATIVE_PATH + "?" + NATIVE_QUERY)

        # (a) native route through the kernel-router (served in Form, no CPython)
        nat_router = measure_get(kbase + NATIVE_PATH + "?" + NATIVE_QUERY, N)
        # (b) the SAME computation through the real app's serve_via_kernel guest path
        nat_app = measure_get(app_base + NATIVE_PATH + "?" + NATIVE_QUERY, N)
        # (c) the fan-out route DIRECTLY on FastAPI
        fan_direct = measure_get(app_base + FANOUT_GET_PATH, N)
        # (d) the SAME fan-out route THROUGH the kernel-router (proxy hop)
        fan_router = measure_get(kbase + FANOUT_GET_PATH, N)

        def line(label, s):
            p50, p99, mn = percentiles(s)
            print(f"  {label:<52} p50={p50:7.3f} ms  p99={p99:7.3f} ms  min={mn:7.3f} ms")
            return p50, p99

        print(f"  (n={N} per path, {WARM} warmup, whole-request wall time incl. loopback)")
        nr50, _ = line(f"native {NATIVE_PATH} THROUGH kernel-router (Form)", nat_router)
        na50, _ = line(f"native {NATIVE_PATH} via app serve_via_kernel guest", nat_app)
        fd50, _ = line(f"fan-out {FANOUT_GET_PATH} DIRECT on FastAPI", fan_direct)
        fr50, _ = line(f"fan-out {FANOUT_GET_PATH} THROUGH kernel-router proxy", fan_router)

        print("\n--- THE HONEST READ ---")
        proxy_overhead = fr50 - fd50
        native_saving = na50 - nr50
        print(f"  proxy-hop overhead (fan-out): through-router p50 {fr50:.3f} ms "
              f"- direct p50 {fd50:.3f} ms = {proxy_overhead:+.3f} ms "
              f"({proxy_overhead/fd50*100:+.1f}% of the direct call)")
        print(f"  native-route saving: app guest-path p50 {na50:.3f} ms "
              f"- kernel-router native p50 {nr50:.3f} ms = {native_saving:+.3f} ms "
              f"(the native route skips the whole CPython request lifecycle)")
        print(f"  native through router is {na50/nr50:.1f}x faster than the same "
              f"computation through the app's CPython request + serve_via_kernel.")

        if failures:
            print(f"\nFAIL: {len(failures)} case(s) did not match", file=sys.stderr)
            for f in failures:
                print(f"   {f}", file=sys.stderr)
            return 1
        print("\nok — the kernel-router served a NATIVE route in Form (value == "
              "the real app's), and FANNED OUT GET + POST to the REAL FastAPI app "
              "(genuine app responses, body forwarded). Real numbers above.")
        return 0
    finally:
        for p in (router_proc, app_proc):
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


if __name__ == "__main__":
    sys.exit(main())
