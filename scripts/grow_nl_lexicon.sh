#!/usr/bin/env bash
# grow_nl_lexicon.sh — grow the translation pivot's neutral-symbol lexicon from the
# REAL parallel corpus. The content lives in the locale files (web/messages/{en,id}.json);
# this is a thin PROJECTOR (the "no seed scripts" pattern: source is the files, a sync
# pass projects them). The translation LOGIC stays in form-stdlib/nl-translate.fk (Form);
# this only fills the lexicon's DATA rows between the >>>CORPUS / <<<CORPUS markers.
#
# Each row is (symbol phase en id): the symbol is the body's OWN neutral token (c<i>,
# a door over the NodeID, no tongue privileged); the phase is thermodynamic
# (substrate-thermodynamics) — corpus words enter as WATER (actively circulating in the
# live UI); the structural seeds above the marker stay ICE. The MDL-minimal symbol
# assignment (frequent meaning → short symbol) is the named next rung; symbols are
# sequential here. Re-run to update as the corpus changes — the table is dynamic.
#
# Usage: scripts/grow_nl_lexicon.sh [cap]   (cap = max corpus rows, default 40)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CAP="${1:-40}"
TARGET="$ROOT/form/form-stdlib/nl-translate.fk"
python3 - "$ROOT" "$CAP" "$TARGET" <<'PY'
import json, sys
root, cap, target = sys.argv[1], int(sys.argv[2]), sys.argv[3]
def flat(d, p=''):
    o = {}
    for k, v in d.items():
        if isinstance(v, dict): o.update(flat(v, p + k + '.'))
        elif isinstance(v, str): o[p + k] = v
    return o
en = flat(json.load(open(f"{root}/web/messages/en.json")))
idj = flat(json.load(open(f"{root}/web/messages/id.json")))
SEED = {"source","native","kernel","body","cell","recipe","witness"}
seen, rows = set(), []
for k in sorted(en):
    if k not in idj: continue
    e, i = en[k].strip().lower(), idj[k].strip().lower()
    if not e or not i or ' ' in e or ' ' in i: continue
    if not e.isalpha() or not i.isalpha(): continue
    if len(e) < 2 or e in SEED or e in seen or e == i: continue   # skip seeds, dups, identical, codes
    seen.add(e); rows.append((e, i))
total = len(rows); rows = rows[:cap]
src = open(target).read().splitlines(keepends=True)
out, lo, hi = [], None, None
for n, line in enumerate(src):
    if ">>>CORPUS" in line: lo = n
    if "<<<CORPUS" in line: hi = n
if lo is None or hi is None or hi <= lo:
    sys.exit("markers >>>CORPUS / <<<CORPUS not found in " + target)
gen = []
for n, (e, i) in enumerate(rows):
    gen.append('            (list "c%d" "water" "%s" "%s")\n' % (n, e, i))
new = src[:lo+1] + gen + src[hi:]
open(target, "w").write("".join(new))
print(f"grew lexicon: {len(rows)} corpus rows (of {total} pairs, cap {cap}) -> {target}")
PY
