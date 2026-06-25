#!/usr/bin/env python3
"""form_cli_stats.py — CARRIER. The `form-cli stats` dashboard: six lenses on the body's real records.

The DERIVED statistics — rates, the tool->native sovereignty share, the small categorical histograms
(escalation reasons, oracles), the learning trend — are the four-way-proven recipe form-cli-stats.fk
(fcst-count / fcst-pct / fcst-native-share / fcst-improving? / fcst-lift). This script only reads the
record files and feeds coded lists to the kernel. Reading 3 MB of catalog to a raw count is carrier
I/O; the meaning on top of the counts is Form.

Records (under ~/.coherence-network/):
  form-cli-corpus/corpus.jsonl   real agent turns — tool frequency, oracle distribution
  form-cli-catalog.jsonl         captured oracle calls — the local lane's training samples
  form-cli-escalations.jsonl     local->remote crossings + reasons
  form-cli-trust.json            local-suffice pass/att (the confidence primitive's accumulator)
  form-cli-model-metric.json     native tool-predictor's last held-out scores (written by `form-cli train`)
"""
import json, os, subprocess, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO = os.path.join(ROOT, "form", "form-kernel-go", "bin-go")
STATS_FK = os.path.join(ROOT, "form", "form-stdlib", "form-cli-stats.fk")
CN = os.path.expanduser("~/.coherence-network")
CORPUS = f"{CN}/form-cli-corpus/corpus.jsonl"
CATALOG = f"{CN}/form-cli-catalog.jsonl"
ESCAL = f"{CN}/form-cli-escalations.jsonl"
TRUST = f"{CN}/form-cli-trust.json"
METRIC = f"{CN}/form-cli-model-metric.json"
RAG_INDEX = f"{CN}/rag-index/index.jsonl"


def kernel(exprs):
    """run form-cli-stats.fk + a list of (print ...) exprs on the Go kernel; return outputs as ints/strs."""
    src = open(STATS_FK).read() + "\n" + "\n".join(f"(print {e})" for e in exprs) + "\n"
    tmp = "/tmp/fcst_run.fk"; open(tmp, "w").write(src)
    return subprocess.run([GO, tmp], capture_output=True, text=True).stdout.split()


def pct(n, total):
    return int(kernel([f"(fcst-pct {n} {total})"])[0])


def jsonl(path):
    if not os.path.exists(path): return []
    out = []
    for l in open(path):
        l = l.strip()
        if l:
            try: out.append(json.loads(l))
            except Exception: pass
    return out


def bar(p, width=24):
    return "█" * int(round(p / 100 * width)) + "·" * (width - int(round(p / 100 * width)))


def main():
    turns = jsonl(CORPUS)
    catalog_n = sum(1 for _ in open(CATALOG)) if os.path.exists(CATALOG) else 0
    escal = jsonl(ESCAL)
    trust = json.load(open(TRUST)) if os.path.exists(TRUST) else {}
    metric = json.load(open(METRIC)) if os.path.exists(METRIC) else None
    rag_docs = sum(1 for _ in open(RAG_INDEX)) if os.path.exists(RAG_INDEX) else 0
    ask = trust.get("ask", {"pass": 0, "att": 0})
    att, passed = ask.get("att", 0), ask.get("pass", 0)
    escalated = att - passed

    print("\n  form-cli stats — the body's real records (counts: carrier I/O · stats: form-cli-stats.fk, four-way)\n")

    # 1 ─ LEARNING
    print("  ── learning ──")
    print(f"    captured oracle→native samples (catalog) : {catalog_n}")
    print(f"    local-suffice rate (trust)               : {pct(passed, att)}%  ({passed}/{att} asks held locally)")
    print(f"    escalations logged                        : {len(escal)}")
    if att >= 8:
        # outcome sequence over asks (1 = local sufficed) — the flywheel turning
        seq = [1] * passed + [0] * escalated
        imp = kernel([f"(fcst-improving? (list {' '.join(map(str, seq))}))",
                      f"(fcst-lift (list {' '.join(map(str, seq))}))"])
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
        won = [k for k, v in metric.get("perTool", {}).items()]
        print(f"    per-tool measured       : {', '.join(f'{k} {v:.0f}%' for k, v in list(metric.get('perTool', {}).items())[:6])}")
    else:
        print("    native tool-predictor not yet measured — run `form-cli train`")

    # 5 ─ LOCAL GROUNDED LANE
    print("\n  ── local grounded lane ──")
    print(f"    answers held locally (sufficient)        : {passed}  ({pct(passed, att)}% of asks)")
    print(f"    air-gapped grounded hits                 : {passed} asks")

    # 6 ─ REMOTE ORACLE
    print("\n  ── remote oracle ──")
    print(f"    escalations (network crossings)          : {len(escal)}  ({pct(escalated, att)}% of asks)")
    if escal:
        reasons = [e.get("reason", "?") for e in escal]
        cats = sorted(set(reasons))
        coded = [cats.index(r) for r in reasons]
        lst = "(list " + " ".join(map(str, coded)) + ")"
        counts = kernel([f"(fcst-count {lst} {i})" for i in range(len(cats))])  # one bare int per category
        for c, n in zip(cats, counts):
            print(f"    reason  {c:16} {n}  ({pct(int(n), len(escal))}% of escalations)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
