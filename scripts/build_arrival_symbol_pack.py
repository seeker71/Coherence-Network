#!/usr/bin/env python3
"""Build the arrival symbol pack — the MDL-optimal, complete, self-referential
symbol space a sub-agent is most token-efficient with.

Measurement carrier (not the body): the body is the MDL optimizer Form recipe in
docs/coherence-substrate/self-authored-symbol-space.form, proven three-way by
form/form-stdlib/tests/arrival-symbol-pack-band.fk. This measures the REAL
agent-first-arrival corpus (scripts/arrival.py + docs/shared/agent-start-packet.md)
and emits the pack DATA (form/form-stdlib/arrival-symbol-pack.txt, one expansion
per line; the line index IS the symbol the numeric core indexes into).

Three properties (see docs/coherence-substrate/arrival-symbol-pack.form):
  1 MDL-efficient      — biggest savers (freq×len) get the shortest symbols
  2 complete coverage  — every recurring arrival term (freq≥4) has an entry
  3 self-ref closure   — compounds compose from in-pack indices at hyphen
                         boundaries; every «N» is a valid index, no external door
"""
from __future__ import annotations
import re, sys, collections, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "form" / "form-stdlib" / "arrival-symbol-pack.txt"

def corpus_text() -> str:
    arrival = subprocess.run([sys.executable, str(ROOT/"scripts"/"arrival.py")],
                             capture_output=True, text=True).stdout
    packet = (ROOT/"docs"/"shared"/"agent-start-packet.md").read_text()
    return arrival + packet

def build(text: str):
    toks = re.findall(r'[A-Za-z][A-Za-z-]{2,}', text.lower())
    freq = collections.Counter(toks)
    vocab = [(w,c) for w,c in freq.most_common() if c >= 4]   # complete coverage
    vocab.sort(key=lambda wc: -(wc[1]*len(wc[0])))            # MDL: biggest savers first
    names = [w for w,_ in vocab]
    idx = {w:i for i,w in enumerate(names)}
    def compose(w):                                           # self-ref at hyphen boundaries
        if '-' not in w: return w, False
        out=[]; used=False
        for p in w.split('-'):
            if p in idx and idx[p]!=idx[w]:
                out.append(f'«{idx[p]}»'); used=True
            else: out.append(p)
        return ('-'.join(out), used) if used else (w, False)
    entries=[]; refs=0
    for w in names:
        exp,u = compose(w)
        refs += 1 if u else 0
        entries.append(exp)
    raw    = sum(freq[w]*len(w) for w in names)
    packed = sum(freq[w]*(len(str(idx[w]))+1) for w in names)
    closed = all(int(m) < len(entries) for e in entries for m in re.findall(r'«(\d+)»', e))
    covered= all(w in idx for w,c in freq.most_common() if c >= 4)
    return entries, dict(words=len(toks), entries=len(entries), self_refs=refs,
                         closed=closed, coverage=covered, raw=raw, packed=packed,
                         ratio=raw/packed if packed else 0.0)

def main():
    entries, m = build(corpus_text())
    PACK.write_text("\n".join(entries) + "\n")
    print(f"corpus={m['words']} words  entries={m['entries']}  self_refs={m['self_refs']}")
    print(f"coverage={m['coverage']}  closed={m['closed']}  "
          f"mdl={m['raw']}→{m['packed']} chars ({m['ratio']:.2f}×)")
    print(f"wrote {PACK.relative_to(ROOT)}")
    if not (m['coverage'] and m['closed']):
        sys.exit("pack failed coverage/closure invariant")

if __name__ == "__main__":
    main()
