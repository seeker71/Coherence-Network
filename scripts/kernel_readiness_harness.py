#!/usr/bin/env python3
"""kernel_readiness_harness.py — readiness evidence for the API → Form-kernel flip.

The question Urs named: before flipping a FastAPI endpoint to run its body on
the Form-native kernel (form-kernel-rust / kernel-bmf) instead of inline
CPython, we need EVIDENCE — not a green demo count — that the kernel path is
healthy enough to carry real traffic. A demo count proves CORRECTNESS on a
handful of hand-authored inputs. It does NOT prove PROFILE, SHAPE, or
CIRCULATION under load.

This harness is that evidence. It is the empirical companion to
scripts/substrate_parity_harness.py (which compares substrate-verb Python
impls against Form source for VALUE/structure) — but where the parity harness
asks "do they agree?", this one asks "is the kernel path fast and stable
enough to flip, and at what cost?". It measures the *deploy-shaped* dispatch:
the exact path api/app/routers/utils.py takes via serve_via_kernel.

────────────────────────────────────────────────────────────────────────────
The two kernel-bmf paths — and why the distinction is decisive for the flip
────────────────────────────────────────────────────────────────────────────

There are TWO different "run this on the kernel" paths in the body, with
profiles orders of magnitude apart. An honest readiness doc must not conflate
them:

  PATH A — "compiled-recipe execute" (what the LIVE endpoint does today)
    api/app/services/form_kernel_bridge.serve_via_kernel:
      1. load_recipe(endpoint_X.fk)   — a .fk PRE-COMPILED at deploy time
                                         (the deploy pipeline runs
                                         `python-compile X.py X.fk` once)
      2. inject_bindings(...)          — rewrite (let ...) literals, in-process
      3. run_recipe(...)               — fork+exec form-kernel-rust <tmp.fk>
    The py→fk COMPILE is a BUILD-TIME cost, amortized across every request.
    Per-request cost = inject (µs) + subprocess spawn + kernel execute (~ms).

  PATH B — "python-bmf on kernel" (the pyfkb-run.sh --kernel rust pipeline)
    form/scripts/pyfkb-run.sh:
      source-compiles ~10 BML preludes through the Go kernel, then runs the
      whole python-bmf scanner+grammar+eval pipeline over raw .py bytes.
    This is the "API code → Form-native, no Python in the path" dream, but
    per-call it re-source-compiles the preludes — a heavy, fixed overhead
    that a per-request shell-out would pay every time. It is a PARITY proof
    path, NOT a serving path. Measured here to show WHY a persistent/warm
    kernel is required before B could ever serve load.

The flip Urs is weighing is PATH A for the pure-computation core. So PATH A
is the headline measurement; PATH B is measured as the honest "this is what
naive shell-out-the-whole-pipeline would cost" counter-evidence.

────────────────────────────────────────────────────────────────────────────
Core abstraction (Urs's first rule): ONE replay-and-profile engine
────────────────────────────────────────────────────────────────────────────

`profile_runtime(label, thunk, iters)` times any zero-arg callable under
warmup + N iterations and returns a Profile (p50/p95/p99/min/max/mean/stdev).
`run_readiness_case(case, ...)` feeds ONE case through BOTH runtimes via that
single engine and emits (value_match, cpython_profile, kernel_profile, ratio).
The captured calls are DATA (CASES below); the engine never branches per
endpoint. Adding an endpoint = adding a CaptureCall, never code.

────────────────────────────────────────────────────────────────────────────
Provenance honesty
────────────────────────────────────────────────────────────────────────────

The inputs below are REPRESENTATIVE-DERIVED from each endpoint's Pydantic
contract and query defaults in the owning api/app/routers/kernel_*.py module —
they are NOT sampled from live production traffic. Capturing real traffic (request log →
replay corpus) is the named next step before a real flip. Each case says so.

Usage:
    python3 scripts/kernel_readiness_harness.py                 # full report
    python3 scripts/kernel_readiness_harness.py --iters 200     # heavier load
    python3 scripts/kernel_readiness_harness.py --endpoint coherence_weight
    python3 scripts/kernel_readiness_harness.py --path-b        # also profile PATH B
    python3 scripts/kernel_readiness_harness.py --json out.json # machine-readable
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


REPO = Path(__file__).resolve().parent.parent
API = REPO / "api"
ADAPTER = REPO / "form" / "form-kernel-ts" / "seedbank" / "python-adapter"
EXAMPLES = ADAPTER / "examples"
RUST_BIN = REPO / "form" / "form-kernel-rust" / "target" / "release" / "form-kernel-rust"
PYFKB = REPO / "form" / "scripts" / "pyfkb-run.sh"
# The persistent-serve route table: registered ONCE into a warm kernel by
# `form-kernel-rust serve`. Holds the same recipe bodies the live endpoints run.
SERVE_ROUTES = REPO / "scripts" / "kernel_readiness_routes.fk"

if str(API) not in sys.path:
    sys.path.insert(0, str(API))

# ---------------------------------------------------------------------------
# Captured calls — DATA fed to the one engine. Each names a real endpoint, a
# representative input (provenance honest), and the CPython source-example fn.
# ---------------------------------------------------------------------------


_DEMO_FUNC_CACHE: dict[tuple[str, str], Callable[..., Any]] = {}


def demo_func(demo_py: str, fn_name: str) -> Callable[..., Any]:
    """Load a CPython baseline from the source example that compiles to the recipe."""
    key = (demo_py, fn_name)
    if key in _DEMO_FUNC_CACHE:
        return _DEMO_FUNC_CACHE[key]
    path = EXAMPLES / demo_py
    spec = importlib.util.spec_from_file_location(f"kernel_readiness_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load demo source: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, fn_name)
    _DEMO_FUNC_CACHE[key] = fn
    return fn


@dataclass
class CaptureCall:
    """One representative endpoint call, replayable on both runtimes.

    name            human id, matches the endpoint
    fk_demo         the .py demo whose body IS the recipe (under EXAMPLES);
                    compiled to .fk once = the deploy artifact
    bindings        the (let ...) inputs the live endpoint injects per request
    cpython_ref     zero-arg thunk computing the reference value in CPython
                    from the source example that compiles to the recipe
    parse           how the live endpoint parses the kernel's textual output
    response_shape  the API contract's response fields (SHAPE check, not just
                    scalar) — what the kernel value must slot into
    provenance      where the input came from (honest: derived vs sampled)
    """

    name: str
    fk_demo: str
    bindings: Dict[str, Any]
    cpython_ref: Callable[[], Any]
    parse: Callable[[str], Any]
    response_shape: List[str]
    provenance: str
    # Persistent-serve fields: the route path registered in SERVE_ROUTES and
    # the query string fired per request. `serve_query` is "" when the handler
    # computes a frozen sample (list/float args the string-only serve alist
    # can't carry — see SERVE_ROUTES header); a real query string when the
    # endpoint's inputs marshal cleanly (the two integer NodeID endpoints).
    serve_path: str = ""
    serve_query: str = ""


# --- CPython references: loaded from the canonical source examples that compile
#     to the recipe. Production route modules stay dispatch-only.


CASES: List[CaptureCall] = [
    CaptureCall(
        name="coherence_weight",
        fk_demo="endpoint_coherence_weight_demo.py",
        bindings={"values": [72, 38, 91, 55, 28, 67, 84, 45, 95, 12], "threshold": 50},
        cpython_ref=lambda: demo_func(
            "endpoint_coherence_weight_demo.py", "coherence_weight"
        )(
            [72, 38, 91, 55, 28, 67, 84, 45, 95, 12], 50
        ),
        parse=int,
        response_shape=["weight", "values", "threshold", "runtime"],
        provenance="representative-derived from kernel_nodeid.py query defaults (NOT traffic-sampled)",
        serve_path="/coherence_weight",
        serve_query="",  # list arg — handler computes frozen sample (serve alist is string-only)
    ),
    CaptureCall(
        name="nodeid_distance",
        fk_demo="endpoint_nodeid_distance_demo.py",
        bindings={
            "a_pkg": 1, "a_lvl": 5, "a_type": 4, "a_inst": 1,
            "b_pkg": 1, "b_lvl": 4, "b_type": 4, "b_inst": 7,
        },
        cpython_ref=lambda: demo_func(
            "endpoint_nodeid_distance_demo.py", "manhattan"
        )(1, 5, 4, 1, 1, 4, 4, 7),
        parse=int,
        response_shape=["distance", "a", "b", "runtime"],
        provenance="representative-derived from kernel_nodeid.py query defaults (NOT traffic-sampled)",
        serve_path="/nodeid_distance",
        serve_query="a_pkg=1&a_lvl=5&a_type=4&a_inst=1&b_pkg=1&b_lvl=4&b_type=4&b_inst=7",
    ),
    CaptureCall(
        name="nodeid_compatibility",
        fk_demo="endpoint_nodeid_compatibility_demo.py",
        bindings={
            "a_pkg": 1, "a_lvl": 5, "a_type": 4, "a_inst": 1,
            "b_pkg": 1, "b_lvl": 4, "b_type": 4, "b_inst": 7,
        },
        cpython_ref=lambda: demo_func(
            "endpoint_nodeid_compatibility_demo.py", "compatibility"
        )(1, 5, 4, 1, 1, 4, 4, 7),
        parse=int,
        response_shape=["compatibility", "a", "b", "runtime"],
        provenance="representative-derived from kernel_nodeid.py query defaults (NOT traffic-sampled)",
        serve_path="/nodeid_compatibility",
        serve_query="a_pkg=1&a_lvl=5&a_type=4&a_inst=1&b_pkg=1&b_lvl=4&b_type=4&b_inst=7",
    ),
    CaptureCall(
        name="weighted_average",
        fk_demo="endpoint_weighted_average_demo.py",
        bindings={"values": [0.5, 0.75, 1.0], "weights": [0.25, 0.25, 0.5]},
        cpython_ref=lambda: demo_func(
            "endpoint_weighted_average_demo.py", "weighted_average"
        )([0.5, 0.75, 1.0], [0.25, 0.25, 0.5]),
        parse=float,
        response_shape=["average", "values", "weights", "runtime"],
        provenance="representative-derived from kernel_scoring.py query defaults (NOT traffic-sampled)",
        serve_path="/weighted_average",
        serve_query="",  # list+float args — handler computes frozen sample
    ),
]


# ---------------------------------------------------------------------------
# Profile — the shape every timing measurement produces.
# ---------------------------------------------------------------------------


@dataclass
class Profile:
    label: str
    iters: int
    samples_ms: List[float] = field(default_factory=list, repr=False)
    mean_ms: float = 0.0
    stdev_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    error: Optional[str] = None

    def finalize(self) -> "Profile":
        s = sorted(self.samples_ms)
        if not s:
            return self

        def pct(p: float) -> float:
            # nearest-rank percentile — honest on small N, no interpolation games
            k = max(0, min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1)))))
            return s[k]

        self.mean_ms = statistics.fmean(s)
        self.stdev_ms = statistics.pstdev(s) if len(s) > 1 else 0.0
        self.p50_ms = pct(50)
        self.p95_ms = pct(95)
        self.p99_ms = pct(99)
        self.min_ms = s[0]
        self.max_ms = s[-1]
        return self


# ---------------------------------------------------------------------------
# THE ONE ENGINE — profile any zero-arg thunk under warmup + N iterations.
# Every runtime (CPython, kernel PATH A, kernel PATH B) is measured by this
# single function. Runtimes differ only in the thunk handed in.
# ---------------------------------------------------------------------------


def profile_runtime(
    label: str,
    thunk: Callable[[], Any],
    iters: int,
    warmup: int = 5,
) -> tuple[Profile, Any]:
    """Time `thunk` over `iters` iterations after `warmup` discarded runs.

    Returns (Profile, last_value). Warmup absorbs cold-cache / first-spawn
    cost so steady-state is what's reported; variance is preserved (we keep
    every sample, report stdev + percentiles, never just the mean).
    """
    prof = Profile(label=label, iters=iters)
    last_value: Any = None
    try:
        for _ in range(warmup):
            last_value = thunk()
        for _ in range(iters):
            t0 = time.perf_counter()
            last_value = thunk()
            prof.samples_ms.append((time.perf_counter() - t0) * 1000.0)
    except Exception as e:  # surface, don't hide
        prof.error = f"{type(e).__name__}: {e}"
    return prof.finalize(), last_value


# ---------------------------------------------------------------------------
# Runtime thunks — each builds the zero-arg callable the engine times.
# ---------------------------------------------------------------------------


def _ensure_bridge():
    """Import the live dispatch helpers from api/, pointing at the local bin.

    The harness uses the EXACT functions the live endpoint uses
    (inject_bindings + run_recipe), so the measured path is the deployed one,
    not a re-implementation.
    """
    if str(API) not in sys.path:
        sys.path.insert(0, str(API))
    os.environ.setdefault("FORM_KERNEL_RUST_BIN", str(RUST_BIN))
    from app.services import form_kernel_bridge as bridge  # type: ignore

    return bridge


def compile_demo_to_fk(demo_py: str, dst: Path) -> float:
    """Compile a .py demo to .fk via the TS python-compile (the deploy step).

    Returns the wall-clock seconds the compile took — this is the BUILD-TIME
    cost, measured once and reported separately from per-request latency. The
    live endpoint never pays this per request; the deploy pipeline does, once.
    """
    src = EXAMPLES / demo_py
    t0 = time.perf_counter()
    subprocess.run(
        ["npx", "tsx", "src/main.ts", "python-compile", str(src), str(dst)],
        cwd=str(ADAPTER),
        check=True,
        capture_output=True,
        text=True,
    )
    return time.perf_counter() - t0


def make_cpython_thunk(case: CaptureCall) -> Callable[[], Any]:
    return case.cpython_ref


def make_kernel_path_a_thunk(case: CaptureCall, fk_source: str, bridge) -> Callable[[], Any]:
    """PATH A per-request thunk: inject bindings + fork+exec the rust kernel.

    This is precisely serve_via_kernel's per-request work (minus load_recipe,
    which the live endpoint also does once-warm via the .fk on disk — we hold
    fk_source in memory to isolate the per-request inject+run cost, the same
    way a warmed process would).
    """
    def thunk() -> Any:
        injected = bridge.inject_bindings(fk_source, case.bindings)
        raw = bridge.run_recipe(injected)
        return case.parse(raw)

    return thunk


def make_inline_thunk(case: CaptureCall, fk_source: str, bridge) -> Callable[[], Any]:
    """INLINE per-request thunk: inject bindings + a C call into the warm PyO3
    kernel — NO process spawn, NO socket loopback.

    This is precisely serve_via_kernel's per-request work on the hot path: the
    `form_kernel_rust` extension is imported ONCE at module load (a warm Rust
    runtime living in the Python process); each request injects literals and
    calls `compile_and_run`, returning an already-typed Python value. The only
    per-request cost is inject (µs) + parse + recipe execution in-process — the
    spawn AND the HTTP/1.0 loopback that dominate PATH A and SERVE are both
    gone. This is the production hot path the readiness evidence named.
    """
    def thunk() -> Any:
        injected = bridge.inject_bindings(fk_source, case.bindings)
        value = bridge.run_inline(injected)
        # run_inline returns a native typed value (int/float/list); parse is a
        # no-op for the int/float cases (int(int)==int, float(float)==float).
        try:
            return case.parse(value)
        except (TypeError, ValueError):
            return case.parse(str(value))

    return thunk


def make_preload_thunk(case: CaptureCall, handle: int, bridge) -> Callable[[], Any]:
    """PRELOAD per-request thunk: run a pre-parsed route — NO inject, NO parse.

    The warm Preloader parsed this recipe ONCE (split into setup + body) when
    the handle was loaded. Each request only converts the bindings dict and
    walks the held body NodeID in a child frame — the per-request tokenize +
    read_sexp + defn-rebind that the inline-with-parse thunk pays is gone. This
    isolates exactly the cost the route-preload pair removes.
    """
    def thunk() -> Any:
        value = bridge.run_preloaded(handle, case.bindings)
        try:
            return case.parse(value)
        except (TypeError, ValueError):
            return case.parse(str(value))

    return thunk


def make_path_b_thunk(demo_py: str) -> Callable[[], Any]:
    """PATH B thunk: the full pyfkb-run.sh --kernel rust pipeline per call.

    Re-source-compiles the BML preludes and runs the python-bmf pipeline over
    raw .py bytes every invocation — the naive "shell out the whole thing"
    cost. Measured to show why a persistent kernel is required before B serves.
    """
    src = EXAMPLES / demo_py

    def thunk() -> Any:
        proc = subprocess.run(
            [str(PYFKB), "--kernel", "rust", str(src)],
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout.rstrip("\n").splitlines()[-1]

    return thunk


# ---------------------------------------------------------------------------
# Persistent serve — the apples-to-apples model Urs named.
#
# A per-request fork+exec (PATH A) is the WRONG comparison: CPython serves from
# a warm, already-loaded process; it does not fork an interpreter per request.
# The honest counterpart is `form-kernel-rust serve`: it loads SERVE_ROUTES
# ONCE into a long-lived Kernel+Arena, then dispatches each HTTP/1.0 GET to the
# matching handler closure with a fresh child frame — NO per-request spawn, NO
# per-request source-compile. This is the number that decides the flip.
#
# The +jit variant asks the warm kernel to `jit_compile` each route's recipe at
# load (real recipe→machine-code via rustc cdylib). For the four endpoint
# recipes this is a no-op the harness MEASURES and reports honestly: their
# bodies use `_plus` / `abs` / list natives outside the JIT subset, so
# jit_compile returns 0. The JIT mechanism IS real (proven on a pure-operator
# recipe — see profile_jit_demonstrator); the gap is the emit coverage, not the
# compiler. Both facts are evidence.
# ---------------------------------------------------------------------------

import http.client
import socket


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class PersistentServe:
    """Start `form-kernel-rust serve` once; hold it warm for the whole run.

    Context manager: __enter__ spawns the listener on a free port, waits until
    it accepts, and yields self; __exit__ kills it. The whole point is that the
    kernel + routes load EXACTLY ONCE — every request inside the block is
    request→handler→recipe-walk→response over the already-loaded process, the
    apples-to-apples counterpart to a warm CPython worker.

    `jit=True` writes a sibling routes file that appends `(jit_compile "<fn>")`
    for each endpoint computation so the warm kernel attempts a recipe→native
    compile at load. Honest by construction: if jit_compile returns 0 the route
    still serves via recipe-walk (same value), and the latency simply won't move
    — which is itself the measured finding.
    """

    # The endpoint computation function each route dispatches into — the name
    # jit_compile would target. (Handlers themselves close over these.)
    JIT_TARGETS = ["coherence_weight", "manhattan", "compatibility", "weighted_average"]

    def __init__(self, routes_path: Path, jit: bool = False):
        self.jit = jit
        self.port = _free_port()
        self._proc: Optional[subprocess.Popen] = None
        self._tmp_routes: Optional[Path] = None
        if jit:
            base = routes_path.read_text(encoding="utf-8")
            lines = [base, "\n; +jit: attempt real recipe→native compile at load"]
            for fn in self.JIT_TARGETS:
                lines.append(f'(let _jit_{fn} (jit_compile "{fn}"))')
            import tempfile as _tf
            fd = _tf.NamedTemporaryFile("w", suffix="_jit.fk", delete=False)
            fd.write("\n".join(lines))
            fd.close()
            self._tmp_routes = Path(fd.name)
            self.routes_path = self._tmp_routes
            self.jit_results: Dict[str, Optional[int]] = {fn: None for fn in self.JIT_TARGETS}
        else:
            self.routes_path = routes_path
            self.jit_results = {}

    def __enter__(self) -> "PersistentServe":
        self._proc = subprocess.Popen(
            [str(RUST_BIN), "serve", "--port", str(self.port),
             "--routes", str(self.routes_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        # Wait until the listener accepts (bounded) — the one-time load cost.
        deadline = time.time() + 10.0
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    break
            except OSError:
                if self._proc.poll() is not None:
                    err = self._proc.stderr.read().decode() if self._proc.stderr else ""
                    raise RuntimeError(f"serve exited during startup: {err}")
                time.sleep(0.02)
        else:
            raise RuntimeError("serve did not start listening within 10s")
        return self

    def request(self, path: str, query: str) -> str:
        """One HTTP/1.0 GET over the warm kernel; return the response body."""
        target = path if not query else f"{path}?{query}"
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10.0)
        try:
            conn.request("GET", target)
            resp = conn.getresponse()
            return resp.read().decode().strip()
        finally:
            conn.close()

    def __exit__(self, *exc) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._tmp_routes is not None:
            try:
                self._tmp_routes.unlink()
            except OSError:
                pass


def make_serve_thunk(server: PersistentServe, case: CaptureCall) -> Callable[[], Any]:
    """Per-request thunk: one HTTP GET over the already-loaded kernel."""
    def thunk() -> Any:
        body = server.request(case.serve_path, case.serve_query)
        return case.parse(body)
    return thunk


# ---------------------------------------------------------------------------
# JIT demonstrator — what a REAL recipe→machine-code compile buys, measured.
#
# The four endpoint recipes are outside the JIT emit subset, so jit_compile is
# a no-op for them. To still answer "what does real JIT do?" with a NUMBER, we
# measure the compiler on a recipe that IS in the subset: fib expressed in the
# operator forms emit_rust_source covers (`add`/`sub`/`lt`). Walked vs compiled,
# same kernel, same input. This isolates the JIT speedup from the endpoint gap.
# ---------------------------------------------------------------------------


@dataclass
class JitDemo:
    available: bool          # rustc present + compile returned 1
    compile_returned: int    # raw jit_compile return (1 ok / 0 unavailable / -1 unbound)
    walked_p50_ms: float
    jit_p50_ms: float
    speedup: Optional[float]
    note: str


def profile_jit_demonstrator(iters: int) -> JitDemo:
    """Measure walked-vs-jit on an in-subset recipe (fib via add/sub/lt)."""
    # Drive MANY fib calls inside ONE kernel run so the recipe-execution cost
    # dominates the fixed spawn (+ one-time rustc compile in the jit case). A
    # single fib(28) is ~comparable to spawn; a loop of K fib(30) makes the
    # walk-vs-native delta the thing the wall clock measures.
    n, k = 30, 8
    fib_def = "(defn fib (n) (if (lt n 2) n (add (fib (sub n 1)) (fib (sub n 2)))))"
    loop_def = f"(defn loopk (i acc) (if (eq i 0) acc (loopk (sub i 1) (add acc (fib {n})))))"
    walked_fk = f"{fib_def}\n{loop_def}\n(loopk {k} 0)"
    jit_fk = f'{fib_def}\n(let _c (jit_compile "fib"))\n{loop_def}\n(loopk {k} 0)'

    def run(src: str) -> str:
        import tempfile as _tf
        f = _tf.NamedTemporaryFile("w", suffix=".fk", delete=False)
        f.write(src)
        f.close()
        try:
            p = subprocess.run([str(RUST_BIN), f.name], capture_output=True,
                               text=True, timeout=60)
            return p.stdout.rstrip("\n").splitlines()[-1]
        finally:
            os.unlink(f.name)

    # Probe jit_compile's return code once.
    probe_fk = (
        f"(defn fib (n) (if (lt n 2) n (add (fib (sub n 1)) (fib (sub n 2)))))\n"
        f'(jit_compile "fib")'
    )
    try:
        compile_returned = int(run(probe_fk))
    except Exception:
        compile_returned = -2

    if compile_returned != 1:
        return JitDemo(
            available=False, compile_returned=compile_returned,
            walked_p50_ms=0.0, jit_p50_ms=0.0, speedup=None,
            note="jit_compile did not return 1 (rustc missing or recipe outside subset)",
        )

    # These thunks include subprocess spawn + the run; we report the RATIO of
    # walked to jit so the shared spawn cost cancels and the recipe-execution
    # delta is what surfaces. n is chosen so walk-cost >> spawn-cost.
    # Few iters — each run is heavy (seconds for the walked case).
    reps = max(3, min(8, iters // 12))
    walked_prof, _ = profile_runtime("jit-demo/walked", lambda: run(walked_fk),
                                     reps, warmup=1)
    jit_prof, _ = profile_runtime("jit-demo/compiled", lambda: run(jit_fk),
                                  reps, warmup=1)
    speedup = (walked_prof.p50_ms / jit_prof.p50_ms) if jit_prof.p50_ms else None
    return JitDemo(
        available=True, compile_returned=1,
        walked_p50_ms=walked_prof.p50_ms, jit_p50_ms=jit_prof.p50_ms,
        speedup=speedup,
        note=f"{k}x fib({n}) walked vs recipe→native (rustc cdylib); jit incl. one-time compile",
    )


# ---------------------------------------------------------------------------
# Readiness case result + the per-case driver (uses the ONE engine for both).
# ---------------------------------------------------------------------------


@dataclass
class ReadinessResult:
    name: str
    provenance: str
    response_shape: List[str]
    compile_s: float                 # PATH A build-time cost (once, not per-req)
    cpython: Profile
    kernel_a: Profile
    path_b: Optional[Profile]
    cpython_value: Any
    kernel_a_value: Any
    value_match: bool
    ratio_a_p50: Optional[float]     # kernel PATH A p50 / cpython p50
    verdict: str
    # Persistent-serve (the apples-to-apples model). Populated only when the
    # serve measurement runs (--persistent); None otherwise so PATH A output is
    # unchanged when serve isn't requested.
    serve: Optional[Profile] = None
    serve_value: Any = None
    serve_value_match: Optional[bool] = None
    ratio_serve_p50: Optional[float] = None  # serve p50 / cpython p50
    serve_jit: Optional[Profile] = None
    serve_jit_value: Any = None
    serve_verdict: Optional[str] = None
    serve_marshalled: bool = False           # True when a real query string carried inputs
    # Inline (PyO3) — the warm in-process kernel, no spawn, no loopback. The
    # production hot path. Populated only when --inline runs.
    inline: Optional[Profile] = None
    inline_value: Any = None
    inline_value_match: Optional[bool] = None
    ratio_inline_p50: Optional[float] = None  # inline p50 / cpython p50
    inline_verdict: Optional[str] = None
    # Route-preload (PyO3 Preloader) — the inline path with the per-request
    # parse dropped: recipe parsed ONCE at load, only the body walks per
    # request. Populated only when --preload runs.
    preload: Optional[Profile] = None
    preload_value: Any = None
    preload_value_match: Optional[bool] = None
    ratio_preload_p50: Optional[float] = None  # preload p50 / cpython p50
    preload_verdict: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        # drop raw sample arrays from json for size; percentiles are kept
        for k in ("cpython", "kernel_a", "path_b", "serve", "serve_jit", "inline", "preload"):
            if d.get(k) is not None:
                d[k].pop("samples_ms", None)
        return d


def _verdict(value_match: bool, ratio: Optional[float], ka: Profile) -> str:
    if ka.error:
        return f"NOT-YET — kernel path errored: {ka.error}"
    if not value_match:
        return "NOT-YET — value parity FAILED (correctness gate not met)"
    if ratio is None:
        return "UNKNOWN — could not compute ratio"
    if ratio <= 3.0:
        return f"READY — correct, p50 within {ratio:.1f}x CPython (healthy envelope)"
    if ratio <= 50.0:
        return (
            f"CORRECT-BUT-SLOWER — {ratio:.1f}x CPython p50; acceptable only for "
            f"low-volume calls. Warm/persistent kernel removes the spawn cost."
        )
    return (
        f"NOT-YET — {ratio:.0f}x CPython p50; per-call subprocess spawn dominates. "
        f"Needs a persistent/inline (PyO3) kernel before a flip carries load."
    )


def _serve_verdict(value_match: bool, ratio: Optional[float], prof: Profile) -> str:
    """Readiness verdict under the PERSISTENT-SERVE model (spawn removed)."""
    if prof.error:
        return f"NOT-YET — serve path errored: {prof.error}"
    if not value_match:
        return "NOT-YET — value parity FAILED over the warm channel"
    if ratio is None:
        return "UNKNOWN — could not compute serve ratio"
    # Absolute envelope matters more than the ratio here: CPython's pure-compute
    # p50 is sub-microsecond, so any HTTP round-trip is a large MULTIPLE yet may
    # be a tiny ABSOLUTE overhead. Judge on absolute p99 against an HTTP budget.
    if prof.p99_ms <= 2.0:
        return (f"READY (shape) — warm channel, p50={prof.p50_ms:.3f}ms "
                f"p99={prof.p99_ms:.3f}ms; sub-2ms request→response, no spawn")
    if prof.p99_ms <= 10.0:
        return (f"HEALTHY-ENVELOPE — warm channel p99={prof.p99_ms:.3f}ms; "
                f"low-single-digit-ms, dominated by HTTP/1.0 loopback, not compute")
    return (f"REVIEW — warm channel p99={prof.p99_ms:.3f}ms exceeds 10ms; "
            f"investigate loopback/marshalling overhead")


def _inline_verdict(value_match: bool, ratio: Optional[float], prof: Profile) -> str:
    """Readiness verdict under the INLINE (PyO3) model — spawn AND loopback gone.

    Inline removes BOTH the per-request process spawn (PATH A) and the HTTP/1.0
    loopback (SERVE). What remains is inject (µs) + a C call + recipe execution.
    CPython's pure-compute p50 is sub-microsecond, so even a small constant
    overhead reads as a large MULTIPLE — judge on the ABSOLUTE p99 against a
    per-request budget, same posture as the serve verdict but with a tighter
    envelope (no socket).
    """
    if prof.error:
        return f"NOT-YET — inline path errored: {prof.error}"
    if not value_match:
        return "NOT-YET — value parity FAILED on the inline (PyO3) path"
    if ratio is None:
        return "UNKNOWN — could not compute inline ratio"
    if prof.p99_ms <= 0.1:
        return (f"READY — warm in-process kernel, p50={prof.p50_ms:.4f}ms "
                f"p99={prof.p99_ms:.4f}ms; sub-100µs, no spawn, no loopback")
    if prof.p99_ms <= 1.0:
        return (f"READY (shape) — inline p50={prof.p50_ms:.4f}ms "
                f"p99={prof.p99_ms:.4f}ms; sub-ms in-process, spawn+loopback removed")
    if prof.p99_ms <= 5.0:
        return (f"HEALTHY-ENVELOPE — inline p99={prof.p99_ms:.4f}ms; low-ms, "
                f"recipe execution + inject, no transport")
    return (f"REVIEW — inline p99={prof.p99_ms:.4f}ms exceeds 5ms; "
            f"investigate recipe-walk / inject overhead")


def _preload_verdict(
    value_match: bool, prof: Profile, inline: Optional[Profile]
) -> str:
    """Verdict under the ROUTE-PRELOAD model — parse dropped from the inline path.

    Same absolute-envelope posture as the inline verdict (no spawn, no
    loopback), but the headline finding is the DELTA vs inline-with-parse: how
    much the per-request tokenize/read/defn-rebind cost was. When an inline
    profile is present we name the speedup so the gain is legible at a glance.
    """
    if prof.error:
        return f"NOT-YET — preload path errored: {prof.error}"
    if not value_match:
        return "NOT-YET — value parity FAILED on the route-preload path"
    delta = ""
    if inline is not None and not inline.error and prof.p50_ms > 0:
        drop = inline.p50_ms - prof.p50_ms
        speedup = inline.p50_ms / prof.p50_ms if prof.p50_ms else 0.0
        delta = (f"  [parse drop: p50 {inline.p50_ms:.5f}→{prof.p50_ms:.5f}ms, "
                 f"−{drop*1000:.1f}µs, {speedup:.2f}x vs inline-with-parse]")
    if prof.p99_ms <= 0.1:
        return (f"READY — warm preloaded route, p50={prof.p50_ms:.5f}ms "
                f"p99={prof.p99_ms:.5f}ms; sub-100µs, parse dropped{delta}")
    if prof.p99_ms <= 1.0:
        return (f"READY (shape) — preload p50={prof.p50_ms:.5f}ms "
                f"p99={prof.p99_ms:.5f}ms; sub-ms, no per-request parse{delta}")
    if prof.p99_ms <= 5.0:
        return (f"HEALTHY-ENVELOPE — preload p99={prof.p99_ms:.5f}ms; "
                f"low-ms, recipe-walk only{delta}")
    return (f"REVIEW — preload p99={prof.p99_ms:.5f}ms exceeds 5ms{delta}")


def measure_preload(
    results: List[ReadinessResult],
    cases: List[CaptureCall],
    iters: int,
    bridge,
) -> None:
    """Fill preload fields on `results` using the warm Preloader (route-preload).

    Loads each case's recipe into the Preloader ONCE (split + parse), then times
    only run_preloaded per request — the path with the per-request parse removed.
    Reuses the same warmed CPython + inline baselines on each ReadinessResult so
    the delta is apples-to-apples against the inline-with-parse number.
    """
    if not bridge.preload_available():
        for r in results:
            r.preload_verdict = "UNAVAILABLE — Preloader (route-preload pair) not importable"
        return
    for case in cases:
        r = next((x for x in results if x.name == case.name), None)
        if r is None:
            continue
        # Load once (split + parse) — NOT timed per request; mirror the live
        # bridge's preload_route(recipe, binding-name-set) seam.
        recipe = f"endpoint_{case.name}_demo.fk"
        handle = bridge.preload_route(recipe, set(case.bindings))
        if handle is None:
            r.preload_verdict = "UNAVAILABLE — recipe did not split/parse for preload"
            continue
        prof, val = profile_runtime(
            f"{case.name}/preload", make_preload_thunk(case, handle, bridge), iters
        )
        r.preload = prof
        r.preload_value = val
        r.preload_value_match = (not prof.error) and _values_agree(r.cpython_value, val)
        if r.cpython.p50_ms > 0 and prof.p50_ms > 0 and not prof.error:
            r.ratio_preload_p50 = prof.p50_ms / r.cpython.p50_ms
        r.preload_verdict = _preload_verdict(
            bool(r.preload_value_match), prof, r.inline
        )


def measure_inline(
    results: List[ReadinessResult],
    cases: List[CaptureCall],
    iters: int,
    bridge,
) -> None:
    """Fill inline fields on `results` using the warm PyO3 kernel.

    The `form_kernel_rust` extension is already imported once at bridge module
    load — that IS the warm kernel. Each case re-uses the same compiled .fk the
    PATH A measurement built (held in /tmp by run_readiness_case), injects its
    bindings, and calls run_inline. CPython's baseline is reused from each
    ReadinessResult so the comparison is against the identical warm-CPython
    number PATH A and SERVE used.
    """
    if not bridge.inline_available():
        for r in results:
            r.inline_verdict = "UNAVAILABLE — form_kernel_rust PyO3 extension not importable"
        return
    for case in cases:
        r = next((x for x in results if x.name == case.name), None)
        if r is None:
            continue
        fk_source = (Path("/tmp") / f"kr_{case.name}.fk").read_text(encoding="utf-8")
        prof, val = profile_runtime(
            f"{case.name}/inline", make_inline_thunk(case, fk_source, bridge), iters
        )
        r.inline = prof
        r.inline_value = val
        r.inline_value_match = (not prof.error) and _values_agree(r.cpython_value, val)
        if r.cpython.p50_ms > 0 and prof.p50_ms > 0 and not prof.error:
            r.ratio_inline_p50 = prof.p50_ms / r.cpython.p50_ms
        r.inline_verdict = _inline_verdict(
            bool(r.inline_value_match), r.ratio_inline_p50, prof
        )


def measure_persistent_serve(
    results: List[ReadinessResult],
    cases: List[CaptureCall],
    iters: int,
    with_jit: bool,
) -> None:
    """Fill serve fields on `results` using ONE warm kernel per mode.

    The kernel + routes load EXACTLY ONCE per mode (the whole apples-to-apples
    point). Every case's requests fire over that single warm process. CPython's
    baseline is already on each ReadinessResult (cpython profile) — we reuse it
    so the comparison is against the identical warm-CPython number PATH A used.
    """
    by_name = {r.name: r for r in results}

    # Mode: kernel-persistent-serve. One warm server, all cases.
    with PersistentServe(SERVE_ROUTES, jit=False) as server:
        for case in cases:
            r = by_name.get(case.name)
            if r is None:
                continue
            prof, val = profile_runtime(
                f"{case.name}/serve", make_serve_thunk(server, case), iters
            )
            r.serve = prof
            r.serve_value = case.parse(str(val)) if not isinstance(val, (int, float)) else val
            r.serve_value_match = (not prof.error) and _values_agree(r.cpython_value, val)
            r.serve_marshalled = bool(case.serve_query)
            if r.cpython.p50_ms > 0 and prof.p50_ms > 0 and not prof.error:
                r.ratio_serve_p50 = prof.p50_ms / r.cpython.p50_ms
            r.serve_verdict = _serve_verdict(
                bool(r.serve_value_match), r.ratio_serve_p50, prof
            )

    if not with_jit:
        return

    # Mode: kernel-persistent-serve+jit. Same shape, warm kernel attempts a
    # recipe→native compile of each endpoint computation at load.
    with PersistentServe(SERVE_ROUTES, jit=True) as server:
        for case in cases:
            r = by_name.get(case.name)
            if r is None:
                continue
            prof, val = profile_runtime(
                f"{case.name}/serve+jit", make_serve_thunk(server, case), iters
            )
            r.serve_jit = prof
            r.serve_jit_value = (
                case.parse(str(val)) if not isinstance(val, (int, float)) else val
            )


def run_readiness_case(
    case: CaptureCall,
    iters: int,
    bridge,
    include_path_b: bool,
) -> ReadinessResult:
    # Build the deploy artifact (.fk) — compile-once, timed separately.
    fk_dst = Path("/tmp") / f"kr_{case.name}.fk"
    compile_s = compile_demo_to_fk(case.fk_demo, fk_dst)
    fk_source = fk_dst.read_text(encoding="utf-8")

    # CPython reference — ONE engine.
    cpy_prof, cpy_val = profile_runtime(
        f"{case.name}/cpython", make_cpython_thunk(case), iters
    )
    # Kernel PATH A — SAME engine, different thunk.
    ka_prof, ka_val_raw = profile_runtime(
        f"{case.name}/kernel-rust-pathA",
        make_kernel_path_a_thunk(case, fk_source, bridge),
        iters,
    )

    # VALUE parity — compare normalized (parse already applied in thunk).
    ka_val = ka_val_raw
    value_match = (not ka_prof.error) and _values_agree(cpy_val, ka_val)

    ratio = None
    if cpy_prof.p50_ms > 0 and ka_prof.p50_ms > 0 and not ka_prof.error:
        ratio = ka_prof.p50_ms / cpy_prof.p50_ms

    path_b = None
    if include_path_b:
        path_b, _ = profile_runtime(
            f"{case.name}/path-b-pyfkb",
            make_path_b_thunk(case.fk_demo),
            max(3, iters // 10),  # PATH B is heavy; fewer iters, still warmed
            warmup=2,
        )

    return ReadinessResult(
        name=case.name,
        provenance=case.provenance,
        response_shape=case.response_shape,
        compile_s=compile_s,
        cpython=cpy_prof,
        kernel_a=ka_prof,
        path_b=path_b,
        cpython_value=cpy_val,
        kernel_a_value=ka_val,
        value_match=value_match,
        ratio_a_p50=ratio,
        verdict=_verdict(value_match, ratio, ka_prof),
    )


def _values_agree(a: Any, b: Any) -> bool:
    """Value equality tolerant of int/float surface (kernel prints, py types)."""
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-9
        except (TypeError, ValueError):
            return False
    return a == b


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render(
    results: List[ReadinessResult],
    iters: int,
    include_path_b: bool,
    include_serve: bool = False,
    include_inline: bool = False,
    include_preload: bool = False,
    jit_demo: Optional["JitDemo"] = None,
) -> str:
    L: List[str] = []
    L.append("=" * 78)
    L.append("kernel_readiness_harness — API → Form-kernel flip evidence")
    L.append(f"rust binary: {RUST_BIN}  (present: {RUST_BIN.is_file()})")
    L.append(f"iterations/runtime: {iters}  (after 5-run warmup; steady-state)")
    L.append("PATH A = live endpoint dispatch (compile-once .fk + per-req fork+exec)")
    if include_serve:
        L.append("SERVE  = persistent `form-kernel-rust serve` — routes load ONCE, "
                 "request→response over the warm process (apples-to-apples w/ CPython)")
    if include_inline:
        L.append("INLINE = warm PyO3 `form_kernel_rust` in-process — C call into Rust, "
                 "NO spawn, NO loopback (the prior hot path; inject + re-parse each call)")
    if include_preload:
        L.append("PRELOAD = warm Preloader — recipe parsed ONCE at load, per request "
                 "only the body walks (no inject, no re-parse: the parse dropped)")
    if include_path_b:
        L.append("PATH B = pyfkb full python-bmf pipeline per call (naive shell-out)")
    L.append("=" * 78)
    for r in results:
        L.append("")
        L.append(f"── {r.name}")
        L.append(f"   provenance : {r.provenance}")
        L.append(f"   resp shape : {r.response_shape}")
        L.append(f"   value      : cpython={r.cpython_value!r}  kernel={r.kernel_a_value!r}"
                 f"  match={'YES' if r.value_match else 'NO'}")
        L.append(f"   compile .fk: {r.compile_s*1000:.1f} ms  (BUILD-TIME, once — NOT per-request)")
        L.append(f"   cpython    : p50={r.cpython.p50_ms:.4f}ms p95={r.cpython.p95_ms:.4f} "
                 f"p99={r.cpython.p99_ms:.4f} mean={r.cpython.mean_ms:.4f} sd={r.cpython.stdev_ms:.4f}")
        if r.kernel_a.error:
            L.append(f"   kernel A   : ERROR {r.kernel_a.error}")
        else:
            L.append(f"   kernel A   : p50={r.kernel_a.p50_ms:.4f}ms p95={r.kernel_a.p95_ms:.4f} "
                     f"p99={r.kernel_a.p99_ms:.4f} mean={r.kernel_a.mean_ms:.4f} sd={r.kernel_a.stdev_ms:.4f}")
        if r.ratio_a_p50 is not None:
            L.append(f"   ratio (p50): kernel A / cpython = {r.ratio_a_p50:.1f}x")
        if r.serve is not None:
            marsh = "real-query-args" if r.serve_marshalled else "frozen-sample (list/float arg)"
            if r.serve.error:
                L.append(f"   serve      : ERROR {r.serve.error}")
            else:
                L.append(f"   serve      : p50={r.serve.p50_ms:.4f}ms p95={r.serve.p95_ms:.4f} "
                         f"p99={r.serve.p99_ms:.4f} mean={r.serve.mean_ms:.4f} sd={r.serve.stdev_ms:.4f}")
                L.append(f"   serve val  : {r.serve_value!r}  match="
                         f"{'YES' if r.serve_value_match else 'NO'}  [{marsh}]")
                if r.ratio_serve_p50 is not None:
                    L.append(f"   serve ratio: serve p50 / cpython p50 = {r.ratio_serve_p50:.0f}x "
                             f"(absolute p99={r.serve.p99_ms:.3f}ms — judge on the ABSOLUTE)")
            if r.serve_jit is not None and not r.serve_jit.error:
                L.append(f"   serve+jit  : p50={r.serve_jit.p50_ms:.4f}ms "
                         f"p99={r.serve_jit.p99_ms:.4f}  (no-op for this recipe — see JIT note)")
            if r.serve_verdict is not None:
                L.append(f"   SERVE VERD : {r.serve_verdict}")
        if r.inline is not None or r.inline_verdict is not None:
            if r.inline is None:
                L.append(f"   inline     : {r.inline_verdict}")
            elif r.inline.error:
                L.append(f"   inline     : ERROR {r.inline.error}")
            else:
                L.append(f"   inline     : p50={r.inline.p50_ms:.5f}ms p95={r.inline.p95_ms:.5f} "
                         f"p99={r.inline.p99_ms:.5f} mean={r.inline.mean_ms:.5f} sd={r.inline.stdev_ms:.5f}")
                L.append(f"   inline val : {r.inline_value!r}  match="
                         f"{'YES' if r.inline_value_match else 'NO'}  (PyO3, no spawn, no loopback)")
                if r.ratio_inline_p50 is not None:
                    L.append(f"   inline rt  : inline p50 / cpython p50 = {r.ratio_inline_p50:.1f}x "
                             f"(absolute p99={r.inline.p99_ms:.5f}ms — judge on the ABSOLUTE)")
                if r.inline_verdict is not None:
                    L.append(f"   INLINE VERD: {r.inline_verdict}")
        if r.preload is not None or r.preload_verdict is not None:
            if r.preload is None:
                L.append(f"   preload    : {r.preload_verdict}")
            elif r.preload.error:
                L.append(f"   preload    : ERROR {r.preload.error}")
            else:
                L.append(f"   preload    : p50={r.preload.p50_ms:.5f}ms p95={r.preload.p95_ms:.5f} "
                         f"p99={r.preload.p99_ms:.5f} mean={r.preload.mean_ms:.5f} sd={r.preload.stdev_ms:.5f}")
                L.append(f"   preload val: {r.preload_value!r}  match="
                         f"{'YES' if r.preload_value_match else 'NO'}  (parse dropped, walk only)")
                if r.inline is not None and not r.inline.error and r.preload.p50_ms > 0:
                    drop = r.inline.p50_ms - r.preload.p50_ms
                    spd = r.inline.p50_ms / r.preload.p50_ms if r.preload.p50_ms else 0.0
                    L.append(f"   parse drop : inline p50 {r.inline.p50_ms:.5f}ms → preload "
                             f"{r.preload.p50_ms:.5f}ms = −{drop*1000:.1f}µs ({spd:.2f}x)")
                if r.ratio_preload_p50 is not None:
                    L.append(f"   preload rt : preload p50 / cpython p50 = {r.ratio_preload_p50:.1f}x "
                             f"(absolute p99={r.preload.p99_ms:.5f}ms — judge on the ABSOLUTE)")
                if r.preload_verdict is not None:
                    L.append(f"   PRELOAD VRD: {r.preload_verdict}")
        if r.path_b is not None:
            if r.path_b.error:
                L.append(f"   PATH B     : ERROR {r.path_b.error}")
            else:
                ratio_b = (r.path_b.p50_ms / r.cpython.p50_ms) if r.cpython.p50_ms else 0
                L.append(f"   PATH B     : p50={r.path_b.p50_ms:.1f}ms  ({ratio_b:.0f}x cpython) "
                         f"— full prelude re-compile per call")
        L.append(f"   VERDICT    : {r.verdict}")
    if jit_demo is not None:
        L.append("")
        L.append("── JIT (real recipe→machine-code, measured on an in-subset recipe)")
        if not jit_demo.available:
            L.append(f"   jit_compile returned {jit_demo.compile_returned} — {jit_demo.note}")
        else:
            L.append(f"   {jit_demo.note}")
            L.append(f"   walked  p50 = {jit_demo.walked_p50_ms:.1f} ms")
            L.append(f"   jit     p50 = {jit_demo.jit_p50_ms:.1f} ms")
            if jit_demo.speedup is not None:
                L.append(f"   speedup     = {jit_demo.speedup:.0f}x (recipe→native via rustc cdylib)")
        L.append("   NOTE: the 4 endpoint recipes are OUTSIDE the JIT emit subset")
        L.append("         (their bodies use `_plus`/`abs`/list natives, not the")
        L.append("         operator forms emit_rust_source covers), so jit_compile is a")
        L.append("         no-op FOR THEM. The compiler is real; the gap is emit coverage.")
    L.append("")
    L.append("=" * 78)
    ready = sum(1 for r in results if r.verdict.startswith("READY"))
    slow = sum(1 for r in results if r.verdict.startswith("CORRECT-BUT-SLOWER"))
    notyet = sum(1 for r in results if r.verdict.startswith("NOT-YET"))
    L.append(f"SUMMARY (PATH A): {len(results)} calls — {ready} READY · "
             f"{slow} CORRECT-BUT-SLOWER · {notyet} NOT-YET")
    if include_serve:
        s_ready = sum(1 for r in results if (r.serve_verdict or "").startswith("READY"))
        s_healthy = sum(1 for r in results if (r.serve_verdict or "").startswith("HEALTHY"))
        s_match = sum(1 for r in results if r.serve_value_match)
        L.append(f"SUMMARY (SERVE): {len(results)} calls — {s_match}/{len(results)} value-parity"
                 f" · {s_ready} READY-shape · {s_healthy} HEALTHY-ENVELOPE")
    if include_inline:
        i_ready = sum(1 for r in results if (r.inline_verdict or "").startswith("READY"))
        i_healthy = sum(1 for r in results if (r.inline_verdict or "").startswith("HEALTHY"))
        i_match = sum(1 for r in results if r.inline_value_match)
        L.append(f"SUMMARY (INLINE): {len(results)} calls — {i_match}/{len(results)} value-parity"
                 f" · {i_ready} READY · {i_healthy} HEALTHY-ENVELOPE")
    if include_preload:
        p_ready = sum(1 for r in results if (r.preload_verdict or "").startswith("READY"))
        p_match = sum(1 for r in results if r.preload_value_match)
        drops = [
            (r.inline.p50_ms - r.preload.p50_ms)
            for r in results
            if r.preload is not None and not r.preload.error
            and r.inline is not None and not r.inline.error
        ]
        avg_drop = (sum(drops) / len(drops)) if drops else 0.0
        L.append(f"SUMMARY (PRELOAD): {len(results)} calls — {p_match}/{len(results)} value-parity"
                 f" · {p_ready} READY · mean parse-drop vs inline = {avg_drop*1000:.1f}µs p50")
    L.append("Value parity is the floor; the profile decides readiness. See "
             "kernels/API_KERNEL_READINESS.md for the readiness map.")
    L.append("=" * 78)
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--iters", type=int, default=50, help="timed iterations per runtime")
    ap.add_argument("--endpoint", help="run only this endpoint by name")
    ap.add_argument("--path-b", action="store_true", help="also profile the pyfkb PATH B")
    ap.add_argument("--persistent", action="store_true",
                    help="also measure the PERSISTENT serve path (the apples-to-apples model)")
    ap.add_argument("--inline", action="store_true",
                    help="also measure the INLINE PyO3 path (warm in-process kernel, no spawn/loopback)")
    ap.add_argument("--preload", action="store_true",
                    help="also measure the ROUTE-PRELOAD path (recipe parsed once, parse dropped per request)")
    ap.add_argument("--jit", action="store_true",
                    help="with --persistent: add the +jit serve mode; also runs the JIT demonstrator")
    ap.add_argument("--json", help="write machine-readable results to this path")
    args = ap.parse_args(argv)

    if not RUST_BIN.is_file():
        print(f"form-kernel-rust binary not found at {RUST_BIN}", file=sys.stderr)
        print("build it: cd form/form-kernel-rust && cargo build --release", file=sys.stderr)
        return 2

    bridge = _ensure_bridge()
    if not bridge.kernel_available():
        print("kernel binary present but not executable / not found by bridge", file=sys.stderr)
        return 2

    cases = CASES
    if args.endpoint:
        cases = [c for c in CASES if c.name == args.endpoint]
        if not cases:
            print(f"no endpoint named {args.endpoint!r}", file=sys.stderr)
            return 2

    results = [
        run_readiness_case(c, args.iters, bridge, include_path_b=args.path_b)
        for c in cases
    ]

    jit_demo = None
    if args.persistent:
        if not SERVE_ROUTES.is_file():
            print(f"serve routes file missing at {SERVE_ROUTES}", file=sys.stderr)
            return 2
        measure_persistent_serve(results, cases, args.iters, with_jit=args.jit)
    if args.inline:
        measure_inline(results, cases, args.iters, bridge)
    # Preload runs AFTER inline so the verdict can name the parse-drop delta
    # against the inline-with-parse number measured on the same warm process.
    if args.preload:
        measure_preload(results, cases, args.iters, bridge)
    if args.jit:
        jit_demo = profile_jit_demonstrator(args.iters)

    print(render(results, args.iters, args.path_b,
                 include_serve=args.persistent, include_inline=args.inline,
                 include_preload=args.preload, jit_demo=jit_demo))

    if args.json:
        Path(args.json).write_text(
            json.dumps([r.to_dict() for r in results], indent=2, default=str),
            encoding="utf-8",
        )
        print(f"\nwrote {args.json}")

    # Exit nonzero only on a correctness failure — slowness is evidence, not
    # a test failure. The verdict is for humans; CI gates on value parity.
    return 0 if all(r.value_match for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
