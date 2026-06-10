#!/usr/bin/env python3
"""Focused end-to-end probe for /api/utils/grounded_cost.

This is the complex-endpoint slice for the native HTTP stack:

* Python source-body timing, without HTTP.
* Python endpoint-shape timing: query parse -> body -> JSON render.
* Compiled Python-adapter recipe timing through the Rust and Go kernel binaries.
* FastAPI over HTTP as a kernel-guest route.
* Native kernel HTTP route over the same query.
* Go JIT treatment/miss counts from framebuffer observations, plus dispatch
  evidence that separates "compiled artifact exists" from "call used it".

The probe is intentionally narrow. It gives one endpoint enough structure to
improve the general flow without turning the broad readiness harness into a
one-off special case.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "api"
ADAPTER_DIR = ROOT / "form" / "form-kernel-ts" / "seedbank" / "python-adapter"
EXAMPLES_DIR = ADAPTER_DIR / "examples"
PY_DEMO = EXAMPLES_DIR / "endpoint_grounded_cost_demo.py"
FK_RECIPE = EXAMPLES_DIR / "endpoint_grounded_cost_demo.fk"
BML_HANDLER = ROOT / "form" / "form-stdlib" / "tests" / "grounded-cost-record-handler-band.fk"
RUST_BIN = ROOT / "form" / "form-kernel-rust" / "target" / "release" / "form-kernel-rust"
GO_BIN = ROOT / "form" / "form-kernel-go" / "bin-go"
PRODUCTION_ROUTES = ROOT / "deploy" / "kernel-router" / "production-routes.fk"
FORM_STDLIB = ROOT / "form" / "form-stdlib"


@dataclass
class Profile:
    label: str
    iters: int
    samples_ms: list[float] = field(default_factory=list, repr=False)
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    stdev_ms: float = 0.0
    error: str | None = None

    def finalize(self) -> "Profile":
        samples = sorted(self.samples_ms)
        if not samples:
            return self

        def pct(p: float) -> float:
            idx = max(0, min(len(samples) - 1, round((p / 100.0) * (len(samples) - 1))))
            return samples[idx]

        self.p50_ms = pct(50)
        self.p95_ms = pct(95)
        self.p99_ms = pct(99)
        self.min_ms = samples[0]
        self.max_ms = samples[-1]
        self.mean_ms = statistics.fmean(samples)
        self.stdev_ms = statistics.pstdev(samples) if len(samples) > 1 else 0.0
        return self


@dataclass
class Fixture:
    specs: list[dict[str, float]]
    commits: list[dict[str, int]]
    links: list[dict[str, float]]
    runtime_cost: float
    query: str
    bad_query: str


def profile(label: str, thunk: Callable[[], Any], iters: int, warmup: int = 5) -> tuple[Profile, Any]:
    prof = Profile(label=label, iters=iters)
    last: Any = None
    try:
        for _ in range(warmup):
            last = thunk()
        for _ in range(iters):
            start = time.perf_counter()
            last = thunk()
            prof.samples_ms.append((time.perf_counter() - start) * 1000.0)
    except Exception as exc:
        prof.error = f"{type(exc).__name__}: {exc}"
    return prof.finalize(), last


def fixture(spec_count: int, commit_count: int, link_count: int) -> Fixture:
    specs = [
        {
            "actual_cost": round(0.5 + (i % 7) * 0.25, 6),
            "estimated_cost": round(0.75 + (i % 11) * 0.35, 6),
        }
        for i in range(spec_count)
    ]
    commits = [
        {
            "change_files": i % 9,
            "lines_added": (i * 17) % 500,
        }
        for i in range(commit_count)
    ]
    links = [
        {
            "estimated_cost": round(0.1 + (i % 13) * 0.2, 6),
        }
        for i in range(link_count)
    ]
    runtime_cost = 2.25
    sac = ",".join(str(x["actual_cost"]) for x in specs)
    sec = ",".join(str(x["estimated_cost"]) for x in specs)
    cfs = ",".join(str(x["change_files"]) for x in commits)
    las = ",".join(str(x["lines_added"]) for x in commits)
    lec = ",".join(str(x["estimated_cost"]) for x in links)
    query = (
        f"spec_actual_costs={sac}&spec_estimated_costs={sec}"
        f"&commit_change_files={cfs}&commit_lines_added={las}"
        f"&lineage_estimated_costs={lec}&runtime_cost={runtime_cost}"
    )
    bad_query = (
        "spec_actual_costs=1.0,2.0&spec_estimated_costs=1.0"
        "&commit_change_files=1&commit_lines_added=1"
    )
    return Fixture(specs, commits, links, runtime_cost, query, bad_query)


def import_bridge_and_handler() -> tuple[Any, Callable[..., list[float]]]:
    if str(API_DIR) not in sys.path:
        sys.path.insert(0, str(API_DIR))
    from app.services import form_kernel_bridge as bridge  # type: ignore

    spec = importlib.util.spec_from_file_location("grounded_cost_source_reference", PY_DEMO)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load source reference: {PY_DEMO}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return bridge, mod.grounded_cost


def source_reference_endpoint_json(
    fx: Fixture,
    source_reference: Callable[..., list[float]],
) -> str:
    outputs = source_reference(fx.specs, fx.commits, fx.links, fx.runtime_cost)
    body = {
        "spec_actual_cost_sum": outputs[0],
        "spec_estimated_cost_sum": outputs[1],
        "runtime_cost": outputs[2],
        "commit_cost_sum": outputs[3],
        "lineage_estimated_cost": outputs[4],
        "computed_actual_cost": outputs[5],
        "spec_count_in": len(fx.specs),
        "commit_count_in": len(fx.commits),
        "lineage_count_in": len(fx.links),
        "runtime": "python-source-reference",
    }
    return json.dumps(body, separators=(",", ":"))


def values_without_runtime(body: str) -> dict[str, Any]:
    value = json.loads(body)
    value.pop("runtime", None)
    return value


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_get(base: str, path: str, query: str = "", timeout: float = 15.0) -> tuple[int, str, dict[str, str]]:
    url = base.rstrip("/") + path + (f"?{query}" if query else "")
    req = urllib.request.Request(url, headers={"Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (
                resp.status,
                resp.read().decode("utf-8"),
                {k.lower(): v for k, v in resp.headers.items()},
            )
    except urllib.error.HTTPError as exc:
        return (
            exc.code,
            exc.read().decode("utf-8"),
            {k.lower(): v for k, v in exc.headers.items()},
        )


def wait_for_http(base: str, path: str, timeout: float = 40.0) -> None:
    deadline = time.monotonic() + timeout
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            http_get(base, path, timeout=2.0)
            return
        except Exception as exc:
            last = exc
            time.sleep(0.15)
    raise RuntimeError(f"{base}{path} did not answer before timeout: {last}")


class ProcessServer:
    def __init__(self, command: list[str], cwd: Path, env: dict[str, str] | None = None):
        self.command = command
        self.cwd = cwd
        self.env = env
        self.proc: subprocess.Popen[str] | None = None

    def __enter__(self) -> "ProcessServer":
        self.proc = subprocess.Popen(
            self.command,
            cwd=str(self.cwd),
            env=self.env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        return self

    def __exit__(self, *exc: object) -> None:
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def assert_alive(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is not None:
            stderr = self.proc.stderr.read() if self.proc.stderr is not None else ""
            raise RuntimeError(f"process exited early with {self.proc.returncode}: {stderr[-2000:]}")


def compile_probe(force: bool) -> dict[str, Any]:
    if not PY_DEMO.is_file():
        return {"status": "missing-python-demo", "path": str(PY_DEMO)}
    if not FK_RECIPE.is_file():
        return {"status": "missing-compiled-recipe", "path": str(FK_RECIPE)}

    recipe_bytes = FK_RECIPE.read_bytes()
    out: dict[str, Any] = {
        "status": "committed-recipe-present",
        "recipe": str(FK_RECIPE.relative_to(ROOT)),
        "sha256": hashlib.sha256(recipe_bytes).hexdigest(),
        "bytes": len(recipe_bytes),
    }
    compiler = ADAPTER_DIR / "scripts" / "kernel-bmf-compile"
    missing_toolchain = [
        str(path)
        for path in (compiler, GO_BIN, RUST_BIN)
        if not path.exists()
    ]
    if missing_toolchain and not force:
        out["recompile"] = "skipped-form-native-toolchain-absent"
        out["missing_toolchain"] = missing_toolchain
        return out

    with tempfile.NamedTemporaryFile("w", suffix=".fk", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        start = time.perf_counter()
        proc = subprocess.run(
            [str(compiler), str(PY_DEMO), str(tmp_path)],
            cwd=str(ADAPTER_DIR),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        out["recompile_ms"] = (time.perf_counter() - start) * 1000.0
        out["recompile_returncode"] = proc.returncode
        if proc.returncode == 0 and tmp_path.is_file():
            compiled = tmp_path.read_bytes()
            out["recompile_sha256"] = hashlib.sha256(compiled).hexdigest()
            out["recompile_matches_committed"] = compiled == recipe_bytes
        else:
            out["recompile_error"] = (proc.stderr or proc.stdout)[-2000:]
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
    return out


def run_kernel_source(
    binary: Path,
    source: str,
    timeout: float = 60.0,
    trace: bool = False,
) -> subprocess.CompletedProcess[str]:
    with tempfile.NamedTemporaryFile("w", suffix=".fk", delete=False) as tmp:
        tmp.write(source)
        tmp_path = tmp.name
    try:
        args = [str(binary)]
        if trace:
            args.append("trace")
        args.append(tmp_path)
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def run_kernel_file(source: str, timeout: float = 60.0, trace: bool = False) -> subprocess.CompletedProcess[str]:
    return run_kernel_source(RUST_BIN, source, timeout=timeout, trace=trace)


def recipe_thunk(bridge: Any, fx: Fixture) -> Callable[[], list[float]]:
    source = bridge.load_recipe(FK_RECIPE)

    def thunk() -> list[float]:
        injected = bridge.inject_bindings(
            source,
            {
                "specs": fx.specs,
                "commits": fx.commits,
                "links": fx.links,
                "runtime_cost": fx.runtime_cost,
            },
        )
        raw = bridge.run_recipe(injected)
        return [float(x) for x in str(raw).strip("[]").split(", ")]

    return thunk


def kernel_source_recipe_thunk(binary: Path, bridge: Any, fx: Fixture) -> Callable[[], list[float]]:
    source = bridge.load_recipe(FK_RECIPE)

    def thunk() -> list[float]:
        injected = bridge.inject_bindings(
            source,
            {
                "specs": fx.specs,
                "commits": fx.commits,
                "links": fx.links,
                "runtime_cost": fx.runtime_cost,
            },
        )
        proc = run_kernel_source(binary, injected, timeout=60.0)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-2000:])
        raw = proc.stdout.rstrip("\n").splitlines()[-1]
        return [float(x) for x in str(raw).strip("[]").split(", ")]

    return thunk


def trace_injected_recipe(bridge: Any, fx: Fixture) -> dict[str, Any]:
    source = bridge.inject_bindings(
        bridge.load_recipe(FK_RECIPE),
        {
            "specs": fx.specs,
            "commits": fx.commits,
            "links": fx.links,
            "runtime_cost": fx.runtime_cost,
        },
    )
    proc = run_kernel_file(source, trace=True)
    if proc.returncode != 0:
        return {"error": proc.stderr[-2000:], "returncode": proc.returncode}
    trace = json.loads(proc.stdout)
    tr = trace.get("trace", {})
    return {
        "elapsed_us": trace.get("elapsed_us"),
        "result": trace.get("result"),
        "total_walks": tr.get("total_walks"),
        "top_functions": tr.get("functions", [])[:8],
        "top_natives": tr.get("natives", [])[:10],
        "top_arms": tr.get("arms", [])[:8],
    }


def portable_bml_probe() -> dict[str, Any]:
    """Run the sibling-portable BML/Form handler body on available kernels."""
    if not BML_HANDLER.is_file():
        return {"status": "missing", "path": str(BML_HANDLER)}

    expected = "[4.75, 6.75, 2.25, 0.75, 6.75, 7.75]"
    out: dict[str, Any] = {
        "status": "present",
        "path": str(BML_HANDLER.relative_to(ROOT)),
        "expected": expected,
        "kernels": {},
    }
    cases = {
        "rust": [str(RUST_BIN), str(BML_HANDLER)],
        "go": [str(GO_BIN), str(BML_HANDLER)],
    }
    for name, cmd in cases.items():
        if not Path(cmd[0]).is_file():
            out["kernels"][name] = {"status": "missing-binary", "binary": cmd[0]}
            continue
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        result = proc.stdout.rstrip("\n").splitlines()[-1] if proc.stdout.strip() else ""
        out["kernels"][name] = {
            "status": "ok" if proc.returncode == 0 else "error",
            "returncode": proc.returncode,
            "result": result,
            "matches_expected": result == expected,
            "stderr": proc.stderr[-1000:] if proc.returncode != 0 else "",
        }
    return out


def trace_native_count(trace_report: dict[str, Any], native_name: str) -> int:
    trace = trace_report.get("trace", {})
    for row in trace.get("natives", []):
        if row.get("name") == native_name:
            return int(row.get("count", 0))
    return 0


def framebuffer_count(trace_report: dict[str, Any], file: str, line: int | None = None) -> int:
    total = 0
    for row in trace_report.get("framebuffer_counts", []):
        if row.get("file") != file:
            continue
        if line is not None and int(row.get("line", -1)) != line:
            continue
        total += int(row.get("count", 0))
    return total


def framebuffer_totals(trace_report: dict[str, Any]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for row in trace_report.get("framebuffer_counts", []):
        file = str(row.get("file", ""))
        totals[file] = totals.get(file, 0) + int(row.get("count", 0))
    return totals


def go_jit_dispatch_probe() -> dict[str, Any]:
    """Separate compiled-artifact status from actual Go JIT dispatch."""
    if not GO_BIN.is_file():
        return {"status": "missing-go-binary", "binary": str(GO_BIN)}

    cases = {
        "int_i64": (
            '(do '
            '(defn double-and-sum (n) '
            '  (if (eq n 0) 0 (add (mul n 2) (double-and-sum (sub n 1))))) '
            '(let c (jit_compile "double-and-sum")) '
            '(let compiled (jit_compiled? "double-and-sum")) '
            '(let r1 (double-and-sum 5)) '
            '(let r2 (double-and-sum 10)) '
            '(list c compiled r1 r2))'
        ),
        "float_f64": (
            '(do '
            '(defn min2 (a b) (if (gt a b) b a)) '
            '(let c (jit_compile "min2")) '
            '(let compiled (jit_compiled? "min2")) '
            '(let r1 (min2 10.0 2.5)) '
            '(let r2 (min2 3.5 9.0)) '
            '(list c compiled r1 r2))'
        ),
    }

    out: dict[str, Any] = {"status": "ok", "kernel": "go", "cases": {}}
    for label, source in cases.items():
        proc = run_kernel_source(GO_BIN, source, timeout=60.0, trace=True)
        if proc.returncode != 0:
            out["cases"][label] = {
                "status": "error",
                "returncode": proc.returncode,
                "stderr": proc.stderr[-2000:],
            }
            continue
        trace_report = json.loads(proc.stdout)
        out["cases"][label] = {
            "status": "ok",
            "result": trace_report.get("result"),
            "dispatch_count": trace_native_count(trace_report, "jit-go-dispatch"),
            "framebuffer_jit_dispatch_hits": framebuffer_count(
                trace_report, "observe/go/jit/dispatch-hit"
            ),
            "framebuffer_jit_guard_misses": framebuffer_count(
                trace_report, "observe/go/jit/guard-miss"
            ),
            "framebuffer_counts": framebuffer_totals(trace_report),
            "total_walks": trace_report.get("trace", {}).get("total_walks"),
            "top_natives": trace_report.get("trace", {}).get("natives", []),
        }
    return out


def go_choice_observation_probe() -> dict[str, Any]:
    if not GO_BIN.is_file():
        return {"status": "missing-go-binary", "binary": str(GO_BIN)}
    source = "(choose (fail) (add 40 2) (stop))"
    proc = run_kernel_source(GO_BIN, source, timeout=30.0, trace=True)
    if proc.returncode != 0:
        return {
            "status": "error",
            "returncode": proc.returncode,
            "stderr": proc.stderr[-2000:],
        }
    trace_report = json.loads(proc.stdout)
    trace = trace_report.get("trace", {})
    return {
        "status": "ok",
        "result": trace_report.get("result"),
        "choice_attempts": trace.get("choice_attempts"),
        "choice_successes": trace.get("choice_successes"),
        "choice_failures": trace.get("choice_failures"),
        "framebuffer_choice_attempts": framebuffer_count(
            trace_report, "observe/go/choice/attempt"
        ),
        "framebuffer_choice_failures": framebuffer_count(
            trace_report, "observe/go/choice/fail"
        ),
        "framebuffer_choice_successes": framebuffer_count(
            trace_report, "observe/go/choice/success"
        ),
        "framebuffer_counts": framebuffer_totals(trace_report),
    }


def jit_probe(bridge: Any) -> dict[str, Any]:
    if not GO_BIN.is_file():
        return {"status": "missing-go-binary", "binary": str(GO_BIN)}

    source = bridge.load_recipe(FK_RECIPE)
    setup, _body = bridge.split_recipe(source, set())
    names = re.findall(r"\(defn\s+([^\s()]+)", source)
    probe = "(list " + " ".join(
        f'(list "{name}" (jit_compile "{name}") (jit_compiled? "{name}"))'
        for name in names
    ) + ")"
    proc = run_kernel_source(GO_BIN, f"(do {setup} {probe})", timeout=120.0, trace=True)
    if proc.returncode != 0:
        return {
            "status": "error",
            "kernel": "go",
            "error": proc.stderr[-2000:],
            "returncode": proc.returncode,
            "dispatch_probe": go_jit_dispatch_probe(),
        }
    trace_report = json.loads(proc.stdout)
    line = str(trace_report.get("result", ""))
    rows = []
    for name, compile_result, compiled in re.findall(r"\[([^,\]]+),\s*(-?\d+),\s*(-?\d+)\]", line):
        rows.append(
            {
                "name": name.strip(" []"),
                "jit_compile": int(compile_result),
                "jit_compiled": int(compiled),
            }
        )
    counts = {
        "compiled": sum(1 for row in rows if row["jit_compile"] == 1),
        "missed": sum(1 for row in rows if row["jit_compile"] == 0),
        "unbound": sum(1 for row in rows if row["jit_compile"] == -1),
        "total": len(rows),
        "framebuffer_compile_success": framebuffer_count(
            trace_report, "observe/go/jit/compile-success"
        ),
        "framebuffer_compile_fail": framebuffer_count(
            trace_report, "observe/go/jit/compile-fail"
        ),
        "framebuffer_compile_hit": framebuffer_count(
            trace_report, "observe/go/jit/compile-hit"
        ),
    }
    return {
        "status": "ok",
        "kernel": "go",
        "counts": counts,
        "rows": rows,
        "framebuffer_counts": framebuffer_totals(trace_report),
        "dispatch_probe": go_jit_dispatch_probe(),
        "note": (
            "Go JIT compile-state is body-NodeID keyed, and dispatch proof is now "
            "framebuffer-counted. grounded_cost still heats list/dict/record fold "
            "shapes that are outside the scalar JIT subset, so remaining misses point "
            "at generic container/fold lowering rather than endpoint-specific branches."
        ),
    }


def run_http_pair(fx: Fixture, iters: int) -> dict[str, Any]:
    fastapi_port = free_port()
    native_port = free_port()
    fastapi_base = f"http://127.0.0.1:{fastapi_port}"
    native_base = f"http://127.0.0.1:{native_port}"

    env = dict(os.environ)
    env["COH_ENV"] = "dev"

    with ProcessServer(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(fastapi_port),
            "--log-level",
            "warning",
        ],
        API_DIR,
        env=env,
    ) as fastapi, ProcessServer(
        [
            str(RUST_BIN),
            "serve",
            "--port",
            str(native_port),
            "--routes",
            str(PRODUCTION_ROUTES),
            "--stdlib",
            str(FORM_STDLIB),
        ],
        ROOT,
    ) as native:
        time.sleep(0.2)
        fastapi.assert_alive()
        native.assert_alive()
        wait_for_http(fastapi_base, "/api/health")
        wait_for_http(native_base, "/api/utils/grounded_cost", timeout=20.0)

        def fastapi_call() -> str:
            status, body, _headers = http_get(fastapi_base, "/api/utils/grounded_cost", fx.query)
            if status != 200:
                raise RuntimeError(f"FastAPI returned {status}: {body[:500]}")
            return body

        def native_call() -> str:
            status, body, _headers = http_get(native_base, "/api/utils/grounded_cost", fx.query)
            if status != 200:
                raise RuntimeError(f"native returned {status}: {body[:500]}")
            return body

        fastapi_profile, fastapi_body = profile("fastapi-kernel-guest-http", fastapi_call, iters)
        native_profile, native_body = profile("native-kernel-http", native_call, iters)

        fastapi_bad = http_get(fastapi_base, "/api/utils/grounded_cost", fx.bad_query)
        native_bad = http_get(native_base, "/api/utils/grounded_cost", fx.bad_query)

    return {
        "fastapi_kernel_guest_http": asdict(fastapi_profile),
        "native_kernel_http": asdict(native_profile),
        "value_match_runtime_ignored": values_without_runtime(fastapi_body) == values_without_runtime(native_body),
        "fastapi_runtime": json.loads(fastapi_body).get("runtime"),
        "native_runtime": json.loads(native_body).get("runtime"),
        "fastapi_body": fastapi_body,
        "native_body": native_body,
        "bad_request": {
            "fastapi_status": fastapi_bad[0],
            "native_status": native_bad[0],
            "fastapi_body": fastapi_bad[1],
            "native_body": native_bad[1],
            "match": fastapi_bad[0] == native_bad[0] and fastapi_bad[1] == native_bad[1],
        },
    }


def strip_samples(report: dict[str, Any]) -> dict[str, Any]:
    for key in (
        "source_reference_body",
        "source_reference_endpoint_shape",
        "kernel_recipe_subprocess",
        "go_kernel_recipe_subprocess",
    ):
        if key in report and isinstance(report[key], dict):
            report[key].pop("samples_ms", None)
    http = report.get("http")
    if isinstance(http, dict):
        for key in ("fastapi_kernel_guest_http", "native_kernel_http"):
            if key in http and isinstance(http[key], dict):
                http[key].pop("samples_ms", None)
    return report


def render(report: dict[str, Any]) -> str:
    lines = [
        "grounded_cost endpoint probe",
        f"fixture: specs={report['fixture']['specs']} commits={report['fixture']['commits']} "
        f"links={report['fixture']['links']}",
        f"compile: {report['compile']['status']} ({report['compile'].get('recompile', 'recompile-attempted')})",
        f"portable BML/Form handler: {report['portable_bml_handler']['status']} "
        f"{report['portable_bml_handler'].get('kernels', {})}",
        "",
        "timing:",
    ]
    for key in (
        "source_reference_body",
        "source_reference_endpoint_shape",
        "kernel_recipe_subprocess",
        "go_kernel_recipe_subprocess",
    ):
        prof = report[key]
        if prof.get("error"):
            lines.append(f"  {key}: ERROR {prof['error']}")
        else:
            lines.append(
                f"  {key}: p50={prof['p50_ms']:.5f}ms p95={prof['p95_ms']:.5f}ms "
                f"p99={prof['p99_ms']:.5f}ms"
            )
    http = report.get("http")
    if isinstance(http, dict) and http.get("skipped"):
        lines.append("  http: skipped")
    elif isinstance(http, dict) and "error" not in http:
        fprof = http["fastapi_kernel_guest_http"]
        nprof = http["native_kernel_http"]
        lines.extend(
            [
                f"  fastapi_kernel_guest_http: p50={fprof['p50_ms']:.5f}ms "
                f"p95={fprof['p95_ms']:.5f}ms p99={fprof['p99_ms']:.5f}ms "
                f"runtime={http['fastapi_runtime']}",
                f"  native_kernel_http: p50={nprof['p50_ms']:.5f}ms "
                f"p95={nprof['p95_ms']:.5f}ms p99={nprof['p99_ms']:.5f}ms "
                f"runtime={http['native_runtime']}",
                f"  http value match ignoring runtime: {http['value_match_runtime_ignored']}",
                f"  422 parity: {http['bad_request']['match']}",
            ]
        )
    elif isinstance(http, dict):
        lines.append(f"  http: ERROR {http['error']}")

    jit = report["jit"]
    dispatch_probe = jit.get("dispatch_probe", {})
    if jit.get("status") == "ok":
        jit_lines = [
            f"  compile results: {jit['counts']}",
            f"  framebuffer counts: {jit.get('framebuffer_counts', {})}",
            f"  dispatch probe: {dispatch_probe.get('cases', dispatch_probe)}",
            f"  note: {jit['note']}",
        ]
    else:
        jit_lines = [
            f"  error: {jit.get('error', jit.get('status'))}",
            f"  dispatch probe: {dispatch_probe.get('cases', dispatch_probe)}",
        ]
    lines.extend(
        [
            "",
            "jit:",
            f"  kernel: {jit.get('kernel', 'unknown')} status={jit.get('status', 'unknown')}",
            *jit_lines,
            "",
            "trace:",
            f"  elapsed_us={report['trace'].get('elapsed_us')} total_walks={report['trace'].get('total_walks')}",
            f"  top_natives={report['trace'].get('top_natives')}",
            "",
            f"choice observation: {report.get('choice_observation')}",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--specs", type=int, default=50)
    parser.add_argument("--commits", type=int, default=40)
    parser.add_argument("--links", type=int, default=30)
    parser.add_argument("--body-iters", type=int, default=10000)
    parser.add_argument("--recipe-iters", type=int, default=20)
    parser.add_argument("--http-iters", type=int, default=100)
    parser.add_argument("--skip-http", action="store_true")
    parser.add_argument("--compile", action="store_true", help="attempt a fresh python-adapter compile")
    parser.add_argument("--json", action="store_true", help="print full JSON report")
    args = parser.parse_args(argv)

    if not RUST_BIN.is_file():
        print(f"missing rust kernel binary: {RUST_BIN}", file=sys.stderr)
        return 2
    if not PRODUCTION_ROUTES.is_file():
        print(f"missing production route manifest: {PRODUCTION_ROUTES}", file=sys.stderr)
        return 2

    bridge, source_reference = import_bridge_and_handler()
    fx = fixture(args.specs, args.commits, args.links)
    expected = source_reference(fx.specs, fx.commits, fx.links, fx.runtime_cost)

    source_body_profile, source_body_value = profile(
        "source-reference-body",
        lambda: source_reference(fx.specs, fx.commits, fx.links, fx.runtime_cost),
        args.body_iters,
        warmup=100,
    )
    source_endpoint_profile, source_endpoint_value = profile(
        "source-reference-endpoint-shape",
        lambda: source_reference_endpoint_json(fx, source_reference),
        args.body_iters,
        warmup=100,
    )
    recipe_profile, recipe_value = profile(
        "kernel-recipe-subprocess",
        recipe_thunk(bridge, fx),
        args.recipe_iters,
        warmup=2,
    )
    go_recipe_profile, go_recipe_value = profile(
        "go-kernel-recipe-subprocess",
        kernel_source_recipe_thunk(GO_BIN, bridge, fx),
        args.recipe_iters,
        warmup=2,
    )

    report: dict[str, Any] = {
        "endpoint": "/api/utils/grounded_cost",
        "fixture": {
            "specs": args.specs,
            "commits": args.commits,
            "links": args.links,
            "runtime_cost": fx.runtime_cost,
            "query_bytes": len(fx.query),
        },
        "compile": compile_probe(args.compile),
        "expected_source_reference_value": expected,
        "source_reference_body": asdict(source_body_profile),
        "source_reference_body_value": source_body_value,
        "source_reference_endpoint_shape": asdict(source_endpoint_profile),
        "source_reference_endpoint_value": source_endpoint_value,
        "kernel_recipe_subprocess": asdict(recipe_profile),
        "kernel_recipe_value": recipe_value,
        "kernel_recipe_value_match": recipe_value == expected if recipe_profile.error is None else False,
        "go_kernel_recipe_subprocess": asdict(go_recipe_profile),
        "go_kernel_recipe_value": go_recipe_value,
        "go_kernel_recipe_value_match": (
            go_recipe_value == expected if go_recipe_profile.error is None else False
        ),
        "portable_bml_handler": portable_bml_probe(),
        "jit": jit_probe(bridge),
        "choice_observation": go_choice_observation_probe(),
        "trace": trace_injected_recipe(bridge, fx),
    }

    if args.skip_http:
        report["http"] = {"skipped": True}
    else:
        try:
            report["http"] = run_http_pair(fx, args.http_iters)
        except Exception as exc:
            report["http"] = {"error": f"{type(exc).__name__}: {exc}"}

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render(strip_samples(report)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
