#!/usr/bin/env python3
"""Audit BML/BMF-specific host-native surfaces in sibling kernels.

The clean BML/BMF architecture keeps language semantics in BML/Form source.
This guard makes existing compatibility shims explicit and fails when new
`bml_` or `bmf_` natives enter a host kernel without updating the boundary.
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

ALLOWED_LANGUAGE_NATIVES = {
    "bml_scan_file": {
        "classification": "compatibility_scanner",
        "migration": "Replace with BML/Form lexicon-driven scanner or generic scan_with_lexicon.",
    },
    "bmf_apply_rule_native": {
        "classification": "deprecated_bmf_semantic_fast_path",
        "migration": "Replace with BML/Form compiled BMF automaton over generic VM/cursor steps.",
    },
}


def native_names(path: Path) -> list[str]:
    text = path.read_text()
    names: list[str] = []
    for pattern in REGISTER_PATTERNS:
        names.extend(pattern.findall(text))
    return sorted(set(names))


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
    unexpected = {
        kernel: [native for native in names if native not in ALLOWED_LANGUAGE_NATIVES]
        for kernel, names in by_kernel.items()
    }
    missing = {
        kernel: [native for native in expected if native not in names]
        for kernel, names in by_kernel.items()
    }

    report = {
        "status": "pass",
        "allowed_language_natives": ALLOWED_LANGUAGE_NATIVES,
        "by_kernel": by_kernel,
        "unexpected": unexpected,
        "missing": missing,
    }

    if any(unexpected.values()) or any(missing.values()):
        report["status"] = "fail"

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
