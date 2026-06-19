#!/usr/bin/env python3
"""form_cli_ask_smart.py — CARRIER. The form-cli ask engine, interactive AND non-interactive.

The two decisions that matter are PROVEN Form recipes, not Python:
  - form-cli-repl.fk      launch mode (interactive / one-shot / help) + per-line routing
  - form-cli-sufficiency.fk  accept / retry / escalate after the local lane answers
This script only gathers run-time reads, asks the kernel for the verdict, runs the local
grounded oracle, and — when the recipe says escalate — calls the subscription oracle (claude -p)
for the real answer, recording the crossing so the local lane learns.

Modes (like claude/codex/cursor/gemini/grok):
  form_cli_ask_smart.py "question"     one-shot (print mode) — for scripts/pipes
  form_cli_ask_smart.py                bare at a terminal -> interactive REPL
  form_cli_ask_smart.py --repl         force the REPL
REPL lines: '(...)' eval on the kernel · '/cmd' meta-command · anything else a question.
"""
import argparse, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import form_cli_rag as rag

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO = os.path.join(ROOT, "form", "form-kernel-go", "bin-go")
STD = os.path.join(ROOT, "form", "form-stdlib")
LOGIC = ["form-cli-router.fk", "form-cli-judge.fk", "form-cli-sufficiency.fk", "form-cli-repl.fk"]
TRUST_FILE = os.path.expanduser("~/.coherence-network/form-cli-trust.json")
ESCALATIONS = os.path.expanduser("~/.coherence-network/form-cli-escalations.jsonl")
REASONS = {0: "ok", 1: "empty", 2: "bad-shape", 3: "weak-content", 4: "low-confidence", 5: "low-trust"}
VERDICTS = {0: "accept", 1: "retry", 2: "escalate"}


def kernel(exprs):
    """run the proven recipes + a list of (print ...) exprs on the Go kernel; return their outputs."""
    src = "\n".join(open(os.path.join(STD, r)).read() for r in LOGIC)
    src += "\n" + "\n".join(f"(print {e})" for e in exprs) + "\n"
    tmp = "/tmp/fcli_logic.fk"; open(tmp, "w").write(src)
    return subprocess.run([GO, tmp], capture_output=True, text=True).stdout.split()


def ollama(model, prompt):
    return rag._post("/api/generate", {"model": model, "prompt": prompt, "stream": False})["response"].strip()


def judge(question, answer, model):
    out = ollama(model, f"Question: {question}\n\nProposed answer:\n{answer}\n\n"
                        "Rate the answer on two axes, each an integer 0-100. COVERAGE: how fully it "
                        "answers the question. GROUNDEDNESS: how specific and supported it is. "
                        "Reply with ONLY two integers separated by a space: COVERAGE GROUNDEDNESS")
    nums = [int(x) for x in re.findall(r"\d+", out)][:2]
    return tuple((nums + [40, 40])[:2])


def load_trust(key):
    try: db = json.load(open(TRUST_FILE))
    except Exception: db = {}
    stat = db.get(key, {"pass": 3, "att": 5})
    return db, stat, min(100, stat["pass"] * 100 // max(1, stat["att"]))


def save_trust(db, key, stat):
    db[key] = stat
    os.makedirs(os.path.dirname(TRUST_FILE), exist_ok=True)
    json.dump(db, open(TRUST_FILE, "w"))


def answer_once(q, a):
    """the local-first ask: ground locally, judge, let the recipe decide, escalate if not enough."""
    hits = rag.retrieve(q, rag.INDEX, a.k)
    print("── retrieved (Form-ranked: rag-retrieve.fk) ──")
    for h in hits: print(f"  · {h['id']}  ({h['kind']})")
    db, stat, trust = load_trust("ask")
    retries = a.retries
    while True:
        local = rag.ground(q, hits, a.model)
        has_output = 1 if local.strip() else 0
        refusal = any(p in local.lower() for p in ("do not answer", "does not answer", "cannot answer",
                                                    "no information", "not enough", "don't have"))
        shape_ok = 0 if refusal else 1
        content, confidence = judge(q, local, a.judge) if has_output else (0, 0)
        sig = [has_output, shape_ok, content, confidence, trust, retries]
        out = kernel([f"(fsuf-verdict (fsuf-signals {' '.join(map(str, sig))}))",
                      f"(fsuf-reason (fsuf-signals {' '.join(map(str, sig))}))"])
        v, r = int(out[0]), int(out[1])
        print(f"\n── signals: out={has_output} shape={shape_ok} content={content} conf={confidence} "
              f"trust={trust} retries={retries}  →  {VERDICTS[v]} (reason: {REASONS[r]}) ──")
        if v == 0:
            print("\n── answer [local · sufficient, 0 subscription tokens] ──\n" + local)
            stat["pass"] += 1; stat["att"] += 1; break
        if v == 1 and retries > 0:
            print("  (transient — re-running the local lane)"); retries -= 1; continue
        if a.local_only:
            print("\n── answer [local · --local-only, escalation suppressed] ──\n" + local)
            stat["att"] += 1; break
        print(f"\n── escalating to the subscription oracle ({a.remote}) — reason: {REASONS[r]} ──")
        remote = subprocess.run(a.remote.split() + [q], capture_output=True, text=True, timeout=240).stdout.strip()
        print("\n── answer [remote · claude] ──\n" + (remote or "(no remote output)"))
        os.makedirs(os.path.dirname(ESCALATIONS), exist_ok=True)
        open(ESCALATIONS, "a").write(json.dumps({"question": q, "local": local, "remote": remote,
                                                  "reason": REASONS[r], "signals": sig}) + "\n")
        print(f"\n  (crossing recorded → {ESCALATIONS} — the gap teaches the local lane)")
        stat["att"] += 1; break
    save_trust(db, "ask", stat)


def eval_form(expr):
    """REPL '(...)' line: evaluate a Form expression on the kernel (0 tokens)."""
    tmp = "/tmp/fcli_eval.fk"; open(tmp, "w").write(f"(print {expr})\n")
    res = subprocess.run([GO, tmp], capture_output=True, text=True)
    out = [l for l in res.stdout.splitlines() if l.strip() and l.strip() != "null"]
    print("\n".join(out) or (res.stderr.strip() or "(no result)"))


def repl(a):
    print("form-cli — interactive (local-first, escalates to the oracle when local isn't enough)")
    print("  type a question · '(expr)' evals on the kernel · /help · /exit\n")
    while True:
        try:
            line = input("form-cli› ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        is_empty = 1 if not line else 0
        paren = 1 if line[:1] == "(" else 0
        slash = 1 if line[:1] == "/" else 0
        kind = int(kernel([f"(frepl-classify {is_empty} {paren} {slash})"])[0])
        if kind == 3:
            continue
        if kind == 0:                                   # Form expression
            eval_form(line)
        elif kind == 1:                                 # meta-command
            cmd = line[1:].split()
            name = cmd[0] if cmd else ""
            if name in ("exit", "quit", "q"): break
            elif name == "help":
                print("  /model NAME  switch local answerer · /local on|off  toggle escalation\n"
                      "  /exit  leave · '(expr)' eval Form · anything else = a question")
            elif name == "model" and len(cmd) > 1: a.model = cmd[1]; print(f"  local model → {a.model}")
            elif name == "local" and len(cmd) > 1: a.local_only = (cmd[1] == "on"); print(f"  escalation {'off' if a.local_only else 'on'}")
            else: print("  unknown command — /help")
        else:                                           # a question
            answer_once(line, a)
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("-m", "--model", default="coder")
    ap.add_argument("-j", "--judge", default="llama3.2:3b")
    ap.add_argument("--remote", default="claude -p")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--local-only", action="store_true", dest="local_only", help="never escalate (air-gapped)")
    ap.add_argument("--print", "-p", action="store_true", dest="print_mode", help="one-shot print mode")
    ap.add_argument("--repl", action="store_true", help="force interactive REPL")
    a = ap.parse_args()

    # forced REPL must NOT pre-read stdin — the loop needs it.
    if a.repl:
        repl(a); return 0

    # the LAUNCH decision is the proven recipe, not python ifs
    tty = 1 if sys.stdin.isatty() else 0
    piped = "" if tty else sys.stdin.read().strip()
    has_input = 1 if (a.question or piped) else 0
    pflag = 1 if a.print_mode else 0
    mode = int(kernel([f"(frepl-mode {pflag} {tty} {has_input})"])[0])

    if mode == 0:
        repl(a)
    elif mode == 1:
        answer_once(a.question or piped, a)
    else:
        print("usage: form-cli ask+ \"question\"   |   form-cli  (interactive)   |   form-cli -p \"q\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
