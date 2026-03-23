---
name: pipeline-monitor
description: Monitor the Coherence Network task pipeline for blockers and remarkable events. Reports stale tasks, blind timeouts, provider outages, success streaks, and idea completions.
license: MIT
metadata:
  author: coherence-network
  version: "1.0"
allowed-tools: Read Bash Grep
---

# Pipeline Monitor

Check the Coherence Network task pipeline and report on:

1. **Blockers** — anything stopping progress:
   - Tasks stuck in `running` for more than 10 minutes
   - Providers with 3+ consecutive failures (blocked by Thompson Sampling)
   - Ideas with all tasks failed and no pending retry
   - Blind timeouts (cost with zero diagnostic value)

2. **Remarkable events** — noteworthy progress:
   - Ideas that advanced a phase (spec → impl → test → review → complete)
   - Provider success streaks (5+ consecutive successes)
   - New providers coming online or existing ones recovering
   - Batch completion rates above 90%
   - Ideas reaching `validated` manifestation status

## How to run

```bash
python .cursor/skills/pipeline-monitor/scripts/check_pipeline.py
```

The script outputs a structured report suitable for Telegram or console display.

## Integration

This skill can be run:
- On demand: `python .cursor/skills/pipeline-monitor/scripts/check_pipeline.py`
- On a schedule: pair with the local_runner `--loop` mode
- Via Telegram: responds to `/attention` command
- Via OpenClaw: as a periodic health check skill
