#!/usr/bin/env python3
"""Structural diff between two .fkb artifacts with artifact-local id remapping.

The proof loop named in `specs/form-binary-to-native-python-emitter.md`
compares a `source.fkb` against a `roundtrip.fkb` produced by the
emitted Python compiler. Raw NodeIDs differ between artifacts because
each binary has its own local instance counter — equality has to be
structural after id remapping.

Difference classes the report names (every other difference fails the
proof):

  - artifact-local-id-remap
  - symbol-lens-choice
  - source-span-normalization
  - formatting-comment-loss
  - helper-allocation
  - stable-order-normalization

Usage:

    python3 form/scripts/diff_form_artifacts.py source.fkb roundtrip.fkb --explain
    python3 form/scripts/diff_form_artifacts.py a.fkb b.fkb --json diff.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from kernels.python_bmf.sdk import NodeID, read_fkb  # noqa: E402


ACCEPTED_CLASSES = (
    "artifact-local-id-remap",
    "symbol-lens-choice",
    "source-span-normalization",
    "formatting-comment-loss",
    "helper-allocation",
    "stable-order-normalization",
)


def _structural_hash(node: dict, by_id: dict[str, dict], memo: dict[str, str]) -> str:
    nid = str(node["nodeid"])
    if nid in memo:
        return memo[nid]
    child_hashes = []
    for c in node.get("children", []):
        c_node = by_id.get(str(c))
        if c_node is None:
            child_hashes.append(f"missing:{c}")
        else:
            child_hashes.append(_structural_hash(c_node, by_id, memo))
    payload = {
        "kind": node.get("kind"),
        "value": node.get("value"),
        "children": child_hashes,
    }
    h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    memo[nid] = h
    return h


def _index(nodes: list[dict]) -> dict[str, dict]:
    return {str(n["nodeid"]): n for n in nodes}


def diff_artifacts(source_path: str, target_path: str) -> dict:
    source_nodes = read_fkb(source_path)
    target_nodes = read_fkb(target_path)
    src_by_id = _index(source_nodes)
    tgt_by_id = _index(target_nodes)

    src_hashes: dict[str, str] = {}
    tgt_hashes: dict[str, str] = {}
    src_memo: dict[str, str] = {}
    tgt_memo: dict[str, str] = {}
    for n in source_nodes:
        src_hashes[str(n["nodeid"])] = _structural_hash(n, src_by_id, src_memo)
    for n in target_nodes:
        tgt_hashes[str(n["nodeid"])] = _structural_hash(n, tgt_by_id, tgt_memo)

    src_hash_set = set(src_hashes.values())
    tgt_hash_set = set(tgt_hashes.values())

    # Id-remap class: same structural hash on both sides, different NodeID.
    remapped = []
    src_hash_to_id: dict[str, list[str]] = {}
    for nid, h in src_hashes.items():
        src_hash_to_id.setdefault(h, []).append(nid)
    for tgt_nid, h in tgt_hashes.items():
        if h in src_hash_to_id:
            for src_nid in src_hash_to_id[h]:
                if src_nid != tgt_nid:
                    remapped.append({"source": src_nid, "target": tgt_nid, "hash": h})

    only_source_hashes = sorted(src_hash_set - tgt_hash_set)
    only_target_hashes = sorted(tgt_hash_set - src_hash_set)
    only_source = [
        {"nodeid": nid, "kind": src_by_id[nid]["kind"], "value": src_by_id[nid]["value"]}
        for h in only_source_hashes
        for nid in src_hash_to_id.get(h, [])[:1]
    ]
    tgt_hash_to_id: dict[str, list[str]] = {}
    for nid, h in tgt_hashes.items():
        tgt_hash_to_id.setdefault(h, []).append(nid)
    only_target = [
        {"nodeid": nid, "kind": tgt_by_id[nid]["kind"], "value": tgt_by_id[nid]["value"]}
        for h in only_target_hashes
        for nid in tgt_hash_to_id.get(h, [])[:1]
    ]

    return {
        "source": source_path,
        "target": target_path,
        "source_node_count": len(source_nodes),
        "target_node_count": len(target_nodes),
        "remapped": remapped,
        "only_source": only_source,
        "only_target": only_target,
        "classes": {
            "artifact-local-id-remap": len(remapped),
            "structural-mismatch-source-only": len(only_source),
            "structural-mismatch-target-only": len(only_target),
        },
    }


def _explain(report: dict) -> str:
    lines = []
    lines.append(f"source: {report['source']} ({report['source_node_count']} nodes)")
    lines.append(f"target: {report['target']} ({report['target_node_count']} nodes)")
    lines.append("")
    lines.append("Difference class counts:")
    for k, v in report["classes"].items():
        accepted = k in ACCEPTED_CLASSES
        marker = "ok" if accepted else ("zero" if v == 0 else "FAIL")
        lines.append(f"  {marker:>4}  {k}: {v}")
    lines.append("")
    if report["remapped"]:
        lines.append(f"Artifact-local id remaps (showing first 5 of {len(report['remapped'])}):")
        for r in report["remapped"][:5]:
            lines.append(f"  {r['source']}  ↔  {r['target']}")
        lines.append("")
    if report["only_source"]:
        lines.append(f"Source-only structures (first 5 of {len(report['only_source'])}):")
        for n in report["only_source"][:5]:
            lines.append(f"  {n['nodeid']}  {n['kind']}  {json.dumps(n['value'])[:80]}")
        lines.append("")
    if report["only_target"]:
        lines.append(f"Target-only structures (first 5 of {len(report['only_target'])}):")
        for n in report["only_target"][:5]:
            lines.append(f"  {n['nodeid']}  {n['kind']}  {json.dumps(n['value'])[:80]}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Structural diff between two .fkb artifacts")
    p.add_argument("source", help="source .fkb path")
    p.add_argument("target", help="target .fkb path")
    p.add_argument("--explain", action="store_true", help="print human-readable report")
    p.add_argument("--json", help="write machine-readable JSON report to path")
    args = p.parse_args(argv)
    report = diff_artifacts(args.source, args.target)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, indent=2, sort_keys=True))
    if args.explain or not args.json:
        print(_explain(report))
    # Exit 0 if only accepted classes are non-zero; 1 otherwise.
    unexplained = report["classes"]["structural-mismatch-source-only"] + report["classes"][
        "structural-mismatch-target-only"
    ]
    return 0 if unexplained == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
