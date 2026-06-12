#!/usr/bin/env python3
"""Op-gap analysis for the fourth arm: which head-words do mismatching bands
use that the flattener's vocabulary lacks, ranked by how many bands each
missing op blocks. Reads the survey's results.tsv; BML sources are read via
their source-compiled artifacts (same cache key discipline as the survey)."""
import hashlib
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

FORM = Path(__file__).resolve().parent.parent
OUT = FORM / "form-stdlib/.cache/fourth-survey"
SC_DIR = FORM / "form-stdlib/.cache/source-compiled"

KNOWN = {
    "add", "sub", "le", "cons", "nth", "head", "tail", "len",
    "str_len", "str_eq", "str_concat", "div", "mod",
    "band", "bor", "bxor", "shl_u32", "shr_u32", "rotr_u32",
    "add_u32", "bnot_u32", "mul",
    "if", "list", "empty", "do", "gt", "ge", "eq", "and",
    "ord", "not", "defn", "let",
    # lowerings (2026-06-12)
    "lt", "or", "char_at", "byte_to_str",
    # fourth-shim.fk rows — core mirrors + string stones
    "nil?", "plus", "minus", "times", "divide", "identity",
    "abs", "min2", "max2", "sum", "product", "maximum", "minimum",
    "append", "range", "take", "drop", "reverse",
    "substring", "int_to_str", "str_to_int", "str_find",
}

CHAIN = [
    "form-stdlib/form-ontology-loader.fk", "form-stdlib/line-grammar.fk",
    "form-stdlib/bmf-core.fk", "form-stdlib/bmf-grammar.fk",
    "form-stdlib/bml.fk", "form-stdlib/bml-source.fk",
    "form-stdlib/source-compiler.fk",
]


def compiler_stamp():
    h = hashlib.sha1()
    for f in CHAIN + ["form-kernel-go/bin-go"]:
        h.update((FORM / f).read_bytes())
    return h.hexdigest()[:16]


def shasum16(path):
    # the survey keys by `shasum < file` (sha1 of content)
    return hashlib.sha1(path.read_bytes()).hexdigest()[:16]


STAMP = compiler_stamp()


def prepped(path):
    text = path.read_text(errors="replace")
    if not re.search(r"^\s*section \[", text, re.M):
        return path
    cached = SC_DIR / f"{shasum16(path)}-{STAMP}.fk"
    return cached if cached.exists() else None


def band_srcs(stem):
    band = FORM / f"form-stdlib/tests/{stem}-band.fk"
    text = band.read_text(errors="replace")
    m = re.search(r"^; preludes:(.*)$", text, re.M)
    mods = []
    if m:
        mods = [p for p in m.group(1).split() if not p.endswith("core.fk")]
    if not mods and (FORM / f"form-stdlib/{stem}.fk").exists():
        mods = [f"form-stdlib/{stem}.fk"]
    return [FORM / p for p in mods] + [band]


def strip_comments(text):
    return re.sub(r";[^\n]*", "", text)


def main():
    results = OUT / "results.tsv"
    rows = [
        ln.split("\t")
        for ln in results.read_text().splitlines()
        if ln.strip()
    ]
    blocked = defaultdict(set)   # missing-op -> bands
    band_missing = {}            # band -> sorted missing ops
    unreadable = []
    for row in rows:
        stem, cat = row[0], row[1]
        if not (cat.endswith("-mismatch") or cat.endswith("-flatten-empty")):
            continue
        srcs = []
        ok = True
        for p in band_srcs(stem):
            pp = prepped(p)
            if pp is None:
                ok = False
                break
            srcs.append(strip_comments(pp.read_text(errors="replace")))
        if not ok:
            unreadable.append(stem)
            continue
        all_text = "\n".join(srcs)
        defined = set(re.findall(r"\(defn\s+([^\s()]+)", all_text))
        # a defn's parameter list reads as a parenthesized form — its first
        # name is no op; subtract every declared param (and fn-lambda params)
        params = set()
        for plist in re.findall(r"\(defn\s+[^\s()]+\s*\(([^)]*)\)", all_text):
            params.update(plist.split())
        for plist in re.findall(r"\(fn\s*\(([^)]*)\)", all_text):
            params.update(plist.split())
        heads = set(re.findall(r"\(([a-z_][^\s()]*)", all_text))
        missing = heads - KNOWN - defined - params
        band_missing[stem] = sorted(missing)
        for op in missing:
            blocked[op].add(stem)

    print(f"bands analyzed: {len(band_missing)}  (unreadable: {len(unreadable)})")
    print("\n── missing ops by blocked-band count ──")
    for op, bands in sorted(blocked.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(bands):4d}  {op}")
    print("\n── bands blocked ONLY by the top-N closable ops ──")
    # cumulative: if we teach ops one by one (most-blocking first), how many
    # bands become fully covered at each step?
    order = [op for op, _ in sorted(blocked.items(), key=lambda kv: -len(kv[1]))]
    taught = set()
    for op in order[:40]:
        taught.add(op)
        freed = [b for b, miss in band_missing.items() if set(miss) <= taught]
        print(f"teach {op:24s} -> {len(freed):3d} bands fully in-vocabulary")
    (OUT / "band-missing-ops.tsv").write_text(
        "\n".join(f"{b}\t{' '.join(m)}" for b, m in sorted(band_missing.items()))
        + "\n"
    )
    print(f"\nper-band detail: {OUT / 'band-missing-ops.tsv'}")


if __name__ == "__main__":
    main()
