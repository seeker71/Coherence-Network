#!/usr/bin/env bash
# form_cli_learn.sh — the continuous-learning loop's body, in ONE motion: grow the tool-use corpus
# from this machine's sessions, then retrain the native predictor on the GROWN corpus — ALWAYS
# re-featurizing so the stale /tmp cache that silently froze the corpus (the trap of 2026-06-21)
# cannot bite again. `form-cli learn` runs this. Carrier only — the model is a Form FFN step
# (the Form recipe jte-mlp-train-msl); this orchestrates tap -> featurize -> train -> cache metric.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
CORPUS="$HOME/.coherence-network/form-cli-corpus/corpus.jsonl"
DAT="/tmp/agent_tooluse.dat"

echo "⟐ form-cli learn — grow the corpus from sessions, then retrain the native predictor on it"

before=$(wc -l < "$CORPUS" 2>/dev/null || echo 0)

# 1. tap this machine's Claude Code sessions into the corpus (idempotent; Read/Edit/Write-heavy)
python3 "$ROOT/scripts/claude_corpus.py" 2>&1 | head -1

after=$(wc -l < "$CORPUS" 2>/dev/null || echo 0)
echo "  corpus: ${before} -> ${after} turns"

# 2. ALWAYS re-featurize the grown corpus — this is what makes "more samples" actually reach the model
#    (agent_tooluse_train.sh skips featurize when $DAT exists, so we regenerate it here every time).
rm -f "$DAT"
python3 "$ROOT/scripts/agent_tooluse_featurize.py" "$DAT" 2>&1 | head -1

# 3. retrain on the fresh dataset; agent_tooluse_train.sh caches the held-out metric for `form-cli stats`
DATA="$DAT" exec bash "$ROOT/scripts/agent_tooluse_train.sh" "$@"
