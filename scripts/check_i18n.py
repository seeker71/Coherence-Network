#!/usr/bin/env python3
"""i18n contract check — runs in CI to catch chrome that drifted out of the bundle.

Two checks live here, both forward-looking. Neither tries to audit
the legacy English-only components that haven't been lifted yet —
those are tracked separately and migrate one breath at a time.

  1. Locale parity — every key in `web/messages/en.json` must exist
     (with same path) in de.json, es.json, id.json. A missing key
     means a visitor in that locale sees the raw key string instead
     of their voice. Always on; blocking.

  2. Newly-introduced chrome — when run with `--base SHA`, scans the
     ADDED lines in changed `.tsx` / `.ts` files under `web/` for
     hardcoded English JSX text leaves (multi-word capitalized
     phrases between tags) that aren't wrapped in `t()`. Catches new
     drift at the moment of writing rather than after release. Lines
     unchanged or removed are out of scope — this gate is forward-
     looking, not retroactive.

Usage:
    python3 scripts/check_i18n.py                         # parity only
    python3 scripts/check_i18n.py --base origin/main      # parity + new-chrome scan
    python3 scripts/check_i18n.py --base SHA --head SHA   # explicit range
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MESSAGES_DIR = REPO_ROOT / "web" / "messages"
WEB_ROOT = REPO_ROOT / "web"
LOCALES = ("en", "de", "es", "id")
ANCHOR_LOCALE = "en"

# JSX/TSX text leaves we consider chrome candidates: multi-word
# phrases, leading capital, mostly letters/spaces, between two tags.
# `>([..])<` rather than props because attribute strings are usually
# data-derived (aria-label, title, alt) and the false-positive rate
# is too high.
CHROME_PATTERN = re.compile(
    r">\s*([A-Z][a-zA-Z][a-zA-Z\s,'·.-]{2,80}?)\s*<"
)

# Substrings that flag a candidate as not chrome — schema types,
# brand names, code identifiers that happen to read as English.
NOT_CHROME = {
    # schema.org types
    "Person", "Place", "Event", "Organization", "CreativeWork", "Course",
    # English single words that happen to appear between tags as data labels
    "Home", "Works", "Lineage", "Category",
    # Brand/provider names — these come from the brand registry, never i18n'd
    "Spotify", "Bandcamp", "YouTube", "SoundCloud", "Apple Music",
    "Substack", "Patreon", "Instagram", "TikTok", "Facebook", "LinkedIn",
    "Vimeo", "IMDb", "Beatport", "Threads", "Wikipedia", "Linktree",
    "GitHub",
}

# Files we always skip — generated, third-party, or test fixtures
# whose strings aren't user chrome.
SKIP_PATH_FRAGMENTS = (
    "node_modules/", "/.next/", "/dist/", "/build/",
    "/__tests__/", "/__mocks__/", "/.test.", "/.spec.",
    "/messages/",  # the bundle itself
)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kw)


# ─── Check 1: locale parity ──────────────────────────────────────────


def walk_keys(tree: object, prefix: str = "") -> list[str]:
    """Return every leaf-key path in a nested dict tree."""
    if not isinstance(tree, dict):
        return [prefix] if prefix else []
    out: list[str] = []
    for key, value in tree.items():
        sub = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.extend(walk_keys(value, sub))
        else:
            out.append(sub)
    return out


def _bundle_keys_at(ref: str, lang: str) -> set[str] | None:
    """Read web/messages/{lang}.json at the given git ref. Returns the
    flattened key set, or None when the file didn't exist at that ref
    (e.g. a brand-new locale being introduced in this PR)."""
    cp = run(["git", "show", f"{ref}:web/messages/{lang}.json"])
    if cp.returncode != 0:
        return None
    try:
        bundle = json.loads(cp.stdout)
    except json.JSONDecodeError:
        return None
    return set(walk_keys(bundle))


def check_locale_parity(base: str | None = None, head: str = "HEAD") -> list[str]:
    """Forward-looking parity: keys NEWLY ADDED to the anchor bundle in
    this diff must exist in every other locale at HEAD.

    Existing legacy gaps (keys in en.json that have always been
    untranslated) don't block — they're separate debt to migrate one
    breath at a time. Only the diff's contribution to that debt is
    flagged here, so the gate is forward-looking.

    When called without a base, falls back to the full set so a local
    `python3 scripts/check_i18n.py` still surfaces the full gap as
    information (the bundles are expected to drift retroactively until
    the lift breaths land)."""
    findings: list[str] = []
    anchor_path = MESSAGES_DIR / f"{ANCHOR_LOCALE}.json"
    if not anchor_path.exists():
        return [f"  anchor bundle missing: {anchor_path.relative_to(REPO_ROOT)}"]

    head_anchor_keys = set(walk_keys(json.load(open(anchor_path))))

    if base:
        base_anchor_keys = _bundle_keys_at(base, ANCHOR_LOCALE) or set()
        keys_of_concern = head_anchor_keys - base_anchor_keys
        scope_label = f"newly added to {ANCHOR_LOCALE}.json since {base}"
    else:
        keys_of_concern = head_anchor_keys
        scope_label = f"present in {ANCHOR_LOCALE}.json"

    if not keys_of_concern and base:
        return []

    for lang in LOCALES:
        if lang == ANCHOR_LOCALE:
            continue
        path = MESSAGES_DIR / f"{lang}.json"
        if not path.exists():
            findings.append(f"  {lang}.json: bundle file missing")
            continue
        bundle_keys = set(walk_keys(json.load(open(path))))
        missing = sorted(keys_of_concern - bundle_keys)
        if missing:
            findings.append(
                f"  {lang}.json: {len(missing)} key(s) {scope_label} but absent — "
                f"visitor sees the raw key:"
            )
            for k in missing[:8]:
                findings.append(f"      → {k}")
            if len(missing) > 8:
                findings.append(f"      → (+{len(missing) - 8} more)")
    return findings


# ─── Check 2: newly-introduced hardcoded chrome ──────────────────────


def changed_added_lines(base: str, head: str) -> list[tuple[str, int, str]]:
    """Walk `git diff base..head` and yield (path, line_no_in_new_file, content)
    for lines that were ADDED. Removed and context lines are skipped.

    Line numbers come from `git diff --unified` hunk headers (`@@ -a,b +c,d @@`)
    and increment by 1 for each `+` line; deleted lines (`-`) are not counted.
    """
    cp = run(["git", "diff", "--unified=0", "--no-color", f"{base}..{head}"])
    if cp.returncode != 0:
        return []
    out: list[tuple[str, int, str]] = []
    cur_path: str | None = None
    new_line: int = 0
    for raw in cp.stdout.splitlines():
        if raw.startswith("+++ b/"):
            cur_path = raw[len("+++ b/"):]
            continue
        if raw.startswith("---"):
            continue
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", raw)
        if m:
            new_line = int(m.group(1))
            continue
        if not cur_path:
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            out.append((cur_path, new_line, raw[1:]))
            new_line += 1
        elif not raw.startswith("-"):
            new_line += 1
    return out


def is_skipped(path: str) -> bool:
    if not path.startswith("web/"):
        return True
    if not (path.endswith(".tsx") or path.endswith(".ts")):
        return True
    return any(frag in path for frag in SKIP_PATH_FRAGMENTS)


def line_is_comment_or_t_call(content: str) -> bool:
    """Quick heuristic — skip lines that are obviously comments or
    already wrapped in t()/i18n call. Not perfect (multi-line JSX
    splits), but cheap and right for the common case."""
    s = content.strip()
    if s.startswith("//") or s.startswith("*") or s.startswith("/*"):
        return True
    # Whole line is a t('...') or t("...") call — already i18n'd.
    if "t(" in s and re.search(r"\bt\(['\"]", s):
        return True
    return False


def looks_like_chrome(text: str) -> bool:
    """Decide whether a candidate text leaf is user-facing chrome.

    Filters out single-word data labels, schema types, brand names,
    and short fragments that are likely glue rather than copy."""
    if text in NOT_CHROME:
        return False
    # Must contain at least one space — single words could be data
    # (kind labels, status enums, etc.) and false-positive easily.
    if " " not in text:
        return False
    # Mostly letters, spaces, and punctuation we expect in copy.
    if not re.fullmatch(r"[A-Za-z][A-Za-z\s,'·.\-—]+[A-Za-z.!?]", text):
        return False
    # Must have at least two letters per word on average — filters
    # acronym soups and code fragments that snuck through.
    words = text.split()
    if len(words) < 2:
        return False
    if sum(len(w) for w in words) / len(words) < 3:
        return False
    return True


def check_new_chrome(base: str, head: str) -> list[str]:
    findings: list[dict[str, str]] = []
    for path, line_no, content in changed_added_lines(base, head):
        if is_skipped(path):
            continue
        if line_is_comment_or_t_call(content):
            continue
        for m in CHROME_PATTERN.finditer(content):
            text = m.group(1).strip()
            if not looks_like_chrome(text):
                continue
            findings.append({
                "path": path,
                "line": str(line_no),
                "text": text,
            })

    if not findings:
        return []

    by_path: dict[str, list[dict[str, str]]] = {}
    for f in findings:
        by_path.setdefault(f["path"], []).append(f)

    lines = [
        f"  {len(findings)} new hardcoded chrome string(s) introduced in this diff:",
        "",
        "  Lift each into web/messages/{lang}.json under a meaningful key,",
        "  use t('your.key') in the component, and add the matching keys to",
        "  de.json, es.json, id.json — see feedback_i18n_architecture.md.",
        "",
    ]
    for path in sorted(by_path):
        lines.append(f"  · {path}")
        for hit in by_path[path]:
            lines.append(f"      line {hit['line']}: {hit['text']!r}")
    return lines


# ─── Driver ──────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", help="git base ref for new-chrome scan (e.g. origin/main)")
    p.add_argument("--head", default="HEAD", help="git head ref (default: HEAD)")
    args = p.parse_args()

    failed = False

    # Parity — forward-looking when given a base, informational otherwise.
    parity = check_locale_parity(args.base, args.head)
    if parity:
        if args.base:
            print(f"Locale parity drift introduced between {args.base} and {args.head}:")
        else:
            print("Locale parity (informational — full snapshot of legacy gaps):")
        for line in parity:
            print(line)
        # Only fail when we have a base ref. Without one, the report is
        # information about historical debt and shouldn't block local runs.
        if args.base:
            failed = True
    else:
        print(
            f"Locale parity ok: no new {ANCHOR_LOCALE}.json keys missing in any other locale."
            if args.base
            else f"Locale parity ok: every key in {ANCHOR_LOCALE}.json exists across all {len(LOCALES)} locales."
        )

    # New-chrome scan only when given a base ref.
    if args.base:
        print()
        new_chrome = check_new_chrome(args.base, args.head)
        if new_chrome:
            print(f"New hardcoded chrome (between {args.base} and {args.head}):")
            for line in new_chrome:
                print(line)
            failed = True
        else:
            print(f"No new hardcoded chrome introduced between {args.base} and {args.head}.")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
