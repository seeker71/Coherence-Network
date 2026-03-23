#!/usr/bin/env python3
"""Build README files from templates by expanding <!-- include: path --> markers.

No external dependencies. Works with Python 3.8+.
"""

import os
import re
import sys
import shutil

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INCLUDE_RE = re.compile(r"^<!-- include: (.+?) -->$", re.MULTILINE)

# Templates and their output paths (relative to repo root).
# Special case: skills template also copies to an external path.
SKILL_EXTERNAL = os.path.expanduser(
    "~/.openclaw/workspace/skills/coherence-network/SKILL.md"
)

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

            # Special: copy skill output to external path
            if tpl_rel == "skills/coherence-network/SKILL.template.md":
                ext_dir = os.path.dirname(SKILL_EXTERNAL)
                if os.path.isdir(ext_dir):
                    shutil.copy2(out_abs, SKILL_EXTERNAL)
                    print(f"COPY  {SKILL_EXTERNAL}")
                else:
                    print(f"SKIP  external copy ({ext_dir} not found)")

    return all_ok


def main() -> None:
    check = "--check" in sys.argv
    ok = build(check=check)
    if check and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
