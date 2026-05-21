"""word_cell_rewriter — gesture 3 at word-cell granularity.

The in-memory gas-cell modify-preview counts byte-level occurrences of a
string. That's enough to surface where a rename would touch, but it can
collide with substrings (e.g. "choice" matches "choices" and "no-choice"
without distinction).

The word-cell rewriter is one altitude up: tokenize each artifact through
the same `tokenize_words` pipeline the WORD domain uses (PR #1748), then
substitute at the lemma+POS layer. A rename of `choice.NOUN` does not
touch `choices.NOUN` (different lemma after stemming) or `chosen.VERB`
(different POS).

This module ships the *in-memory* version of that gesture, callable from
either perceptron script. The substrate-native version composes naturally
once the WORD-cell graph is ingested at scale; the interfaces are
identical.

The module degrades gracefully:
- if `app.services.substrate.markdown_frontend.tokenize_words` is
  importable (PR #1748 merged), uses it for tokenization;
- otherwise, falls back to a regex word tokenizer that's good enough
  for the rewrite preview shape.

This is the closure of the gap named at the end of PR #1752:
*Word-cell-granularity rewrites for gesture 3*.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Tokenizer — uses substrate's if available, else a local fallback
# ---------------------------------------------------------------------------


def _fallback_tokenize(text: str) -> List[Dict[str, Any]]:
    """A local tokenizer matching the shape of tokenize_words from
    markdown_frontend.py. Returns dicts with `kind=word|punct` and the
    standard fields word entries carry.
    """
    tokens: List[Dict[str, Any]] = []
    for raw in re.findall(r"[A-Za-z][A-Za-z0-9_-]*|[\.\?,!;:]", text):
        if re.match(r"[A-Za-z]", raw):
            tokens.append({
                "surface": raw,
                "lemma": raw.lower(),
                "pos": "UNK",
                "hz": 432,
                "field": "neutral",
                "kind": "word",
            })
        else:
            tokens.append({"surface": raw, "kind": "punct"})
    return tokens


def _get_tokenizer() -> Callable[[str], List[Dict[str, Any]]]:
    """Return the body-tuned tokenizer when available, else the fallback."""
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
        from app.services.substrate.markdown_frontend import tokenize_words  # noqa
        return tokenize_words
    except Exception:
        return _fallback_tokenize


# ---------------------------------------------------------------------------
# Rewrite preview
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RewriteMatch:
    """One word-cell that would be touched by a rewrite."""

    path: str
    lemma: str
    pos: str
    surface: str        # the original spelling in the file (e.g. "Choices")
    count: int          # how many times this (lemma, POS) appears in the file


def preview_word_rewrite(
    paths: List[Path],
    *,
    find_lemma: str,
    find_pos: Optional[str] = None,
    replace_lemma: Optional[str] = None,
) -> List[RewriteMatch]:
    """Walk the given files, tokenize each, count word-cells that would be
    touched by a rewrite of `find_lemma`.

    Args:
        paths: Files to scan. The caller decides scope.
        find_lemma: Lemma to match (case-insensitive; stored lowercase).
        find_pos: Optional POS filter. When None, matches any POS.
        replace_lemma: Naming only — does not modify files. Reserved for
            the substrate-native version that will rewrite via recipe.

    Returns RewriteMatch tuples per file with at least one hit, ordered
    by count descending.
    """
    tokenize = _get_tokenizer()
    find = find_lemma.lower()
    pos_filter = find_pos.upper() if find_pos else None

    matches: List[RewriteMatch] = []
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        tokens = tokenize(text)
        per_file: Dict[Tuple[str, str], List[str]] = {}
        for t in tokens:
            if t.get("kind") != "word":
                continue
            if t.get("lemma", "").lower() != find:
                continue
            if pos_filter and t.get("pos", "UNK").upper() != pos_filter:
                continue
            key = (find, t.get("pos", "UNK"))
            per_file.setdefault(key, []).append(t.get("surface", t["lemma"]))
        for (lemma, pos), surfaces in per_file.items():
            matches.append(RewriteMatch(
                path=str(p),
                lemma=lemma,
                pos=pos,
                surface=surfaces[0],   # representative surface form
                count=len(surfaces),
            ))

    matches.sort(key=lambda m: -m.count)
    return matches


def summarize(matches: List[RewriteMatch]) -> Dict[str, int]:
    """Top-line counts: total occurrences and number of files."""
    return {
        "total_occurrences": sum(m.count for m in matches),
        "files_touched": len(matches),
        "distinct_pos": len({m.pos for m in matches}),
    }


# ---------------------------------------------------------------------------
# CLI — runnable demonstration
# ---------------------------------------------------------------------------


def _cli(argv: Optional[List[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lemma", required=True, help="Lemma to find")
    parser.add_argument("--pos", help="Optional POS filter (e.g. NOUN, VERB)")
    parser.add_argument("--paths", nargs="+",
                        help="Files to scan (relative to repo root)")
    parser.add_argument("--top", type=int, default=10,
                        help="How many top files to show")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    if args.paths:
        paths = [repo_root / p for p in args.paths]
    else:
        # Default: walk the same chosen set the in-memory perceptron uses.
        paths = [
            repo_root / "docs/vision-kb/concepts/lc-recipe-branching-sense.md",
            repo_root / "docs/vision-kb/concepts/lc-assemblage-point.md",
            repo_root / "docs/coherence-substrate/recipe-branching-sense.form",
            repo_root / "docs/coherence-substrate/prose-as-recipe.form",
            repo_root / "scripts/prose_recipe_roundtrip.py",
        ]
    paths = [p for p in paths if p.exists()]

    matches = preview_word_rewrite(
        paths, find_lemma=args.lemma, find_pos=args.pos,
    )
    summary = summarize(matches)

    print(f"Rewrite preview for lemma={args.lemma!r}"
          + (f" pos={args.pos!r}" if args.pos else "")
          + f" across {len(paths)} files")
    print(f"  {summary['total_occurrences']} occurrences"
          f" in {summary['files_touched']} files"
          f" across {summary['distinct_pos']} POS")
    print()
    for m in matches[:args.top]:
        rel = Path(m.path).relative_to(repo_root) if m.path.startswith(str(repo_root)) else m.path
        print(f"  {m.count:>4}  {m.lemma}.{m.pos:<6}  ({m.surface!r:<14})  {rel}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_cli())
