#!/usr/bin/env python3
"""Export graph-stored content back into the repo as files.

The graph is the runtime source of truth — every page renders from it.
This script closes the loop by walking each content-bearing node and
projecting its current state back into the repo's canonical files
(`docs/presence-content/{slug}.json`, etc.). Run periodically (or
on-demand after a wave of web edits) to keep the repo as a readable
mirror of what's live.

Outside edits flow into the graph immediately. This job is how those
edits flow back into git history so the repo remains the body's
autobiography rather than its sole input.

Content types currently exported:

  presence_content  → docs/presence-content/{slug}.json
                      walked from any node whose properties carry a
                      `presence_content` JSON envelope (mostly
                      contributors and a few assets/places).

Future content types (concept stories, idea bodies, spec frontmatter)
follow the same pattern — add a walker per type.

Usage:
    python3 scripts/export_graph_to_repo.py                 # dry-run, prints diffs
    python3 scripts/export_graph_to_repo.py --write         # write files (no commit)
    python3 scripts/export_graph_to_repo.py --commit        # write + git commit + push
    python3 scripts/export_graph_to_repo.py --api-url …     # alternate API root
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parent.parent
PRESENCE_CONTENT_DIR = REPO_ROOT / "docs" / "presence-content"
CONCEPTS_DIR = REPO_ROOT / "docs" / "vision-kb" / "concepts"
DEFAULT_API = "https://api.coherencycoin.com"


def _fetch_json(url: str, timeout: int = 30) -> dict | None:
    req = urlrequest.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "coherence-export/1.0",
        },
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError) as e:
        sys.stderr.write(f"fetch {url} failed: {e}\n")
        return None


def list_nodes_with_presence_content(api_url: str) -> list[dict]:
    """Walk every node carrying a `presence_content` property.

    The list endpoint already returns full node.to_dict() including
    properties, so a single page-walk per type is enough — no need to
    re-fetch each node. Types covered are the ones the composting move
    populated (contributor, asset, scene, place, community, event,
    network-org, practice); adding a new type later is one entry in
    this tuple.
    """
    items: list[dict] = []
    seen_ids: set[str] = set()
    for node_type in (
        "contributor",
        "asset",
        "scene",
        "place",
        "community",
        "event",
        "network-org",
        "practice",
        "workspace",
        "interested-person",
    ):
        offset = 0
        page_size = 500
        while True:
            url = (
                f"{api_url.rstrip('/')}/api/graph/nodes"
                f"?type={node_type}&limit={page_size}&offset={offset}"
            )
            page = _fetch_json(url, timeout=60)
            if not page or not page.get("items"):
                break
            for n in page["items"]:
                if n.get("id") in seen_ids:
                    continue
                seen_ids.add(n["id"])
                if n.get("presence_content"):
                    items.append(n)
            if len(page["items"]) < page_size:
                break
            offset += page_size
    return items


def _quote(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(s, safe="")


def slug_for_node(node: dict) -> str | None:
    """Resolve the repo filename slug for a node.

    Prefers the node's `presence_slug` override (when the static
    directory used a non-slug URL like /people/urs ↔ slug=urs-muff),
    then the `slug` property, then the id-suffix.
    """
    slug = node.get("presence_slug") or node.get("slug")
    if slug:
        return str(slug)
    node_id = node.get("id", "")
    if ":" in node_id:
        return node_id.split(":", 1)[1]
    return node_id or None


def export_presence_content(
    nodes: list[dict],
    *,
    write: bool,
) -> tuple[list[Path], list[Path]]:
    """Project each node's `presence_content` to its JSON file on disk.

    Returns (written_files, removed_files).
    """
    PRESENCE_CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    removed: list[Path] = []
    expected_files: set[Path] = set()

    for node in nodes:
        slug = slug_for_node(node)
        if not slug:
            sys.stderr.write(f"skipping node {node.get('id')!r} — no slug\n")
            continue
        content = node.get("presence_content")
        if not isinstance(content, dict):
            continue
        dest = PRESENCE_CONTENT_DIR / f"{slug}.json"
        expected_files.add(dest)

        new_text = json.dumps(content, indent=2, ensure_ascii=False) + "\n"

        # Semantic diff: parse both files as JSON and compare as dicts.
        # The graph stores property dicts whose key-order is not
        # guaranteed, and human-authored files may have different
        # whitespace. Treat structurally-equal content as no-change.
        existing_content: dict | None = None
        if dest.exists():
            try:
                existing_content = json.loads(dest.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing_content = None
        if existing_content == content:
            continue  # no semantic change

        if write:
            dest.write_text(new_text, encoding="utf-8")
        written.append(dest)
        print(f"  {'wrote' if write else 'would write'} {dest.relative_to(REPO_ROOT)}")

    # Files in the repo that don't correspond to any live node — these
    # are orphans (node deleted but file remained). Don't auto-remove
    # them in the dry-run print; let the writer make the call.
    for existing in PRESENCE_CONTENT_DIR.glob("*.json"):
        if existing not in expected_files:
            removed.append(existing)
            print(f"  {'removed' if write else 'would remove'} {existing.relative_to(REPO_ROOT)} (orphan)")
            if write:
                existing.unlink()

    return written, removed


def list_concepts_with_story(api_url: str) -> list[dict]:
    """Walk concept nodes that carry `story_content`.

    Concept stories live on the graph as the `story_content` field
    after `sync_kb_to_db.py` projects them in. Edits via
    `PATCH /api/concepts/{id}/story` from the /vision/{id}/edit web
    surface land on the same field, so the same field is what we
    export back to the repo.
    """
    items: list[dict] = []
    offset = 0
    page_size = 500
    while True:
        url = (
            f"{api_url.rstrip('/')}/api/graph/nodes"
            f"?type=concept&limit={page_size}&offset={offset}"
        )
        page = _fetch_json(url, timeout=60)
        if not page or not page.get("items"):
            break
        for n in page["items"]:
            if n.get("story_content"):
                items.append(n)
        if len(page["items"]) < page_size:
            break
        offset += page_size
    return items


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_block, body). Empty frontmatter is "".

    The block is the YAML between the leading `---` lines (without
    the dashes); the body is everything after the closing `---\n`.
    When no frontmatter is present, returns ("", text).
    """
    if not text.startswith("---\n"):
        return "", text
    rest = text[4:]
    end = rest.find("\n---\n")
    if end < 0:
        return "", text
    return rest[:end], rest[end + 5:]


def export_concept_stories(
    nodes: list[dict],
    *,
    write: bool,
) -> list[Path]:
    """Project concept story bodies back to docs/vision-kb/concepts/.

    Preserves the existing frontmatter (so hand-curated `hz`, `status`,
    `updated`, `domains`, `axes` fields aren't lost) and only replaces
    the markdown body when graph `story_content` differs. For nodes
    without an existing file (rare — would mean a concept was minted
    via the API without ever being authored in the repo), writes a
    minimal frontmatter derived from graph properties.

    Returns list of files written.
    """
    if not CONCEPTS_DIR.is_dir():
        return []
    written: list[Path] = []
    for node in nodes:
        concept_id = node.get("id", "")
        if not concept_id:
            continue
        dest = CONCEPTS_DIR / f"{concept_id}.md"
        # sync_kb_to_db.py strips the leading `# Title` from the file
        # before storing in `story_content`. Re-prepend it on export
        # so the round-tripped file matches the repo's canonical shape.
        story = (node.get("story_content") or "").strip()
        title = (node.get("name") or "").strip()
        new_body = f"# {title}\n\n{story}\n" if title else story + "\n"

        existing_text = dest.read_text(encoding="utf-8") if dest.exists() else ""
        existing_fm, existing_body = _split_frontmatter(existing_text)

        if existing_text:
            # Preserve existing frontmatter — humans curate it
            new_text = f"---\n{existing_fm}\n---\n\n{new_body.lstrip()}"
            # Re-normalize: if existing body matches semantically, skip
            if existing_body.strip() == new_body.strip():
                continue
        else:
            # Minimal frontmatter derived from graph
            from datetime import datetime
            hz = node.get("sacred_frequency")
            status = node.get("lifecycle_state") or "seed"
            today = datetime.utcnow().strftime("%Y-%m-%d")
            fm_lines = [f"id: {concept_id}"]
            if hz:
                fm_lines.append(f"hz: {hz}")
            fm_lines.append(f"status: {status}")
            fm_lines.append(f"updated: {today}")
            new_text = "---\n" + "\n".join(fm_lines) + "\n---\n\n" + new_body.lstrip()

        if write:
            dest.write_text(new_text, encoding="utf-8")
        written.append(dest)
        print(f"  {'wrote' if write else 'would write'} {dest.relative_to(REPO_ROOT)}")
    return written


def git_commit_and_push(written: list[Path], removed: list[Path]) -> bool:
    """Stage the writes/removals, commit if there's a diff, push.

    Returns True if a commit was made. False if there was nothing to
    commit. Raises if git itself errors.
    """
    if not written and not removed:
        return False

    # Stage everything in the content directories we touch
    subprocess.check_call(
        ["git", "add",
         str(PRESENCE_CONTENT_DIR.relative_to(REPO_ROOT)),
         str(CONCEPTS_DIR.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
    )

    # Bail if the index is clean (e.g. files were re-written with
    # identical content after JSON formatting normalised them)
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=REPO_ROOT,
    )
    if diff.returncode == 0:
        print("  no staged changes after `git add` — index clean")
        return False

    summary = f"{len(written)} written, {len(removed)} removed"
    message = (
        "tend(content): scheduled export of graph content to repo\n"
        "\n"
        "Mirror of the graph's authored content into the repo. Outside\n"
        "edits land in the graph immediately; this commit brings the\n"
        f"repo's projection into alignment. {summary}.\n"
        "\n"
        "Generated by scripts/export_graph_to_repo.py.\n"
    )
    subprocess.check_call(
        ["git", "commit", "-m", message],
        cwd=REPO_ROOT,
    )
    print(f"  committed: {summary}")

    # Push if a remote is configured and we're on a branch that tracks it
    try:
        subprocess.check_call(["git", "push"], cwd=REPO_ROOT)
        print("  pushed to remote")
    except subprocess.CalledProcessError:
        sys.stderr.write("  push failed — leaving commit local\n")

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write changed files to disk (default: dry-run)",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Write + git commit + push the diff (implies --write)",
    )
    args = parser.parse_args()

    if args.commit:
        args.write = True

    if not shutil.which("git") and args.commit:
        sys.stderr.write("git not on PATH; cannot --commit\n")
        return 2

    print(f"Walking graph at {args.api_url}…")

    presence_nodes = list_nodes_with_presence_content(args.api_url)
    print(f"  found {len(presence_nodes)} nodes carrying presence_content")
    pc_written, pc_removed = export_presence_content(presence_nodes, write=args.write)

    concept_nodes = list_concepts_with_story(args.api_url)
    print(f"  found {len(concept_nodes)} concepts carrying story_content")
    concept_written = export_concept_stories(concept_nodes, write=args.write)

    total_written = pc_written + concept_written
    if not total_written and not pc_removed:
        print("repo already matches graph — nothing to export")
        return 0

    if args.commit:
        git_commit_and_push(total_written, pc_removed)
    elif args.write:
        print(
            f"wrote {len(total_written)} files, removed {len(pc_removed)} — "
            f"repo updated, no commit (--commit to push)"
        )
    else:
        print(
            f"would write {len(total_written)} files, remove {len(pc_removed)} "
            "(re-run with --write)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
