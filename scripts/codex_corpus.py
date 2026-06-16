#!/usr/bin/env python3
"""codex_corpus.py — tap the local Codex session logs into (task -> response) pairs.

The form-cli corpus (form_cli_capture.sh) reads Claude Code transcripts. The other
half of the body's session history lives in ~/.codex as Codex rollouts — a different
shape: {type:"response_item", payload:{type:"message"|"reasoning"|"function_call"|
"function_call_output", role, content}}. This carrier pairs each genuine user task
with the assistant message that follows, into the MLX chat instruction shape a local
model trains on. It is the "use ALL the session logs" half the Claude extractor can't
read — a host-IO bootstrap until the kernel reads session ledgers natively.

Honest yield: pairs are deduped globally by the user message's first 120 chars, and
boilerplate openings (AGENTS.md / permissions / worktree-context dumps) are filtered.
Most Codex sessions open with near-identical boilerplate, so the unique-task yield is
far smaller than the session count — that is correct (duplicates are not new signal),
not a bug. Reasoning/tool-call payloads are skipped; only message turns pair.

Usage: codex_corpus.py [--out PATH] [--per-session N] [--cap TOTAL]
"""
from __future__ import annotations
import argparse, glob, json, os

ROOTS = [os.path.expanduser("~/.codex/sessions"), os.path.expanduser("~/.codex/archived_sessions")]
BOILER = ("AGENTS.md instructions", "<permissions instructions>", "Repo/worktree context",
          "Global Codex", "<INSTRUCTIONS>", "# Coherence Network")


def _text(payload: dict) -> str:
    c = payload.get("content")
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    if isinstance(c, str):
        return c
    return payload.get("text", "") or ""


def _boiler(t: str) -> bool:
    return any(b in t[:200] for b in BOILER)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.expanduser("~/.coherence-network/codex-pairs.jsonl"))
    ap.add_argument("--per-session", type=int, default=6)
    ap.add_argument("--cap", type=int, default=14000)
    args = ap.parse_args()

    files = []
    for r in ROOTS:
        files += glob.glob(os.path.join(r, "**", "rollout*.jsonl"), recursive=True)
    print(f"{len(files)} codex sessions", flush=True)

    n = 0; seen: set[int] = set()
    with open(args.out, "w") as out:
        for fi, f in enumerate(files):
            if n >= args.cap:
                break
            per = 0; last_user = None
            try:
                for line in open(f, encoding="utf-8", errors="ignore"):
                    if per >= args.per_session:
                        break
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if rec.get("type") != "response_item":
                        continue
                    p = rec.get("payload", {})
                    if p.get("type") != "message":
                        continue
                    role = p.get("role"); t = _text(p).strip()
                    if role == "user":
                        last_user = t if (8 < len(t) < 2000 and not _boiler(t)) else None
                    elif role == "assistant" and last_user and len(t) > 30:
                        key = hash(last_user[:120])
                        if key not in seen:
                            seen.add(key)
                            out.write(json.dumps({"messages": [
                                {"role": "user", "content": last_user[:2000]},
                                {"role": "assistant", "content": t[:2000]}]}) + "\n")
                            n += 1; per += 1
                        last_user = None
            except Exception:
                continue
            if fi % 2000 == 0:
                print(f"  ...{fi} sessions, {n} pairs", flush=True)
    print(f"[codex corpus: {n} instruction pairs -> {args.out}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
