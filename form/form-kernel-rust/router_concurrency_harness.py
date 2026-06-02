#!/usr/bin/env python3
"""Concurrency proof for the kernel-as-router WORKER POOL.

The companion to router_proof_harness.py. That harness proves the inverted
topology (the kernel owns the front door, native in Form, tail fanned out).
THIS one proves the load-bearing concurrency gap named in KERNEL_AS_ROUTER.md
is closed: `cli_serve` now dispatches accepted streams to a POOL of kernel
workers, each owning its OWN Kernel + Arena (the `!Sync` per-process intern
table means a pool, not one shared mutable kernel).

Three properties, all MEASURED (not asserted):

  1. CORRECT UNDER CONCURRENCY — 50 parallel clients all get HTTP 200 with the
     right native value and X-Form-Router: native-kernel. No request is dropped
     or corrupted when many hit at once.

  2. NO CROSS-REQUEST STATE BLEED — the critical correctness property of the
     pool. Each client sends a DIFFERENT input to the input-driven native
     handler (/count_signals?values=<k commas> → k+1) and must get back its OWN
     k+1, never another client's. Because each worker has its own Kernel+Arena,
     concurrent value-walks with different inputs cannot bleed into one another.
     If the pool shared mutable kernel state, overlapping requests would corrupt
     each other's frame bindings and the per-client fingerprints would scramble.

  3. THE POOL ACTUALLY PARALLELIZES — single-worker (--workers 1) vs N-worker
     throughput under the SAME concurrent load. With CPU-bearing native handlers
     (the recursive char-walk over a long input string), one worker serializes
     the walks; N workers run them on N cores. We report req/s and p50/p99 for
     both and show N-worker throughput climbs above 1-worker. Real numbers.

Run from form/form-kernel-rust/:
    cargo build --release
    python3 router_concurrency_harness.py
"""
from __future__ import annotations

import concurrent.futures
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
ROUTES = HERE / "examples" / "router-proof.fk"

# How many parallel clients hammer the server at once.
CONCURRENCY = 50
# Requests per throughput measurement (spread across the CONCURRENCY clients).
LOAD_REQUESTS = 600
# CPU weight per request: the native /count_signals handler walks the input
# string char-by-char in the kernel (recursive Form). A long input makes each
# request carry real CPU so a single worker visibly serializes while N workers
# parallelize. ~4000 commas keeps each request a few ms of pure value-walk.
HEAVY_COMMAS = 4000


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_port(port: int, timeout: float = 8.0) -> None:
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


def fetch(url: str):
    """Return (status, body, router-header) for a GET."""
    try:
        with urllib.request.urlopen(url, timeout=30.0) as r:
            return r.status, r.read().decode("utf-8"), r.headers.get("X-Form-Router")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), e.headers.get("X-Form-Router")
    except Exception as e:  # noqa: BLE001 - report the failure as a tuple
        return -1, f"{type(e).__name__}: {e}", None


def start_server(workers: int, port: int) -> subprocess.Popen:
    proc = subprocess.Popen(
        [
            str(BIN), "serve",
            "--port", str(port),
            "--routes", str(ROUTES),
            "--workers", str(workers),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    wait_for_port(port)
    return proc


def stop_server(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=3.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2.0)


def prove_no_bleed(base: str) -> list:
    """Fire CONCURRENCY parallel clients, EACH with a different input, and check
    every client gets back ITS OWN correct value. /count_signals?values=<k
    commas> returns k+1, so client k expects str(k+1) — a unique per-client
    fingerprint. Any cross-request bleed scrambles the mapping."""
    # k=0 would mean an empty values arg (the handler returns "0"); start at 1
    # so each client has a non-trivial distinct comma-count fingerprint.
    inputs = list(range(1, CONCURRENCY + 1))

    def one(k: int):
        url = f"{base}/count_signals?values={',' * k}"  # k commas -> k+1 fields
        status, body, router = fetch(url)
        return k, status, body, router

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        for k, status, body, router in ex.map(one, inputs):
            results[k] = (status, body, router)

    failures = []
    for k in inputs:
        status, body, router = results[k]
        expect = str(k + 1)
        ok = status == 200 and body == expect and router == "native-kernel"
        if not ok:
            failures.append((k, expect, status, body, router))
    return failures


def measure_throughput(base: str, label: str) -> dict:
    """Drive LOAD_REQUESTS heavy native requests through CONCURRENCY parallel
    clients and report wall-clock throughput + latency percentiles."""
    heavy_url = f"{base}/count_signals?values={',' * HEAVY_COMMAS}"
    expect = str(HEAVY_COMMAS + 1)

    def one(_i: int):
        t0 = time.perf_counter()
        status, body, _router = fetch(heavy_url)
        dt = (time.perf_counter() - t0) * 1000.0
        return dt, (status == 200 and body == expect)

    latencies = []
    correct = 0
    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        for dt, ok in ex.map(one, range(LOAD_REQUESTS)):
            latencies.append(dt)
            correct += 1 if ok else 0
    wall = time.perf_counter() - t_start

    latencies.sort()
    p50 = statistics.median(latencies)
    p99 = latencies[min(len(latencies) - 1, int(0.99 * len(latencies)))]
    rps = LOAD_REQUESTS / wall if wall > 0 else float("inf")
    print(
        f"  [{label:>10}] {LOAD_REQUESTS} reqs @ {CONCURRENCY} parallel: "
        f"{rps:8.1f} req/s  p50={p50:6.2f} ms  p99={p99:7.2f} ms  "
        f"correct={correct}/{LOAD_REQUESTS}"
    )
    return {"rps": rps, "p50": p50, "p99": p99, "correct": correct, "wall": wall}


def main() -> int:
    if not BIN.exists():
        print(f"build first: cargo build --release ({BIN} missing)", file=sys.stderr)
        return 2
    if not ROUTES.exists():
        print(f"missing routes file: {ROUTES}", file=sys.stderr)
        return 2

    ncpu = os.cpu_count() or 4
    n_workers = min(max(ncpu, 4), 8)  # the multi-worker pool size to compare
    print(f"host cores={ncpu}; comparing 1 worker vs {n_workers} workers; "
          f"{CONCURRENCY} parallel clients\n")

    failures = []

    # ---- Property 1 + 2: correctness + NO cross-request bleed under load ----
    # Run against the MULTI-worker pool — the case where bleed would appear if
    # workers shared mutable kernel state.
    port = free_port()
    proc = start_server(n_workers, port)
    try:
        base = f"http://127.0.0.1:{port}"
        bleed_failures = prove_no_bleed(base)
        if bleed_failures:
            print(f"  [no-bleed ] {CONCURRENCY} parallel clients, DISTINCT inputs "
                  f"-> FAIL ({len(bleed_failures)} mismatched)")
            for k, expect, status, body, router in bleed_failures[:8]:
                print(f"      client k={k}: expected {expect!r} got "
                      f"status={status} body={body!r} router={router}")
            failures.extend(bleed_failures)
        else:
            print(f"  [no-bleed ] {CONCURRENCY} parallel clients, each a DISTINCT "
                  f"input -> ALL got their OWN correct value (k commas -> k+1). "
                  f"No cross-request state bleed.")
    finally:
        stop_server(proc)

    # ---- Property 3: the pool actually parallelizes (1 vs N under load) ----
    print()
    port1 = free_port()
    proc1 = start_server(1, port1)
    try:
        single = measure_throughput(f"http://127.0.0.1:{port1}", "1 worker")
    finally:
        stop_server(proc1)

    portn = free_port()
    procn = start_server(n_workers, portn)
    try:
        multi = measure_throughput(f"http://127.0.0.1:{portn}", f"{n_workers} workers")
    finally:
        stop_server(procn)

    speedup = multi["rps"] / single["rps"] if single["rps"] > 0 else 0.0
    print(f"\n  speedup ({n_workers} workers / 1 worker): {speedup:.2f}x "
          f"throughput under {CONCURRENCY}-way concurrent load")

    if single["correct"] != LOAD_REQUESTS or multi["correct"] != LOAD_REQUESTS:
        print("  FAIL: some heavy requests returned wrong/failed values",
              file=sys.stderr)
        failures.append(("throughput-correctness",))

    # The pool must measurably beat the single worker on CPU-bearing concurrent
    # load. We require a real margin (>1.3x) so a noisy near-1.0 result fails
    # rather than passing on jitter — the claim is "the pool parallelizes," and
    # that claim needs a number, not a vibe.
    if speedup < 1.3:
        print(f"\nFAIL: {n_workers}-worker throughput did not exceed 1-worker by a "
              f"real margin ({speedup:.2f}x < 1.3x) — pool not parallelizing",
              file=sys.stderr)
        return 1

    if failures:
        print(f"\nFAIL: {len(failures)} correctness failure(s)", file=sys.stderr)
        return 1

    print("\nok — worker pool: correct under 50-way concurrency, NO cross-request "
          f"state bleed (each isolated kernel), and {speedup:.2f}x throughput from "
          f"{n_workers} workers vs 1. The concurrency gap is closed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
