#!/usr/bin/env python3
"""Sync KB markdown files -> Graph DB via API.

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
    python scripts/sync_kb_to_db.py lc-space --api-key dev-key  # explicit write auth
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import hashlib
import re

from kb_common import (
    KB_DIR, DEFAULT_API, STATUS_ORDER,
    parse_concept_file, parse_frontmatter, extract_story_content, parse_crossrefs,
    api_delete, api_get, api_patch, api_post,
)

GLOSSARY_DIR = KB_DIR.parent / "glossary"
IDEAS_DIR = KB_DIR.parent.parent.parent / "ideas"  # repo root /ideas
SUPPORTED_LANGS = {"en", "de", "es", "id"}

DEFAULT_WRITE_API_KEY = "dev-key"

def _write_headers(api_key: str | None) -> dict[str, str]:
    return {"X-API-Key": api_key} if api_key else {}


def build_create_payload(parsed: dict) -> dict:
    properties = {
        "domains": ["living-collective"],
        "level": 2,
        "lifecycle_state": "gas",
    }
    if parsed.get("hz") is not None:
        properties["sacred_frequency"] = {"hz": parsed["hz"]}
    return {
        "id": parsed["id"],
        "type": "concept",
        "name": parsed.get("name") or parsed["id"],
        "description": parsed.get("description", ""),
        "phase": "gas",
        "properties": properties,
    }


def ensure_concept_node(api_url: str, parsed: dict, api_key: str | None) -> bool:
    concept_id = parsed["id"]
    try:
        api_get(f"{api_url}/api/concepts/{concept_id}")
        return True
    except Exception:
        pass

    status = api_post(
        f"{api_url}/api/graph/nodes",
        build_create_payload(parsed),
        headers=_write_headers(api_key),
    )
    if status in (200, 201):
        print("    created missing concept node")
        return True
    if status == 409:
        return True
    print(f"    create FAILED ({status})", file=sys.stderr)
    return False


def patch_node(api_url: str, node_id: str, properties: dict, api_key: str | None) -> bool:
    """PATCH /api/graph/nodes/{id} with new properties."""
    return api_patch(
        f"{api_url}/api/graph/nodes/{node_id}",
        {"properties": properties},
        headers=_write_headers(api_key),
    )


def load_crossref_map() -> dict[str, set[str]]:
    crossrefs: dict[str, set[str]] = {}
    for filepath in sorted(KB_DIR.glob("*.md")):
        concept_id = filepath.stem
        refs = set(parse_crossrefs(filepath.read_text(encoding="utf-8")))
        refs.discard(concept_id)
        crossrefs[concept_id] = refs
    return crossrefs


def fetch_concept_edges(api_url: str, concept_id: str) -> list[dict]:
    data = api_get(f"{api_url}/api/concepts/{concept_id}/edges")
    return data if isinstance(data, list) else []


def create_edge(api_url: str, from_id: str, to_id: str, edge_type: str, api_key: str | None) -> bool:
    status = api_post(
        f"{api_url}/api/graph/edges",
        {
            "from_id": from_id,
            "to_id": to_id,
            "type": edge_type,
            "created_by": "sync_kb_to_db",
        },
        headers=_write_headers(api_key),
    )
    return status in (200, 201, 409)


def delete_edge(api_url: str, edge_id: str, api_key: str | None) -> bool:
    status = api_delete(f"{api_url}/api/graph/edges/{edge_id}", headers=_write_headers(api_key))
    return status in (200, 404)


def sync_analogous_edges(
    concept_id: str,
    api_url: str,
    dry_run: bool,
    api_key: str | None,
    crossref_map: dict[str, set[str]],
) -> bool:
    desired_peers = set(crossref_map.get(concept_id, set()))
    desired_peers.update(other for other, refs in crossref_map.items() if concept_id in refs)

    if dry_run:
        print(f"    [DRY RUN] would reconcile analogous-to edges for {concept_id}: {sorted(desired_peers)}")
        return True

    try:
        edges = fetch_concept_edges(api_url, concept_id)
    except Exception as exc:
        print(f"    edge fetch FAILED ({exc})", file=sys.stderr)
        return False

    analogous_edges = [
        edge for edge in edges
        if edge.get("type") == "analogous-to"
        and (edge.get("from") == concept_id or edge.get("to") == concept_id)
    ]

    by_peer: dict[str, list[dict]] = {}
    for edge in analogous_edges:
        peer = edge["to"] if edge.get("from") == concept_id else edge["from"]
        by_peer.setdefault(peer, []).append(edge)

    ok = True

    for peer, peer_edges in by_peer.items():
        extras = peer_edges[1:]
        if peer not in desired_peers:
            extras = peer_edges
        for edge in extras:
            if not delete_edge(api_url, edge["id"], api_key):
                print(f"    delete FAILED ({edge['id']})", file=sys.stderr)
                ok = False

    for peer in sorted(desired_peers):
        if peer in by_peer:
            continue
        from_id, to_id = sorted([concept_id, peer])
        if not create_edge(api_url, from_id, to_id, "analogous-to", api_key):
            print(f"    edge create FAILED ({from_id} -> {to_id})", file=sys.stderr)
            ok = False

    return ok


def sync_concept(
    parsed: dict,
    api_url: str,
    dry_run: bool,
    api_key: str | None,
    crossref_map: dict[str, set[str]],
) -> bool:
    concept_id = parsed["id"]
    props = parsed["properties"]

    if dry_run:
        print(f"    [DRY RUN] would ensure + PATCH /api/graph/nodes/{concept_id}")
        return sync_analogous_edges(concept_id, api_url, dry_run, api_key, crossref_map)

    if not ensure_concept_node(api_url, parsed, api_key):
        return False
    if not patch_node(api_url, concept_id, props, api_key):
        return False
    return sync_analogous_edges(concept_id, api_url, dry_run, api_key, crossref_map)


# ---------------------------------------------------------------------------
# Language views — every concept can have views in multiple languages
# ---------------------------------------------------------------------------

def content_hash(markdown: str, title: str, description: str) -> str:
    payload = f"{title}\n\n{description}\n\n{markdown}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_view_file(filepath: Path) -> dict:
    """Parse a view file: English original (lc-xxx.md) or a non-English view
    (lc-xxx.<lang>.md). Returns lang, title, description, markdown, and any
    translation metadata declared in frontmatter.
    """
    text = filepath.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    stem = filepath.stem  # e.g. "lc-nourishing" or "lc-nourishing.de"
    parts = stem.split(".")
    if len(parts) == 2 and parts[1] in SUPPORTED_LANGS:
        concept_id = parts[0]
        lang = fm.get("lang", parts[1])
    else:
        concept_id = stem
        lang = fm.get("lang", "en")

    title_m = re.search(r"^# (.+)$", text, re.MULTILINE)
    desc_m = re.search(r"^>\s*(.+)$", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else ""
    description = desc_m.group(1).strip() if desc_m else ""
    story = extract_story_content(text) or ""

    # Default author_type:
    #   - English view -> original_human (unless frontmatter says otherwise)
    #   - non-English with translated_from -> translation_human
    #   - non-English with no translated_from -> original_human (authored directly in that lang)
    declared_author = fm.get("author_type")
    if declared_author:
        author_type = declared_author
    else:
        if lang == "en" and not fm.get("translated_from"):
            author_type = "original_human"
        elif fm.get("translated_from"):
            author_type = "translation_human"
        else:
            author_type = "original_human"

    return {
        "concept_id": concept_id,
        "lang": lang,
        "title": title,
        "description": description,
        "markdown": story,
        "author_type": author_type,
        "translated_from": fm.get("translated_from"),
        "notes": fm.get("notes"),
    }


def view_files_for_concept(concept_id: str) -> list[Path]:
    """All view files for a concept: the English original plus any <lang>.md siblings."""
    files = []
    en = KB_DIR / f"{concept_id}.md"
    if en.exists():
        files.append(en)
    for lang in SUPPORTED_LANGS - {"en"}:
        p = KB_DIR / f"{concept_id}.{lang}.md"
        if p.exists():
            files.append(p)
    return files


def sync_views_for_concept(
    concept_id: str, api_url: str, dry_run: bool, api_key: str | None
) -> tuple[int, int]:
    """Project every language view file for a concept into the DB.

    Order matters: sync the anchor-eligible (non-translated) view first so its
    content_hash is available to the translated views for linkage. For now the
    English file acts as the starting point if no other lang file is marked as
    the anchor; when a non-English view is edited to become the anchor, a
    subsequent sync pass will re-read the files and update accordingly.
    """
    files = view_files_for_concept(concept_id)
    if not files:
        return (0, 0)

    # First pass: parse all views
    parsed_views = [parse_view_file(f) for f in files]

    # Build a map lang -> content_hash so translated views can reference
    hashes: dict[str, str] = {}
    for v in parsed_views:
        hashes[v["lang"]] = content_hash(v["markdown"], v["title"], v["description"])

    written = 0
    failed = 0
    for v in parsed_views:
        body: dict = {
            "lang": v["lang"],
            "content_title": v["title"],
            "content_description": v["description"],
            "content_markdown": v["markdown"],
            "author_type": v["author_type"],
        }
        if v["translated_from"]:
            body["translated_from_lang"] = v["translated_from"]
            body["translated_from_hash"] = hashes.get(v["translated_from"], "")
        if v["notes"]:
            body["notes"] = v["notes"]

        if dry_run:
            print(f"    [DRY RUN] would POST /api/concepts/{concept_id}/views ({v['lang']}, {v['author_type']})")
            written += 1
            continue

        status = api_post(
            f"{api_url}/api/concepts/{concept_id}/views",
            body,
            headers=_write_headers(api_key),
        )
        if status in (200, 201):
            print(f"    view synced: {v['lang']} ({v['author_type']})")
            written += 1
        else:
            print(f"    view FAILED: {v['lang']} (status {status})", file=sys.stderr)
            failed += 1
    return written, failed


# ---------------------------------------------------------------------------
# Idea view files — ideas/{slug}.{lang}.md project into /api/views/idea/{slug}
# ---------------------------------------------------------------------------

def parse_idea_view_file(filepath: Path) -> dict:
    """Parse ideas/<slug>.<lang>.md into a view payload.

    The non-language file (ideas/agent-pipeline.md) is the English view.
    Files with a .<lang>.md suffix (agent-pipeline.de.md) are translations.
    """
    text = filepath.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    stem = filepath.stem
    parts = stem.split(".")
    if len(parts) == 2 and parts[1] in SUPPORTED_LANGS:
        idea_id = parts[0]
        lang = fm.get("lang", parts[1])
    else:
        idea_id = stem
        lang = fm.get("lang", "en")

    title_m = re.search(r"^# (.+)$", text, re.MULTILINE)
    desc_m = re.search(r"^>\s*(.+)$", text, re.MULTILINE)
    title = (title_m.group(1) if title_m else "").strip()
    description = (desc_m.group(1) if desc_m else "").strip()

    declared_author = fm.get("author_type")
    if declared_author:
        author_type = declared_author
    else:
        if lang == "en" and not fm.get("translated_from"):
            author_type = "original_human"
        elif fm.get("translated_from"):
            author_type = "translation_human"
        else:
            author_type = "original_human"

    return {
        "idea_id": idea_id,
        "lang": lang,
        "title": title,
        "description": description,
        "markdown": text,  # full body as content_markdown
        "author_type": author_type,
        "translated_from": fm.get("translated_from"),
        "notes": fm.get("notes"),
    }


def idea_view_files_for(idea_slug: str) -> list[Path]:
    if not IDEAS_DIR.exists():
        return []
    files = []
    en = IDEAS_DIR / f"{idea_slug}.md"
    if en.exists():
        files.append(en)
    for lang in SUPPORTED_LANGS - {"en"}:
        p = IDEAS_DIR / f"{idea_slug}.{lang}.md"
        if p.exists():
            files.append(p)
    return files


def sync_idea_views_for(
    idea_slug: str, api_url: str, dry_run: bool, api_key: str | None
) -> tuple[int, int]:
    files = idea_view_files_for(idea_slug)
    if not files:
        return (0, 0)

    parsed = [parse_idea_view_file(f) for f in files]
    hashes: dict[str, str] = {}
    for v in parsed:
        hashes[v["lang"]] = content_hash(v["markdown"], v["title"], v["description"])

    written = 0
    failed = 0
    for v in parsed:
        body: dict = {
            "lang": v["lang"],
            "content_title": v["title"],
            "content_description": v["description"],
            "content_markdown": v["markdown"],
            "author_type": v["author_type"],
        }
        if v["translated_from"]:
            body["translated_from_lang"] = v["translated_from"]
            body["translated_from_hash"] = hashes.get(v["translated_from"], "")
        if v["notes"]:
            body["notes"] = v["notes"]

        if dry_run:
            print(f"    [DRY RUN] would POST /api/entity-views/idea/{idea_slug} ({v['lang']}, {v['author_type']})")
            written += 1
            continue

        status = api_post(
            f"{api_url}/api/entity-views/idea/{idea_slug}",
            body,
            headers=_write_headers(api_key),
        )
        if status in (200, 201):
            print(f"    idea view synced: {v['lang']} ({v['author_type']})")
            written += 1
        else:
            print(f"    idea view FAILED: {v['lang']} (status {status})", file=sys.stderr)
            failed += 1
    return written, failed


def sync_all_idea_views(api_url: str, dry_run: bool, api_key: str | None) -> tuple[int, int]:
    if not IDEAS_DIR.exists():
        return (0, 0)
    seen: set[str] = set()
    total_written = 0
    total_failed = 0
    for f in sorted(IDEAS_DIR.glob("*.md")):
        parts = f.stem.split(".")
        slug = parts[0]
        if slug in seen:
            continue
        seen.add(slug)
        w, fail = sync_idea_views_for(slug, api_url, dry_run, api_key)
        total_written += w
        total_failed += fail
    return total_written, total_failed


# ---------------------------------------------------------------------------
# Glossary sync
# ---------------------------------------------------------------------------

def parse_glossary_file(filepath: Path) -> tuple[str, list[dict]]:
    """Parse docs/vision-kb/glossary/<lang>.md into (lang, entries).

    Entries are bullet lines of the form:
      - **<source>** → **<target>** — <notes>
    """
    text = filepath.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    lang = fm.get("lang", filepath.stem)
    entries: list[dict] = []
    for line in text.splitlines():
        m = re.match(
            r"^\s*-\s+\*\*(?P<src>[^*]+)\*\*\s*→\s*\*\*(?P<tgt>[^*]+)\*\*\s*(?:—\s*(?P<notes>.*))?$",
            line,
        )
        if m:
            entries.append({
                "source_term": m.group("src").strip(),
                "target_term": m.group("tgt").strip(),
                "notes": (m.group("notes") or "").strip() or None,
            })
    return lang, entries


def sync_glossary(api_url: str, dry_run: bool, api_key: str | None) -> int:
    """Project every glossary file under docs/vision-kb/glossary/ into the DB."""
    if not GLOSSARY_DIR.exists():
        return 0
    total = 0
    for f in sorted(GLOSSARY_DIR.glob("*.md")):
        lang, entries = parse_glossary_file(f)
        if not entries:
            continue
        if dry_run:
            print(f"  glossary {lang}: [DRY RUN] would upsert {len(entries)} entries")
            total += len(entries)
            continue
        ok = api_patch(
            f"{api_url}/api/glossary/{lang}",
            {"entries": entries},
            headers=_write_headers(api_key),
        )
        if ok:
            print(f"  glossary {lang}: upserted {len(entries)} entries")
            total += len(entries)
        else:
            print(f"  glossary {lang}: FAILED", file=sys.stderr)
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync KB markdown -> Graph DB via API")
    parser.add_argument("concepts", nargs="*", help="Concept IDs to sync (e.g., lc-space)")
    parser.add_argument("--all", action="store_true", help="Sync all concept files")
    parser.add_argument("--min-status", default="seed", help="Minimum status to sync (seed|expanding|deepening|mature|complete)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without making changes")
    parser.add_argument("--api-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--api-key", default=DEFAULT_WRITE_API_KEY, help="Write API key for POST/PATCH operations (default: dev-key)")
    parser.add_argument("--views", action="store_true", help="Also sync language view files (lc-xxx.<lang>.md) for each concept")
    parser.add_argument("--idea-views", action="store_true", help="Sync idea view files (ideas/<slug>.<lang>.md) into /api/views/idea/<slug>")
    parser.add_argument("--glossary", action="store_true", help="Also sync glossary files under docs/vision-kb/glossary/")
    args = parser.parse_args(argv)

    if not args.concepts and not args.all and not args.glossary and not args.idea_views:
        parser.print_help()
        return 1

    min_status_level = STATUS_ORDER.get(args.min_status, 0)

    # Collect files to sync — only the canonical per-concept files (lc-xxx.md),
    # not per-language views. View files are handled separately when --views is set.
    files: list[Path] = []
    if args.all:
        for f in sorted(KB_DIR.glob("*.md")):
            parts = f.stem.split(".")
            if len(parts) == 2 and parts[1] in SUPPORTED_LANGS:
                continue  # per-lang view file, handled by --views
            files.append(f)
    else:
        for cid in args.concepts:
            f = KB_DIR / f"{cid}.md"
            if f.exists():
                files.append(f)
            else:
                print(f"WARNING: {f} not found, skipping", file=sys.stderr)

    if not files:
        print("No concept files to sync.")
        return 0

    synced = 0
    skipped = 0
    failed = 0
    crossref_map = load_crossref_map()

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

        if sync_concept(parsed, args.api_url, args.dry_run, args.api_key, crossref_map):
            print(f"    synced to DB")
            synced += 1
        else:
            print(f"    FAILED")
            failed += 1

        if args.views:
            v_written, v_failed = sync_views_for_concept(
                concept_id, args.api_url, args.dry_run, args.api_key
            )
            failed += v_failed

    if args.glossary:
        print("\nSyncing glossary...")
        sync_glossary(args.api_url, args.dry_run, args.api_key)

    if args.idea_views:
        print("\nSyncing idea views...")
        w, f = sync_all_idea_views(args.api_url, args.dry_run, args.api_key)
        failed += f
        print(f"  idea views: {w} synced, {f} failed")

    print(f"\nDone: {synced} synced, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
