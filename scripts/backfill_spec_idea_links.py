#!/usr/bin/env python3
# spec: 181-full-code-traceability
# idea: full-code-traceability
"""Phase 1.1 - Backfill idea_id into spec file frontmatter.
Usage: python3 scripts/backfill_spec_idea_links.py [--apply]
"""
from __future__ import annotations
import argparse, csv, re, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = REPO_ROOT / "specs"
DATA_DIR = REPO_ROOT / "data"

_IDEA_ID_PATTERNS = [
    re.compile(r"idea[_-]id:\s*[""'""'""']?([a-z0-9][a-z0-9-]{2,})", re.IGNORECASE),
    re.compile(r"parent_idea[_-]id:\s*[""'""'""']?([a-z0-9][a-z0-9-]{2,})", re.IGNORECASE),
]
_NOISE = frozenset({"none","null","n/a","string","object","array","type","id","slug"})

def extract_idea_id(content):
    for p in _IDEA_ID_PATTERNS:
        m = p.search(content)
        if m:
            v = m.group(1).lower().strip()
            if v not in _NOISE and len(v) >= 3:
                return v, 1.0
    return None, 0.0

def has_idea_id(content):
    return extract_idea_id(content)[0] is not None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--min-confidence", type=float, default=0.85)
    args = parser.parse_args()
    DATA_DIR.mkdir(exist_ok=True)
    rows = []
    updated = skipped = needs_review = total = 0
    for f in sorted(SPECS_DIR.glob("*.md")):
        if f.name == "TEMPLATE.md": continue
        total += 1
        content = f.read_text(errors="replace")
        if has_idea_id(content):
            skipped += 1
            idea_id, conf = extract_idea_id(content)
            rows.append({"spec_file": f.name, "idea_id_found": idea_id or "", "confidence": conf, "action_taken": "already_linked"})
            continue
        idea_id, confidence = extract_idea_id(content)
        if idea_id and confidence >= args.min_confidence:
            action = "needs_review"
            if args.apply:
                fm = re.match(r"^---
(.*?)
---", content, re.DOTALL)
                if fm and "idea_id" not in fm.group(1):
                    f.write_text("---
" + fm.group(1) + "
idea_id: " + idea_id + "
---" + content[fm.end():])
                elif not fm:
                    f.write_text("---
idea_id: " + idea_id + "
---

" + content)
                action = "written"
            else:
                action = f"would_write:{idea_id}"
            updated += 1
        else:
            needs_review += 1
            action = "needs_review"
        rows.append({"spec_file": f.name, "idea_id_found": idea_id or "", "confidence": round(confidence, 3), "action_taken": action})
    out = DATA_DIR / "backfill_spec_idea_links.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["spec_file","idea_id_found","confidence","action_taken"])
        w.writeheader(); w.writerows(rows)
    print(f"Total: {total}, Skipped: {skipped}, Updated: {updated}, Needs review: {needs_review}")
    print(f"Coverage: {(skipped+updated)*100//max(total,1)}%")
    print(f"Report: {out}")
    if not args.apply: print("Dry run. Use --apply to write changes.")

if __name__ == "__main__":
    sys.exit(main())
