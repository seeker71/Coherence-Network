# Gemini — Coherence Network

Full agent orientation lives in [`AGENTS.md`](AGENTS.md) (provider-neutral) and
[`CLAUDE.md`](CLAUDE.md). Read `AGENTS.md` first — it carries how this body is
tended.

## Session start

Use `make prompt-guide` for repository orientation. The optional greeting below
detects identity from project/git settings and can record the meeting on the
configured substrate. Run it when the person's established memory preference
covers that effect; inspect `remember_sessions` and the live configuration
before promising a storage destination or privacy boundary.

```bash
form-run python3 scripts/session_greeting.py
```

This command can write a meeting record and read prior-session memory.
Conversation, identity linking, durable memory and training retain separate
authorization scopes. The current implementation's behavior must be observed;
this guidance alone changes no capture or deletion control.
