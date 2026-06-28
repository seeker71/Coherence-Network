#!/usr/bin/env python3
"""form_cli_ask_smart.py — thin REPL CARRIER. The form-cli interactive shell.

NO ask logic lives here. The decisions are PROVEN Form recipes run by the kernel:
  - form-cli-repl-control.fk launch mode (interactive / one-shot / help) + per-line routing
  - form-cli-ask.fk          the ask flow (fkwu grounded RAG -> sufficiency -> optional escalate),
                             run via scripts/form_cli_ask.sh — the kernel is the runtime
This file only reads stdin lines, asks the kernel how to route each one, and dispatches:
'(expr)' evaluates on the kernel, '/cmd' is a meta-command, anything else is handed to the Form ask.

Modes (like claude/codex/cursor/gemini/grok): bare at a terminal -> REPL; a question or pipe -> one-shot.
"""
import argparse
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO = os.path.join(ROOT, "form", "form-kernel-go", "bin-go")
STD = os.path.join(ROOT, "form", "form-stdlib")
LOGIC = ["form-cli-repl-control.fk"]   # pure launch/line-routing recipe; no fkwu-only IO loop


def kernel(exprs, timeout=5.0):
    """run the control recipe + a list of (print ...) exprs on the Go kernel; return outputs."""
    src = "\n".join(open(os.path.join(STD, r)).read() for r in LOGIC)
    src += "\n" + "\n".join(f"(print {e})" for e in exprs) + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".fk", delete=False) as f:
        f.write(src)
        tmp = f.name
    try:
        res = subprocess.run([GO, tmp], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"control recipe timed out after {timeout:g}s") from exc
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    if res.returncode != 0:
        detail = (res.stderr or res.stdout or "no output").strip()
        raise RuntimeError(f"control recipe failed: {detail}")
    out = [token for token in res.stdout.split() if token != "null"]
    if not out:
        raise RuntimeError("control recipe produced no output")
    return out


def answer_once(q, a):
    """the ask BODY is Form (form-cli-ask.fk run by the kernel via form_cli_ask.sh) — no Python ask logic."""
    try:
        return subprocess.run(
            [
                "bash",
                os.path.join(ROOT, "scripts", "form_cli_ask.sh"),
                "-m",
                a.model,
                "-j",
                a.judge,
                "--remote",
                a.remote,
                "--timeout",
                str(a.timeout),
                q,
            ],
            timeout=a.timeout + 5,
        ).returncode
    except subprocess.TimeoutExpired:
        print(f"form-cli ask: timeout after {a.timeout:g}s (nothing)", file=sys.stderr)
        return 124


def eval_form(expr):
    """REPL '(...)' line: evaluate a Form expression on the kernel (0 tokens)."""
    with tempfile.NamedTemporaryFile("w", suffix=".fk", delete=False) as f:
        f.write(f"(print {expr})\n")
        tmp = f.name
    try:
        res = subprocess.run([GO, tmp], capture_output=True, text=True)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    out = [line for line in res.stdout.splitlines() if line.strip() and line.strip() != "null"]
    print("\n".join(out) or (res.stderr.strip() or "(no result)"))


def repl(a):
    print("form-cli — interactive (fkwu grounded first, escalates only on a local miss)")
    print("  type a question · '(expr)' evals on the kernel · /help · /exit\n")
    while True:
        try:
            line = input("form-cli› ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        try:
            kind = int(kernel([f"(frepl-classify {1 if not line else 0} "
                               f"{1 if line[:1] == '(' else 0} {1 if line[:1] == '/' else 0})"])[0])
        except RuntimeError as exc:
            print(f"form-cli: {exc}", file=sys.stderr)
            continue
        if kind == 3:
            continue
        if kind == 0:                                   # Form expression -> kernel
            eval_form(line)
        elif kind == 1:                                 # meta-command
            cmd = line[1:].split()
            name = cmd[0] if cmd else ""
            if name in ("exit", "quit", "q"):
                break
            elif name == "help":
                print("  /do TASK  run the agent loop (read/edit/bash/search) · /model NAME · /judge NAME\n"
                      "  /exit  leave · '(expr)' eval Form · anything else = a question")
            elif name == "model" and len(cmd) > 1:
                a.model = cmd[1]
                print(f"  local model → {a.model}")
            elif name == "judge" and len(cmd) > 1:
                a.judge = cmd[1]
                print(f"  judge → {a.judge}")
            elif name == "do" and len(cmd) > 1:     # agentic task: the TIERED Form agent loop (local-first, escalate)
                subprocess.run(["bash", os.path.join(ROOT, "scripts", "form_cli_agent.sh"), line.split(None, 1)[1]],
                               env={**os.environ, "LOCAL": a.model, "REMOTE": a.remote})
            else:
                print("  unknown command — /help")
        else:                                           # a question -> the Form ask flow
            answer_once(line, a)
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("-m", "--model", default="coder")
    ap.add_argument("-j", "--judge", default="llama3.2:3b")
    ap.add_argument("--remote", default="claude -p")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--print", "-p", action="store_true", dest="print_mode", help="one-shot print mode")
    ap.add_argument("--repl", action="store_true", help="force interactive REPL")
    a = ap.parse_args()

    if a.repl:                                          # forced REPL must NOT pre-read stdin
        repl(a)
        return 0

    # the LAUNCH decision is the proven recipe, not python ifs
    tty = 1 if sys.stdin.isatty() else 0
    piped = "" if tty else sys.stdin.read().strip()
    has_input = 1 if (a.question or piped) else 0
    try:
        mode = int(kernel([f"(frepl-mode {1 if a.print_mode else 0} {tty} {has_input})"])[0])
    except RuntimeError as exc:
        print(f"form-cli: {exc}", file=sys.stderr)
        return 1

    if mode == 0:
        repl(a)
    elif mode == 1:
        return answer_once(a.question or piped, a)
    else:
        print("usage: form-cli ask+ \"question\"   |   form-cli  (interactive)   |   form-cli -p \"q\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
