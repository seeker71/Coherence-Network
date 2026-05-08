#!/usr/bin/env python3
"""Build compact cryptographic trace roots for field source bodies and artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FIELD_DIR = Path("docs/field/urs")
ANALYSIS_ROOT = Path("/Users/ursmuff/CoherenceFieldAnalysis")
DOWNLOADS_DIR = Path("/Users/ursmuff/Downloads")
HASH_ALGORITHM = "sha256"


SOURCE_PATTERNS = [
    ("youtube-takeout", ANALYSIS_ROOT / "input" / "youtube", ["*.zip", "*.html", "*.json", "*.jsonl"]),
    ("audible-export", ANALYSIS_ROOT / "input" / "audible", ["*.json", "*.jsonl", "*.csv", "*.html"]),
    ("browser-trace", ANALYSIS_ROOT / "input" / "browser", ["*.json", "*.jsonl", "*.sqlite", "*.db"]),
    ("downloaded-takeout", DOWNLOADS_DIR, ["takeout-*.zip"]),
    ("photo-archive", DOWNLOADS_DIR, ["Photos-*.zip"]),
    ("project-archive", DOWNLOADS_DIR, ["Water Project.zip", "Angelic-*.zip"]),
]

REPO_ARTIFACTS = [
    "output/ten_year_events.jsonl",
    "trace/manifest.json",
    "trace/monthly_spectrum.json",
    "trace/author_index.jsonl",
    "trace/work_index.jsonl",
    "trace/significant_work_index.jsonl",
    "trace/concept_work_map.json",
    "trace/youtube_podcast_spectrum.json",
    "trace/digital_influence_inventory.json",
    "output/chronological_story_with_frequency.md",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def merkle_root(hex_hashes: list[str]) -> str | None:
    if not hex_hashes:
        return None
    level = [bytes.fromhex(item) for item in hex_hashes]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        next_level = []
        for index in range(0, len(level), 2):
            next_level.append(hashlib.sha256(b"node:" + level[index] + level[index + 1]).digest())
        level = next_level
    return level[0].hex()


def stable_json_hash(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(b"json:" + data)


def source_id(label: str, path: Path, digest: str) -> str:
    stem = path.name.lower().replace(" ", "-")
    return f"source:{label}:{stem}:{digest[:12]}"


def summarize_zip(path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            return {
                "zip_entries": len(names),
                "sample_entries": names[:8],
            }
    except zipfile.BadZipFile:
        return {}


def collect_source_bodies() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for label, root, patterns in SOURCE_PATTERNS:
        if not root.exists():
            continue
        for pattern in patterns:
            for path in sorted(root.glob(pattern)):
                if not path.is_file() or path in seen:
                    continue
                seen.add(path)
                digest = sha256_file(path)
                stat = path.stat()
                row = {
                    "id": source_id(label, path, digest),
                    "label": label,
                    "path": str(path),
                    "path_class": "local_source_body",
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                    "sha256": digest,
                    "content_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                }
                if path.suffix.lower() == ".zip":
                    row.update(summarize_zip(path))
                rows.append(row)
    return rows


def line_hashes(path: Path) -> tuple[list[str], Counter[str], Counter[str]]:
    hashes: list[str] = []
    source_counts: Counter[str] = Counter()
    evidence_counts: Counter[str] = Counter()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                canonical = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                source_counts[str(row.get("source") or "unknown")] += 1
                evidence_counts[str(row.get("evidence_level") or "unknown")] += 1
            except json.JSONDecodeError:
                canonical = line.rstrip("\n")
            hashes.append(sha256_bytes(b"event:" + canonical.encode("utf-8")))
    return hashes, source_counts, evidence_counts


def normalized_event_trace(field_dir: Path) -> dict[str, Any]:
    path = field_dir / "output" / "ten_year_events.jsonl"
    hashes, source_counts, evidence_counts = line_hashes(path)
    return {
        "path": str(path),
        "line_count": len(hashes),
        "file_sha256": sha256_file(path),
        "event_leaf_hash_algorithm": "sha256('event:' + canonical_json(row))",
        "event_merkle_root": merkle_root(hashes),
        "first_event_hash": hashes[0] if hashes else None,
        "last_event_hash": hashes[-1] if hashes else None,
        "source_counts": dict(source_counts.most_common()),
        "evidence_level_counts": dict(evidence_counts.most_common()),
    }


def repo_artifact_trace(field_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for rel in REPO_ARTIFACTS:
        path = field_dir / rel
        if not path.exists():
            continue
        stat = path.stat()
        rows.append(
            {
                "path": str(path),
                "artifact_relpath": rel,
                "size_bytes": stat.st_size,
                "sha256": sha256_file(path),
                "content_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            }
        )
    return rows


def build(field_dir: Path) -> dict[str, Any]:
    sources = collect_source_bodies()
    events = normalized_event_trace(field_dir)
    artifacts = repo_artifact_trace(field_dir)
    source_root = merkle_root([stable_json_hash(row) for row in sources])
    artifact_root = merkle_root([stable_json_hash(row) for row in artifacts])
    combined_root = merkle_root(
        [
            stable_json_hash({"kind": "source_bodies", "root": source_root}),
            stable_json_hash({"kind": "normalized_events", "root": events["event_merkle_root"]}),
            stable_json_hash({"kind": "repo_artifacts", "root": artifact_root}),
        ]
    )
    return {
        "schema_version": "field-source-crypto-trace/v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "hash_algorithm": HASH_ALGORITHM,
        "publication_boundary": "This is a compact cryptographic trace. It publishes hashes, sizes, source classes, and Merkle roots; bulky raw source bodies remain outside the repo unless deliberately promoted.",
        "roots": {
            "source_body_merkle_root": source_root,
            "normalized_event_merkle_root": events["event_merkle_root"],
            "repo_artifact_merkle_root": artifact_root,
            "combined_trace_root": combined_root,
        },
        "source_bodies": sources,
        "normalized_event_trace": events,
        "repo_artifacts": artifacts,
        "dynamic_access": {
            "artifact_api": "/api/field-stories/urs-field-story/artifacts/trace-source-crypto",
            "month_trace_api": "/api/field-stories/urs-field-story/trace/month/{YYYY-MM}",
            "author_trace_api": "/api/field-stories/urs-field-story/trace/author/{name_or_id}",
            "work_trace_api": "/api/field-stories/urs-field-story/trace/work/{work_id}",
            "mcp_tool": "get_field_story_trace",
        },
        "truth_boundary": {
            "exact_now": "Source bodies, normalized event file, and repo-served trace artifacts have SHA-256 hashes and Merkle roots.",
            "next_precision": "For exact row-to-source-body proofs in every API slice, normalized rows should gain source_body_id and event_hash fields during ingestion.",
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build field source crypto trace manifest.")
    parser.add_argument("--field-dir", type=Path, default=FIELD_DIR)
    args = parser.parse_args()
    payload = build(args.field_dir)
    out = args.field_dir / "trace" / "source_crypto_trace.json"
    write_json(out, payload)
    print(f"source_bodies={len(payload['source_bodies'])}")
    print(f"normalized_events={payload['normalized_event_trace']['line_count']}")
    print(f"combined_trace_root={payload['roots']['combined_trace_root']}")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
