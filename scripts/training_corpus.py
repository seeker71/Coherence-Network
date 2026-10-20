"""Import selected repository edges as local learning pairs with explicit per-invocation consent.

The body is full of labeled training pairs because it maintains edges: a commit's
(message -> diff), a spec's (idea -> spec) and (spec -> code) frontmatter, a concept's
(concept -> cross-ref) and (concept -> visual). Each edge is one (intent -> realization)
example, and the edge the body already verifies (the merge, the source map, the cross-ref)
IS the label. Form-related edges matter most; the rest train too.

ONE engine, sources as DATA: a source is a generator yielding
(intent, realization, lane, label). New edge-types (concept, image, relationship) drop in
as another entry in SOURCES, never a parallel script. The pair-shape, the three separable
lanes, and content-addressing live in form-stdlib/training-catalog.fk; this sources the
body's edges into the existing catalog_capture. North star: walk the substrate edge graph
directly (it already holds these edges — concept-corpus.fk, spec ingest) once the kernel
reads it natively; this is the host-IO bootstrap carrier until then.

Usage:
  training_corpus.py --source git --range ORIG_HEAD..HEAD --capture-consent selected-excerpt-local-learning-v1

Choose and review the source range before consenting. The consent flag permits
only this invocation's selected repository excerpts to become a separate local
learning copy. It does not enroll future imports or chat transcripts.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "mcp-server"))
from coherence_mcp_server.form_cli_tools import CAPTURE_CONSENT, catalog_capture

MAX_TEXT = 8000  # bound each record; the full artifact always lives in the body


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, cwd=REPO).stdout


def _frontmatter(text: str) -> str:
    parts = text.split("---", 2)
    return parts[1] if len(parts) >= 3 else ""


# -- sources (each yields (intent, realization, lane, label)) ------------------

def source_git(range_spec: str | None = None, backfill: int | None = None, **_):
    """git commit (message -> diff), labeled by the merge. Form-related commits first."""
    if backfill:
        shas = _git("log", "--format=%H", "-n", str(backfill), "--", "*.fk", "*.form").split()
    elif range_spec:
        shas = _git("log", "--format=%H", range_spec, "--", "*.fk", "*.form").split()
    else:
        shas = []
    for sha in shas:
        msg = _git("show", "-s", "--format=%s%n%n%b", sha).strip()
        diff = _git("show", sha, "--format=", "--unified=3")[:MAX_TEXT]
        if msg and diff.strip():
            yield (msg, diff, "git-commit-to-diff", "merged")


def source_chain(**_):
    """spec frontmatter edges: idea->spec (idea_id) and spec->code (source map)."""
    for spec in sorted((REPO / "specs").glob("*.md")):
        if spec.stem in ("INDEX", "TEMPLATE"):
            continue
        fm = _frontmatter(spec.read_text(encoding="utf-8", errors="ignore"))
        if not fm:
            continue
        idea_m = re.search(r"^\s*idea_id:\s*(\S+)", fm, re.MULTILINE)
        reqs_m = re.search(r"requirements:\s*(.+?)(?:\n\w|\Z)", fm, re.DOTALL)
        idea = idea_m.group(1) if idea_m else ""
        reqs = reqs_m.group(1).strip() if reqs_m else ""
        intent = f"{spec.stem}\n{reqs}".strip()[:MAX_TEXT]
        files = re.findall(r"^\s*-\s*file:\s*(\S+)", fm, re.MULTILINE)
        if idea and idea != "{parent-idea-slug}":
            yield (f"idea: {idea}", intent, "idea-to-spec", "spec-registered")
        if files:
            yield (intent, "\n".join(files)[:MAX_TEXT], "spec-to-code", "spec-source-verified")


SOURCES = {"git": source_git, "chain": source_chain}


def feed(pairs, *, capture_consent: str | None = None) -> dict[str, int]:
    if capture_consent != CAPTURE_CONSENT:
        raise ValueError("Select repository excerpts and consent before reading them for local learning")
    counts: dict[str, int] = {}
    for intent, realization, lane, label in pairs:
        # request = intent, raw = transmuted = realization (a verified body edge is the
        # trusted output — no fear to transmute); lane + outcome carry the label.
        receipt = catalog_capture(
            intent, realization, realization, lane, label,
            capture_consent=capture_consent,
        )
        if not receipt.get("captured"):
            raise RuntimeError(receipt.get("error", "Local learning capture failed"))
        counts[lane] = counts.get(lane, 0) + 1
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="git", choices=[*SOURCES, "all"])
    ap.add_argument("--range", dest="range_spec", default=None,
                    help="git range of just-merged commits, e.g. ORIG_HEAD..HEAD")
    ap.add_argument("--backfill", type=int, default=None, help="git: last N .fk/.form commits")
    ap.add_argument(
        "--capture-consent", choices=[CAPTURE_CONSENT],
        help="Consent to a separate local learning copy of this invocation's selected repository excerpts",
    )
    args = ap.parse_args()
    if args.capture_consent != CAPTURE_CONSENT:
        ap.error("--capture-consent is required before source content is read")
    names = list(SOURCES) if args.source == "all" else [args.source]
    total: dict[str, int] = {}
    for name in names:
        for lane, n in feed(
            SOURCES[name](range_spec=args.range_spec, backfill=args.backfill),
            capture_consent=args.capture_consent,
        ).items():
            total[lane] = total.get(lane, 0) + n
    for lane, n in sorted(total.items()):
        print(f"[catalog] {lane}: fed {n} (intent->realization) pairs")
    if not total:
        print("[catalog] no pairs fed (empty range / no edges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
