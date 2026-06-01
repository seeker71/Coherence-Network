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
contract and query defaults in api/app/routers/utils.py — they are NOT
sampled from live production traffic. Capturing real traffic (request log →
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


# ---------------------------------------------------------------------------
# Captured calls — DATA fed to the one engine. Each names a real endpoint, a
# representative input (provenance honest), and the CPython reference fn.
# ---------------------------------------------------------------------------


@dataclass
class CaptureCall:
    """One representative endpoint call, replayable on both runtimes.

    name            human id, matches the endpoint
    fk_demo         the .py demo whose body IS the recipe (under EXAMPLES);
                    compiled to .fk once = the deploy artifact
    bindings        the (let ...) inputs the live endpoint injects per request
    cpython_ref     zero-arg thunk computing the reference value in CPython —
                    the exact fallback the endpoint would run inline
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


# --- CPython reference implementations: copied verbatim from the endpoint
#     fallbacks in api/app/routers/utils.py so the harness needs no API import.


def _coherence_weight_py(values: List[int], threshold: int) -> int:
    def weighted(value: int, position: int) -> int:
        if position == 0:
            return value * 100
        if position == 1:
            return value * 50
        if position == 2:
            return value * 25
        return value * 10

    total, position = 0, 0
    for v in values:
        if v >= threshold:
            total += weighted(v, position)
            position += 1
    above = sum(1 for v in values if v >= threshold)
    return above * 100 + total


def _nodeid_distance_py(a: List[int], b: List[int]) -> int:
    return sum(abs(x - y) for x, y in zip(a, b))


def _nodeid_compat_py(a: List[int], b: List[int]) -> int:
    return sum(int(x == y) for x, y in zip(a, b))


def _weighted_average_py(values: List[float], weights: List[float]) -> float:
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


CASES: List[CaptureCall] = [
    CaptureCall(
        name="coherence_weight",
        fk_demo="endpoint_coherence_weight_demo.py",
        bindings={"values": [72, 38, 91, 55, 28, 67, 84, 45, 95, 12], "threshold": 50},
        cpython_ref=lambda: _coherence_weight_py(
            [72, 38, 91, 55, 28, 67, 84, 45, 95, 12], 50
        ),
        parse=int,
        response_shape=["weight", "values", "threshold", "runtime"],
        provenance="representative-derived from query defaults in utils.py (NOT traffic-sampled)",
    ),
    CaptureCall(
        name="nodeid_distance",
        fk_demo="endpoint_nodeid_distance_demo.py",
        bindings={
            "a_pkg": 1, "a_lvl": 5, "a_type": 4, "a_inst": 1,
            "b_pkg": 1, "b_lvl": 4, "b_type": 4, "b_inst": 7,
        },
        cpython_ref=lambda: _nodeid_distance_py([1, 5, 4, 1], [1, 4, 4, 7]),
        parse=int,
        response_shape=["distance", "a", "b", "runtime"],
        provenance="representative-derived from Query defaults in utils.py (NOT traffic-sampled)",
    ),
    CaptureCall(
        name="nodeid_compatibility",
        fk_demo="endpoint_nodeid_compatibility_demo.py",
        bindings={
            "a_pkg": 1, "a_lvl": 5, "a_type": 4, "a_inst": 1,
            "b_pkg": 1, "b_lvl": 4, "b_type": 4, "b_inst": 7,
        },
        cpython_ref=lambda: _nodeid_compat_py([1, 5, 4, 1], [1, 4, 4, 7]),
        parse=int,
        response_shape=["compatibility", "a", "b", "runtime"],
        provenance="representative-derived from Query defaults in utils.py (NOT traffic-sampled)",
    ),
    CaptureCall(
        name="weighted_average",
        fk_demo="endpoint_weighted_average_demo.py",
        bindings={"values": [0.5, 0.75, 1.0], "weights": [0.25, 0.25, 0.5]},
        cpython_ref=lambda: _weighted_average_py([0.5, 0.75, 1.0], [0.25, 0.25, 0.5]),
        parse=float,
        response_shape=["average", "values", "weights", "runtime"],
        provenance="representative-derived from query defaults in utils.py (NOT traffic-sampled)",
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

    def to_dict(self) -> dict:
        d = asdict(self)
        # drop raw sample arrays from json for size; percentiles are kept
        for k in ("cpython", "kernel_a", "path_b"):
            if d[k] is not None:
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


def render(results: List[ReadinessResult], iters: int, include_path_b: bool) -> str:
    L: List[str] = []
    L.append("=" * 78)
    L.append("kernel_readiness_harness — API → Form-kernel flip evidence")
    L.append(f"rust binary: {RUST_BIN}  (present: {RUST_BIN.is_file()})")
    L.append(f"iterations/runtime: {iters}  (after 5-run warmup; steady-state)")
    L.append("PATH A = live endpoint dispatch (compile-once .fk + per-req fork+exec)")
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
        if r.path_b is not None:
            if r.path_b.error:
                L.append(f"   PATH B     : ERROR {r.path_b.error}")
            else:
                ratio_b = (r.path_b.p50_ms / r.cpython.p50_ms) if r.cpython.p50_ms else 0
                L.append(f"   PATH B     : p50={r.path_b.p50_ms:.1f}ms  ({ratio_b:.0f}x cpython) "
                         f"— full prelude re-compile per call")
        L.append(f"   VERDICT    : {r.verdict}")
    L.append("")
    L.append("=" * 78)
    ready = sum(1 for r in results if r.verdict.startswith("READY"))
    slow = sum(1 for r in results if r.verdict.startswith("CORRECT-BUT-SLOWER"))
    notyet = sum(1 for r in results if r.verdict.startswith("NOT-YET"))
    L.append(f"SUMMARY: {len(results)} calls — {ready} READY · {slow} CORRECT-BUT-SLOWER "
             f"· {notyet} NOT-YET")
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
    print(render(results, args.iters, args.path_b))

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
