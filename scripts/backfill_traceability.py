#!/usr/bin/env python3
"""Backfill traceability links: spec→idea, code→spec, PR→spec.

Scans the codebase and automatically discovers relationships:
1. Spec files → idea IDs (from frontmatter, content, and name matching)
2. Code files → spec IDs (from comments, docstrings, and file headers)
3. Builds value_lineage_links connecting idea → spec → implementation

Usage:
    python3 scripts/backfill_traceability.py                # dry-run (report only)
    python3 scripts/backfill_traceability.py --apply         # apply changes via API
    python3 scripts/backfill_traceability.py --apply --api https://api.coherencycoin.com
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = REPO_ROOT / "specs"
API_DIR = REPO_ROOT / "api" / "app"
API_BASE = os.environ.get("COHERENCE_API_URL", "https://api.coherencycoin.com")
API_KEY = os.environ.get("COHERENCE_API_KEY", "dev-key")

_client = httpx.Client(timeout=15.0)


def api(method: str, path: str, body: dict | None = None) -> dict | list | None:
    headers = {"X-API-Key": API_KEY}
    url = f"{API_BASE}{path}"
    try:
        if method == "GET":
            resp = _client.get(url)
        elif method == "POST":
            resp = _client.post(url, json=body, headers=headers)
        elif method == "PATCH":
            resp = _client.patch(url, json=body, headers=headers)
        else:
            return None
        if resp.status_code >= 400:
            return None
        return resp.json() if resp.text.strip() else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Phase 1a: Spec files → idea IDs
# ---------------------------------------------------------------------------

def _extract_spec_number(filename: str) -> str | None:
    """Extract spec number from filename like '122-crypto-treasury-bridge.md'."""
    m = re.match(r"(\d+)-", filename)
    return m.group(1) if m else None


def _extract_idea_refs_from_spec(content: str) -> list[str]:
    """Find idea IDs referenced in spec content."""
    # Pattern: idea_id: xxx, idea-id: xxx, parent_idea: xxx
    refs = set()
    for pattern in [
        r"idea[_-]id:\s*[\"']?(\S+?)[\"']?\s",
        r"parent_idea[_-]id:\s*[\"']?(\S+?)[\"']?\s",
        r"Idea:\s*(\S+)",
        r"idea `([a-z0-9-]+)`",
    ]:
        for m in re.finditer(pattern, content, re.IGNORECASE):
            ref = m.group(1).strip().rstrip(",;)\"'")
            noise = {"None", "null", "N/A", "string", "string|null", "properties:", "tracked:", "added_properties:", "type", "object", "array"}
            if len(ref) > 3 and ref not in noise and not ref.startswith("http"):
                refs.add(ref)
    return list(refs)


def _match_spec_to_idea_by_content(spec_content: str, ideas: list[dict], min_score: float = 0.3) -> tuple[str | None, float]:
    """Match a spec to an idea by keyword overlap on full content.

    Returns (idea_id, score) or (None, 0.0).
    """
    stopwords = {"this", "that", "with", "from", "into", "which", "should", "would",
                 "could", "each", "every", "when", "then", "than", "more", "also",
                 "need", "ideas", "spec", "idea", "endpoint", "returns", "status",
                 "response", "test", "file", "data", "will", "must", "have", "been",
                 "does", "make", "like", "only", "used", "using", "based"}
    spec_words = set(re.findall(r"[a-z]{4,}", spec_content[:3000].lower())) - stopwords

    best_match = None
    best_score = 0.0
    for idea in ideas:
        idea_text = (idea.get("name", "") + " " + idea.get("description", "")).lower()
        idea_words = set(re.findall(r"[a-z]{4,}", idea_text)) - stopwords
        overlap = len(spec_words & idea_words)
        score = overlap / max(len(idea_words), 1) if overlap >= 5 else 0.0
        if score > best_score:
            best_score = score
            best_match = idea.get("id")

    if best_score >= min_score and best_match:
        return best_match, best_score
    return None, 0.0


def scan_specs(ideas: list[dict]) -> list[dict]:
    """Scan all spec files and find idea links."""
    results = []
    for spec_file in sorted(SPECS_DIR.glob("*.md")):
        if spec_file.name == "TEMPLATE.md":
            continue
        content = spec_file.read_text(errors="replace")
        spec_num = _extract_spec_number(spec_file.name)
        spec_id = spec_file.stem

        # Extract title from first heading
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else spec_id

        # Try explicit idea references first
        idea_refs = _extract_idea_refs_from_spec(content)
        method = "explicit" if idea_refs else "none"
        match_score = 1.0 if idea_refs else 0.0

        # Fall back to content-based matching
        if not idea_refs:
            matched, score = _match_spec_to_idea_by_content(content, ideas)
            if matched:
                idea_refs = [matched]
                method = "content_match"
                match_score = score

        results.append({
            "spec_file": spec_file.name,
            "spec_id": spec_id,
            "spec_num": spec_num,
            "title": title[:60],
            "idea_refs": idea_refs,
            "method": method,
            "match_score": match_score,
        })
    return results


# ---------------------------------------------------------------------------
# Phase 1b: Code files → spec IDs
# ---------------------------------------------------------------------------

def _extract_spec_refs_from_code(content: str) -> list[str]:
    """Find spec references in code file content."""
    refs = set()
    for pattern in [
        r"[Ss]pec\s+(\d{2,3})",           # "Spec 122", "spec 053"
        r"spec[_-](\d{2,3})",              # "spec_122", "spec-053"
        r"specs/(\d+-[a-z-]+)",            # "specs/122-crypto-treasury"
        r"Implements:\s*spec[_-]?(\d+)",   # "Implements: spec-122"
    ]:
        for m in re.finditer(pattern, content):
            refs.add(m.group(1))
    return sorted(refs)


def scan_code() -> list[dict]:
    """Scan all Python files for spec references."""
    results = []
    for py_file in sorted(API_DIR.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        content = py_file.read_text(errors="replace")
        spec_refs = _extract_spec_refs_from_code(content)
        if spec_refs:
            rel_path = py_file.relative_to(REPO_ROOT)
            results.append({
                "file": str(rel_path),
                "spec_refs": spec_refs,
            })
    return results


# ---------------------------------------------------------------------------
# Report and apply
# ---------------------------------------------------------------------------

def main():
    global API_BASE
    parser = argparse.ArgumentParser(description="Backfill traceability links")
    parser.add_argument("--apply", action="store_true", help="Apply changes via API")
    parser.add_argument("--api", default=None, help="API base URL")
    args = parser.parse_args()

    if args.api:
        API_BASE = args.api

    # Load ideas from API
    print("Loading ideas from API...")
    all_ideas_data = api("GET", "/api/ideas?limit=300")
    if not all_ideas_data:
        print("ERROR: Could not load ideas from API")
        sys.exit(1)
    ideas = all_ideas_data.get("ideas", all_ideas_data) if isinstance(all_ideas_data, dict) else all_ideas_data
    print(f"  {len(ideas)} ideas loaded")

    # Phase 1a: Spec → Idea
    print("\n=== Phase 1a: Spec files → Idea IDs ===\n")
    spec_results = scan_specs(ideas)
    linked = [r for r in spec_results if r["idea_refs"]]
    unlinked = [r for r in spec_results if not r["idea_refs"]]

    print(f"Total spec files: {len(spec_results)}")
    print(f"  Linked to ideas: {len(linked)} ({len(linked)*100//max(len(spec_results),1)}%)")
    print(f"    Explicit refs: {sum(1 for r in linked if r['method'] == 'explicit')}")
    print(f"    Name matches:  {sum(1 for r in linked if r['method'] == 'name_match')}")
    print(f"  Unlinked:        {len(unlinked)}")

    if linked:
        print(f"\n  Linked specs:")
        for r in linked[:20]:
            print(f"    {r['spec_file'][:35]:37s} → {r['idea_refs'][0][:30]:32s} ({r['method']})")
        if len(linked) > 20:
            print(f"    ... and {len(linked)-20} more")

    if unlinked:
        print(f"\n  Unlinked specs (need manual linking):")
        for r in unlinked[:10]:
            print(f"    {r['spec_file'][:35]:37s} {r['title'][:40]}")
        if len(unlinked) > 10:
            print(f"    ... and {len(unlinked)-10} more")

    # Phase 1b: Code → Spec
    print("\n=== Phase 1b: Code files → Spec IDs ===\n")
    code_results = scan_code()
    total_code_files = sum(1 for _ in API_DIR.rglob("*.py") if "__pycache__" not in str(_))
    print(f"Total Python files: {total_code_files}")
    print(f"  With spec refs: {len(code_results)} ({len(code_results)*100//max(total_code_files,1)}%)")

    all_spec_refs = set()
    for r in code_results:
        all_spec_refs.update(r["spec_refs"])
    print(f"  Unique specs referenced: {len(all_spec_refs)}")

    for r in code_results[:15]:
        print(f"    {r['file'][:45]:47s} → spec {', '.join(r['spec_refs'][:3])}")
    if len(code_results) > 15:
        print(f"    ... and {len(code_results)-15} more")

    # Summary
    spec_coverage = len(linked) * 100 // max(len(spec_results), 1)
    code_coverage = len(code_results) * 100 // max(total_code_files, 1)
    print(f"\n=== Traceability Score ===")
    print(f"  Spec → Idea: {spec_coverage}% ({len(linked)}/{len(spec_results)})")
    print(f"  Code → Spec: {code_coverage}% ({len(code_results)}/{total_code_files})")
    print(f"  Overall:     {(spec_coverage + code_coverage) // 2}%")

    # Apply if requested
    if args.apply and linked:
        print(f"\n=== Applying {len(linked)} spec→idea links via API ===")
        applied = 0
        for r in linked:
            idea_id = r["idea_refs"][0]
            # Create a value lineage link: idea → spec
            result = api("POST", "/api/value-lineage/links", {
                "idea_id": idea_id,
                "spec_id": r["spec_id"],
                "implementation_refs": [],
                "contributors": {"spec_author": "seeker71"},
                "estimated_cost": 1.0,
            })
            if result and result.get("id"):
                applied += 1
                print(f"  ✓ {r['spec_id'][:25]} → {idea_id[:25]}")
            else:
                print(f"  ✗ {r['spec_id'][:25]} → {idea_id[:25]} (failed)")
        print(f"\nApplied: {applied}/{len(linked)}")
    elif not args.apply:
        print(f"\nDry run. Use --apply to create lineage links.")


if __name__ == "__main__":
    main()
