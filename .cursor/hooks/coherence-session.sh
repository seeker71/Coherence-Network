#!/usr/bin/env bash
# Cursor sessionStart hook — bind this agent + the human into session memory.
#
# Cursor command hooks exchange JSON over stdin/stdout, and sessionStart has no
# context-injection output field, so we run the binding for its effect (the
# bootstrap call inside session_greeting records this agent<->user meeting on
# the substrate) and return valid empty JSON. The greeting text itself surfaces
# in agents whose session-start renders hook stdout (Claude Code, Codex).
#
# Never blocks the session: any failure is swallowed.
cat >/dev/null 2>&1 || true   # consume the stdin JSON cursor sends
root="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -n "$root" ]; then
  python3 "$root/scripts/session_greeting.py" >/dev/null 2>&1 || true
fi
echo '{}'
