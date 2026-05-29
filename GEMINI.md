# Gemini — Coherence Network

Full agent orientation lives in [`AGENTS.md`](AGENTS.md) (provider-neutral) and
[`CLAUDE.md`](CLAUDE.md). Read `AGENTS.md` first — it carries how this body is
tended.

## Session start

Gemini CLI has no session-start command hook, so this is the one instruction
that can't be automated: at the start of a session, run the greeting so this
agent and the human are recognized and remembered (same as the Claude/Codex/
Grok hooks do automatically):

```bash
python3 "$(git rev-parse --show-toplevel)/scripts/session_greeting.py"
```

It detects the agent and the human (git config / project identity), records the
meeting on the substrate, and greets with memory of prior sessions. It is
read-only-safe, never blocks, and honors `remember_sessions` opt-out.
