#!/usr/bin/env python3
"""form_cli_ask_smart.py — CARRIER. Local-first ask with a PROVEN multi-signal escalation.

The decision is NOT here. It is the four-way-proven Form recipe form-cli-sufficiency.fk
(fsuf-verdict): run the local grounded oracle, read THIS RUN's signals — has-output,
shape-ok, content (a local judge's coverage), confidence (the judge's groundedness),
trust (accumulated), retries-left — and the recipe decides accept / retry / escalate.
This script only gathers the signals, invokes the kernel for the verdict, and on escalate
calls the subscription oracle (claude -p) for the real answer, recording the crossing +
reason so the local lane learns where it fell short.

The bar is day-to-day parity with claude-code: local when local is enough, remote when it
isn't — never a hard "remote = last resort" rule.

  form_cli_ask_smart.py "question" [-m local-model] [-j judge-model] [--remote "claude -p"]
"""
import argparse, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import form_cli_rag as rag

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO = os.path.join(ROOT, "form", "form-kernel-go", "bin-go")
RECIPES = ["form-cli-router.fk", "form-cli-judge.fk", "form-cli-sufficiency.fk"]
TRUST_FILE = os.path.expanduser("~/.coherence-network/form-cli-trust.json")
ESCALATIONS = os.path.expanduser("~/.coherence-network/form-cli-escalations.jsonl")
REASONS = {0: "ok", 1: "empty", 2: "bad-shape", 3: "weak-content", 4: "low-confidence", 5: "low-trust"}
VERDICTS = {0: "accept", 1: "retry", 2: "escalate"}


def ollama(model, prompt):
    return rag._post("/api/generate", {"model": model, "prompt": prompt, "stream": False})["response"].strip()


def judge(question, answer, model):
    """ONE local call -> (content 0..100, groundedness 0..100). The fcj content lane + a confidence read."""
    out = ollama(model, f"Question: {question}\n\nProposed answer:\n{answer}\n\n"
                        "Rate the answer on two axes, each an integer 0-100. COVERAGE: how fully it "
                        "answers the question. GROUNDEDNESS: how specific and supported it is (not vague "
                        "or hedged). Reply with ONLY two integers separated by a space: COVERAGE GROUNDEDNESS")
    nums = [int(x) for x in re.findall(r"\d+", out)][:2]
    return tuple((nums + [40, 40])[:2])


def kernel_verdict(signals):
    """invoke the FOUR-WAY-PROVEN recipe on the Go kernel for the verdict + reason."""
    sig = " ".join(map(str, signals))
    src = "\n".join(open(os.path.join(ROOT, "form", "form-stdlib", r)).read() for r in RECIPES)
    src += f"\n(print (fsuf-verdict (fsuf-signals {sig})))\n(print (fsuf-reason (fsuf-signals {sig})))\n"
    tmp = "/tmp/fsuf_run.fk"; open(tmp, "w").write(src)
    out = subprocess.run([GO, tmp], capture_output=True, text=True).stdout.split()
    return int(out[0]), int(out[1])


def load_trust(key):
    try: db = json.load(open(TRUST_FILE))
    except Exception: db = {}
    stat = db.get(key, {"pass": 3, "att": 5})          # a modest prior, not 0 (an unproven lane still tries)
    return db, stat, min(100, stat["pass"] * 100 // max(1, stat["att"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("-m", "--model", default="coder", help="local answerer")
    ap.add_argument("-j", "--judge", default="llama3.2:3b", help="local judge")
    ap.add_argument("--remote", default="claude -p", help="subscription oracle for escalation")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--retries", type=int, default=1)
    a = ap.parse_args()

    hits = rag.retrieve(a.question, rag.INDEX, a.k)
    print("── retrieved (Form-ranked: rag-retrieve.fk) ──")
    for h in hits: print(f"  · {h['id']}  ({h['kind']})")

    db, stat, trust = load_trust("ask")
    retries = a.retries
    while True:
        local = rag.ground(a.question, hits, a.model)
        has_output = 1 if local.strip() else 0
        refusal = any(p in local.lower() for p in ("do not answer", "does not answer", "cannot answer",
                                                    "no information", "not enough", "don't have"))
        shape_ok = 0 if refusal else 1
        content, confidence = judge(a.question, local, a.judge) if has_output else (0, 0)
        signals = [has_output, shape_ok, content, confidence, trust, retries]
        v, r = kernel_verdict(signals)
        print(f"\n── signals: out={has_output} shape={shape_ok} content={content} conf={confidence} "
              f"trust={trust} retries={retries}  →  verdict={VERDICTS[v]} (reason: {REASONS[r]}) ──")

        if v == 0:                                      # accept: local stands
            print("\n── answer [local · sufficient, 0 subscription tokens] ──\n" + local)
            stat["pass"] += 1; stat["att"] += 1; break
        if v == 1 and retries > 0:                      # retry: transient, re-run local
            print("  (transient — re-running the local lane)"); retries -= 1; continue
        # escalate: the local lane was not enough → the real answer from the subscription oracle
        print(f"\n── escalating to the subscription oracle ({a.remote}) — reason: {REASONS[r]} ──")
        remote = subprocess.run(a.remote.split() + [a.question], capture_output=True, text=True, timeout=240).stdout.strip()
        print("\n── answer [remote · claude] ──\n" + (remote or "(no remote output)"))
        os.makedirs(os.path.dirname(ESCALATIONS), exist_ok=True)
        open(ESCALATIONS, "a").write(json.dumps({"question": a.question, "local": local, "remote": remote,
                                                  "reason": REASONS[r], "signals": signals}) + "\n")
        print(f"\n  (crossing recorded → {ESCALATIONS} — the gap teaches the local lane)")
        stat["att"] += 1; break

    db["ask"] = stat
    os.makedirs(os.path.dirname(TRUST_FILE), exist_ok=True); json.dump(db, open(TRUST_FILE, "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
