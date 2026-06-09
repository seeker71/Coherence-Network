#!/usr/bin/env python3
"""Run Form validation workloads as parallel shards.

The shard runner preserves ``form/validate.sh`` execution semantics by invoking
that script for each workload. Python only mirrors validate.sh's default
workload enumeration and schedules the resulting explicit workloads.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FORM_DIR = REPO_ROOT / "form"
VALIDATE_SH = FORM_DIR / "validate.sh"
DEFAULT_OUTPUT_LINES = 120


@dataclass(frozen=True)
class Workload:
    label: str
    args: tuple[str, ...]

    @property
    def searchable_text(self) -> str:
        return f"{self.label} {' '.join(self.args)}"


@dataclass(frozen=True)
class ShardResult:
    workload: Workload
    command: tuple[str, ...]
    returncode: int
    duration_seconds: float
    output: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _read_preludes(path: Path) -> list[str]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("; preludes:"):
                    return line.removeprefix("; preludes:").strip().split()
    except OSError:
        return []
    return []


def _enumerate_default_workloads() -> list[Workload]:
    workloads: list[Workload] = []

    for path in sorted((FORM_DIR / "form-samples").glob("*.fk")):
        rel = path.relative_to(FORM_DIR).as_posix()
        workloads.append(Workload(path.name, (rel,)))

    tests_dir = FORM_DIR / "form-stdlib" / "tests"
    if tests_dir.is_dir():
        test_paths = list(sorted(tests_dir.glob("*.fk")))
        test_paths.extend(sorted(tests_dir.glob("*.form")))
        for path in test_paths:
            rel = path.relative_to(FORM_DIR).as_posix()
            base = path.stem
            module = FORM_DIR / "form-stdlib" / f"{base}.fk"
            preludes = _read_preludes(path)
            if preludes:
                args = ("form-stdlib/core.fk", *preludes, rel)
            elif module.is_file() and module != path:
                args = (
                    "form-stdlib/core.fk",
                    module.relative_to(FORM_DIR).as_posix(),
                    rel,
                )
            else:
                args = ("form-stdlib/core.fk", rel)
            workloads.append(Workload(f"stdlib/{path.name}", args))

    return workloads


def _filter_workloads(
    workloads: list[Workload],
    include_regex: str | None,
    exclude_regex: str | None,
    limit: int | None,
) -> list[Workload]:
    selected = workloads
    if include_regex:
        include = re.compile(include_regex)
        selected = [w for w in selected if include.search(w.searchable_text)]
    if exclude_regex:
        exclude = re.compile(exclude_regex)
        selected = [w for w in selected if not exclude.search(w.searchable_text)]
    if limit is not None:
        selected = selected[:limit]
    return selected


def _build_command(workload: Workload, binary: bool) -> tuple[str, ...]:
    command: list[str] = ["./validate.sh"]
    if binary:
        command.append("--binary")
    command.extend(workload.args)
    return tuple(command)


def _command_display(command: tuple[str, ...]) -> str:
    return shlex.join(command)


def _run_shard(workload: Workload, binary: bool, timeout: float | None) -> ShardResult:
    command = _build_command(workload, binary)
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=FORM_DIR,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        output = proc.stdout or ""
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        output = f"{output}\nTIMEOUT after {timeout:g}s\n"
        returncode = 124
    duration = time.perf_counter() - started
    return ShardResult(workload, command, returncode, duration, output)


def _trim_output(output: str, max_lines: int) -> str:
    if max_lines <= 0:
        return output.rstrip()
    lines = output.rstrip().splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    omitted = len(lines) - max_lines
    return "\n".join([f"... {omitted} earlier line(s) omitted ...", *lines[-max_lines:]])


def _print_failure(result: ShardResult, output_lines: int) -> None:
    print("")
    print(f"--- failed shard: {result.workload.label}")
    print(f"command: cd {FORM_DIR} && {_command_display(result.command)}")
    print(f"exit: {result.returncode}")
    print(f"duration: {result.duration_seconds:.2f}s")
    print("output:")
    trimmed = _trim_output(result.output, output_lines)
    print(trimmed if trimmed else "(no output captured)")


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return value


def _nonnegative_int(raw: str) -> int:
    value = int(raw)
    if value < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return value


def _parse_args(argv: list[str]) -> argparse.Namespace:
    default_jobs = min(4, os.cpu_count() or 1)
    parser = argparse.ArgumentParser(
        description=(
            "Run the same default workloads as form/validate.sh, sharded across "
            "parallel validate.sh invocations."
        )
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=_positive_int,
        default=default_jobs,
        help=f"parallel shard count after the warm shard (default: {default_jobs})",
    )
    parser.add_argument(
        "--regex",
        "--include-regex",
        dest="include_regex",
        help="only run workloads whose label or file list matches this regex",
    )
    parser.add_argument(
        "--exclude-regex",
        help="skip workloads whose label or file list matches this regex",
    )
    parser.add_argument(
        "--limit",
        type=_nonnegative_int,
        help="run at most this many workloads after regex filtering",
    )
    parser.add_argument(
        "--binary",
        action="store_true",
        help="pass --binary to validate.sh for each shard",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print selected shard commands without running them",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="seconds before an individual shard is marked failed with exit 124",
    )
    parser.add_argument(
        "--output-lines",
        type=_nonnegative_int,
        default=DEFAULT_OUTPUT_LINES,
        help=(
            "number of captured output lines to show for each failed shard "
            f"(default: {DEFAULT_OUTPUT_LINES}; 0 shows all)"
        ),
    )
    parser.add_argument(
        "--fail-on-empty",
        action="store_true",
        help="exit nonzero when filters select no workloads",
    )
    return parser.parse_args(argv)


def _print_selection(workloads: list[Workload], binary: bool, jobs: int) -> None:
    mode = "binary" if binary else "source"
    print(f"form-validate-shards: selected {len(workloads)} workload(s), jobs={jobs}, mode={mode}")


def run(argv: list[str]) -> int:
    args = _parse_args(argv)
    if not VALIDATE_SH.is_file():
        print(f"missing validate script: {VALIDATE_SH}", file=sys.stderr)
        return 2

    try:
        workloads = _filter_workloads(
            _enumerate_default_workloads(),
            args.include_regex,
            args.exclude_regex,
            args.limit,
        )
    except re.error as exc:
        print(f"invalid regex: {exc}", file=sys.stderr)
        return 2

    _print_selection(workloads, args.binary, args.jobs)
    if not workloads:
        message = "no workloads selected"
        if args.fail_on_empty:
            print(message, file=sys.stderr)
            return 1
        print(message)
        return 0

    if args.dry_run:
        for index, workload in enumerate(workloads, start=1):
            command = _build_command(workload, args.binary)
            print(f"{index:4d}. {workload.label}: cd {FORM_DIR} && {_command_display(command)}")
        return 0

    total_started = time.perf_counter()
    print(f"warm 1/{len(workloads)} {workloads[0].label}")
    warm_result = _run_shard(workloads[0], args.binary, args.timeout)
    if warm_result.ok:
        print(f"ok   {warm_result.duration_seconds:7.2f}s {warm_result.workload.label} (warm)")
    else:
        print(f"FAIL {warm_result.duration_seconds:7.2f}s {warm_result.workload.label} (warm)")
        _print_failure(warm_result, args.output_lines)
        print("")
        print("form-validate-shards: 0 ok, 1 failed")
        return 1

    ok_results = [warm_result]
    failed_results: list[ShardResult] = []
    remaining = workloads[1:]
    completed = 1

    if remaining:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = {
                executor.submit(_run_shard, workload, args.binary, args.timeout): workload
                for workload in remaining
            }
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                completed += 1
                status = "ok  " if result.ok else "FAIL"
                print(
                    f"{status} {result.duration_seconds:7.2f}s "
                    f"{result.workload.label} [{completed}/{len(workloads)}]"
                )
                if result.ok:
                    ok_results.append(result)
                else:
                    failed_results.append(result)

    elapsed = time.perf_counter() - total_started
    for result in failed_results:
        _print_failure(result, args.output_lines)

    print("")
    print(
        "form-validate-shards: "
        f"{len(ok_results)} ok, {len(failed_results)} failed, {elapsed:.2f}s elapsed"
    )
    return 1 if failed_results else 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
