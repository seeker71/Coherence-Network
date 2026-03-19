#!/usr/bin/env python3
"""Seed data/coherence.db from spec markdown files, commit evidence JSON, and seed_ideas.json.

Populates the unified DB with content hashes so the DB and files stay in sync.
Idempotent — safe to run multiple times.

Usage:
    python3 scripts/seed_db.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.services import unified_db  # noqa: E402
from app.services import spec_registry_service  # noqa: E402
from app.services import commit_evidence_service  # noqa: E402
from app.services import idea_registry_service  # noqa: E402
from app.services import idea_service  # noqa: E402


def sha256_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _parse_spec_file(path: Path) -> dict | None:
    """Extract spec_id, title, and summary from a spec markdown file."""
    name = path.stem  # e.g. "001-health-check"
    match = re.match(r"^(\d+)-(.+)$", name)
    if not match:
        return None
    spec_id = match.group(1)
    content = path.read_text(encoding="utf-8")
    content_bytes = path.read_bytes()

    # Title: first # heading
    title = name.replace("-", " ").title()
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            break

    # Summary: first non-empty, non-heading paragraph
    summary = title
    lines = content.splitlines()
    in_paragraph = False
    para_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_paragraph and para_lines:
                break
            continue
        if stripped.startswith("#"):
            if in_paragraph and para_lines:
                break
            continue
        in_paragraph = True
        para_lines.append(stripped)
    if para_lines:
        summary = " ".join(para_lines)[:500]

    return {
        "spec_id": spec_id,
        "title": title,
        "summary": summary,
        "content_path": f"specs/{path.name}",
        "content_hash": sha256_of(content_bytes),
    }


def seed_specs() -> int:
    """Seed spec registry from specs/*.md files."""
    specs_dir = ROOT / "specs"
    if not specs_dir.exists():
        print("  No specs/ directory found")
        return 0

    from app.models.spec_registry import SpecRegistryCreate, SpecRegistryUpdate

    count = 0
    for path in sorted(specs_dir.glob("*.md")):
        parsed = _parse_spec_file(path)
        if not parsed:
            continue

        existing = spec_registry_service.get_spec(parsed["spec_id"])
        if existing is None:
            spec_registry_service.create_spec(SpecRegistryCreate(
                spec_id=parsed["spec_id"],
                title=parsed["title"],
                summary=parsed["summary"],
                content_path=parsed["content_path"],
                content_hash=parsed["content_hash"],
            ))
        else:
            spec_registry_service.update_spec(parsed["spec_id"], SpecRegistryUpdate(
                content_path=parsed["content_path"],
                content_hash=parsed["content_hash"],
            ))
        count += 1

    return count


def seed_evidence() -> int:
    """Seed commit evidence from docs/system_audit/commit_evidence_*.json."""
    evidence_dir = ROOT / "docs" / "system_audit"
    if not evidence_dir.exists():
        print("  No docs/system_audit/ directory found")
        return 0

    count = 0
    for path in sorted(evidence_dir.glob("commit_evidence_*.json")):
        try:
            content_bytes = path.read_bytes()
            payload = json.loads(content_bytes)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  SKIP {path.name}: {e}")
            continue
        if not isinstance(payload, dict):
            continue

        content_hash = sha256_of(content_bytes)
        commit_evidence_service.upsert_record(
            payload,
            source_file=str(path.relative_to(ROOT)),
        )
        # Update content_hash on the record
        from app.services.unified_db import session
        from app.services.commit_evidence_service import CommitEvidenceRecord
        with session() as s:
            row = (
                s.query(CommitEvidenceRecord)
                .filter(CommitEvidenceRecord.source_file == str(path.relative_to(ROOT)))
                .first()
            )
            if row and getattr(row, "content_hash", None) != content_hash:
                row.content_hash = content_hash
                s.add(row)

        count += 1

    return count


def seed_ideas() -> int:
    """Seed ideas from data/seed_ideas.json via idea_service defaults."""
    # idea_service.list_ideas() triggers default idea creation
    result = idea_service.list_ideas()
    return len(result.ideas) if result else 0


def checkpoint_wal() -> None:
    """Fold WAL into the main DB file for a clean git commit."""
    eng = unified_db.engine()
    url = unified_db.database_url()
    if not url.startswith("sqlite"):
        return
    try:
        with eng.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    except Exception as e:
        print(f"  WAL checkpoint warning: {e}")


def main() -> None:
    # Ensure data/ directory exists
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"DB: {unified_db.database_url()}")
    unified_db.ensure_schema()

    print("Seeding specs...")
    spec_count = seed_specs()
    print(f"  {spec_count} specs seeded")

    print("Seeding commit evidence...")
    evidence_count = seed_evidence()
    print(f"  {evidence_count} evidence records seeded")

    print("Seeding ideas...")
    idea_count = seed_ideas()
    print(f"  {idea_count} ideas loaded")

    print("Checkpointing WAL...")
    checkpoint_wal()

    print("Done.")


if __name__ == "__main__":
    main()
