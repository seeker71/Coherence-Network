# agent-turn training corpus

Samples of agent reasoning + tool use, so the native form-cli models can be
tried on the same tasks and measured against the oracle that produced them
(champion-challenger). When the oracle is `claude`, these teach the native
models to reach the agent's own reasoning.

## Shape

Each line is one agent turn — a `form-cli-sample.fk` cell:

```json
{"task": "...", "oracle": "claude", "reasoning": "...",
 "steps": [{"tool": "Bash", "surface": "os-kernel", "args": "...", "result": "...",
            "args_sig": "...", "result_sig": "..."}],
 "answer": "...", "outcome": "success", "task_sig": "...", "answer_sig": "..."}
```

Every tool step is a **membrane crossing** (`native-recipe` / `os-kernel` /
`local-oracle` / `remote-oracle`). A turn with no `remote-oracle` step is
**offline-reproducible** — the native models can replay it air-gapped. Each
sample derives two training pairs: reasoning (`task → answer`) and tool
(`task → tool` per step). Validated four-way by `form-cli-sample-band` → 1023.

## Files

- **`seed.jsonl`** — committed, curated, real exemplars (verified clean).
- **`corpus.jsonl`** — local accumulation, gitignored. Grows as turns are captured.

## Capture

```bash
# the agent's own turns, from a session transcript
scripts/form_cli_capture.sh --from-transcript <session>.jsonl 10
# one turn (form_cli_close_gap.sh calls this on every gap close)
scripts/form_cli_capture.sh --gap "<task>" "<reasoning>" "<answer>" <outcome> <oracle>
```

## Cell sovereignty — structural, not manual

The capture carrier **refuses** any turn touching tender/personal markers — a
matched turn is dropped whole, never scrubbed-and-kept. The corpus can never hold
gated content by construction. System-reminder/non-human turns are dropped too.
Every sample's shape is validated on the kernel before it lands.

## Replay (the measurement)

Take a sample's `task`, run it through form-cli's native loop, and compare the
native answer + tool sequence to the captured one. That is the champion
(`oracle`) vs challenger (`form-native`) competition — how the native models are
doing, on real work.
