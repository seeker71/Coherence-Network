#!/usr/bin/env python3
"""Sync KB markdown files → Graph DB via API.

Reads concept files from docs/vision-kb/concepts/{id}.md, parses them
into structured properties, and PATCHes the graph node via the API.

This is the primary enrichment path: expand content in KB markdown,
then sync to DB. The ontology JSON is no longer the editing surface.

Usage:
    python scripts/sync_kb_to_db.py lc-space                    # sync one concept
    python scripts/sync_kb_to_db.py lc-space lc-nourishment     # sync multiple
    python scripts/sync_kb_to_db.py --all                       # sync all
    python scripts/sync_kb_to_db.py --all --min-status expanding # only expanding+
    python scripts/sync_kb_to_db.py lc-space --dry-run          # show what would change
    python scripts/sync_kb_to_db.py lc-space --api-url http://localhost:8000  # local API
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    import urllib.request
    httpx = None  # type: ignore

KB_DIR = Path(__file__).resolve().parent.parent / "docs" / "vision-kb" / "concepts"
DEFAULT_API = "https://api.coherencycoin.com"

STATUS_ORDER = {"seed": 0, "expanding": 1, "mature": 2, "complete": 3}


def parse_frontmatter(text: str) -> dict:
    """Extract YAML-like frontmatter between --- markers."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm


def parse_section(text: str, heading: str) -> str | None:
    """Extract content under a ## heading, stopping at the next ## or end."""
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        return None
    content = match.group(1).strip()
    return content if content else None


def parse_list_items(text: str) -> list[str]:
    """Parse markdown bullet list into strings."""
    items = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            items.append(line[2:].strip())
    return items


def parse_resource_items(text: str) -> list[dict]:
    """Parse resource entries like: 📐 [Name](url) — description (type: blueprint)"""
    resources = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Match: icon [Name](url) — description
        m = re.match(r"[^\[]*\[([^\]]+)\]\(([^)]+)\)\s*[—–-]\s*(.*)", line)
        if m:
            name, url, desc = m.group(1), m.group(2), m.group(3)
            # Try to extract type from end: (type: blueprint) or just (blueprint)
            rtype = "guide"
            tm = re.search(r"\((?:type:\s*)?(\w+)\)\s*$", desc)
            if tm:
                rtype = tm.group(1)
                desc = desc[:tm.start()].strip()
            resources.append({"name": name, "url": url, "type": rtype, "description": desc})
    return resources


def parse_materials(text: str) -> list[dict]:
    """Parse materials entries like: **Name** — description"""
    materials = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"\*\*([^*]+)\*\*\s*[—–-]\s*(.*)", line)
        if m:
            materials.append({"name": m.group(1), "description": m.group(2)})
        elif line.startswith("- ") or line.startswith("* "):
            # Simple bullet format: - Name — description
            inner = line[2:].strip()
            m2 = re.match(r"\*\*([^*]+)\*\*\s*[—–-]\s*(.*)", inner)
            if m2:
                materials.append({"name": m2.group(1), "description": m2.group(2)})
    return materials


def parse_scale_notes(text: str) -> dict:
    """Parse scale notes: **50 people**: ..., **100 people**: ..., **200 people**: ..."""
    notes = {}
    current_key = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        if "**50" in stripped or "50 people" in stripped.lower():
            if current_key:
                notes[current_key] = " ".join(current_lines).strip()
            current_key = "small"
            current_lines = [re.sub(r"^.*?:\s*", "", stripped.split("**")[-1]).strip()]
        elif "**100" in stripped or "100 people" in stripped.lower():
            if current_key:
                notes[current_key] = " ".join(current_lines).strip()
            current_key = "medium"
            current_lines = [re.sub(r"^.*?:\s*", "", stripped.split("**")[-1]).strip()]
        elif "**200" in stripped or "200 people" in stripped.lower():
            if current_key:
                notes[current_key] = " ".join(current_lines).strip()
            current_key = "large"
            current_lines = [re.sub(r"^.*?:\s*", "", stripped.split("**")[-1]).strip()]
        elif current_key and stripped:
            current_lines.append(stripped)

    if current_key:
        notes[current_key] = " ".join(current_lines).strip()

    return notes if any(notes.values()) else {}


def parse_location_adaptations(text: str) -> list[dict]:
    """Parse climate adaptations: **Temperate** — notes"""
    adaptations = []
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r"[-*]\s*\*\*(\w+)\*\*\s*[—–:-]\s*(.*)", line)
        if m:
            adaptations.append({"climate": m.group(1).lower(), "notes": m.group(2)})
    return adaptations


def parse_visuals(text: str) -> list[dict]:
    """Parse visual entries: N. **Caption** — `prompt text`"""
    visuals = []
    for line in text.split("\n"):
        line = line.strip()
        # Match: N. **Caption** — `prompt`  OR  N. Caption — `prompt`
        m = re.match(r"\d+\.\s*\*?\*?([^*`]+?)\*?\*?\s*[—–-]\s*`([^`]+)`", line)
        if m:
            visuals.append({"caption": m.group(1).strip(), "prompt": m.group(2).strip()})
    return visuals


def extract_story_content(text: str) -> str:
    """Extract the full markdown body after frontmatter, stripping the title line."""
    # Remove frontmatter
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].strip()
    # Remove the first # Title line
    lines = text.split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def extract_inline_visuals(text: str) -> list[dict]:
    """Extract inline visuals from ![caption](visuals:prompt) format."""
    visuals = []
    for m in re.finditer(r"!\[([^\]]*)\]\(visuals:([^)]+)\)", text):
        visuals.append({"caption": m.group(1).strip(), "prompt": m.group(2).strip()})
    return visuals


def parse_concept_file(filepath: Path) -> dict:
    """Parse a concept KB markdown file into properties dict for API PATCH."""
    text = filepath.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    props = {}

    # Always sync the full story content (the living narrative)
    story = extract_story_content(text)
    if story:
        props["story_content"] = story

    # Extract inline visuals from ![caption](visuals:prompt)
    inline_visuals = extract_inline_visuals(text)
    if inline_visuals:
        props["visuals"] = inline_visuals

    # Also parse structured sections (for backward compatibility)
    resources_text = parse_section(text, "Resources")
    if resources_text:
        r = parse_resource_items(resources_text)
        if r:
            props["resources"] = r

    materials_text = parse_section(text, "Materials & Methods")
    if materials_text:
        m = parse_materials(materials_text)
        if m:
            props["materials_and_methods"] = m

    scale_text = parse_section(text, "At Scale")
    if scale_text:
        s = parse_scale_notes(scale_text)
        if s:
            props["scale_notes"] = s

    adapt_text = parse_section(text, "Climate Adaptations")
    if adapt_text:
        a = parse_location_adaptations(adapt_text)
        if a:
            props["location_adaptations"] = a

    visuals_text = parse_section(text, "Visuals")
    if visuals_text:
        v = parse_visuals(visuals_text)
        if v and not inline_visuals:  # inline visuals take precedence
            props["visuals"] = v

    costs_text = parse_section(text, "Costs")
    if costs_text:
        props["cost_notes"] = costs_text

    return {"id": fm.get("id", filepath.stem), "status": fm.get("status", "seed"), "properties": props}


def patch_node(api_url: str, node_id: str, properties: dict) -> bool:
    """PATCH /api/graph/nodes/{id} with new properties."""
    url = f"{api_url}/api/graph/nodes/{node_id}"
    body = json.dumps({"properties": properties}).encode()

    if httpx:
        resp = httpx.patch(url, json={"properties": properties}, timeout=30)
        if resp.status_code == 200:
            return True
        print(f"  ERROR: {resp.status_code} {resp.text[:200]}", file=sys.stderr)
        return False
    else:
        req = urllib.request.Request(url, data=body, method="PATCH")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            return False


def main():
    parser = argparse.ArgumentParser(description="Sync KB markdown → Graph DB via API")
    parser.add_argument("concepts", nargs="*", help="Concept IDs to sync (e.g., lc-space)")
    parser.add_argument("--all", action="store_true", help="Sync all concept files")
    parser.add_argument("--min-status", default="seed", help="Minimum status to sync (seed|expanding|mature|complete)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without making changes")
    parser.add_argument("--api-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    args = parser.parse_args()

    if not args.concepts and not args.all:
        parser.print_help()
        sys.exit(1)

    min_status_level = STATUS_ORDER.get(args.min_status, 0)

    # Collect files to sync
    files: list[Path] = []
    if args.all:
        files = sorted(KB_DIR.glob("*.md"))
    else:
        for cid in args.concepts:
            f = KB_DIR / f"{cid}.md"
            if f.exists():
                files.append(f)
            else:
                print(f"WARNING: {f} not found, skipping", file=sys.stderr)

    if not files:
        print("No concept files to sync.")
        sys.exit(0)

    synced = 0
    skipped = 0
    failed = 0

    for filepath in files:
        parsed = parse_concept_file(filepath)
        concept_id = parsed["id"]
        status = parsed["status"]
        props = parsed["properties"]

        status_level = STATUS_ORDER.get(status, 0)
        if status_level < min_status_level:
            skipped += 1
            continue

        if not props:
            print(f"  {concept_id}: no enrichment data to sync (status: {status})")
            skipped += 1
            continue

        field_summary = ", ".join(f"{k}({len(v) if isinstance(v, (list, dict)) else 'str'})" for k, v in props.items())
        print(f"  {concept_id}: {field_summary}")

        if args.dry_run:
            print(f"    [DRY RUN] would PATCH /api/graph/nodes/{concept_id}")
            synced += 1
            continue

        if patch_node(args.api_url, concept_id, props):
            print(f"    ✓ synced to DB")
            synced += 1
        else:
            print(f"    ✗ failed")
            failed += 1

    print(f"\nDone: {synced} synced, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()
