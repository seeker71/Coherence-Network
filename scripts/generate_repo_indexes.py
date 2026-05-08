#!/usr/bin/env python3
"""Generate INDEX.md files for source-code directories.

The body's narrative layer (specs, ideas, concepts, lineage,
presences) has had INDEX.md files for a while — agents can find any
spec or concept in a few hundred tokens. The body's code layer
(routers, services, models, components, scripts) does not yet have
indexes, so finding an API endpoint or a React component means
greedy-grepping ~960 files.

This script closes that gap. For each unindexed source directory it
extracts the first docstring/comment block from every file and
writes a single INDEX.md that lists every file with one short line
of purpose. An agent loads the relevant INDEX (~3-8KB) and knows
exactly which file to read next.

It also writes a root MANIFEST.md that points at every INDEX in the
repo, so the agent's first orientation costs <500 tokens.

Run it whenever the file set changes:

    python3 scripts/generate_repo_indexes.py
    python3 scripts/generate_repo_indexes.py --check     # CI: fail if stale

A pre-commit hook can run --check to catch missing top-of-file
purpose statements before they land.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


# Directories that carry source code and would benefit from an INDEX.
# (path, file_glob, label)
TARGETS: list[tuple[str, str, str]] = [
    ("api/app/routers",   "*.py",  "API routers — every HTTP endpoint surface"),
    ("api/app/services",  "*.py",  "API services — business logic and graph operations"),
    ("api/app/models",    "*.py",  "API models — Pydantic + ORM shapes"),
    ("api/tests",         "*.py",  "API tests — flow-centric"),
    ("web/lib",           "*.ts",  "Web library — shared client/server helpers"),
    ("web/components",    "*.tsx", "Web components — shared React surfaces"),
    ("web/app",           "page.tsx", "Web routes — every visible page in the app"),
    ("scripts",           "*.py",  "Scripts — operational tools, generators, syncers"),
]

# Directories that already have an INDEX. We only show them in MANIFEST.
EXISTING_INDEXES = [
    ("CLAUDE.md", "Body tending practice + Quick Lookup table"),
    ("specs/INDEX.md", "All specs, grouped by parent idea (auto-generated)"),
    ("ideas/INDEX.md", "Super-ideas (16) across the 6 pillars"),
    ("docs/vision-kb/INDEX.md", "Living Collective wiki — concepts, axes, lineage"),
    ("docs/vision-kb/locations/INDEX.md", "Climate adaptations"),
    ("docs/vision-kb/materials/INDEX.md", "Construction methods"),
    ("docs/vision-kb/realization/INDEX.md", "Governance, economics, membership, phases"),
    ("docs/vision-kb/resources/INDEX.md", "Open-source plans, references, books"),
    ("docs/vision-kb/scales/INDEX.md", "50 / 100 / 200 people configurations"),
    ("docs/vision-kb/spaces/INDEX.md", "Hearth, garden, workshop, sanctuary, gathering"),
    ("docs/vision-kb/stories/INDEX.md", "Field vignettes — scenes from the future"),
    ("docs/lineage/INDEX.md", "Teaching lineages and presences"),
    ("docs/presences/INDEX.md", "Specific presences in the field"),
]

# Files we always skip when reading purposes.
SKIP_FILES = {"__init__.py", "INDEX.md", "README.md"}


def extract_purpose(path: Path) -> str:
    """Read the first docstring or comment block from a source file.

    Returns a single-line purpose string or "" if none found.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    suffix = path.suffix
    lines = text.splitlines()

    if suffix == ".py":
        # Try a triple-quoted module docstring first.
        for i, raw in enumerate(lines):
            line = raw.strip()
            if not line:
                continue
            if line.startswith('"""') or line.startswith("'''"):
                quote = line[:3]
                # Same-line: """one-liner."""
                rest = line[3:]
                if rest.endswith(quote) and len(rest) > 3:
                    return _clean(rest[:-3])
                if rest:
                    return _clean(rest)
                # Multi-line: read next non-empty line.
                for j in range(i + 1, min(i + 6, len(lines))):
                    nxt = lines[j].strip()
                    if nxt:
                        if nxt.endswith(quote):
                            nxt = nxt[: -len(quote)]
                        return _clean(nxt)
                return ""
            if line.startswith("#"):
                return _clean(line.lstrip("# ").rstrip())
            # Skip imports and pragmas, keep looking.
            if line.startswith(("from ", "import ", "@", "def ", "class ")):
                break
            break

    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        in_block = False
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if not in_block:
                if line.startswith("/**") or line.startswith("/*"):
                    rest = line[3 if line.startswith("/**") else 2 :].strip()
                    if rest.endswith("*/"):
                        return _clean(rest[:-2].strip().lstrip("* "))
                    if rest:
                        return _clean(rest.lstrip("* "))
                    in_block = True
                    continue
                if line.startswith("//"):
                    return _clean(line[2:].strip())
                # First non-comment, non-import code → no purpose found.
                if line.startswith(("import ", "export ", "const ", "function ", "interface ", "type ", "class ", "//", '"use ', "'use ")):
                    if line.startswith(("//", )):
                        return _clean(line[2:].strip())
                    break
                break
            else:
                # Inside a block comment.
                cleaned = line.lstrip("* ").rstrip()
                if cleaned.endswith("*/"):
                    cleaned = cleaned[:-2].strip()
                if cleaned:
                    return _clean(cleaned)

    return ""


def _clean(s: str) -> str:
    s = s.strip().strip('"').strip("'").strip()
    s = re.sub(r"\s+", " ", s)
    if len(s) > 200:
        s = s[:197] + "..."
    return s


def list_files(dir_path: Path, glob: str) -> list[Path]:
    if glob == "page.tsx":
        # web/app — scan for every page.tsx recursively.
        return sorted(p for p in dir_path.rglob("page.tsx"))
    return sorted(p for p in dir_path.glob(glob) if p.name not in SKIP_FILES)


def render_index(dir_label: str, dir_path: Path, files: list[Path]) -> str:
    """Build the INDEX.md content for a directory."""
    rel_dir = dir_path.relative_to(REPO_ROOT)
    lines = [
        f"# {rel_dir} — {dir_label}",
        "",
        "> Auto-generated by `scripts/generate_repo_indexes.py`. Each entry's",
        "> purpose comes from the top docstring/comment of the file. To update",
        "> a description, edit the file's first line and re-run the script.",
        "",
        f"**Total files**: {len(files)}",
        "",
    ]
    if not files:
        lines.append("_No files yet._")
        return "\n".join(lines) + "\n"

    # Group: for web/app/page.tsx files, show as routes
    if dir_path.name == "app":
        lines.append("| Route | File | Purpose |")
        lines.append("|---|---|---|")
        for f in files:
            route_dir = f.parent.relative_to(dir_path)
            route = "/" if str(route_dir) == "." else f"/{route_dir}"
            rel_file = f.relative_to(REPO_ROOT)
            purpose = extract_purpose(f) or "_no top-of-file purpose_"
            lines.append(f"| `{route}` | [{rel_file.name}]({rel_file.relative_to(rel_dir)}) | {purpose} |")
    else:
        lines.append("| File | Purpose |")
        lines.append("|---|---|")
        for f in files:
            rel = f.relative_to(dir_path)
            purpose = extract_purpose(f) or "_no top-of-file purpose_"
            lines.append(f"| [{rel}]({rel}) | {purpose} |")

    return "\n".join(lines) + "\n"


def render_manifest(targets: list[tuple[str, Path, list[Path]]]) -> str:
    """Build the root MANIFEST.md pointing at every INDEX in the repo."""
    lines = [
        "# Repo Manifest",
        "",
        "> Single entry-point for finding any file in this repo. The narrative",
        "> layer (specs, ideas, concepts, lineage) has been indexed for a",
        "> while; the code layer (routers, services, components, scripts) is",
        "> indexed by `scripts/generate_repo_indexes.py`.",
        "",
        "> An agent landing here costs ~400 tokens to know which INDEX to",
        "> drill into next, then ~1500 tokens to know which file to read.",
        "> Total cost to locate any file: under 2K tokens.",
        "",
        "## Narrative layer (existing)",
        "",
        "| Index | Purpose |",
        "|---|---|",
    ]
    for path, purpose in EXISTING_INDEXES:
        lines.append(f"| [{path}]({path}) | {purpose} |")

    lines += [
        "",
        "## Code layer (auto-generated)",
        "",
        "| Index | Files | Purpose |",
        "|---|---|---|",
    ]
    for label, dir_path, files in targets:
        rel = dir_path.relative_to(REPO_ROOT)
        lines.append(f"| [{rel}/INDEX.md]({rel}/INDEX.md) | {len(files)} | {label} |")

    lines += [
        "",
        "## Convention",
        "",
        "Every new source file gets a one-line purpose statement at the top:",
        "",
        "- **Python**: a module docstring (`\"\"\"What this module does.\"\"\"`) on line 1",
        "- **TypeScript/TSX**: a leading `// What this file does` comment OR a JSDoc block `/** What this file does */`",
        "",
        "After adding/renaming files, re-run:",
        "",
        "```",
        "python3 scripts/generate_repo_indexes.py",
        "```",
        "",
        "CI runs `--check` and fails if any INDEX.md is stale.",
        "",
    ]
    return "\n".join(lines)


def render_specs_index() -> str:
    """Build specs/INDEX.md from spec frontmatter, grouped by idea_id.

    Each spec carries `idea_id` and `status` in its frontmatter and a
    `# Heading — short essence` H1. The heading after the em-dash is the
    one-line essence; we use it as the entry's description so the index
    stays in sync with what each spec claims to be, and never drifts
    again behind the body.

    Status is enumerated in the preamble so the wellness check can read
    the count via the existing `(\\d+)\\s+specs\\s+\\(` pattern.
    """
    specs_dir = REPO_ROOT / "specs"
    if not specs_dir.is_dir():
        return ""

    entries: list[dict[str, str]] = []
    for path in sorted(specs_dir.glob("*.md")):
        if path.name in {"INDEX.md", "TEMPLATE.md"}:
            continue
        text = path.read_text(encoding="utf-8")
        idea = _spec_field(text, "idea_id") or "(unfiled)"
        status = _spec_field(text, "status") or "unknown"
        essence = _spec_essence(text)
        entries.append({
            "slug": path.stem,
            "idea": idea,
            "status": status,
            "essence": essence,
        })

    counts: dict[str, int] = {}
    for e in entries:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    total = len(entries)
    status_summary = ", ".join(
        f"{counts[s]} {s}" for s in sorted(counts, key=lambda k: -counts[k])
    )

    by_idea: dict[str, list[dict[str, str]]] = {}
    for e in entries:
        by_idea.setdefault(e["idea"], []).append(e)
    idea_keys = sorted(by_idea, key=lambda k: (-len(by_idea[k]), k))

    lines = [
        "# Spec Index",
        "",
        f"> {total} specs ({status_summary}). Grouped by parent idea.",
        f"> Read frontmatter (`limit=30`) for source files, requirements, done_when.",
        ">",
        "> Auto-generated by `scripts/generate_repo_indexes.py`. The essence",
        "> after each spec slug is parsed from the spec's H1 line",
        "> (`# Title — essence`); edit that line to update the description.",
        "",
        f"## By Idea ({len(by_idea)} ideas → {total} specs)",
        "",
    ]
    for idea in idea_keys:
        idea_entries = sorted(by_idea[idea], key=lambda e: e["slug"])
        lines.append(f"### {idea} ({len(idea_entries)} spec{'s' if len(idea_entries) != 1 else ''})")
        for e in idea_entries:
            essence = e["essence"]
            tail = f" — {essence}" if essence else ""
            lines.append(f"- [{e['slug']}]({e['slug']}.md){tail}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _spec_field(text: str, key: str) -> str:
    """Pull a top-level scalar from the spec's YAML frontmatter."""
    head, *rest = text.split("---", 2)
    if not rest:
        return ""
    fm = rest[0] if len(rest) == 1 else rest[0]
    m = re.search(rf"^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", fm, re.MULTILINE)
    if not m:
        return ""
    val = m.group(1).strip().strip('"').strip("'")
    return val


def _spec_essence(text: str) -> str:
    """Pull the essence after the em-dash in the first H1.

    `# Spec Title — essence phrase` → "essence phrase". When no em-dash
    is present, falls back to the H1 minus the leading hash. Skips the
    YAML frontmatter so YAML comments (`# ...`) inside it don't get
    mistaken for the title.
    """
    head, *rest = text.split("---", 2)
    body = rest[1] if len(rest) >= 2 else text
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("# "):
            continue
        title = line[2:].strip()
        # Common prefix the body uses; the slug already carries this.
        for prefix in ("Spec: ", "spec: "):
            if title.startswith(prefix):
                title = title[len(prefix):].strip()
                break
        for sep in (" — ", " – ", " - "):
            if sep in title:
                return title.split(sep, 1)[1].strip()
        return title
    return ""


def write_or_check(path: Path, content: str, check: bool) -> bool:
    """Write content to path. Returns True if the file changed (or would change in --check)."""
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing == content:
        return False
    if check:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true", help="exit 1 if any INDEX would change")
    args = p.parse_args()

    target_data: list[tuple[str, Path, list[Path]]] = []
    changed = []

    for rel_dir, glob, label in TARGETS:
        dir_path = REPO_ROOT / rel_dir
        if not dir_path.exists():
            continue
        files = list_files(dir_path, glob)
        target_data.append((label, dir_path, files))

        index_path = dir_path / "INDEX.md"
        content = render_index(label, dir_path, files)
        if write_or_check(index_path, content, args.check):
            changed.append(str(index_path.relative_to(REPO_ROOT)))

    specs_index_path = REPO_ROOT / "specs" / "INDEX.md"
    specs_index = render_specs_index()
    if specs_index and write_or_check(specs_index_path, specs_index, args.check):
        changed.append("specs/INDEX.md")

    manifest_path = REPO_ROOT / "MANIFEST.md"
    manifest = render_manifest(target_data)
    if write_or_check(manifest_path, manifest, args.check):
        changed.append("MANIFEST.md")

    if args.check:
        if changed:
            print("Stale indexes (run `python3 scripts/generate_repo_indexes.py`):")
            for c in changed:
                print(f"  {c}")
            return 1
        print("All indexes up to date.")
        return 0

    if changed:
        print(f"Updated {len(changed)} index file(s):")
        for c in changed:
            print(f"  {c}")
    else:
        print("All indexes already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
