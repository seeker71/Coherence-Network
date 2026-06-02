#!/usr/bin/env python3
"""Audit BML/BMF-specific host-native surfaces in sibling kernels.

The clean BML/BMF architecture keeps language semantics in BML/Form source.
This guard makes the remaining compatibility shim explicit and fails when
language scanner semantics enter a host kernel instead of living in Form data.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

KERNELS = {
    "go": ROOT / "form/form-kernel-go/main.go",
    "rust": ROOT / "form/form-kernel-rust/src/main.rs",
    "typescript": ROOT / "form/form-kernel-ts/src/kernel.ts",
}

REGISTER_PATTERNS = [
    re.compile(r"\.registerNative\(\s*\"([^\"]+)\""),
    re.compile(r"\.register_native\(\s*\"([^\"]+)\""),
    re.compile(r"\bregisterNative\(\s*\"([^\"]+)\""),
    re.compile(r"\bregister_native\(\s*\"([^\"]+)\""),
]

ALLOWED_LANGUAGE_NATIVES: dict[str, dict[str, str]] = {}

REQUIRED_GENERIC_NATIVES = {"source_scan_file"}

FORBIDDEN_SCANNER_PATTERNS = [
    re.compile(r"BML_NATIVE_(KEYWORDS|PROPERTIES|OPS)"),
    re.compile(r"\bbmlNative(Keywords|Properties|Ops)\b"),
    re.compile(r"\bbml_native_(keyword|property|name_kind)\b"),
    re.compile(r"\bregisterNative\(\s*\"bml_scan_file\""),
    re.compile(r"\bregister_native\(\s*\"bml_scan_file\""),
    re.compile(r"\bregisterNative\(\s*\"bmf_apply_rule_native\""),
    re.compile(r"\bregister_native\(\s*\"bmf_apply_rule_native\""),
]


def native_names(path: Path) -> list[str]:
    text = path.read_text()
    names: list[str] = []
    for pattern in REGISTER_PATTERNS:
        names.extend(pattern.findall(text))
    return sorted(set(names))


def forbidden_scanner_hits(path: Path) -> list[str]:
    text = path.read_text()
    hits: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in FORBIDDEN_SCANNER_PATTERNS:
            if pattern.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")
                break
    return hits


def main() -> int:
    by_kernel: dict[str, list[str]] = {}
    for name, path in KERNELS.items():
        names = native_names(path)
        by_kernel[name] = [
            native
            for native in names
            if native.startswith("bml_") or native.startswith("bmf_")
        ]

    expected = sorted(ALLOWED_LANGUAGE_NATIVES)
    all_natives = {kernel: native_names(path) for kernel, path in KERNELS.items()}
    unexpected = {
        kernel: [native for native in names if native not in ALLOWED_LANGUAGE_NATIVES]
        for kernel, names in by_kernel.items()
    }
    missing = {
        kernel: [native for native in expected if native not in names]
        for kernel, names in by_kernel.items()
    }
    missing_generic = {
        kernel: [native for native in sorted(REQUIRED_GENERIC_NATIVES) if native not in names]
        for kernel, names in all_natives.items()
    }
    forbidden_scanner_semantics = {
        kernel: forbidden_scanner_hits(path)
        for kernel, path in KERNELS.items()
    }

    report = {
        "status": "pass",
        "allowed_language_natives": ALLOWED_LANGUAGE_NATIVES,
        "required_generic_natives": sorted(REQUIRED_GENERIC_NATIVES),
        "by_kernel": by_kernel,
        "unexpected": unexpected,
        "missing": missing,
        "missing_generic": missing_generic,
        "forbidden_scanner_semantics": forbidden_scanner_semantics,
    }

    if (
        any(unexpected.values())
        or any(missing.values())
        or any(missing_generic.values())
        or any(forbidden_scanner_semantics.values())
    ):
        report["status"] = "fail"

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
