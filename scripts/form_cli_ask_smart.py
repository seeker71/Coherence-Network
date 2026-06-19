#!/usr/bin/env python3
"""form_cli_ask_smart.py — thin REPL CARRIER. The form-cli interactive shell.

NO ask logic lives here. The decisions are PROVEN Form recipes run by the kernel:
  - form-cli-repl.fk         launch mode (interactive / one-shot / help) + per-line routing
  - form-cli-ask.fk          the whole ask flow (local oracle -> judge -> sufficiency -> escalate),
                             run via scripts/form_cli_ask.sh — the kernel is the runtime
This file only reads stdin lines, asks the kernel how to route each one, and dispatches:
'(expr)' evaluates on the kernel, '/cmd' is a meta-command, anything else is handed to the Form ask.

Modes (like claude/codex/cursor/gemini/grok): bare at a terminal -> REPL; a question or pipe -> one-shot.
"""
import argparse, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO = os.path.join(ROOT, "form", "form-kernel-go", "bin-go")
STD = os.path.join(ROOT, "form", "form-stdlib")
LOGIC = ["form-cli-repl.fk"]   # the launch/line-routing recipe (decisions stay in Form)


def kernel(exprs):
    """run the control recipe + a list of (print ...) exprs on the Go kernel; return outputs."""
    src = "\n".join(open(os.path.join(STD, r)).read() for r in LOGIC)
    src += "\n" + "\n".join(f"(print {e})" for e in exprs) + "\n"
    tmp = "/tmp/fcli_logic.fk"; open(tmp, "w").write(src)
    return subprocess.run([GO, tmp], capture_output=True, text=True).stdout.split()


def answer_once(q, a):
    """the ask BODY is Form (form-cli-ask.fk run by the kernel via form_cli_ask.sh) — no Python ask logic."""
    subprocess.run(["bash", os.path.join(ROOT, "scripts", "form_cli_ask.sh"),
                    "-m", a.model, "-j", a.judge, "--remote", a.remote, q])


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
        kind = int(kernel([f"(frepl-classify {1 if not line else 0} "
                           f"{1 if line[:1] == '(' else 0} {1 if line[:1] == '/' else 0})"])[0])
        if kind == 3:
            continue
        if kind == 0:                                   # Form expression -> kernel
            eval_form(line)
        elif kind == 1:                                 # meta-command
            cmd = line[1:].split(); name = cmd[0] if cmd else ""
            if name in ("exit", "quit", "q"): break
            elif name == "help":
                print("  /model NAME  switch local answerer · /judge NAME  switch judge\n"
                      "  /exit  leave · '(expr)' eval Form · anything else = a question")
            elif name == "model" and len(cmd) > 1: a.model = cmd[1]; print(f"  local model → {a.model}")
            elif name == "judge" and len(cmd) > 1: a.judge = cmd[1]; print(f"  judge → {a.judge}")
            else: print("  unknown command — /help")
        else:                                           # a question -> the Form ask flow
            answer_once(line, a)
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("-m", "--model", default="coder")
    ap.add_argument("-j", "--judge", default="llama3.2:3b")
    ap.add_argument("--remote", default="claude -p")
    ap.add_argument("--print", "-p", action="store_true", dest="print_mode", help="one-shot print mode")
    ap.add_argument("--repl", action="store_true", help="force interactive REPL")
    a = ap.parse_args()

    if a.repl:                                          # forced REPL must NOT pre-read stdin
        repl(a); return 0

    # the LAUNCH decision is the proven recipe, not python ifs
    tty = 1 if sys.stdin.isatty() else 0
    piped = "" if tty else sys.stdin.read().strip()
    has_input = 1 if (a.question or piped) else 0
    mode = int(kernel([f"(frepl-mode {1 if a.print_mode else 0} {tty} {has_input})"])[0])

    if mode == 0:
        repl(a)
    elif mode == 1:
        answer_once(a.question or piped, a)
    else:
        print("usage: form-cli ask+ \"question\"   |   form-cli  (interactive)   |   form-cli -p \"q\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
