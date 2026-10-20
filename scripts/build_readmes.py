#!/usr/bin/env python3
"""Build README files from templates by expanding <!-- include: path --> markers.

No external dependencies. Works with Python 3.8+.
"""

import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INCLUDE_RE = re.compile(r"^<!-- include: (.+?) -->$", re.MULTILINE)

# Templates and their output paths (relative to repo root).
# Installing a skill is a separate, explicit whole-directory operation.
TEMPLATES = [
    "README.template.md",
    "cli/README.template.md",
    "mcp-server/README.template.md",
    "skills/coherence-network/SKILL.template.md",
]


def output_path(template_rel: str) -> str:
    """README.template.md -> README.md"""
    return template_rel.replace(".template.md", ".md")


def expand(template_text: str, template_name: str) -> str:
    header = f"<!-- AUTO-GENERATED from {template_name}. Edit the template, not this file. -->\n"

    def _replace(m: re.Match) -> str:
        frag_rel = m.group(1).strip()
        frag_abs = os.path.join(REPO_ROOT, frag_rel)
        if not os.path.isfile(frag_abs):
            print(f"ERROR: fragment not found: {frag_abs}", file=sys.stderr)
            sys.exit(1)
        with open(frag_abs, "r") as f:
            return f.read().rstrip("\n")

    body = INCLUDE_RE.sub(_replace, template_text)
    # Skill discovery reads YAML at byte zero; generated provenance belongs
    # after the metadata, never in front of it.
    if template_name == "SKILL.template.md" and body.startswith("---\n"):
        closing = body.find("\n---\n", 4)
        if closing != -1:
            end = closing + len("\n---\n")
            return body[:end] + "\n" + header + body[end:]
    return header + body


def build(check: bool = False) -> bool:
    all_ok = True
    for tpl_rel in TEMPLATES:
        tpl_abs = os.path.join(REPO_ROOT, tpl_rel)
        if not os.path.isfile(tpl_abs):
            print(f"SKIP: {tpl_rel} (not found)")
            continue

        with open(tpl_abs, "r") as f:
            tpl_text = f.read()

        result = expand(tpl_text, os.path.basename(tpl_rel))
        out_rel = output_path(tpl_rel)
        out_abs = os.path.join(REPO_ROOT, out_rel)

        if check:
            if os.path.isfile(out_abs):
                with open(out_abs, "r") as f:
                    existing = f.read()
                if existing != result:
                    print(f"DIFF: {out_rel} is out of date (re-run scripts/build_readmes.py)")
                    all_ok = False
                else:
                    print(f"OK:   {out_rel}")
            else:
                print(f"MISS: {out_rel} does not exist")
                all_ok = False
        else:
            os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)
            with open(out_abs, "w") as f:
                f.write(result)
            print(f"WROTE {out_rel}")

    return all_ok


def main() -> None:
    check = "--check" in sys.argv
    ok = build(check=check)
    if check and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
