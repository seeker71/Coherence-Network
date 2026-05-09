#!/usr/bin/env python3
"""Generate machine-translated locale siblings (de/es/id) for curated
/people/{slug}/en.tsx content modules — the safe-strings path.

Translates: metadata.{title,description}, breadcrumbName,
hero.{eyebrow,name}, every fact's label and string-typed value,
every article's heading. Leaves JSX bodies (welcome, body, footer,
JSX-typed fact values, panel/article bodies) in English; the
PersonProfileTemplate's source-language disclosure banner explains
this honestly to non-EN readers in their own language.

JSX-body translation through libretranslate produces edge-case
build breaks (lowercases SVG attribute names, mangles fragments,
splits sentences awkwardly around placeholders). The two paths
forward — refactor content modules into plain-string + markdown,
or use the Claude API translator backend — are deferred to their
own focused breath. The locale-router doesn't care which path the
file came through; refinement of any individual {lang}.tsx file is
welcome at any time.

Usage:
    LIBRETRANSLATE_URL=http://localhost:5000 \\
        python3 scripts/generate_curated_translations.py --all

    python3 scripts/generate_curated_translations.py --slug bml-language --target-lang de --overwrite
"""
from __future__ import annotations
import argparse, json, os, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "web" / "content" / "people"
LT_URL = os.environ.get("LIBRETRANSLATE_URL", "http://localhost:5000")
DEFAULT_TARGETS = ("de", "es", "id")

TRANSLATABLE_FIELDS = {
    "title", "description", "breadcrumbName",
    "eyebrow", "name", "heading", "label", "value",
}

HEADER = """// ════════════════════════════════════════════════════════════════════
// MASCHINELL ÜBERSETZT · machine-translated string fields from en.tsx
// JSX bodies remain in English; refinement welcome.
// To regenerate: python3 scripts/generate_curated_translations.py \\
//                  --slug {slug} --target-lang {lang} --overwrite
// ════════════════════════════════════════════════════════════════════
"""


def translate(text: str, target_lang: str) -> str:
    if not text or not text.strip():
        return text
    s = text.strip()
    # Skip URLs, classnames, gradient/HSL strings, single-token labels.
    if s.startswith(("http://", "https://", "/", "#")):
        return text
    if "linear-gradient" in s or s.startswith("hsl(") or "hsl(" in s and ")" in s and len(s) < 80:
        return text
    if re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", s):  # single-kebab-token
        return text
    # Tailwind-class detector: tokens with class-shaped patterns
    words = s.split()
    if len(words) >= 3 and all(re.match(r"^[a-z][a-z0-9:\[\]/.\-_()]*$", w) for w in words):
        return text
    req = urllib.request.Request(
        f"{LT_URL}/translate",
        data=json.dumps({"q": text, "source": "en", "target": target_lang, "format": "text"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r).get("translatedText", text)
    except Exception as e:
        sys.stderr.write(f"  warn: {e}\n")
        return text


def translate_module(en_text: str, target_lang: str) -> str:
    fields_pat = "|".join(sorted(TRANSLATABLE_FIELDS))
    pat = re.compile(rf'(\s|^|,|\{{)\s*({fields_pat})\s*:\s*"((?:[^"\\]|\\.)*)"')
    def _sub(m: re.Match) -> str:
        prefix, field, value = m.group(1), m.group(2), m.group(3)
        translated = translate(value, target_lang).replace('"', '\\"')
        return f'{prefix}{field}: "{translated}"'
    return pat.sub(_sub, en_text)


def update_index(slug: str) -> None:
    index_path = ROOT / slug / "index.ts"
    if not index_path.exists():
        return
    text = index_path.read_text()
    fn_match = re.search(r'export function (\w+)\(', text)
    if not fn_match:
        return
    fn_name = fn_match.group(1)
    available = sorted({p.stem for p in (ROOT / slug).glob("*.tsx") if p.stem in {"en", "de", "es", "id"}})
    if "en" not in available:
        return
    non_en = [l for l in available if l != "en"]
    imports = ['import en from "./en";']
    for lang in non_en:
        imports.append(f'import {lang} from "./{lang}";')
    if non_en:
        dispatch = "\n".join(f'  if (lang === "{l}") return {l};' for l in non_en)
        body = f'export function {fn_name}(lang: LocaleCode): PersonProfileContent {{\n{dispatch}\n  return en;\n}}'
    else:
        body = f'export function {fn_name}(_lang: LocaleCode): PersonProfileContent {{\n  return en;\n}}'
    index_path.write_text(
        'import type { LocaleCode } from "@/lib/locales";\n'
        'import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";\n'
        + "\n".join(imports) + "\n\n" + body + "\n"
    )


def generate(slug: str, lang: str, *, overwrite: bool = False) -> bool:
    en_path = ROOT / slug / "en.tsx"
    out_path = ROOT / slug / f"{lang}.tsx"
    if not en_path.exists():
        return False
    if out_path.exists() and not overwrite:
        return False
    print(f"  → {slug}/{lang}.tsx")
    try:
        translated = translate_module(en_path.read_text(), lang)
        out_path.write_text(HEADER.format(slug=slug, lang=lang) + translated)
        return True
    except Exception as e:
        print(f"     ✗ {e}")
        if out_path.exists():
            out_path.unlink()
        return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--slug")
    p.add_argument("--all", action="store_true")
    p.add_argument("--target-lang")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args()
    if not args.slug and not args.all:
        p.error("specify --slug or --all")
    targets = [args.target_lang] if args.target_lang else list(DEFAULT_TARGETS)
    if args.slug:
        slugs = [args.slug]
    else:
        slugs = sorted(d.name for d in ROOT.iterdir() if d.is_dir() and (d / "en.tsx").exists())
    print(f"=== generate_curated_translations · langs={targets} · slugs={len(slugs)} ===")
    n = 0
    for slug in slugs:
        for lang in targets:
            if generate(slug, lang, overwrite=args.overwrite):
                n += 1
        update_index(slug)
    print(f"\n  generated {n} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
