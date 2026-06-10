#!/usr/bin/env python3
"""Wellness check — a gentle sensing of the body.

Surfaces drift between what the orientation documents claim and what the
filesystem actually holds. Finds files at visible locations that nothing
reaches for. Reports composting progress on known draft trails.

Run: make wellness   (or)   python3 scripts/wellness_check.py

Not an audit. A felt-sense reading. The body stays supple through
continuous tending — this tool is how we notice where tending is needed
without having to stumble over it.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files at root that are meant to be there even without incoming refs.
# Config, tooling, canonical orientation, license-style docs.
ROOT_EXEMPT = {
    "CLAUDE.md",
    "AGENTS.md",
    "AGENT.md",
    "README.md",
    "README.template.md",
    "CONTRIBUTING.md",
}


def count_files(dir_name: str, exclude: set[str]) -> int:
    d = ROOT / dir_name
    if not d.is_dir():
        return 0
    return sum(1 for p in d.glob("*.md") if p.name not in exclude)


def read_first_match(path: Path, pattern: str) -> int | None:
    if not path.exists():
        return None
    m = re.search(pattern, path.read_text())
    return int(m.group(1)) if m else None


def git_grep_refs(name: str) -> list[str]:
    """Files that mention `name`, excluding itself and known noise dirs."""
    r = subprocess.run(
        ["git", "grep", "-l", "--no-color", name, "--",
         "*.md", "*.py", "*.ts", "*.tsx", "*.sh", "*.json",
         "*.yml", "*.yaml", "Makefile", "*.toml"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    return [line for line in r.stdout.splitlines() if line and line != name]


def sense_proprioception() -> list[str]:
    findings = []

    # specs/INDEX.md
    actual = count_files("specs", {"INDEX.md", "TEMPLATE.md"})
    claimed = read_first_match(ROOT / "specs" / "INDEX.md", r"(\d+)\s+specs\s+\(")
    if claimed is None:
        findings.append("  specs/INDEX.md — count pattern not found; cannot verify")
    elif claimed == actual:
        findings.append(f"  specs/INDEX.md — aligned ({actual} specs)")
    else:
        findings.append(f"  specs/INDEX.md — drift: INDEX claims {claimed}, body has {actual}")

    # ideas/INDEX.md — "N super-ideas"
    actual_i = count_files("ideas", {"INDEX.md"})
    claimed_i = read_first_match(ROOT / "ideas" / "INDEX.md", r"(\d+)\s+super-ideas")
    if claimed_i is None:
        findings.append("  ideas/INDEX.md — count pattern not found; cannot verify")
    elif claimed_i == actual_i:
        findings.append(f"  ideas/INDEX.md — aligned ({actual_i} super-ideas)")
    else:
        findings.append(f"  ideas/INDEX.md — drift: INDEX claims {claimed_i}, body has {actual_i}")

    # vision-kb/INDEX.md concept count
    # Exclude language variants (lc-name.lang.md) from the concept tally —
    # translations are the same concept in another voice, not separate concepts.
    vkb_concepts_dir = ROOT / "docs" / "vision-kb" / "concepts"
    if vkb_concepts_dir.is_dir():
        actual_c = sum(
            1 for p in vkb_concepts_dir.glob("*.md")
            if p.name.count(".") == 1  # lc-foo.md has one dot; lc-foo.de.md has two
        )
        claimed_c = read_first_match(
            ROOT / "docs" / "vision-kb" / "INDEX.md",
            r"\*\*Concepts\*\*:\s*(\d+)",
        )
        if claimed_c is None:
            findings.append("  vision-kb/INDEX.md — concept count pattern not found")
        elif claimed_c == actual_c:
            findings.append(f"  vision-kb/INDEX.md — aligned ({actual_c} concepts)")
        else:
            findings.append(
                f"  vision-kb/INDEX.md — drift: INDEX claims {claimed_c}, body has {actual_c}"
            )

    return findings


def sense_circulation() -> list[str]:
    """Root-level .md files with no incoming references."""
    findings = []
    for p in sorted(ROOT.glob("*.md")):
        if p.name in ROOT_EXEMPT:
            continue
        refs = git_grep_refs(p.name)
        if not refs:
            findings.append(f"  {p.name} — no readers")
    if not findings:
        findings.append("  root is clear; every .md has circulation")
    return findings


def sense_metabolism() -> list[str]:
    """Progress on known draft trails."""
    findings = []
    drafts = sorted(ROOT.glob("docs/LIVING_COLLECTIVE_*.md"))
    if not drafts:
        findings.append("  no LIVING_COLLECTIVE_*.md drafts remain at top of docs/")
    else:
        total_lines = sum(sum(1 for _ in p.open()) for p in drafts)
        findings.append(f"  {len(drafts)} drafts remain — {total_lines} lines awaiting home")
        for p in drafts:
            lines = sum(1 for _ in p.open())
            findings.append(f"    · {p.name} ({lines} lines)")
    return findings


def sense_spec_sources() -> list[str]:
    """Do the paths spec frontmatter 'source:' points at actually exist?

    Missing paths are signal, not failure. Draft specs are forward
    projections — their source paths name files that haven't been
    written yet, so we skip them here (the draft status itself is the
    acknowledgement). Active and done specs are where missing paths
    are real drift worth surfacing.
    """
    findings: list[dict[str, str]] = []
    specs_dir = ROOT / "specs"
    if not specs_dir.is_dir():
        return ["  specs/ directory not found"]

    for spec in sorted(specs_dir.glob("*.md")):
        if spec.name in ("INDEX.md", "TEMPLATE.md"):
            continue
        text = spec.read_text()
        # Truncate scan to the frontmatter section (between first two '---' lines)
        head, *rest = text.split("---", 2)
        if not rest:
            continue
        frontmatter = rest[0] if len(rest) == 1 else rest[0]
        # Skip draft specs — they describe future work; missing paths
        # are intentional, not drift.
        status_m = re.search(r"^\s*status\s*:\s*(\S+)", frontmatter, re.MULTILINE)
        status = (status_m.group(1).strip().strip('"').strip("'") if status_m else "").lower()
        if status == "draft":
            continue
        for m in re.finditer(r"^\s*-\s*file:\s*(\S+)", frontmatter, re.MULTILINE):
            path = m.group(1).strip()
            if path.startswith("..") or "://" in path or path.startswith("specs/"):
                continue
            if not (ROOT / path).exists():
                findings.append({"spec": spec.name, "path": path})

    if not findings:
        return ["  every spec's source: paths point at files that exist"]

    by_spec: dict[str, list[str]] = {}
    for f in findings:
        by_spec.setdefault(f["spec"], []).append(f["path"])

    lines = [
        f"  {len(findings)} source paths missing across {len(by_spec)} spec(s)"
    ]
    for spec_name in sorted(by_spec):
        paths = by_spec[spec_name]
        lines.append(f"    · {spec_name} — {len(paths)} missing")
        for p in paths[:3]:
            lines.append(f"      → {p}")
        if len(paths) > 3:
            lines.append(f"      → (+{len(paths) - 3} more)")
    return lines


def sense_spec_symbols() -> list[str]:
    """Do the symbols spec frontmatter claims still resolve in their files?

    The companion to sense_spec_sources. That lens catches missing files;
    this catches the quieter drift: a spec frontmatter says
    ``source: file: api/app/services/foo.py / symbols: [bar()]``,
    the file is still there, but ``bar()`` has been renamed,
    deleted, or moved. The body's claim aged silently.

    Symbols are matched against common Python, TypeScript, and Form declaration
    shapes (def, class, async def, top-level assignment, export
    function/class/const/type/interface). Identifiers that don't match
    a real-looking name pattern are skipped — many spec frontmatters
    use prose-shaped entries inside ``symbols: [...]`` ("error_summary,
    error_category fields") that aren't single identifiers.

    Drafts skipped (forward projections). Missing paths skipped (those
    are caught by sense_spec_sources). This lens speaks only to symbol
    resolution inside files that exist.
    """
    specs_dir = ROOT / "specs"
    if not specs_dir.is_dir():
        return ["  specs/ directory not found"]

    # Matches `- file: path` followed (within the next few lines)
    # by `symbols: [...]`. Anchored to start of line so we don't catch
    # source: lines from prose elsewhere in the frontmatter.
    src_pattern = re.compile(
        r"^\s*-\s*file:\s*(\S+)\s*\n\s*symbols:\s*\[(.*?)\]",
        re.MULTILINE | re.DOTALL,
    )
    # Strict identifier shape — skip prose-y entries like "GovernanceHealth fields"
    ident_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def _symbol_resolves(text: str, sym: str) -> bool:
        # Common declaration shapes across Python, TS, Form, and Rust.
        # Note: every `export` form admits `default` between `export` and
        # the keyword — Next.js page components use that convention
        # (`export default function Home() {...}`); the body has dozens
        # of pages that name their default export this way. Without
        # `default` in the alternation, the lens would fire false-positive
        # drifts for every named default export.
        #
        # Rust patterns follow the same shape: optional visibility
        # (`pub`, `pub(crate)`, `pub(super)`), optional `unsafe`/`async`,
        # then the keyword. Generics (`<T: Trait>`) live after the
        # identifier and don't affect the match — patterns end with
        # `\b` after `sym`, so `pub struct Tracked<T: TrackedPrimitive>`
        # resolves as cleanly as `pub struct Tracked`.
        patterns = [
            rf"\bdef\s+{re.escape(sym)}\b",            # python function
            rf"\bclass\s+{re.escape(sym)}\b",          # python class
            rf"\basync\s+def\s+{re.escape(sym)}\b",    # async python function
            rf"\bexport\s+(?:default\s+)?(?:async\s+)?function\s+{re.escape(sym)}\b",
            rf"\bexport\s+(?:default\s+)?(?:async\s+)?(?:const|let|var)\s+{re.escape(sym)}\b",
            rf"\bexport\s+(?:default\s+)?class\s+{re.escape(sym)}\b",
            rf"\bexport\s+(?:type|interface)\s+{re.escape(sym)}\b",
            # TS/JS non-exported declarations. `function` is a reserved
            # word so it doesn't appear in prose as a definition marker;
            # the `function`-keyword match is safe without `export`.
            # `const`/`let`/`var` are anchored to line-start (with
            # optional indentation) so the match stays close to
            # module-scope shape and doesn't fire on parameter lists
            # or deeply-nested locals.
            rf"\b(?:async\s+)?function\s+{re.escape(sym)}\b",
            rf"^\s*(?:const|let|var)\s+{re.escape(sym)}\s*[:=]",
            rf"^\s*form\s+{re.escape(sym)}\b",         # Form shape
            rf"^\s*defn\s+{re.escape(sym)}\b",         # Form definition
            # Rust — struct, enum, trait, type alias, fn, union, macro
            rf"\b(?:pub(?:\([^)]+\))?\s+)?(?:unsafe\s+)?(?:async\s+)?fn\s+{re.escape(sym)}\b",
            rf"\b(?:pub(?:\([^)]+\))?\s+)?struct\s+{re.escape(sym)}\b",
            rf"\b(?:pub(?:\([^)]+\))?\s+)?enum\s+{re.escape(sym)}\b",
            rf"\b(?:pub(?:\([^)]+\))?\s+)?trait\s+{re.escape(sym)}\b",
            rf"\b(?:pub(?:\([^)]+\))?\s+)?type\s+{re.escape(sym)}\b",
            rf"\b(?:pub(?:\([^)]+\))?\s+)?union\s+{re.escape(sym)}\b",
            rf"\bmacro_rules!\s+{re.escape(sym)}\b",
            rf"^\s*(?:function\s+)?{re.escape(sym)}\s*\(\)\s*\{{",  # shell function
            rf"^{re.escape(sym)}\s*[:=]",              # top-level assignment / type alias
            rf"\b{re.escape(sym)}\s*=\s*\(",           # arrow function / lambda binding
        ]
        return any(re.search(p, text, re.MULTILINE) for p in patterns)

    drift_by_spec: dict[str, list[tuple[str, str]]] = {}
    pending_by_spec: dict[str, list[tuple[str, str]]] = {}
    specs_with_symbol_claims = 0
    symbols_checked = 0

    for spec in sorted(specs_dir.glob("*.md")):
        if spec.name in ("INDEX.md", "TEMPLATE.md", "MANIFEST.md"):
            continue
        text = spec.read_text()
        head, *rest = text.split("---", 2)
        if not rest:
            continue
        fm = rest[0] if len(rest) == 1 else rest[0]
        status_m = re.search(r"^\s*status\s*:\s*(\S+)", fm, re.MULTILINE)
        status = (status_m.group(1).strip().strip('"').strip("'") if status_m else "").lower()
        if status == "draft":
            continue

        # status=active spec convention: source: may list target symbols
        # (what WILL exist when done) alongside shipped ones. Unresolved
        # symbols in active specs are "pending implementation" — honest
        # signal of in-progress work, not drift between spec and code.
        # status=done specs (or unclassified) are where unresolved
        # symbols mean the spec's claim genuinely drifted from reality.
        is_active = status == "active"

        spec_had_claims = False
        for m in src_pattern.finditer(fm):
            path = m.group(1).strip()
            if path.startswith("..") or "://" in path or path.startswith("specs/"):
                continue
            file_path = ROOT / path
            if not file_path.exists():
                # sense_spec_sources handles missing-file drift.
                continue
            raw_symbols = m.group(2)
            # Strip () call shape, quotes, surrounding whitespace.
            candidates = [s.strip().strip("'\"") for s in raw_symbols.split(",")]
            candidates = [re.sub(r"\(.*", "", s).strip() for s in candidates]
            # Keep only identifier-shaped entries.
            candidates = [s for s in candidates if ident_re.match(s)]
            if not candidates:
                continue
            spec_had_claims = True
            try:
                file_text = file_path.read_text()
            except Exception:
                continue
            for sym in candidates:
                symbols_checked += 1
                if not _symbol_resolves(file_text, sym):
                    bucket = pending_by_spec if is_active else drift_by_spec
                    bucket.setdefault(spec.stem, []).append((path, sym))

        if spec_had_claims:
            specs_with_symbol_claims += 1

    if not drift_by_spec and not pending_by_spec:
        return [
            f"  every claimed symbol resolves in its file ({symbols_checked} symbols "
            f"across {specs_with_symbol_claims} spec(s) checked)"
        ]

    lines: list[str] = []

    if drift_by_spec:
        total_drifts = sum(len(v) for v in drift_by_spec.values())
        lines.append(
            f"  {total_drifts} symbol claim(s) do not resolve across {len(drift_by_spec)} spec(s) "
            f"(of {specs_with_symbol_claims} with symbol claims · {symbols_checked} symbols checked)"
        )
        for spec_name in sorted(drift_by_spec)[:3]:
            items = drift_by_spec[spec_name]
            first = items[0]
            lines.append(f"    · {spec_name} — `{first[1]}` not found in {first[0]}")
            if len(items) > 1:
                lines.append(f"      (+{len(items) - 1} more in this spec)")
        if len(drift_by_spec) > 3:
            lines.append(f"    · (+{len(drift_by_spec) - 3} more specs with symbol drift)")
        lines.append(
            "  (Drift here is signal, not failure. A renamed function is the body "
            "evolving; the spec's claim wants the same breath.)"
        )

    if pending_by_spec:
        if lines:
            lines.append("")
        total_pending = sum(len(v) for v in pending_by_spec.values())
        lines.append(
            f"  {total_pending} target symbol(s) pending across {len(pending_by_spec)} active spec(s) "
            "— active work whose source: lists what will exist when done"
        )
        for spec_name in sorted(pending_by_spec)[:3]:
            items = pending_by_spec[spec_name]
            first = items[0]
            lines.append(f"    · {spec_name} — `{first[1]}` not yet in {first[0]}")
            if len(items) > 1:
                lines.append(f"      (+{len(items) - 1} more pending in this spec)")
        if len(pending_by_spec) > 3:
            lines.append(
                f"    · (+{len(pending_by_spec) - 3} more active specs with pending symbols)"
            )

    if not drift_by_spec and pending_by_spec:
        # Only active-spec pending exists — name the clean ground line up top
        lines.insert(
            0,
            f"  every claimed symbol resolves in done/inactive specs ({symbols_checked} symbols "
            f"across {specs_with_symbol_claims} spec(s) checked)",
        )

    return lines


def sense_locale_parity() -> list[str]:
    """Do the body's voice speak the same body in every tongue?

    The web body speaks through every ``web/messages/{lang}.json``
    translation file. The current default bundle is the canonical source —
    new chrome strings, copy refinements, and new sections land there first
    and are mirrored into the installed locale bundles. When that mirroring
    lags, a visitor sees half the page in their language and half falling back
    to the default locale mid-sentence.

    This lens compares the key set of each locale to the default bundle,
    surfacing:
      · missing keys (the default bundle has strings the locale doesn't)
      · extra keys (locale carries strings the default bundle no longer has)

    Drift is signal, not failure. A locale at 99% parity with three
    extras is a body recently moving; a locale at 70% is a body
    bilingual in name only. The number speaks; the body chooses what
    to do with it.
    """
    # Substrate-altitude companion: form/form-stdlib/i18n-parity.fk
    # reaches the same per-locale leaf counts through (i18n-load → recursive
    # node_category walk). Python stays the runtime reporter; Form proves
    # the corpus is reachable from substrate without the Python boundary.
    messages_dir = ROOT / "web" / "messages"
    if not messages_dir.is_dir():
        return ["  web/messages/ directory not found"]

    en_path = messages_dir / "en.json"
    if not en_path.exists():
        return ["  web/messages/en.json not found (no canonical source to compare to)"]

    import json

    def _flatten(d: dict, prefix: str = "") -> set[str]:
        keys: set[str] = set()
        for k, v in d.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys |= _flatten(v, path)
            else:
                keys.add(path)
        return keys

    try:
        en = json.loads(en_path.read_text())
    except Exception as e:
        return [f"  could not parse web/messages/en.json: {e}"]
    en_keys = _flatten(en)

    locales = sorted(p for p in messages_dir.glob("*.json") if p.stem != "en")
    if not locales:
        return ["  no non-en locales to compare"]

    lines = [f"  en holds {len(en_keys)} keys (canonical source)"]
    all_aligned = True
    for path in locales:
        try:
            data = json.loads(path.read_text())
        except Exception:
            lines.append(f"    · {path.stem}: could not parse")
            all_aligned = False
            continue
        keys = _flatten(data)
        missing = en_keys - keys
        extra = keys - en_keys
        if not missing and not extra:
            lines.append(f"    · {path.stem}: aligned ({len(keys)} keys)")
            continue
        all_aligned = False
        parity_pct = (1 - len(missing) / len(en_keys)) * 100 if en_keys else 100
        bits = []
        if missing:
            bits.append(f"{len(missing)} missing")
        if extra:
            bits.append(f"{len(extra)} extra")
        lines.append(
            f"    · {path.stem}: {len(keys)} keys · {parity_pct:.0f}% parity · {', '.join(bits)}"
        )

    if all_aligned:
        return [f"  every locale aligned with en ({len(en_keys)} keys, {len(locales)} tongues)"]

    return lines


def sense_locale_surfaces() -> list[str]:
    """Check that web, API, and CLI locale doors carry the same installed tongues."""
    script = ROOT / "scripts" / "validate_locale_surfaces.py"
    if not script.exists():
        return ["  scripts/validate_locale_surfaces.py not found"]
    result = subprocess.run(
        [sys.executable, str(script), "--summary"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode == 0 and output:
        return [f"  {output[0]}"]
    lines = ["  locale surface validation wants attention"]
    for line in output[:6]:
        lines.append(f"    {line}")
    if result.stderr.strip():
        lines.append(f"    stderr: {result.stderr.strip().splitlines()[0]}")
    return lines


def sense_chain() -> list[str]:
    """Sense the idea→spec→code→test chain at the segment everything
    else doesn't see: tests the spec claims to have but that don't exist.

    sense_spec_sources catches missing source files. This catches the
    quieter leak: a spec frontmatter declares `test: cd api && pytest
    tests/test_foo.py` and the spec proudly lives, but the test file
    never landed. The body acts as if it's tested when it isn't.

    Two legitimate proof shapes are honored:

      · ``test:`` — a runnable test command (the path it names must exist
        on disk for the proof to count)
      · ``proof: operational`` — the body proves this spec in production
        usage, not via unit tests. Used for specs whose substance is
        operationally exercised (GitHub-API integrations, deploy paths,
        live ledger flows) where a unit test would be theater. The
        spec's frontmatter may also carry ``proof_note: "..."`` to
        describe how the operational proof is observed.

    Drafts skipped (forward projections). Specs with neither a working
    ``test:`` nor a ``proof: operational`` declaration are noted softly
    as a separate count — *no proof claimed*.
    """
    specs_dir = ROOT / "specs"
    if not specs_dir.is_dir():
        return ["  specs/ directory not found"]

    # Match three shapes of test path:
    #   - api/tests/foo.py — explicit api-rooted
    #   - mcp-server/tests/foo.py — explicit mcp-server-rooted
    #   - tests/foo.py — bare, implicitly api/ (the common case)
    test_path_re = re.compile(r"\b(?:api/|mcp-server/)?tests/[\w/]+\.py")
    healthy = 0
    counted = 0  # non-draft specs we evaluated for chain reach
    missing_tests: dict[str, list[str]] = {}     # done/inactive — drift
    pending_tests: dict[str, list[str]] = {}     # active — work in progress
    no_test_declared: list[str] = []
    orphan_specs: list[str] = []
    operational_proof: list[str] = []  # specs honoring "proof: operational"
    duplicate_test_keys: list[str] = []  # YAML smell — two `test:` keys in one frontmatter

    for spec in sorted(specs_dir.glob("*.md")):
        if spec.name in ("INDEX.md", "TEMPLATE.md", "MANIFEST.md"):
            continue
        text = spec.read_text()
        head, *rest = text.split("---", 2)
        if not rest:
            continue
        fm = rest[0] if len(rest) == 1 else rest[0]
        status_m = re.search(r"^\s*status\s*:\s*(\S+)", fm, re.MULTILINE)
        status = (status_m.group(1).strip().strip('"').strip("'") if status_m else "").lower()
        if status == "draft":
            continue
        counted += 1

        # idea_id presence
        idea_m = re.search(r"^\s*idea_id\s*:\s*(\S+)", fm, re.MULTILINE)
        if not idea_m:
            orphan_specs.append(spec.stem)

        # Source path existence (any source: file: declared, all of them present?)
        src_paths = [m.group(1).strip() for m in re.finditer(r"^\s*-\s*file:\s*(\S+)", fm, re.MULTILINE)]
        src_paths = [p for p in src_paths if not p.startswith("..") and "://" not in p and not p.startswith("specs/")]
        src_ok = bool(src_paths) and all((ROOT / p).exists() for p in src_paths)

        # ``proof: operational`` is the second legitimate proof shape:
        # the spec is exercised in production rather than unit-tested.
        # When present, the spec's chain-reach counts as proven even if
        # no test: command is declared.
        proof_m = re.search(r"^\s*proof\s*:\s*(\S+)", fm, re.MULTILINE)
        proof_value = (proof_m.group(1).strip().strip('"').strip("'").lower() if proof_m else "")
        is_operational = proof_value == "operational"

        # test: declaration (string or list) — extract test paths from EVERY
        # `^test:` block. A YAML frontmatter with two `test:` keys (list form
        # followed by scalar, or vice versa) used to break the old single-shot
        # regex: it matched the first `test:` and stopped at the next
        # `^[a-z_]+:` line, which `test:` itself satisfies, leaving the captured
        # group empty. `findall` with a lookahead terminator concatenates all
        # `test:` block bodies, and the duplicate is surfaced as a soft warning.
        test_blocks = re.findall(
            r"^test\s*:(.*?)(?=\n[a-z_]+\s*:|^---|\Z)", fm, re.MULTILINE | re.DOTALL
        )
        if len(test_blocks) > 1:
            duplicate_test_keys.append(spec.stem)
        test_text = "\n".join(test_blocks)
        def _resolve_test_path(p: str) -> str:
            # Already explicit: leave alone (api/tests/... or mcp-server/tests/...)
            if p.startswith("api/") or p.startswith("mcp-server/"):
                return p
            # Bare tests/...py — prepend api/ as the implicit default.
            return f"api/{p}"

        test_paths = sorted(set(_resolve_test_path(p) for p in test_path_re.findall(test_text)))
        test_declared = bool(test_text.strip())
        if not test_declared and not is_operational:
            no_test_declared.append(spec.stem)
            continue
        miss = [t for t in test_paths if not (ROOT / t).exists()]
        if miss:
            # Active specs honestly list target tests before they're
            # written; report those as pending, not drift. Done/
            # inactive specs claiming missing tests are real drift.
            bucket = pending_tests if status == "active" else missing_tests
            bucket[spec.stem] = miss
            continue

        # Chain healthy if: idea_id present, source declared and present,
        # AND (tests declared and present) OR (proof: operational).
        if idea_m and src_ok and (
            (test_paths and not miss) or (is_operational and not test_declared)
        ):
            healthy += 1
            if is_operational:
                operational_proof.append(spec.stem)

    lines = [
        f"  chain healthy: {healthy}/{counted} non-draft specs reach idea→spec→code→test ({(healthy/counted*100) if counted else 0:.0f}%)"
    ]
    if missing_tests:
        lines.append(f"  {len(missing_tests)} done/inactive spec(s) claim a test that doesn't exist on disk")
        for slug in sorted(missing_tests)[:3]:
            miss = ", ".join(missing_tests[slug][:2])
            lines.append(f"    · {slug} — {miss}")
        if len(missing_tests) > 3:
            lines.append(f"    · (+{len(missing_tests) - 3} more)")
    if pending_tests:
        lines.append(
            f"  {len(pending_tests)} active spec(s) carry test paths not yet on disk — pending work"
        )
        for slug in sorted(pending_tests)[:3]:
            miss = ", ".join(pending_tests[slug][:2])
            lines.append(f"    · {slug} — {miss}")
        if len(pending_tests) > 3:
            lines.append(f"    · (+{len(pending_tests) - 3} more)")
    if operational_proof:
        lines.append(
            f"  {len(operational_proof)} spec(s) honor `proof: operational` — proven in production, not unit-tested"
        )
    if no_test_declared:
        lines.append(f"  {len(no_test_declared)} specs have no test: or proof: frontmatter (no proof claimed)")
    if orphan_specs:
        lines.append(f"  {len(orphan_specs)} orphan specs (no idea_id): {', '.join(orphan_specs)}")
    if duplicate_test_keys:
        sample = ", ".join(sorted(duplicate_test_keys)[:3])
        more = f" (+{len(duplicate_test_keys) - 3} more)" if len(duplicate_test_keys) > 3 else ""
        lines.append(
            f"  {len(duplicate_test_keys)} spec(s) carry duplicate `test:` keys — "
            f"deduplicate to one canonical form: {sample}{more}"
        )
    if not missing_tests and not pending_tests and not no_test_declared and not orphan_specs:
        lines.append("  chain reach is whole — every claim has its proof")
    return lines


def sense_form_engine() -> list[str]:
    """Does the meta-circular Form engine cover the Python dispatch?

    The Form-level evaluator in docs/coherence-substrate/form-engine.form
    walks Recipe NodeIDs via `match n.category { @l.t.i => ... }` arms.
    The Python evaluator in api/app/services/substrate/recipe_eval.py
    dispatches on `category.type_ == RBasic.<verb>`. Where Python has
    a verb and Form does not, the meta-circular promise is asymmetric:
    Python can run that recipe, the Form engine cannot.

    Reports the asymmetry. Each missing Form arm is one `@1.2.<t>.<i>`
    arm in form-engine.form away from symmetric — not a failure.
    """
    engine_path = ROOT / "docs" / "coherence-substrate" / "form-engine.form"
    eval_path = ROOT / "api" / "app" / "services" / "substrate" / "recipe_eval.py"
    cat_path = ROOT / "api" / "app" / "services" / "substrate" / "category.py"
    if not (engine_path.is_file() and eval_path.is_file() and cat_path.is_file()):
        return ["  (form-engine artifacts not present; skipping)"]

    cat_src = cat_path.read_text()
    rbasic_match = re.search(r"class RBasic\(IntEnum\):.*?(?=\nclass |\Z)", cat_src, re.DOTALL)
    if not rbasic_match:
        return ["  (could not parse RBasic from category.py)"]
    int_to_name: dict[int, str] = {}
    for name, val in re.findall(r"^\s+([A-Z_]+)\s*=\s*(\d+)", rbasic_match.group(0), re.MULTILINE):
        if name != "UNDEFINED":
            int_to_name[int(val)] = name
    name_to_int = {v: k for k, v in int_to_name.items()}

    form_src = engine_path.read_text()
    block_match = re.search(r"# >>> BEGIN engine\n(.*?)\n# >>> END engine", form_src, re.DOTALL)
    if not block_match:
        return ["  (form-engine.form has no BEGIN/END engine markers)"]
    engine_block = block_match.group(0)
    form_arm_types: set[int] = set()
    for _p, level, t, _i in re.findall(r"@(\d+)\.(\d+)\.(\d+)\.(\d+)", engine_block):
        if int(level) == 2:
            form_arm_types.add(int(t))

    eval_src = eval_path.read_text()
    python_branch_types: set[int] = set()
    for name in re.findall(r"category\.type_\s*==\s*RBasic\.([A-Z_]+)", eval_src):
        if name in name_to_int:
            python_branch_types.add(name_to_int[name])

    if not python_branch_types:
        return ["  (recipe_eval.py exposes no RBasic dispatch — skipping)"]

    covered = sorted(form_arm_types & python_branch_types)
    missing = sorted(python_branch_types - form_arm_types)
    extra = sorted(form_arm_types - python_branch_types)

    lines: list[str] = []
    lines.append(
        f"  meta-circular engine — Form arms cover {len(covered)}/{len(python_branch_types)} "
        f"Python dispatch branches"
    )
    if covered:
        lines.append("    · in Form: " + ", ".join(int_to_name[t] for t in covered))
    if missing:
        lines.append(
            "    · awaiting Form arms: " + ", ".join(int_to_name[t] for t in missing)
        )
    if extra:
        lines.append(
            "    · in Form but not Python: " + ", ".join(int_to_name[t] for t in extra)
        )
    if missing:
        lines.append(
            "  (Each missing arm is one `@1.2.<t>.<i>` row in form-engine.form away"
        )
        lines.append("   from symmetric. Asymmetry is signal, not failure.)")
    else:
        lines.append("  symmetric — Form covers every Python dispatch branch.")
    return lines


def sense_form_ontology() -> list[str]:
    """Does the Form-side ontology table agree with the kernel parsers?

    `form/form-stdlib/form-ontology.json` holds the canonical (name,
    type, inst) rows for parser-special-form primitives (add/gt/and/...)
    and composite shapes (do/let/if/fndef/...). The generated kernel
    `bp` table carries those coordinates, and form-stdlib/form-ontology-loader.fk
    materialises the Form-side bindings from that native table. Each
    kernel (Go/Rust/TS) has its own switch table in parseSexp/buildVerb.
    If a primitive is added to one but not the other, every test that
    doesn't happen to exercise it stays silent through the drift.

    Delegates to form/scripts/validate_form_ontology.py — the canonical
    drift reader. Silent on a clean match; surfaces the divergence
    otherwise.
    """
    script = ROOT / "form" / "scripts" / "validate_form_ontology.py"
    if not script.is_file():
        return ["  (form/scripts/validate_form_ontology.py not present; skipping)"]
    try:
        result = subprocess.run(
            ["python3", str(script)],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as exc:
        return [f"  (validate_form_ontology.py did not run cleanly: {exc})"]
    out = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        return ["  form ontology matches kernel parsers (Go/Rust/TS)"]
    lines = ["  ontology and kernel parsers have drifted:"]
    for line in out.splitlines():
        if line.strip():
            lines.append(f"    {line}")
    return lines


def sense_form_blueprints() -> list[str]:
    """Are Form's user-space Blueprint numbers legible, or scattered magic?

    Every shape the kernel does not dispatch on lives at NodeID (1, 2, 99, N).
    Historically these were allocated ad-hoc — the same number re-declared
    under a dozen local names with a raw `(make_nodeid 1 2 99 N)` in each
    grammar. form-stdlib/blueprint-registry.json now names each shape once;
    form-ontology-loader.fk binds them so `.fk` code asks by name via
    `(bp "name")`. This sense reads scripts/scan_form_blueprints.py: silent
    when no new unregistered number has crept in, loud when one has — the
    forward gate that keeps the sprawl from regrowing.
    """
    script = ROOT / "scripts" / "scan_form_blueprints.py"
    if not script.is_file():
        return ["  (scripts/scan_form_blueprints.py not present; skipping)"]
    try:
        result = subprocess.run(
            ["python3", str(script), "--check"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:
        return [f"  (scan_form_blueprints.py did not run cleanly: {exc})"]
    # First report line carries the legibility numbers; surface it always.
    head = next((ln for ln in result.stdout.splitlines()
                 if "make_nodeid" in ln), "").strip()
    if result.returncode == 0:
        lines = ["  every Form Blueprint number is registered — no magic sprawl"]
        if head:
            lines.append(f"    {head}")
        return lines
    lines = ["  unregistered Blueprint numbers have crept in:"]
    for line in (result.stdout + result.stderr).splitlines():
        if line.strip().startswith(("FAIL", "1.2.99")):
            lines.append(f"    {line.strip()}")
    return lines


def sense_form_primitives() -> list[str]:
    """Does every kernel native carry a declared spec and verification?

    form-stdlib/primitive-registry.fk declares (name, category, spec,
    verification recipe, expected outside, lane) for the whole sibling-parity
    native surface — the kernel-satsang ksat-part discipline applied to the
    primitives themselves. Lane-1 verifications run three-way in
    tests/primitive-registry-band.fk; lane-0 entries are carrier-declared
    (panic-contract, sockets, gc sweep, toolchain, sibling-gap) and this
    sense keeps that tail visible. Delegates to
    form/scripts/validate_primitive_registry.py — the canonical drift gate
    between registry and kernel source.
    """
    script = ROOT / "form" / "scripts" / "validate_primitive_registry.py"
    if not script.is_file():
        return ["  (form/scripts/validate_primitive_registry.py not present; skipping)"]
    try:
        result = subprocess.run(
            ["python3", str(script)],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:
        return [f"  (validate_primitive_registry.py did not run cleanly: {exc})"]
    lines: list[str] = []
    if result.returncode == 0:
        lines.append("  every kernel native carries a declared spec + verification recipe")
        for prefix in ("natives", "lanes", "sibling gaps", "band circulation"):
            for ln in result.stdout.splitlines():
                if ln.startswith(prefix):
                    lines.append(f"    {ln.strip()}")
                    break
        return lines
    lines.append("  the primitive registry and the kernel surface have drifted:")
    for ln in (result.stdout + result.stderr).splitlines():
        if ln.startswith("FAIL"):
            lines.append(f"    {ln.strip()}")
    return lines


METABOLIC_CATEGORY_RULES = [
    {
        "label": "source grammar/parser residue",
        "terms": (
            "parse", "parser", "token", "lexer", "grammar", "operator",
            "query", "render", "decompile", "speculation", "stream", "ast",
            "capture", "pattern",
        ),
        "path_terms": (
            "form_", "grammar", "lexer", "operators", "queries", "render",
            "decompile", "speculation", "stream",
        ),
        "release": (
            "move source scan, grammar, render, decompile, and checking into "
            "Form/BML rules with proof bands"
        ),
    },
    {
        "label": "recipe realization/runtime semantics",
        "terms": (
            "execute", "execution", "runtime", "eval", "evaluate", "walk",
            "frame", "closure", "recipe", "builtin", "inductive",
            "constructor", "choice", "quotient", "method",
        ),
        "path_terms": (
            "eval", "runtime", "recipe_eval", "parallel_eval", "inductive",
            "quotient",
        ),
        "release": (
            "serve these semantics through kernel-native realization, JIT "
            "plans, and Form-side engine cells"
        ),
    },
    {
        "label": "substrate identity/persistence infrastructure",
        "terms": (
            "nodeid", "node_id", "intern", "storage", "store", "database",
            "sqlite", "postgres", "sqlalchemy", "namedcell", "blueprint",
            "category", "atomic", "string", "persistence",
        ),
        "path_terms": ("orm", "kernel", "category", "substrate_strings"),
        "release": (
            "replace host storage helpers with a Form-native persistence "
            "contract and kernel-owned cell store"
        ),
    },
    {
        "label": "domain vocabulary/cell authoring",
        "terms": (
            "resonance", "modality", "lexicon", "relationship", "agent",
            "dimension", "edge", "vocabulary", "canonical", "author",
            "numeric", "format", "shape",
        ),
        "path_terms": (
            "resonance", "modality", "lexicon", "relationship",
            "numeric_formats",
        ),
        "release": (
            "lift repeated domain authoring patterns into domain grammars, "
            "BML handlers, or substrate cells"
        ),
    },
    {
        "label": "format/source frontend",
        "terms": (
            "markdown", "frontmatter", "document", "heading", "section",
            "parse", "render", "source", "frontend",
        ),
        "path_terms": ("markdown", "frontend"),
        "release": (
            "replace host frontends with BMF/BML format grammars and native "
            "emitters"
        ),
    },
    {
        "label": "observation/proof metabolism",
        "terms": (
            "sense", "surprise", "observe", "observation", "trace", "proof",
            "conformance", "attention", "telemetry", "metric", "parallel",
        ),
        "path_terms": ("sense", "surprise", "parallel", "check"),
        "release": (
            "feed observations into framebuffer/native proof cells so sensing "
            "is core metabolism, not a side channel"
        ),
    },
]


STATIC_TO_DYNAMIC_SURFACES = [
    {
        "path": "kernels/BOOTSTRAP_COMPOST_MANIFEST.md",
        "kind": "static release ledger",
        "successor": "substrate:compost-release-ledger-cells",
        "wants": (
            "substrate-backed compost cells for candidate admission, attested "
            "gate, live-consumer state, and release evidence"
        ),
        "resources": (
            "lets attention choose transmutation work by score/category/gate "
            "instead of hand-maintaining the whole candidate universe"
        ),
    },
    {
        "path": "kernels/PHASE_A_FIRING_QUESTIONS.md",
        "kind": "static firing-question narrative",
        "successor": "substrate:metabolic-attestation-cells",
        "wants": (
            "per-cell metabolic attestation records linked to classifier "
            "signals, successor path, and proof command"
        ),
        "resources": (
            "turns manual narrative walks into validations that can be queued, "
            "diffed, and repeated"
        ),
    },
    {
        "path": "docs/shared/agent-start-packet.md",
        "kind": "static compressed agent memory",
        "successor": "substrate:generated-agent-start-packet",
        "wants": (
            "generated start packet sections sourced from live substrate, "
            "wellness, route state, and release ledgers"
        ),
        "resources": (
            "keeps new agents oriented without hand-refreshing long-lived memory"
        ),
    },
    {
        "path": "docs/system_audit/native_route_goal_state.json",
        "kind": "static route-promotion snapshot",
        "successor": "substrate:native-route-goal-cells",
        "wants": (
            "route-goal cells fed by runtime events, BML/front-door catalogs, "
            "and promotion proof state"
        ),
        "resources": (
            "routes attention to the next high-traffic native handler without "
            "treating a JSON snapshot as the living queue"
        ),
    },
]

STATIC_SIGNAL_TERMS = (
    "static",
    "ledger",
    "manifest",
    "readiness map",
    "hand-written",
    "table view",
    "snapshot",
    "manual",
    "hardcoded",
    "fixed",
)


def _count_file_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("rb"))
    except OSError:
        return 0


def _path_term_matches(term: str, rel_lower: str) -> bool:
    stem = Path(rel_lower).stem
    if term.endswith("_"):
        return stem.startswith(term)
    path_words = set(re.findall(r"[a-z0-9]+", rel_lower.replace("_", " ")))
    stem_words = set(stem.split("_"))
    return term == stem or term in path_words or term in stem_words


def _metabolic_category_for_file(
    rel: str,
    path: Path,
) -> tuple[str, str, int, Counter[str]]:
    """Classify a file-cell from repeated lexical/path signals.

    This is deliberately transparent rather than clever: repeated words are
    edge attributes with numeric weight, and the top weighted category becomes
    the current metabolic read. Runtime/framebuffer events can be added as
    more edge sources later without changing the reporting shape.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        text = ""
    rel_lower = rel.lower()

    best_label = "unclassified metabolic surface"
    best_release = "add more measured signals before release"
    best_score = 0
    best_hits: Counter[str] = Counter()
    for rule in METABOLIC_CATEGORY_RULES:
        hits: Counter[str] = Counter()
        score = 0
        for term in rule["terms"]:
            count = len(re.findall(rf"\b{re.escape(term)}\b", text))
            if count:
                hits[term] += count
                score += min(count, 24)
        for term in rule["path_terms"]:
            if _path_term_matches(term, rel_lower):
                hits[term] += 1
                score += 36
        if score > best_score:
            best_label = rule["label"]
            best_release = rule["release"]
            best_score = score
            best_hits = hits

    return best_label, best_release, best_score, best_hits


def _metabolic_groups_for_files(paths: list[Path]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for path in paths:
        rel = str(path.relative_to(ROOT))
        label, release, score, hits = _metabolic_category_for_file(rel, path)
        group = grouped.setdefault(
            label,
            {
                "label": label,
                "release": release,
                "score": 0,
                "loc": 0,
                "files": [],
                "hits": Counter(),
            },
        )
        group["score"] = int(group["score"]) + score
        group["loc"] = int(group["loc"]) + _count_file_lines(path)
        group["files"].append(rel)
        group["hits"].update(hits)

    return sorted(
        grouped.values(),
        key=lambda row: (int(row["loc"]), int(row["score"])),
        reverse=True,
    )


def _static_signal_hits(path: Path) -> Counter[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        text = ""
    hits: Counter[str] = Counter()
    rel_lower = str(path.relative_to(ROOT)).lower()
    for term in STATIC_SIGNAL_TERMS:
        count = text.count(term)
        if term in rel_lower:
            count += 1
        if count:
            hits[term] = count
    return hits


def sense_static_to_dynamic_wants() -> list[str]:
    """Name static surfaces that are asking for dynamic successors.

    Static is not a fault by itself; it is a named resource request. Repeated
    static-signal occurrences are treated as edge events and compressed into
    an edge reputation count between the static surface cell and the dynamic
    successor cell it asks for.
    """
    lines: list[str] = []
    rows: list[tuple[int, dict[str, str], Counter[str], int]] = []
    for surface in STATIC_TO_DYNAMIC_SURFACES:
        path = ROOT / surface["path"]
        if not path.exists():
            continue
        hits = _static_signal_hits(path)
        score = sum(hits.values())
        rows.append((score, surface, hits, _count_file_lines(path)))

    if not rows:
        return ["  no static surfaces named yet"]

    lines.append(
        "  static is a named want, not a dead label — each row asks for a "
        "dynamic successor"
    )
    for score, surface, hits, loc in sorted(rows, key=lambda row: row[0], reverse=True):
        hit_line = ", ".join(
            f"{name}={count}" for name, count in hits.most_common(4)
        )
        reputation_count = max(score, 1)
        lines.append(
            f"  wants_dynamic: {surface['path']} — {surface['kind']} "
            f"({loc} LOC)"
        )
        lines.append(
            f"    edge_reputation: {surface['path']} "
            f"--[wants_dynamic count={reputation_count}]--> "
            f"{surface['successor']}"
        )
        lines.append(
            "    compressed_edges: "
            f"{hit_line or 'path-named static surface=1'}"
        )
        lines.append(f"    wants: {surface['wants']}")
        lines.append(f"    resources: {surface['resources']}")
    return lines


def sense_bootstrap_compost() -> list[str]:
    """How much bootstrap tissue remains, what runtime fills the parity seam,
    what compost is deferred behind which gate.

    The destination is Form-native parsing + compiling: source bytes → BMF
    source objects → Form rules in form-stdlib/grammars/*-bmf.fk → recipe →
    native walker. Every file named in kernels/BOOTSTRAP_COMPOST_MANIFEST.md
    is bootstrap tissue with a named compost gate. The body sees its own
    weight by reading the named files and reporting LOC.

    Selector currently in effect: the default of
    seedbank/python-adapter/scripts/parity_suite.sh's PARITY_THIRD_RUNTIME.
    When that default flips from ts-eval to kernel-bmf, the Phase-A rows
    are residue.
    """
    manifest = ROOT / "kernels" / "BOOTSTRAP_COMPOST_MANIFEST.md"
    if not manifest.is_file():
        return ["  (kernels/BOOTSTRAP_COMPOST_MANIFEST.md not present; skipping)"]

    # Each row of the manifest names a file path with a LOC column. Sum the
    # actual on-disk LOC of every named file that still exists, grouped by
    # Phase A / B / C. Files that have already composted simply don't sum
    # (they're missing). The manifest is the named-for-compost surface;
    # the on-disk LOC is the actual remaining weight.
    phase_files = {
        "A": [
            "form/form-kernel-ts/seedbank/python-adapter/src/lang-python.ts",
            "form/form-kernel-ts/seedbank/python-adapter/src/lang-python-fk.ts",
            "form/form-kernel-ts/seedbank/python-adapter/src/ctor-convergence.ts",
            "form/form-kernel-ts/seedbank/python-adapter/src/lang-python.test.ts",
            "form/form-kernel-ts/seedbank/python-adapter/src/ctor-convergence.test.ts",
            "form/form-kernel-ts/seedbank/ts-adapter/src/lang-ts.ts",
            "form/form-kernel-ts/seedbank/ts-adapter/src/lang-ts-fk.ts",
        ],
        "B": [
            "form/form-kernel-ts/seedbank/python-adapter/src/main.ts",
            "form/form-kernel-ts/seedbank/python-adapter/scripts/parity_suite.sh",
            "form/form-kernel-ts/seedbank/python-adapter/scripts/perf_compare.sh",
            "form/form-kernel-ts/seedbank/ts-adapter/src/main.ts",
            "form/form-kernel-ts/seedbank/ts-adapter/scripts/parity_suite.sh",
        ],
        "C": [
            "api/app/services/form_kernel_bridge.py",
            "api/app/services/substrate/form_runtime.py",
            "api/app/services/substrate/self_host.py",
            "api/app/services/substrate/form_rules.py",
            "api/app/services/substrate/form_builders.py",
        ],
    }

    lines: list[str] = []
    totals: dict[str, tuple[int, int, int]] = {}
    for phase, paths in phase_files.items():
        present = 0
        loc = 0
        absent = 0
        for rel in paths:
            p = ROOT / rel
            if p.is_file():
                try:
                    loc += sum(1 for _ in p.open("rb"))
                    present += 1
                except OSError:
                    pass
            else:
                absent += 1
        totals[phase] = (present, absent, loc)

    grand_loc = sum(t[2] for t in totals.values())
    grand_files = sum(t[0] for t in totals.values())
    lines.append(
        f"  bootstrap weight — {grand_files} files still tissue, "
        f"{grand_loc} LOC remaining (named in manifest)"
    )
    for phase, (present, absent, loc) in totals.items():
        label = {
            "A": "parsers + emitters",
            "B": "CLIs + scripts",
            "C": "Python bridge + runtime",
        }[phase]
        composted = f"; {absent} already composted" if absent else ""
        lines.append(
            f"    · Phase {phase} ({label}): {present} files, {loc} LOC{composted}"
        )

    python_transmutation_groups = [
        (
            "adapter parser/emitter",
            phase_files["A"][:5],
            "Form-native .py→.fk scanner+grammar path replaces "
            "`python-compile` in the Rust-bootstrap leg",
        ),
        (
            "adapter CLI/scripts",
            phase_files["B"][:3],
            "kernel-native source reader + parity/perf gates call the "
            "Form-native grammar path directly",
        ),
        (
            "bridge/runtime",
            phase_files["C"],
            "kernel HTTP + BML/domain handlers serve the routes; Python stays "
            "only as an explicit fanout bridge until each route is promoted",
        ),
    ]
    candidate_count = 0
    candidate_loc = 0
    candidate_lines: list[str] = []
    for label, paths, release_gate in python_transmutation_groups:
        present_paths: list[str] = []
        loc = 0
        for rel in paths:
            p = ROOT / rel
            if not p.is_file():
                continue
            present_paths.append(rel)
            try:
                loc += sum(1 for _ in p.open("rb"))
            except OSError:
                pass
        if not present_paths:
            continue
        candidate_count += len(present_paths)
        candidate_loc += loc
        examples = ", ".join(present_paths[:2])
        if len(present_paths) > 2:
            examples = f"{examples}, +{len(present_paths) - 2} more"
        candidate_lines.append(
            f"    · {label}: {len(present_paths)} files / {loc} LOC — {release_gate}"
        )
        candidate_lines.append(f"      examples: {examples}")

    if candidate_lines:
        lines.append(
            f"  Python transmutation candidates — {candidate_count} named "
            f"Python-dependent files / {candidate_loc} LOC still asking for "
            "Form-native release gates"
        )
        lines.extend(candidate_lines)
        utility_router = ROOT / "api" / "app" / "routers" / "utils.py"
        if utility_router.is_file():
            lines.append(
                "    · utility endpoint rows: api/app/routers/utils.py — "
                "row-level Python implementation surface; release by promoting "
                "each utility endpoint to a Form recipe or BML/domain handler"
            )

    # Wider perimeter — the substrate-Python directory carries more than
    # the manifest's Phase C names. The audit at
    # kernels/UNIVERSAL_TRANSLATOR_AUDIT.md found 16,309 LOC across 24
    # modules in api/app/services/substrate/, of which the manifest names
    # ~2,938 (form_runtime + self_host + form_rules + form_builders).
    # Surfacing the gap so the body sees its TRUE bootstrap weight,
    # not just the manifest-listed subset. These cells already have names:
    # their paths. The gap is that they are not yet named as compost rows
    # in the manifest.
    substrate_dir = ROOT / "api" / "app" / "services" / "substrate"
    if substrate_dir.is_dir():
        substrate_files = sorted(substrate_dir.glob("*.py"))
        substrate_loc = 0
        for p in substrate_files:
            try:
                substrate_loc += sum(1 for _ in p.open("rb"))
            except OSError:
                pass
        phase_c_rels = set(phase_files["C"])
        named_substrate_paths = [
            p for p in substrate_files
            if str(p.relative_to(ROOT)) in phase_c_rels
        ]
        named_substrate_loc = sum(_count_file_lines(p) for p in named_substrate_paths)
        unmanifested_loc = substrate_loc - named_substrate_loc
        unmanifested_files = len(substrate_files) - len(named_substrate_paths)
        lines.append(
            f"  wider perimeter — api/app/services/substrate/ has "
            f"{len(substrate_files)} modules, {substrate_loc} LOC total"
        )
        lines.append(
            f"    · manifest Phase C names {totals.get('C', (0, 0, 0))[0]} "
            f"files / {totals.get('C', (0, 0, 0))[2]} LOC total; "
            f"{len(named_substrate_paths)} of those live in this directory "
            f"({named_substrate_loc} LOC)"
        )
        lines.append(
            f"    · the remaining {unmanifested_files} path-named files / "
            f"{unmanifested_loc} LOC are not yet manifest-listed; "
            "classified below by metabolic signals"
        )
        if unmanifested_files > 0 and unmanifested_loc > 0:
            lines.append(
                "    · treat the path-named, manifest-unlisted perimeter as "
                "transmutation candidates: firing questions validate or refine "
                "the automatic read"
            )
            lines.append(
                "    · dynamic admission: any path-named cell with repeated "
                "Python/bootstrap signals appears here immediately"
            )
            lines.append(
                "    · manifest admission: add a static row when the cell has "
                "a named successor path, release gate, and proof command"
            )
            lines.append(
                "    · release: replacement path is proven, live callers no "
                "longer require the old carrier, and evidence records the drop"
            )
            unmanifested_paths = [
                p for p in substrate_files
                if str(p.relative_to(ROOT)) not in phase_c_rels
            ]
            groups = _metabolic_groups_for_files(unmanifested_paths)
            if groups:
                lines.append(
                    "  metabolic classification — derived from repeated edge "
                    "attributes on path-named substrate cells outside the manifest"
                )
                for group in groups:
                    files = list(group["files"])
                    hits = group["hits"]
                    hit_line = ", ".join(
                        f"{name}={count}"
                        for name, count in hits.most_common(4)
                    )
                    names = ", ".join(Path(rel).name for rel in files)
                    lines.append(
                        f"    · {group['label']}: {len(files)} files / "
                        f"{group['loc']} LOC, score={group['score']}"
                    )
                    lines.append(f"      signals: {hit_line or 'path-only'}")
                    lines.append(f"      files: {names}")
                    lines.append(f"      release: {group['release']}")

    # Lifecycle motion — count rows that have walked from tissue → PROVEN →
    # COMPOST READY → RELEASED. The body senses not just load but movement-
    # through-load. A row appears under each heading when a sibling PR proves
    # parity for a shape; the count grows as the discipline is practiced.
    manifest_text = manifest.read_text(encoding="utf-8")
    sections = {
        "PROVEN": 0,
        "COMPOST READY": 0,
        "RELEASED": 0,
    }
    # Each section's data rows match `| YYYY-MM-DD |` at the start.
    # The heading is `## PROVEN` (etc); we scan rows between headings.
    current_section: str | None = None
    for raw in manifest_text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("## "):
            heading = stripped[3:].split(" — ", 1)[0].strip()
            current_section = heading if heading in sections else None
            continue
        if current_section and re.match(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|", raw):
            sections[current_section] += 1
    lifecycle_summary = ", ".join(
        f"{name.lower()}: {count}" for name, count in sections.items()
    )
    lines.append(f"  lifecycle motion — {lifecycle_summary}")

    # Third-runtime selector — read the default out of the parity script.
    # Today: ts-eval (bootstrap). Destination: kernel-bmf (Form-native).
    parity = ROOT / "form" / "form-kernel-ts" / "seedbank" / "python-adapter" / "scripts" / "parity_suite.sh"
    third = "unknown"
    if parity.is_file():
        m = re.search(
            r'PARITY_THIRD_RUNTIME="?\$\{PARITY_THIRD_RUNTIME:-([a-z0-9-]+)\}',
            parity.read_text(),
        )
        if m:
            third = m.group(1)
    if third == "ts-eval":
        lines.append(
            "  third runtime default: ts-eval (TS bootstrap) — flip to "
            "kernel-bmf when Form-native compiles every PARITY_FILES demo"
        )
    elif third == "kernel-bmf":
        lines.append(
            "  third runtime default: kernel-bmf (Form-native) — the "
            "evalPython/ts-eval seam is retired, but the Phase-A parser + "
            "emitter + CLI remain LIVE (the parity suite's Rust-bootstrap leg, "
            "+ readiness harness deploy step); they release when a Form-native "
            ".py→.fk path replaces python-compile (see manifest Phase A)"
        )
    else:
        lines.append(f"  third runtime default: {third}")

    lines.append(
        "  (kernels/BOOTSTRAP_COMPOST_MANIFEST.md holds the named compost "
        "gates per file.)"
    )
    return lines


def sense_substrate_surprise() -> list[str]:
    """Names structural twins of recently-touched cells that haven't been
    looked at yet.

    Delegates to api/app/services/substrate/sense_surprise.py so the
    `coh substrate sense --surprise` CLI surfaces the same data through
    one shared organ. Previously this logic lived inline and `sense`
    didn't see it — they gave different answers about the same body.

    Silent when there's nothing surprising.
    """
    api_dir = ROOT / "api"
    if not api_dir.is_dir():
        return ["  (api/ not present; skipping)"]
    if str(api_dir) not in sys.path:
        sys.path.insert(0, str(api_dir))

    try:
        from app.services.unified_db import session as session_scope
        from app.services.substrate.sense_surprise import (
            find_unseen_twins, format_for_wellness,
        )
    except Exception:
        return ["  (substrate not importable; skipping)"]

    try:
        with session_scope() as session:
            touched_count, ranked = find_unseen_twins(
                session, ROOT, since="14.days.ago"
            )
    except Exception as exc:
        return [f"  (substrate session failed: {type(exc).__name__})"]
    return format_for_wellness(touched_count, ranked)


def sense_edge_categories() -> list[str]:
    """Name repeated edge categories across concepts, ideas, specs, and files.

    This is the edge-reputation complement to substrate surprise: instead of
    asking which structural twin appeared unexpectedly, it asks which repeated
    relations are already present in source tissue and should be visible as
    named clusters.
    """
    api_dir = ROOT / "api"
    if not api_dir.is_dir():
        return ["  (api/ not present; skipping)"]
    if str(api_dir) not in sys.path:
        sys.path.insert(0, str(api_dir))

    try:
        from app.services.substrate.sense_edge_categories import (
            format_edge_categories_for_wellness,
            observe_edge_categories,
        )
    except Exception:
        return ["  (edge category sensor not importable; skipping)"]

    try:
        report = observe_edge_categories(ROOT)
    except Exception as exc:
        return [f"  (edge category scan failed: {type(exc).__name__})"]
    return format_edge_categories_for_wellness(report)


def sense_contracts() -> list[str]:
    """How are the CI contracts breathing the last 7 days?

    Replaces the inbox channel — the GitHub Actions email firehose was
    surfacing every flake as urgent. Here friction lives in a place the
    body senses on arrival, not in interruption. We name patterns
    (workflow X failed N times this week), not individual flakes.

    Silent when contracts are breathing. Speaks when there's a shape
    worth naming: 3+ failures of the same workflow, or any workflow
    with a >40% failure rate over the window.
    """
    try:
        r = subprocess.run(
            ["gh", "run", "list", "--limit", "200",
             "--json", "conclusion,workflowName,createdAt,event,headBranch"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ["  (gh CLI unavailable — skipping contracts sense)"]
    if r.returncode != 0:
        return ["  (gh run list failed — skipping; may need `gh auth login`)"]

    try:
        runs = json.loads(r.stdout)
    except json.JSONDecodeError:
        return ["  (could not parse gh run list output)"]

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = []
    for run in runs:
        try:
            ts = datetime.fromisoformat(run["createdAt"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if ts >= cutoff:
            recent.append(run)

    if not recent:
        return ["  (no runs in the last 7 days — body resting or gh window short)"]

    by_wf: dict[str, dict[str, int]] = {}
    for run in recent:
        wf = run.get("workflowName", "?")
        outcome = run.get("conclusion") or "in_progress"
        by_wf.setdefault(wf, Counter())[outcome] += 1

    findings = []
    flagged = False
    for wf in sorted(by_wf):
        outcomes = by_wf[wf]
        total = sum(outcomes.values())
        failures = outcomes.get("failure", 0) + outcomes.get("startup_failure", 0)
        if total == 0:
            continue
        rate = failures / total
        if failures >= 3 or rate >= 0.4:
            flagged = True
            findings.append(
                f"  {wf} — {failures}/{total} failed ({int(rate*100)}%) over 7d"
            )

    if not flagged:
        green = sum(1 for run in recent if run.get("conclusion") == "success")
        return [f"  contracts breathing — {green}/{len(recent)} runs green over 7d"]

    findings.insert(0, f"  {len(recent)} runs over 7d; patterns worth naming:")
    findings.append("")
    findings.append("  (Friction here is signal, not pain to silence. If a")
    findings.append("   pattern persists across days, the contract itself may")
    findings.append("   want re-shaping — not the email channel.)")
    return findings


def sense_cells() -> list[str]:
    """Are the agent cells themselves breathing?

    Wellness has senses for artifacts (specs, indexes, contracts, witness-trace)
    but until now has been silent on the cells — the body's hands. This sense
    reads three layers of cell health:

    1. **Structural soundness** — each .claude/agents/*.md has frontmatter
       (name + description + tools), the frontmatter name matches the
       filename stem, and the body carries a ## Frequency preamble.
    2. **Affirmative voice** — descriptions describe what the cell IS,
       rather than what it forbids. Flags well-known negation markers.
    3. **Dispatch wiring** — names in agent_service_executor.py's
       AGENT_BY_TASK_TYPE and GUARD_AGENTS_BY_TASK_TYPE resolve to real files.
    4. **Cursor parallel** — where .cursor/skills/{name}/ mirrors a Claude cell,
       the SKILL.md frontmatter agrees.
    """
    findings: list[str] = []
    agents_dir = ROOT / ".claude" / "agents"
    if not agents_dir.is_dir():
        return ["  (.claude/agents/ not present)"]
    agent_files = sorted(agents_dir.glob("*.md"))
    if not agent_files:
        return ["  (no agents in .claude/agents/)"]

    NEGATION_MARKERS = (
        "do not ", "don't ", " no scope creep",
        " no implementation", " no editing",
        "suggest changes; do not apply",
    )

    soft: list[str] = []
    affirmative = 0
    with_preamble = 0
    structural_ok = 0
    for path in agent_files:
        text = path.read_text()
        fm_m = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
        if not fm_m:
            soft.append(f"  · {path.name}: frontmatter absent")
            continue
        fm = fm_m.group(1)
        name_m = re.search(r"^name:\s*(\S+)", fm, re.MULTILINE)
        desc_m = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
        tools_m = re.search(r"^tools:", fm, re.MULTILINE)
        stem = path.stem
        struct_ok = True
        if not name_m:
            soft.append(f"  · {path.name}: frontmatter missing 'name:'")
            struct_ok = False
        elif name_m.group(1).strip() != stem:
            soft.append(
                f"  · {path.name}: name '{name_m.group(1).strip()}' "
                f"differs from filename stem '{stem}'"
            )
            struct_ok = False
        if not desc_m:
            soft.append(f"  · {path.name}: frontmatter missing 'description:'")
            struct_ok = False
        else:
            desc = desc_m.group(1).strip().lower()
            if any(marker in desc for marker in NEGATION_MARKERS):
                short = desc_m.group(1).strip()
                soft.append(
                    f"  · {path.name}: description carries negation — "
                    f"\"{short[:70]}{'…' if len(short) > 70 else ''}\""
                )
            else:
                affirmative += 1
        if not tools_m:
            soft.append(f"  · {path.name}: frontmatter missing 'tools:'")
            struct_ok = False
        if "## Frequency" in text:
            with_preamble += 1
        else:
            soft.append(f"  · {path.name}: missing '## Frequency' preamble")
        if struct_ok:
            structural_ok += 1

    n = len(agent_files)
    summary_bits = [f"{n} agents present"]
    if affirmative == n:
        summary_bits.append("affirmative")
    else:
        summary_bits.append(f"affirmative {affirmative}/{n}")
    if with_preamble == n:
        summary_bits.append("frequency preamble in each")
    else:
        summary_bits.append(f"preamble {with_preamble}/{n}")
    findings.append("  " + " · ".join(summary_bits))
    findings.extend(soft)

    # Dispatch wiring — does every name in the api map resolve to a cell?
    executor_path = ROOT / "api" / "app" / "services" / "agent_service_executor.py"
    if executor_path.exists():
        exec_text = executor_path.read_text()
        dispatched: set[str] = set()
        for block_pat in (
            r"AGENT_BY_TASK_TYPE[^=]*=\s*\{(.*?)\n\}",
            r"GUARD_AGENTS_BY_TASK_TYPE[^=]*=\s*\{(.*?)\n\}",
        ):
            block_m = re.search(block_pat, exec_text, re.DOTALL)
            if block_m:
                for s in re.findall(r'"([a-z][a-z\-]+)"', block_m.group(1)):
                    dispatched.add(s)
        present_stems = {p.stem for p in agent_files}
        missing = sorted(dispatched - present_stems)
        if missing:
            findings.append("")
            findings.append("  dispatch wiring drift (api → .claude/agents/):")
            for name in missing:
                findings.append(
                    f"  · '{name}' dispatched but no .claude/agents/{name}.md"
                )
        elif dispatched:
            findings.append(
                f"  dispatch wiring coherent ({len(dispatched)} names → .claude/agents/)"
            )

    # Cursor parallel — every .cursor/skills/{name}/ that mirrors a Claude
    # cell should agree on its name in frontmatter.
    cursor_dir = ROOT / ".cursor" / "skills"
    if cursor_dir.is_dir():
        mirror_drift: list[str] = []
        mirror_count = 0
        for skill_dir in sorted(cursor_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            stem = skill_dir.name
            if not (agents_dir / f"{stem}.md").exists():
                continue  # skill without claude mirror — fine
            mirror_count += 1
            sk_m = re.search(
                r"^name:\s*(\S+)", skill_md.read_text(), re.MULTILINE,
            )
            if sk_m and sk_m.group(1).strip() != stem:
                mirror_drift.append(
                    f"  · cursor skill '{stem}/SKILL.md' has frontmatter "
                    f"name '{sk_m.group(1).strip()}' (drifted from dir)"
                )
        if mirror_drift:
            findings.append("")
            findings.append("  cursor parallel:")
            findings.extend(mirror_drift)
        elif mirror_count:
            word = "mirror" if mirror_count == 1 else "mirrors"
            findings.append(
                f"  cursor parallel: {mirror_count} {word} coherent"
            )

    return findings


def sense_substrate_shape() -> list[str]:
    """Sense whether substrate cells carry composed CTORs or flat type-markers.

    The structural-composition discipline promises every cell's CTOR is a
    tree of R_Block.LET (key, value) pairs. The earlier flat encoder
    produced CTORs of trivial-string recipes carrying type-marker strings
    like "name=str". Aggregate counts (cells/blueprints/recipes) look
    stable across either encoding — content-addressing means orphaned
    structured recipes stay in the lattice while cells re-point at flat
    encodings. This sense distinguishes the two by querying
    /api/substrate/shape_health and flags any silent flatten regression.

    Silent when ratio ≥ 95% across all domains. Speaks the moment any
    domain drops below.
    """
    import urllib.request
    import urllib.error

    api = os.environ.get("COHERENCE_API_BASE", "https://api.coherencycoin.com")
    try:
        req = urllib.request.Request(
            f"{api}/api/substrate/shape_health",
            headers={"User-Agent": "wellness-check/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            health = json.load(r)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return [f"  (could not reach {api}/api/substrate/shape_health — {e})"]

    overall = health.get("overall", {})
    domains = health.get("domains", {}) or {}
    flags = health.get("flags", []) or []

    lines: list[str] = []
    total = overall.get("total", 0)
    structured = overall.get("structured", 0)
    flat = overall.get("flat", 0)
    no_ctor = overall.get("no_ctor", 0)
    ratio = overall.get("ratio", 1.0)

    lines.append(
        f"  {total:,} cells · {structured:,} structured · {flat:,} flat · "
        f"{no_ctor:,} no-ctor · {ratio:.0%} composed"
    )

    if not flags:
        lines.append("  composition discipline holding across every domain.")
    else:
        lines.append("")
        for f in flags:
            lines.append(f"  · {f}")

    nonempty = [(name, d) for name, d in domains.items() if d.get("total", 0) > 0]
    if nonempty:
        lines.append("")
        for name, d in sorted(nonempty, key=lambda kv: -kv[1].get("total", 0)):
            r = d.get("ratio", 1.0)
            t = d.get("total", 0)
            s = d.get("structured", 0)
            fl = d.get("flat", 0)
            marker = " ✓" if r >= 0.95 and fl == 0 else " ⚠" if fl > 0 else ""
            lines.append(f"  {name}: {s}/{t} composed ({r:.0%}){marker}")

    return lines


def sense_witness_trace() -> list[str]:
    """How is the witness-trace breathing?

    Every page view writes a row to ``asset_view_events``. The table
    grows linearly with traffic; the daily aggregate stays bounded.
    This sense reads /api/views/health and reports the writer's
    latency band, the table's size band, and the growth band — plus
    any flags that mean it's time to run scripts/trim_view_events.py.

    Silent when all bands are calm. Speaks the moment any band
    crosses budget.
    """
    import urllib.request
    import urllib.error

    api = os.environ.get("COHERENCE_API_BASE", "https://api.coherencycoin.com")
    try:
        req = urllib.request.Request(
            f"{api}/api/views/health",
            headers={"User-Agent": "wellness-check/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            health = json.load(r)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return [f"  (could not reach {api}/api/views/health — {e})"]

    events = health.get("events", {})
    storage = health.get("storage", {})
    writer = health.get("writer", {})
    flags = health.get("flags", []) or []

    lines: list[str] = []
    total_rows = events.get("total_rows", 0)
    growth = events.get("growth_per_day", 0.0)
    mb = storage.get("estimated_mb", 0)
    p95 = (writer.get("ping_latency") or {}).get("p95_ms")
    p95_str = f"p95 {p95:.0f}ms" if isinstance(p95, (int, float)) else "no traffic yet"

    bands = (
        f"writer {writer.get('band', '?')} · "
        f"size {storage.get('size_band', '?')} · "
        f"growth {events.get('growth_band', '?')}"
    )
    lines.append(f"  {total_rows:,} events · ~{mb} MB · {growth:.0f}/day · {p95_str}")
    lines.append(f"  bands: {bands}")

    if flags:
        lines.append("")
        lines.append("  flags raised:")
        for f in flags:
            lines.append(f"    · {f}")
        guidance = health.get("guidance")
        if guidance:
            lines.append("")
            lines.append(f"  → {guidance}")
    else:
        lines.append("  trace breathing within budget. no action needed.")

    return lines


def sense_deploy_lag() -> list[str]:
    """How far behind production is from main.

    The hostinger auto-deploy pipeline merges main → production via
    `deploy/hostinger/auto-deploy.sh`. When merges land on main but
    production stays on an older sha, the body's most-recent work
    isn't reaching visitors — the witness probes that watch production
    surfaces (substrate_form, page_*, etc.) keep firing on stale code
    paths even after a fix has merged.

    This probe compares production's `/api/health.deployed_sha` to
    `origin/main` HEAD via `git ls-remote`. A clean state has
    deployed_sha equal to (or a recent ancestor of) origin/main; a
    deploy-lagged state surfaces with the count of commits behind.

    First sighting: 2026-05-27, when 17 PRs merged to main during a
    session and production stayed at the pre-session sha while the
    witness substrate_form silence persisted for hours because the
    healing-PR was on main but undeployed.
    """
    import subprocess
    import urllib.request
    import json as _json

    lines: list[str] = []

    # Production's deployed_sha
    try:
        req = urllib.request.Request(
            "https://api.coherencycoin.com/api/health",
            headers={"User-Agent": "coherence-wellness/0.1"},
        )
        resp = urllib.request.urlopen(req, timeout=5)
        body = _json.loads(resp.read())
        deployed_sha = body.get("deployed_sha", "")
        uptime = body.get("uptime_human", "?")
    except Exception as exc:
        return [f"  (could not reach https://api.coherencycoin.com/api/health — {exc})"]

    if not deployed_sha:
        return ["  production /api/health did not report deployed_sha"]

    # origin/main HEAD via local git (no network if we already fetched)
    try:
        # Try local first — main may already track origin
        head_main = subprocess.run(
            ["git", "ls-remote", "origin", "main"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=10,
        )
        if head_main.returncode != 0:
            return [f"  (git ls-remote failed: {head_main.stderr.strip()[:80]})"]
        origin_sha = head_main.stdout.split()[0] if head_main.stdout else ""
    except Exception as exc:
        return [f"  (git ls-remote raised: {exc})"]

    if not origin_sha:
        return ["  could not resolve origin/main sha"]

    if deployed_sha == origin_sha:
        lines.append(
            f"  deploy aligned — production at {deployed_sha[:8]} matches origin/main (uptime {uptime})"
        )
        return lines

    # How many commits between them? The production sha may be ahead of
    # local main when this runs from a worktree that hasn't fetched
    # recently; ensure git knows both shas before counting. A fetch
    # first guarantees `git rev-list deployed_sha..origin_sha` resolves
    # both ends.
    try:
        subprocess.run(
            ["git", "fetch", "origin", "main", "--quiet"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=15,
        )
        rev_list = subprocess.run(
            ["git", "rev-list", "--count", f"{deployed_sha}..{origin_sha}"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=10,
        )
        if rev_list.returncode == 0 and rev_list.stdout.strip().isdigit():
            behind = rev_list.stdout.strip()
        else:
            behind = f"? (rev-list could not resolve {deployed_sha[:8]} locally — run `git fetch origin`)"
    except Exception as exc:
        behind = f"? ({exc})"

    lines.append(
        f"  deploy lagged — production at {deployed_sha[:8]} is {behind} commit(s) "
        f"behind origin/main ({origin_sha[:8]}), uptime {uptime}"
    )
    lines.append(
        "  unmerged work doesn't reach visitors until hostinger auto-deploy "
        "fires; if this persists, check `deploy/hostinger/auto-deploy.sh` "
        "workflow runs or ssh-trigger per CLAUDE.md deploy section."
    )
    return lines


# Kernel-native API surface — the readiness envelope this probe senses against.
# From kernels/API_KERNEL_READINESS.md: the route-preload carrier lands the
# integer endpoints at 3-4µs p50 and the list/float ones at 17-48µs p50; the
# inline-with-parse path is sub-200µs p99. A LOCAL `trace` walk (cold subprocess
# kernel, no warm preloader) is a coarser instrument — it includes parse + a
# fresh process's first walk — so the wellness threshold is deliberately loose:
# it catches a recipe that has regressed by an ORDER of magnitude (something
# structurally wrong), not p50 micro-jitter. The precise p50 profile is the
# harness's job (scripts/kernel_readiness_harness.py); this probe senses gross
# drift on the live surface.
_KERNEL_TRACE_REGRESSION_US = 5000  # a single recipe trace over ~5ms ⇒ look


def _kernel_live_endpoint_paths(served: list[dict[str, object]]) -> dict[str, str]:
    """Map kernel-served route ledger rows to live HTTP paths for stability probes."""
    paths: dict[str, str] = {}
    for entry in served:
        route = str(entry.get("route") or "")
        if route.startswith("/api/"):
            paths[route] = route
    return paths


def sense_kernel_api() -> list[str]:
    """Is the kernel-native API surface breathing across all five dimensions?

    The body just brought four endpoints' computational cores live serving
    ``runtime: "inline"`` through the warm in-process Form kernel
    (api/app/routers/utils.py → form_kernel_bridge.serve_via_kernel). This probe
    senses that surface the way Urs named it — performance, stability, accuracy,
    transparency, vitality — each as a concrete signal, quiet when healthy and
    specific when it drifts.

    ONE sensing mechanism: the kernel-served routes are DATA
    (kernel_attribution_report.KERNEL_SERVED_RECIPES); the probe walks them once
    locally (the kernel `trace` gives value + elapsed + attribution in one pass)
    and, when prod is reachable, reads the live ``runtime`` each endpoint serves.

    Degrades gracefully like sense_deploy_lag: with no live kernel/network it
    senses what it can LOCALLY (binary present, recipes parse, value parity,
    attribution present) and from the readiness doc, and SAYS what it couldn't
    reach — it never fakes a live reading.

    The drift it is built to catch (each a real failure mode, not performed
    caution):
      - Stability: an endpoint silently serving ``python-fallback`` — the body
        quietly losing Form-native execution (the exact drift that hid for a
        deploy: kernel loaded but endpoints on python-fallback for missing
        recipes). NAMED, not glossed.
      - Accuracy: a kernel that serves the WRONG value — parity break caught,
        not just a slow one.
      - Performance: the kernel path degraded off the fast carrier, or a recipe
        trace regressed by an order of magnitude.
      - Transparency: attribution/trace signal missing — the body can no longer
        see which Blueprints/recipes a call exercised.
      - Vitality: how MUCH of the API is kernel-served — the ratio and the
        growth edge toward most/all routes through the kernel.
    """
    import importlib.util
    import urllib.request
    import urllib.error

    lines: list[str] = []

    # Load the attribution module (single source of truth for the kernel-served
    # routes + the trace/aggregate mechanism). If it can't load, say so and stop
    # — the probe shares ONE mechanism with the activity view by design.
    attr_path = ROOT / "scripts" / "kernel_attribution_report.py"
    if not attr_path.is_file():
        return ["  drift: scripts/kernel_attribution_report.py missing — "
                "cannot sense the kernel-native surface"]
    try:
        spec = importlib.util.spec_from_file_location("kernel_attribution_report", attr_path)
        attr = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(attr)  # type: ignore[union-attr]
    except Exception as exc:
        return [f"  drift: could not load kernel_attribution_report ({exc})"]

    served = attr.KERNEL_SERVED_RECIPES
    n_served = len(served)

    # --- LOCAL sensing: trace each kernel-served recipe once (value + elapsed +
    # attribution in a single walk). Routes as DATA — one loop, all dimensions.
    local_unreached = not attr.kernel_available()
    parity_breaks: list[str] = []
    missing_recipes: list[str] = []
    slow_recipes: list[str] = []
    attribution_present = False
    embodiment_center: list | None = None  # lc-the-trace-is-the-memory, move 3
    traced = 0
    if not local_unreached:
        report = attr.aggregate()
        traced = report.get("reached", 0)
        for r in report.get("per_recipe", []):
            if r.get("missing"):
                missing_recipes.append(str(r["route"]))
                continue
            if r.get("failed"):
                parity_breaks.append(f"{r['route']} (trace failed)")
                continue
            if not r.get("parity"):
                parity_breaks.append(
                    f"{r['route']} → {r.get('result')} (expected {r.get('expected')})"
                )
            us = r.get("elapsed_us")
            if isinstance(us, (int, float)) and us > _KERNEL_TRACE_REGRESSION_US:
                slow_recipes.append(f"{r['route']} ({us}µs)")
        # Transparency: did the trace actually yield attribution? (hot blueprints
        # + natives attributed to NodeIDs). Empty attribution on a surface that
        # ran = the body can't see what it exercised.
        attribution_present = bool(report.get("arms")) and bool(report.get("natives"))
        # Deeper transparency: the embodiment projection's lived center (the
        # activity-weighted NodeID centroid). Present = the body can see not
        # just WHAT fired but which categories sit nearest its execution center.
        emb = report.get("embodiment") or {}
        embodiment_center = emb.get("center")

    # --- LIVE sensing: prod /api/health + /utils/kernel_status + each endpoint's
    # runtime. Reachability is optional (like sense_deploy_lag) — name what we
    # couldn't reach rather than failing.
    api = os.environ.get("COHERENCE_API_BASE", "https://api.coherencycoin.com")

    def _get(path: str):
        try:
            req = urllib.request.Request(
                f"{api}{path}", headers={"User-Agent": "wellness-kernel/1.0"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return None

    health = _get("/api/health")
    live_runtime = health.get("kernel_runtime") if health else None
    live_fallbacks: list[str] = []
    live_unchecked: list[str] = []
    live_runtimes_seen: set[str] = set()
    live_checked = 0
    live_expected = 0
    live_unreached = health is None
    if not live_unreached:
        # Stability: each transmuted endpoint should report inline/preload, not
        # python-fallback. Hit each with its defaults (no query → documented
        # sample input), read the `runtime` field.
        endpoint_paths = _kernel_live_endpoint_paths(served)
        live_expected = len(endpoint_paths)
        for route in (str(s["route"]) for s in served):
            path = endpoint_paths.get(route)
            if not path:
                continue
            body = _get(path)
            if body is None:
                live_unchecked.append(route)
                continue
            live_checked += 1
            rt = body.get("runtime")
            if rt:
                live_runtimes_seen.add(rt)
            if rt == "python-fallback":
                live_fallbacks.append(route)

    # --- Compose the reading. Quiet when healthy; specific lines on drift. The
    # attention markers (drift:/missing/could not reach) and compost markers
    # (within budget/aligned) steer build_reading's shared shape.

    # Vitality: how much of the API is kernel-served.
    total_routes = _count_api_routes()
    if total_routes:
        pct = 100.0 * n_served / total_routes
        lines.append(
            f"  vitality: {n_served}/{total_routes} API routes kernel-served "
            f"({pct:.1f}%) — the {total_routes - n_served} on pure Python are the growth edge "
            "toward most/all routes through the kernel"
        )
        # The honest runtime-share nuance: route-COUNT is kernel USAGE, not the
        # runtime-SHARE that actually left CPython. Even kernel-served routes run
        # the kernel as a guest-subroutine — routing/binding/validation/response
        # stay CPython. Kernel-FIRST served count is read from the public
        # front-door provenance probe in runtime_surface_report. The kernel-router
        # manifest holds native handlers that serve the WHOLE lifecycle in Form;
        # byte parity is useful evidence, while the native-first gate is web/API
        # smoke, tool flows, native observability, and explicit fallback.
        n_capable = None
        n_kernel_first = None
        front_door_probe = None
        rsr_path = ROOT / "scripts" / "runtime_surface_report.py"
        if rsr_path.is_file():
            try:
                _spec = importlib.util.spec_from_file_location("runtime_surface_report", rsr_path)
                _rsr = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
                _spec.loader.exec_module(_rsr)  # type: ignore[union-attr]
                report = _rsr.build_report()
                n_capable = report.get("kernel_first_capable_routes")
                n_kernel_first = report.get("kernel_first_served_routes")
                front_door_probe = report.get("front_door_probe") or {}
            except Exception:
                n_capable = None
        if n_capable:
            probe_note = ""
            if isinstance(front_door_probe, dict) and front_door_probe.get("reachable"):
                probe_note = (
                    f"; public probe status={front_door_probe.get('status')} "
                    f"router={front_door_probe.get('x_form_router') or '<missing>'}"
                )
            lines.append(
                f"  vitality: runtime-share — {n_kernel_first or 0} routes served "
                f"kernel-FIRST at the public front door; {n_capable} are kernel-first "
                "CAPABLE native handlers in the manifest, whole lifecycle in Form "
                "(gate: web/API/tool smoke + native observability + fallback"
                f"{probe_note}; scripts/runtime_surface_report.py)"
            )
        else:
            lines.append(
                "  vitality: runtime-share — those routes run the kernel as a "
                "guest-subroutine inside CPython (0 kernel-first); usage and "
                "runtime-share are distinct axes (scripts/runtime_surface_report.py)"
            )
    else:
        lines.append(
            f"  vitality: {n_served} routes kernel-served (total-route count unread)"
        )

    # Stability.
    if live_unreached:
        lines.append(f"  stability: could not reach {api}/api/health — sensed locally only")
    elif live_runtime in ("inline", "preload"):
        if live_fallbacks:
            lines.append(
                "  drift: stability — these endpoints served python-fallback "
                "(Form-native execution lost): " + ", ".join(live_fallbacks)
            )
        else:
            seen = ", ".join(sorted(live_runtimes_seen)) or live_runtime
            if live_unchecked:
                unread = ", ".join(live_unchecked[:5])
                more = f", +{len(live_unchecked) - 5} more" if len(live_unchecked) > 5 else ""
                lines.append(
                    f"  stability: production kernel_runtime '{live_runtime}'; "
                    f"checked {live_checked}/{live_expected} kernel-served endpoints ({seen}); "
                    f"runtime unread for: {unread}{more}"
                )
            else:
                lines.append(
                    f"  stability: production kernel_runtime '{live_runtime}'; "
                    f"checked {live_checked}/{live_expected} kernel-served endpoints ({seen}) — no fallback"
                )
    elif live_runtime == "python-fallback":
        lines.append(
            "  drift: stability — production kernel_runtime is 'python-fallback'; "
            "the body has lost Form-native execution on this surface"
        )
    elif live_runtime:
        lines.append(f"  stability: production kernel_runtime '{live_runtime}'")
    else:
        lines.append("  stability: /api/health did not report kernel_runtime")

    # Performance.
    if local_unreached:
        lines.append(
            "  performance: kernel binary not built locally — could not trace; "
            "per kernels/API_KERNEL_READINESS.md the route-preload carrier lands "
            "3-48µs p50 (run scripts/kernel_readiness_harness.py for the live profile)"
        )
    elif slow_recipes:
        lines.append(
            "  drift: performance — recipe trace over the order-of-magnitude "
            "threshold (structurally wrong?): " + ", ".join(slow_recipes)
        )
    elif "python-fallback" in live_runtimes_seen or live_runtime == "python-fallback":
        lines.append(
            "  drift: performance — kernel degraded off the fast carrier to python-fallback"
        )
    else:
        lines.append(
            f"  performance: {traced}/{n_served} recipes trace within the local envelope; "
            "fast carrier intact (inline/preload)"
        )

    # Accuracy (value parity).
    if local_unreached:
        lines.append("  accuracy: parity unverified locally (kernel binary absent)")
    elif parity_breaks:
        lines.append(
            "  drift: accuracy — kernel value-parity BREAK: " + "; ".join(parity_breaks)
        )
    elif missing_recipes:
        lines.append(
            "  accuracy: recipes absent (not compiled here), parity unverified for: "
            + ", ".join(missing_recipes)
        )
    else:
        lines.append(
            f"  accuracy: {traced}/{n_served} recipes match documented value parity"
        )

    # Transparency / attribution.
    if local_unreached:
        lines.append(
            "  transparency: attribution unsensed locally (kernel binary absent)"
        )
    elif attribution_present:
        center_note = ""
        if embodiment_center:
            center_str = ".".join(f"{c:g}" for c in embodiment_center)
            center_note = f"; embodiment center @{center_str} (|proj|→0 = lived center)"
        lines.append(
            "  transparency: attribution present — hot Blueprints + natives "
            "(each resolved to a NodeID) visible via "
            f"scripts/kernel_attribution_report.py{center_note}"
        )
    else:
        lines.append(
            "  drift: transparency — trace produced no attribution; the body "
            "can't see which Blueprints/recipes the calls exercised"
        )

    # A quiet closing line so a fully-healthy reading lands a compost marker.
    drifted = any(line.strip().startswith("drift:") for line in lines)
    if not drifted and not live_unreached and not local_unreached:
        lines.append(
            "  kernel-native surface breathing within envelope — no action needed"
        )

    return lines


def _count_api_routes() -> int:
    """Count route decorators across api/app/routers/*.py — the vitality denominator.

    A coarse count (every @router.<verb>(...) decorator) — enough to size the
    growth edge (kernel-served vs total). Returns 0 if the routers dir is
    unreadable, so the vitality line degrades to a bare served-count.
    """
    routers = ROOT / "api" / "app" / "routers"
    if not routers.is_dir():
        return 0
    pattern = re.compile(r"@router\.(get|post|patch|put|delete)\(")
    total = 0
    for p in routers.glob("*.py"):
        try:
            total += len(pattern.findall(p.read_text(encoding="utf-8")))
        except OSError:
            continue
    return total


def _wellness_attention_line(line: str) -> bool:
    lower = line.lower()
    attention_markers = (
        "drift:",
        "missing",
        "no readers",
        "awaiting home",
        "could not reach",
        "flags raised",
        "not found",
        "cannot verify",
        "no test:",
        "no proof",
        "wants_dynamic:",
    )
    return any(marker in lower for marker in attention_markers)


def _wellness_compost_line(line: str) -> bool:
    lower = line.lower()
    compost_markers = (
        "aligned",
        "root is clear",
        "no action needed",
        "no living_collective_*.md drafts remain",
        "every ",
        "coherent",
        "within budget",
    )
    return any(marker in lower for marker in compost_markers)


def build_reading(sections: list[tuple[str, list[str]]]) -> dict[str, list]:
    """Project the wellness sections into the shared reading shape."""
    sensed: list[str] = []
    attention: list[dict[str, str]] = []
    compost: list[str] = []

    for header, lines in sections:
        first = next((line.strip() for line in lines if line.strip()), "")
        sensed.append(f"{header}: {first}" if first else f"{header}: no reading")
        for line in lines:
            clean = line.strip()
            if not clean:
                continue
            if _wellness_attention_line(clean):
                attention.append(
                    {
                        "surface": header,
                        "reading": clean,
                        "next_action": "Tend this surface with the smallest focused proof.",
                    }
                )
            elif _wellness_compost_line(clean):
                compost.append(f"{header}: {clean}")

    if not compost and not attention:
        compost.append("No added procedure is needed for this breath; keep the reading small.")

    return {
        "what_i_sensed": sensed,
        "what_wants_attention": attention,
        "what_can_compost": compost,
    }


def main() -> int:
    """Sense the body, print to stdout, and cache the reading.

    The cache file lives at .cache/wellness/state.txt. Every cell type —
    Claude sub-agent dispatches, Codex sessions, Cursor sessions, ad-hoc
    bash one-liners — can read it for the body's most recent sensing
    without re-running the slower senses (gh, network). Refreshes every
    time wellness runs; arrival.py runs it at SessionStart, so it stays
    fresh through normal use.
    """
    sections: list[tuple[str, list[str]]] = [
        ("Proprioception — do the maps match the body?", sense_proprioception()),
        ("Circulation — what at root has no readers?", sense_circulation()),
        ("Metabolism — composting-in-progress", sense_metabolism()),
        ("Source maps — do specs point at files that exist?", sense_spec_sources()),
        ("Symbol resolution — do the named symbols still live in those files?", sense_spec_symbols()),
        ("Locale parity — does the body speak the same body in every tongue?", sense_locale_parity()),
        ("Locale surfaces — do web, API, and CLI carry the same tongues?", sense_locale_surfaces()),
        ("Chain — does idea→spec→code→test reach end to end?", sense_chain()),
        ("Form engine — does the meta-circular evaluator cover Python dispatch?", sense_form_engine()),
        ("Form ontology — does the form-side table agree with each kernel parser?", sense_form_ontology()),
        ("Form blueprints — are user-space Blueprint numbers registered, not magic?", sense_form_blueprints()),
        ("Form primitives — does every kernel native carry a spec and a verification recipe?", sense_form_primitives()),
        ("Bootstrap compost — how much parser tissue still stands between us and Form-native?", sense_bootstrap_compost()),
        ("Static-to-dynamic wants — which fixed ledgers ask for live cells?", sense_static_to_dynamic_wants()),
        ("Edge categories — which repeated relations are becoming named clusters?", sense_edge_categories()),
        ("Substrate surprise — structural twins of recent work, unread", sense_substrate_surprise()),
        ("Cells — are the cells themselves breathing?", sense_cells()),
        ("Contracts — are the CI gates breathing? (last 7d)", sense_contracts()),
        ("Substrate shape — do cell CTORs carry composition or flat type-markers?", sense_substrate_shape()),
        ("Witness-trace — is the visit-recorder within budget?", sense_witness_trace()),
        ("Deploy lag — is the body's main reach production?", sense_deploy_lag()),
        ("Kernel-native API — is the transmuted surface breathing (perf/stability/accuracy/transparency/vitality)?", sense_kernel_api()),
    ]
    reading = build_reading(sections)

    out: list[str] = []
    out.append("# Wellness check")
    out.append("")
    out.append("A gentle sensing. Not an audit. Drift is the signal,")
    out.append("not the problem.")
    out.append("")
    for header, lines in sections:
        out.append(f"## {header}")
        out.append("")
        out.extend(lines)
        out.append("")
    out.append("## Reading — shared shape")
    out.append("")
    out.append("what_i_sensed:")
    for item in reading["what_i_sensed"]:
        out.append(f"  · {item}")
    out.append("")
    out.append("what_wants_attention:")
    if reading["what_wants_attention"]:
        for item in reading["what_wants_attention"]:
            out.append(f"  · {item['surface']}: {item['reading']}")
            out.append(f"    → {item['next_action']}")
    else:
        out.append("  · none")
    out.append("")
    out.append("what_can_compost:")
    if reading["what_can_compost"]:
        for item in reading["what_can_compost"]:
            out.append(f"  · {item}")
    else:
        out.append("  · no compost reading this breath")
    out.append("")
    out.append("(Feedback is the blood. Run me anytime the body")
    out.append(" feels slightly off; I'll name what I can sense.)")

    output = "\n".join(out)
    print(output)

    # Cache the reading so any cell can read the body's most recent
    # sensing without re-running the slower senses. The cache stays in
    # .cache/ which is gitignored — this is ephemeral proprioception,
    # not durable memory.
    try:
        cache_dir = ROOT / ".cache" / "wellness"
        cache_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cache_path = cache_dir / "state.txt"
        cache_path.write_text(
            f"# sensed at {timestamp}\n\n{output}\n"
        )
    except OSError:
        pass  # caching is bonus; primary contract is the print

    return 0


if __name__ == "__main__":
    sys.exit(main())
