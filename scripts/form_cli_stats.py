#!/usr/bin/env python3
"""form_cli_stats.py — CARRIER. The `form-cli stats` dashboard: six lenses on the body's real records.

The DERIVED statistics — rates, the tool->native sovereignty share, the small categorical histograms
(escalation reasons, oracles), the learning trend — are the four-way-proven recipe form-cli-stats.fk
(fcst-count / fcst-pct / fcst-native-share / fcst-improving? / fcst-lift). This script only reads the
record files and feeds coded lists to the kernel. Reading 3 MB of catalog to a raw count is carrier
I/O; the meaning on top of the counts is Form.

Records (under ~/.coherence-network/; canonical ask ledger under rag-requests/):
  form-cli-corpus/corpus.jsonl   real agent turns — tool frequency, oracle distribution
  form-cli-catalog.jsonl         captured oracle calls — the local lane's training samples
  rag-requests/form-cli-asks.jsonl
                                canonical native trust rows + observed remote crossings
  form-cli-model-metric.json     native tool-predictor's last held-out scores (written by `form-cli train`)
"""
import collections
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GO = ROOT / "form" / "form" / "form-kernel-go" / "bin-go"
STATS_FK = ROOT / "form" / "form" / "form-stdlib" / "form-cli-stats.fk"
CN = Path.home() / ".coherence-network"
CORPUS = CN / "form-cli-corpus" / "corpus.jsonl"
CATALOG = CN / "form-cli-catalog.jsonl"
ASKS = CN / "rag-requests" / "form-cli-asks.jsonl"
LEGACY_ASKS = CN / "form-cli-asks.jsonl"
METRIC = CN / "form-cli-model-metric.json"
RAG_INDEX = CN / "rag-index" / "index.jsonl"


def kernel(exprs):
    """run form-cli-stats.fk + a list of (print ...) exprs on the Go kernel; return outputs as ints/strs."""
    src = STATS_FK.read_text(encoding="utf-8")
    src += "\n" + "\n".join(f"(print {expr})" for expr in exprs) + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".fk", delete=False) as handle:
        handle.write(src)
        temp_path = Path(handle.name)
    try:
        result = subprocess.run(
            [GO, temp_path],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.split()
    finally:
        temp_path.unlink(missing_ok=True)


def pct(n, total):
    return int(kernel([f"(fcst-pct {n} {total})"])[0])


def jsonl(path):
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def line_count(path):
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def load_json(path):
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def bar(p, width=24):
    filled = round(p / 100 * width)
    return "█" * filled + "·" * (width - filled)


def main():
    turns = jsonl(CORPUS)
    catalog_n = line_count(CATALOG)
    ask_records = jsonl(LEGACY_ASKS) + jsonl(ASKS)
    trust_events = [row for row in ask_records if row.get("event") == "trust"]
    remote_events = [
        row
        for row in ask_records
        if row.get("event") == "remote" and row.get("status") == "served"
    ]
    metric = load_json(METRIC)
    rag_docs = line_count(RAG_INDEX)
    att = len(trust_events)
    passed = sum(row.get("decision") == "accept" for row in trust_events)
    grounded_hits = sum(row.get("grounded") == "yes" for row in trust_events)

    print("\n  form-cli stats — the body's real records (counts: carrier I/O · stats: form-cli-stats.fk, four-way)\n")

    # 1 ─ LEARNING
    print("  ── learning ──")
    print(f"    captured oracle→native samples (catalog) : {catalog_n}")
    print(f"    local-suffice rate (trust)               : {pct(passed, att)}%  ({passed}/{att} asks held locally)")
    print(f"    observed remote crossings                : {len(remote_events)}")
    if att >= 8:
        # outcome sequence over asks (1 = local sufficed) — the flywheel turning
        seq = [1 if row.get("decision") == "accept" else 0 for row in trust_events]
        imp = kernel(
            [
                f"(fcst-improving? (list {' '.join(map(str, seq))}))",
                f"(fcst-lift (list {' '.join(map(str, seq))}))",
            ]
        )
        print(f"    learning trend                            : {'improving' if imp[0]=='1' else 'flat/early'} ({imp[1]}pp late-vs-early)")
    else:
        print(f"    learning trend                            : needs more logged asks (have {att})")

    # 2 ─ MODEL
    print("\n  ── models ──")
    oc = collections.Counter(t.get("oracle", "?") for t in turns)
    for name, n in oc.most_common(6):
        print(f"    corpus oracle  {name:14} {n:5}  ({pct(n, len(turns))}%)")
    print("    local answer lane                        : fkwu grounded RAG")
    print(f"    local RAG index                          : {rag_docs} cells")
    print("    prose synthesis lane                     : pending fkwu+Metal GGUF/block-join composition")
    print("    synthesis receipt                        : form-cli synthesis-status")

    # 3 ─ TOOL
    print("\n  ── tools (real agent corpus) ──")
    tc = collections.Counter()
    for t in turns:
        for s in {st.get("tool") for st in t.get("steps", []) if isinstance(st, dict)}:
            if s: tc[s] += 1
    for name, n in tc.most_common(8):
        p = pct(n, len(turns))
        print(f"    {name:18} {n:5}  {bar(p)} {p}%")

    # 4 ─ TOOL → NATIVE  (the flywheel: how well the native model serves tool selection)
    print("\n  ── tool → native (the native predictor vs the no-learning baseline) ──")
    if metric:
        print(f"    held-out micro-accuracy : {metric['micro']:.1f}%  vs {metric['baseline_micro']:.1f}% baseline")
        print(f"    exact tool-set match    : {metric['exact']:.1f}%  vs {metric['baseline_exact']:.1f}% baseline")
        print(f"    covers all used tools   : {metric['cover']:.1f}%  vs {metric['baseline_cover']:.1f}% baseline")
        print(f"    per-tool measured       : {', '.join(f'{k} {v:.0f}%' for k, v in list(metric.get('perTool', {}).items())[:6])}")
    else:
        print("    native tool-predictor not yet measured — run `form-cli train`")

    # 5 ─ LOCAL GROUNDED LANE
    print("\n  ── local grounded lane ──")
    print(f"    answers held locally (sufficient)        : {passed}  ({pct(passed, att)}% of asks)")
    print(f"    air-gapped grounded hits                 : {grounded_hits} asks")

    # 6 ─ REMOTE ORACLE
    print("\n  ── remote oracle ──")
    print(f"    escalations (network crossings)          : {len(remote_events)}  ({pct(len(remote_events), att)}% of asks)")
    if remote_events:
        reasons = [e.get("reason", "?") for e in remote_events]
        cats = sorted(set(reasons))
        coded = [cats.index(r) for r in reasons]
        lst = "(list " + " ".join(map(str, coded)) + ")"
        counts = kernel([f"(fcst-count {lst} {i})" for i in range(len(cats))])  # one bare int per category
        for c, n in zip(cats, counts):
            print(f"    reason  {c:16} {n}  ({pct(int(n), len(remote_events))}% of escalations)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
