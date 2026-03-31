#!/usr/bin/env python3
# spec: 181-full-code-traceability
# idea: full-code-traceability
"""Phase 1.2 — Backfill idea_id on DB spec rows via fuzzy title matching.

Queries all specs rows in PostgreSQL where idea_id IS NULL.
Cross-references spec title/content against idea names and slugs via fuzzy match.
Updates idea_id on matched rows (confidence >= min_confidence, default 0.85).

Output: audit log at data/backfill_db_audit.csv

Usage:
    python3 scripts/backfill_db_spec_idea_ids.py --dry-run
    python3 scripts/backfill_db_spec_idea_ids.py --apply --min-confidence 0.85
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

# Add api to path for DB access
sys.path.insert(0, str(REPO_ROOT / "api"))


def _normalize(text: str) -> set[str]:
    """Normalize text into a bag of lowercase words (>=4 chars)."""
    stopwords = {
        "this", "that", "with", "from", "into", "which", "should", "would",
        "could", "each", "every", "when", "then", "than", "more", "also",
        "need", "ideas", "spec", "idea", "endpoint", "returns", "status",
        "response", "test", "file", "data", "will", "must", "have", "been",
        "does", "make", "like", "only", "used", "using", "based", "adds",
        "provides", "allow", "allows", "ensure", "ensures",
    }
    return set(re.findall(r"[a-z]{4,}", text.lower())) - stopwords


def fuzzy_match_spec_to_idea(
    spec_title: str,
    ideas: list[dict],
    min_score: float = 0.85,
) -> tuple[str | None, float]:
    """Match spec title to idea by keyword overlap.

    Returns (idea_id, score) or (None, 0.0).
    """
    spec_words = _normalize(spec_title)
    if not spec_words:
        return None, 0.0

    best_id = None
    best_score = 0.0

    for idea in ideas:
        idea_text = idea.get("name", "") + " " + idea.get("description", "")
        idea_words = _normalize(idea_text)
        if not idea_words:
            continue
        overlap = len(spec_words & idea_words)
        if overlap == 0:
            continue
        # Jaccard similarity
        union = len(spec_words | idea_words)
        score = overlap / union if union else 0.0
        if score > best_score:
            best_score = score
            best_id = idea.get("id") or idea.get("slug") or idea.get("name")

    if best_score >= min_score and best_id:
        return str(best_id), round(best_score, 3)
    return None, 0.0


def load_ideas_from_api(api_url: str) -> list[dict]:
    """Load ideas via the Coherence API."""
    try:
        import httpx
        resp = httpx.get(f"{api_url}/api/ideas?limit=500", timeout=15.0)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("ideas", data) if isinstance(data, dict) else data
    except Exception as exc:
        print(f"Warning: Could not load ideas from API: {exc}")
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill idea_id on DB spec rows")
    parser.add_argument("--apply", action="store_true", help="Write updates to DB")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes (default)")
    parser.add_argument("--min-confidence", type=float, default=0.85,
                        help="Minimum match score to auto-update (default: 0.85)")
    parser.add_argument("--api", default=os.environ.get("COHERENCE_API_URL", "https://api.coherencycoin.com"),
                        help="API base URL")
    args = parser.parse_args()

    apply = args.apply and not args.dry_run

    DATA_DIR.mkdir(exist_ok=True)
    audit_path = DATA_DIR / "backfill_db_audit.csv"

    # Load ideas
    print(f"Loading ideas from {args.api}...")
    ideas = load_ideas_from_api(args.api)
    print(f"  {len(ideas)} ideas loaded")

    if not ideas:
        print("No ideas found — cannot match. Exiting.")
        return 1

    # Try to connect to DB
    try:
        import psycopg2  # type: ignore[import]
        from urllib.parse import urlparse

        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://coherence:coherence@localhost:5432/coherence",
        )
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
    except Exception as exc:
        print(f"Warning: DB connection failed ({exc}). Running in report-only mode.")
        conn = None
        cursor = None

    # Fetch specs without idea_id
    specs = []
    if cursor:
        try:
            cursor.execute("SELECT id, title FROM specs WHERE idea_id IS NULL OR idea_id = ''")
            specs = [{"id": row[0], "title": row[1]} for row in cursor.fetchall()]
        except Exception as exc:
            print(f"Warning: Could not query specs table: {exc}")

    print(f"\nSpecs without idea_id: {len(specs)}")

    rows = []
    updated = 0
    needs_review = 0

    for spec in specs:
        spec_id = spec["id"]
        title = spec.get("title") or ""
        idea_id, score = fuzzy_match_spec_to_idea(title, ideas, args.min_confidence)

        if idea_id:
            action = "needs_review"
            if apply and cursor:
                try:
                    cursor.execute(
                        "UPDATE specs SET idea_id = %s WHERE id = %s",
                        (idea_id, spec_id),
                    )
                    action = "updated"
                    updated += 1
                except Exception as exc:
                    action = f"error: {exc}"
            else:
                action = f"would_update:{idea_id}"
                updated += 1
        else:
            needs_review += 1
            action = "needs_review"

        rows.append({
            "spec_id": spec_id,
            "spec_title": title[:60],
            "matched_idea_id": idea_id or "",
            "match_score": score,
            "action": action,
        })

    if apply and cursor:
        try:
            conn.commit()  # type: ignore[union-attr]
        except Exception as exc:
            print(f"Commit failed: {exc}")
        finally:
            cursor.close()
            conn.close()  # type: ignore[union-attr]

    # Write audit log
    with open(audit_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["spec_id", "spec_title", "matched_idea_id", "match_score", "action"]
        )
        writer.writeheader()
        writer.writerows(rows)

    total = len(specs)
    print(f"\n=== DB Spec idea_id Backfill ===")
    print(f"Total specs without idea_id: {total}")
    print(f"Matched (score >= {args.min_confidence}): {updated}")
    print(f"Needs review:                {needs_review}")
    print(f"Audit log:                   {audit_path}")

    if not apply:
        print("\nDry run. Use --apply to write changes to DB.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
