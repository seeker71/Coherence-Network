#!/usr/bin/env python3
"""Emit a bounded code-tool-learning coding-act receipt for a committed turn."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path


def run_git(root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def language_for(path: str) -> tuple[str, str]:
    suffix = Path(path).suffix
    if suffix in {".fk", ".form", ".bml"}:
        return ("Form", "form/BML")
    if suffix == ".py":
        return ("Python", "python-bmf")
    if suffix in {".ts", ".tsx"}:
        return ("TypeScript", "typescript-bmf")
    if suffix == ".rs":
        return ("Rust", "rust-bmf")
    if suffix == ".go":
        return ("Go", "go-bmf")
    if suffix in {".md", ".txt"}:
        return ("Document", "document-bmf")
    if suffix in {".json", ".jsonl"}:
        return ("JSON", "json-codec")
    return ("Unknown", "generic-source")


def source_surface(root: Path, path: str) -> dict[str, object]:
    file_path = root / path
    if file_path.exists() and file_path.is_file():
        content = file_path.read_bytes()
        source_sig = sha256_bytes(content)
        byte_count = len(content)
    else:
        source_sig = "deleted"
        byte_count = 0
    language, grammar = language_for(path)
    node_sig = sha256_text(f"{path}:{source_sig}")
    return {
        "kind": "source-code" if language != "Document" else "document-source",
        "language": language,
        "path": path,
        "source_sig": source_sig,
        "node_sig": node_sig,
        "grammar": grammar,
        "byte_count": byte_count,
    }


def run_verifier(root: Path, spec: str) -> dict[str, object]:
    if "::" not in spec:
        raise SystemExit(f"verifier must be NAME::COMMAND, got: {spec}")
    name, command = spec.split("::", 1)
    start = time.monotonic()
    result = subprocess.run(
        command,
        cwd=root,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    duration_ms = max(1, int((time.monotonic() - start) * 1000))
    output = result.stdout + result.stderr
    return {
        "name": name.strip(),
        "status": "pass" if result.returncode == 0 else "fail",
        "exit_code": result.returncode,
        "duration_ms": duration_ms,
        "evidence_sig": sha256_text(output),
        "raw_output_retained": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", default="HEAD", help="commit to describe")
    parser.add_argument("--out", default="", help="receipt path; defaults under .cache")
    parser.add_argument(
        "--verify",
        action="append",
        default=[],
        metavar="NAME::COMMAND",
        help="run a verifier command and hash its output into the receipt",
    )
    parser.add_argument("--lane", default="form-native:code-tool")
    parser.add_argument("--trust-before", type=int, default=62)
    parser.add_argument("--trust-after", type=int, default=74)
    args = parser.parse_args()

    root = Path(run_git(Path.cwd(), ["rev-parse", "--show-toplevel"]).strip())
    commit = run_git(root, ["rev-parse", args.commit]).strip()
    parent = run_git(root, ["rev-parse", f"{commit}^"]).strip()
    subject = run_git(root, ["show", "-s", "--format=%s", commit]).strip()
    patch = run_git(root, ["diff", "--no-ext-diff", parent, commit])
    files = [
        line
        for line in run_git(root, ["diff", "--name-only", parent, commit]).splitlines()
        if line
    ]
    verifiers = [run_verifier(root, spec) for spec in args.verify]
    verifier_status = "pass" if verifiers and all(v["status"] == "pass" for v in verifiers) else "blocked"
    learned_delta = {
        "lane": args.lane,
        "sample_count": 1 if verifier_status == "pass" else 0,
        "trust_before": args.trust_before,
        "trust_after": args.trust_after,
        "accepted": 1 if verifier_status == "pass" and args.trust_after > args.trust_before else 0,
    }
    receipt = {
        "kind": "code-tool-learning/coding-act-receipt",
        "schema_version": 1,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit,
        "parent": parent,
        "intent": subject,
        "source_surfaces": [source_surface(root, path) for path in files],
        "patch_recipe": {
            "intent": subject,
            "dialect": "git-patch",
            "patch_sig": sha256_text(patch),
            "files_touched": len(files),
            "reversible": 1,
            "raw_patch_retained": 0,
        },
        "verifiers": verifiers,
        "choice_receipt": {
            "selected_path": args.lane,
            "outcome": "success" if verifier_status == "pass" else "fail",
            "token_cost": 0,
            "certainty": 78,
            "sovereignty": 91,
            "trust": args.trust_after if learned_delta["accepted"] else args.trust_before,
        },
        "learned_delta": learned_delta,
        "status": "pass" if learned_delta["accepted"] else "blocked",
    }

    if args.out:
        out_path = Path(args.out)
    else:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        out_path = root / ".cache" / "code-tool-learning" / stamp / "coding-act-receipt.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest = root / ".cache" / "code-tool-learning" / "latest.json"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "PASS code-tool-learning-receipt "
        f"status={receipt['status']} commit={commit[:12]} files={len(files)} "
        f"verifiers={len(verifiers)} trust={learned_delta['trust_before']}->{learned_delta['trust_after']} "
        f"cache={out_path}"
    )
    return 0 if receipt["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
