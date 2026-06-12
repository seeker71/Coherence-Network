#!/usr/bin/env python3
"""Run API-oriented Form band proofs on the universal Hati-OS binary.

This harness compares the Hati-OS arm against the existing sibling proof path:
`form/validate.sh`. It also includes the SQLite-backed mutation harness so the
API-shaped mutation lane is checked against a production-seeded local DB.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FORM = ROOT / "form"
GO_BIN = FORM / "form-kernel-go" / "bin-go"
MUTATION_HARNESS = ROOT / "scripts" / "hati_os_sqlite_mutation_harness.py"
SQLITE_ARCHIVE = ROOT / ".cache" / "hati-os" / "coherence.archive.sqlite"
HATI_OS_FORM_PRELUDE = """(do
    (defn nil? (xs) (eq (len xs) 0))
    (defn plus (a b) (add a b))
    (defn max2 (a b) (if (gt a b) a b))
    (defn cons-flip (acc x) (cons x acc))
    (defn foldl (f init xs)
        (if (nil? xs) init (foldl f (f init (head xs)) (tail xs))))
    (defn sum (xs) (foldl plus 0 xs))
    (defn append (xs ys)
        (if (nil? xs) ys (cons (head xs) (append (tail xs) ys))))
    (defn reverse (xs) (foldl cons-flip (empty) xs))
    (defn kh-tag-header () 43001)
    (defn kh-tag-request () 43002)
    (defn kh-header (name value) (list (kh-tag-header) name value))
    (defn kh-header-name (header) (nth header 1))
    (defn kh-header-value (header) (nth header 2))
    (defn kh-request (method path headers query body)
        (list (kh-tag-request) method path headers query body))
    (defn kh-request-headers (request) (nth request 3))
    (defn kh-ascii-lower-char (c)
        (do
            (let cp (ord c))
            (if (and (ge cp 65) (le cp 90))
                (char_at "abcdefghijklmnopqrstuvwxyz" (sub cp 65))
                c)))
    (defn kh-ascii-lower-loop (text i)
        (if (ge i (str_len text))
            ""
            (str_concat (kh-ascii-lower-char (char_at text i))
                        (kh-ascii-lower-loop text (add i 1)))))
    (defn kh-ascii-lower (text) (kh-ascii-lower-loop text 0))
    (defn kh-str-eq-ci? (left right)
        (if (str_eq left right)
            1
            (if (and (str_eq left "x-api-key") (str_eq right "X-API-Key"))
                1
                (if (and (str_eq left "X-API-Key") (str_eq right "x-api-key")) 1 0))))
    (defn kh-header-value-or (headers name fallback)
        (if (nil? headers)
            fallback
            (if (kh-str-eq-ci? (kh-header-name (head headers)) name)
                (kh-header-value (head headers))
                (kh-header-value-or (tail headers) name fallback))))
    0)
"""


@dataclass(frozen=True)
class BandCase:
    name: str
    modules: list[str]
    band: str
    hati_os_modules: list[str] | None = None
    expected_blocker: str | None = None


CASES = [
    BandCase(
        name="application_graph_node_port",
        modules=["form-stdlib/application-graph-node-port.fk"],
        band="form-stdlib/tests/application-graph-node-port-band.fk",
    ),
    BandCase(
        name="application_graph_response_projection",
        modules=["form-stdlib/application-graph-response-projection.fk"],
        band="form-stdlib/tests/application-graph-response-projection-band.fk",
    ),
    BandCase(
        name="auth_port",
        modules=[
            "form-stdlib/kernel-http.fk",
            "form-stdlib/sha256.fk",
            "form-stdlib/hex.fk",
            "form-stdlib/auth-port.fk",
        ],
        band="form-stdlib/tests/auth-port-band.fk",
        hati_os_modules=[
            "form-stdlib/sha256.fk",
            "form-stdlib/hex.fk",
            "form-stdlib/auth-port.fk",
        ],
    ),
    BandCase(
        name="graph_node_mutation_memory_carrier",
        modules=[
            "form-stdlib/cell-log-store.fk",
            "form-stdlib/storage-port.fk",
            "form-stdlib/storage-port-file.fk",
            "form-stdlib/graph-node-port.fk",
        ],
        band="form-stdlib/tests/graph-node-mutation-memory-carrier-band.fk",
    ),
    BandCase(
        name="graph_node_mutation_file_verdict",
        modules=[
            "form-stdlib/cell-log-store.fk",
            "form-stdlib/storage-port.fk",
            "form-stdlib/storage-port-file.fk",
            "form-stdlib/graph-node-port.fk",
        ],
        band="form-stdlib/tests/graph-node-mutation-file-verdict-band.fk",
    ),
    BandCase(
        name="graph_node_mutation_file_reopen",
        modules=[
            "form-stdlib/cell-log-store.fk",
            "form-stdlib/storage-port.fk",
            "form-stdlib/storage-port-file.fk",
            "form-stdlib/graph-node-port.fk",
        ],
        band="form-stdlib/tests/graph-node-mutation-file-carrier-band.fk",
    ),
    BandCase(
        name="graph_node_port",
        modules=[
            "form-stdlib/cell-log-store.fk",
            "form-stdlib/storage-port.fk",
            "form-stdlib/storage-port-file.fk",
            "form-stdlib/graph-node-port.fk",
        ],
        band="form-stdlib/tests/graph-node-port-band.fk",
    ),
    BandCase(
        name="ideas_graph_projection",
        modules=[
            "form-stdlib/cell-log-store.fk",
            "form-stdlib/storage-port.fk",
            "form-stdlib/storage-port-file.fk",
            "form-stdlib/graph-node-port.fk",
            "form-stdlib/ideas-graph-projection.fk",
        ],
        band="form-stdlib/tests/ideas-graph-projection-band.fk",
    ),
    BandCase(
        name="native_idea_valuation_audit_ledger",
        modules=[
            "form-stdlib/application-graph-node-port.fk",
            "form-stdlib/native-mutation-side-effects.fk",
            "form-stdlib/native-idea-valuation-audit-ledger.fk",
        ],
        band="form-stdlib/tests/native-idea-valuation-audit-ledger-band.fk",
    ),
    BandCase(
        name="native_mutation_public_gate",
        modules=[
            "form-stdlib/application-graph-node-port.fk",
            "form-stdlib/native-mutation-side-effects.fk",
            "form-stdlib/native-mutation-route-side-effects.fk",
            "form-stdlib/native-idea-valuation-audit-ledger.fk",
            "form-stdlib/native-mutation-public-gate.fk",
        ],
        band="form-stdlib/tests/native-mutation-public-gate-band.fk",
    ),
    BandCase(
        name="native_mutation_route_side_effects",
        modules=[
            "form-stdlib/application-graph-node-port.fk",
            "form-stdlib/native-mutation-side-effects.fk",
            "form-stdlib/native-mutation-route-side-effects.fk",
        ],
        band="form-stdlib/tests/native-mutation-route-side-effects-band.fk",
    ),
    BandCase(
        name="native_mutation_side_effects",
        modules=["form-stdlib/native-mutation-side-effects.fk"],
        band="form-stdlib/tests/native-mutation-side-effects-band.fk",
    ),
]


def require_tool(name: str) -> None:
    if not shutil.which(name):
        raise RuntimeError(f"required tool missing: {name}")


def build_go_kernel() -> None:
    if GO_BIN.exists():
        return
    subprocess.run(["go", "build", "-o", "bin-go", "."], cwd=FORM / "form-kernel-go", check=True)


def form_read_list(parts: list[str]) -> str:
    if not parts:
        return "(list)"
    return "(list " + " ".join(f'(read_file "{path}")' for path in parts) + ")"


def materialize_hati_os_source(path: str, work: Path, case_name: str) -> str:
    """Copy source for the Hati table when host-only temp_dir needs grounding."""
    src = FORM / path
    text = src.read_text(encoding="utf-8")
    if "(temp_dir)" not in text:
        return path
    temp_root = work / "case-temp" / case_name
    temp_root.mkdir(parents=True, exist_ok=True)
    out = work / "sources" / case_name / path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text.replace("(temp_dir)", json.dumps(str(temp_root))), encoding="utf-8")
    return str(out)


def band_table_expr(modules: list[str], band: str, prelude_path: Path) -> str:
    modsrcs = form_read_list([str(prelude_path), *modules])
    bandsrc = f'(read_file "{band}")'
    return (
        f"(fks-table-file "
        f"(flt-band-sources-fns {modsrcs} {bandsrc}) "
        f"(flt-band-sources-pool {modsrcs} {bandsrc}))"
    )


def emit_universal_runner(work: Path) -> tuple[Path, dict[str, Path]]:
    build_go_kernel()
    require_tool("clang")
    driver_path = work / "api-band-driver.fk"
    prelude_path = work / "hati-os-form-prelude.fk"
    prelude_path.write_text(HATI_OS_FORM_PRELUDE, encoding="utf-8")
    body = [
        (FORM / "form-stdlib" / "minimal-surface.fk").read_text(encoding="utf-8"),
        (FORM / "form-stdlib" / "hati-os-kernel.fk").read_text(encoding="utf-8"),
        (FORM / "form-stdlib" / "hati-os-kernel-emit.fk").read_text(encoding="utf-8"),
        (FORM / "form-stdlib" / "bmf-mini.fk").read_text(encoding="utf-8"),
        (FORM / "form-stdlib" / "form-parse.fk").read_text(encoding="utf-8"),
        (FORM / "form-stdlib" / "form-flatten.fk").read_text(encoding="utf-8"),
        '(print "==UNI==")',
        "(print (fkc-emit-universal))",
    ]
    for case in CASES:
        modules = [
            materialize_hati_os_source(path, work, case.name)
            for path in (case.hati_os_modules or case.modules)
        ]
        band = materialize_hati_os_source(case.band, work, case.name)
        body.append(f'(print "==CASE:{case.name}==")')
        body.append(f"(print {band_table_expr(modules, band, prelude_path)})")
    body.append('(print "==END==")')
    driver_path.write_text("\n".join(body) + "\n", encoding="utf-8")

    emitted = subprocess.run([str(GO_BIN), str(driver_path)], cwd=FORM, text=True, capture_output=True, check=True)
    sections: dict[str, list[str]] = {}
    current = None
    for line in emitted.stdout.splitlines():
        if line.startswith("==") and line.endswith("=="):
            marker = line[2:-2]
            if marker == "END":
                current = None
                break
            current = marker
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)

    universal_c = work / "fkwu.c"
    universal_c.write_text("\n".join(sections["UNI"]) + "\n", encoding="utf-8")
    universal_bin = work / "fkwu"
    subprocess.run(["clang", "-O2", "-o", str(universal_bin), str(universal_c)], check=True)

    table_paths: dict[str, Path] = {}
    for case in CASES:
        marker = f"CASE:{case.name}"
        table_path = work / f"{case.name}.table.txt"
        table_path.write_text("\n".join(sections[marker]) + "\n", encoding="utf-8")
        table_paths[case.name] = table_path
    return universal_bin, table_paths


def parse_validate_verdict(stdout: str) -> str:
    match = re.search(r"→\s*([0-9]+)", stdout)
    if not match:
        raise RuntimeError(f"could not parse validate verdict from output:\n{stdout}")
    return match.group(1)


def trim_text(text: str, *, max_lines: int = 20) -> str:
    lines = text.strip().splitlines()
    if len(lines) <= max_lines:
        return text.strip()
    keep = max_lines // 2
    omitted = len(lines) - (keep * 2)
    return "\n".join([*lines[:keep], f"... {omitted} line(s) omitted ...", *lines[-keep:]])


def run_case(universal_bin: Path, table_path: Path, case: BandCase) -> dict[str, object]:
    validate_cmd = ["./validate.sh", "form-stdlib/core.fk", *case.modules, case.band]
    validate = subprocess.run(validate_cmd, cwd=FORM, text=True, capture_output=True, check=False)
    if validate.returncode != 0:
        expected = case.expected_blocker is not None
        return {
            "name": case.name,
            "modules": case.modules,
            "band": case.band,
            "expected_blocker": case.expected_blocker,
            "validate_returncode": validate.returncode,
            "validate_stdout": validate.stdout,
            "validate_stderr": validate.stderr,
            "passed": expected,
            "status": "expected_blocked" if expected else "failed",
            "failure": None if expected else "validate_failed",
        }

    sibling_verdict = parse_validate_verdict(validate.stdout)
    hati_os = subprocess.run([str(universal_bin), str(table_path), "0"], text=True, capture_output=True, check=False)
    hati_os_verdict = (hati_os.stdout.strip().splitlines() or [""])[0].strip()
    full_parity = hati_os.returncode == 0 and hati_os_verdict == sibling_verdict
    expected = case.expected_blocker is not None
    passed = full_parity or expected
    return {
        "name": case.name,
        "modules": case.modules,
        "band": case.band,
        "expected_blocker": case.expected_blocker,
        "validate_returncode": validate.returncode,
        "sibling_verdict": sibling_verdict,
        "hati_os_returncode": hati_os.returncode,
        "hati_os_verdict": hati_os_verdict,
        "hati_os_stderr": trim_text(hati_os.stderr),
        "passed": passed,
        "status": "full_parity" if full_parity else ("expected_blocked" if expected else "failed"),
        "failure": None if passed else "verdict_mismatch_or_runtime_failure",
    }


def run_mutation_harness() -> dict[str, object]:
    proc = subprocess.run(
        ["python3", str(MUTATION_HARNESS), "--sqlite-path", str(SQLITE_ARCHIVE), "--tag", "latest"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "passed": False,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    payload = json.loads(proc.stdout)
    payload["passed"] = bool(payload.get("all_passed"))
    return payload


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="hati-os-api-band-suite."))
    universal_bin, table_paths = emit_universal_runner(work)
    cases = [run_case(universal_bin, table_paths[case.name], case) for case in CASES]
    mutation = run_mutation_harness()
    unexpected_failures = [case for case in cases if not case["passed"]]
    payload = {
        "workdir": str(work),
        "universal_bin": str(universal_bin),
        "cases": cases,
        "full_parity_cases": sum(1 for case in cases if case.get("status") == "full_parity"),
        "expected_blocked_cases": sum(1 for case in cases if case.get("status") == "expected_blocked"),
        "unexpected_failures": unexpected_failures,
        "all_band_cases_passed": all(case["passed"] for case in cases),
        "mutation_harness": mutation,
        "all_passed": all(case["passed"] for case in cases) and bool(mutation.get("passed")),
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
