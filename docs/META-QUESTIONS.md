# Meta Questions — Validate, Monitor, Improve

> Questions we should ask regularly to check if things are going well, if we're monitoring effectively, and how we can improve. Use these to catch misconfigurations, detect issues, and drive improvement.

---

## 1. Configuration Coherence

**Does our setup match what we actually use?**

- Are we logging or printing references to tools we don't use? (e.g. "Ollama request count" when AGENT_EXECUTOR_DEFAULT=cursor — use executor-aware messages)
- Do our docs, runbooks, and error messages assume a setup that's not the default?
- Are env vars (OLLAMA_MODEL, CURSOR_CLI_MODEL, etc.) aligned with the active executor?
- Do specs and examples reflect the current routing (Cursor vs Claude vs Ollama)?

**Action:** When adding logging or docs, make them executor-aware. Flag mismatches in ensure_effective_pipeline or monitor.

---

## 2. Monitoring Coverage

**Are we detecting all failure modes?**

- What conditions can occur that we don't yet detect? (e.g. output 0 chars, runner/PM not seen)
- Are we monitoring the right layers? (Goal → Orchestration → Execution → Attention)
- Do our "going well" / "needs attention" lists capture what humans actually care about?
- Is the hierarchical status report complete, or are there blind spots?

**Action:** When an issue is discovered manually, ask: "Should the monitor have detected this?" If yes, add a rule.

---

## 3. Effectiveness Feedback

**Are we learning and improving from outcomes?**

- Do we track which directions, models, or task types fail most?
- When a heal task completes, do we resolve the related monitor issue?
- Are we committing progress automatically, or is work lost?
- Is the backlog moving us toward the overall goal (PLAN.md)?

**Action:** Use GET /api/agent/effectiveness; compare goal_proximity over time. Ensure meta-pipeline items surface from failure analysis.

---

## 4. Automation Gaps

**What still requires manual intervention?**

- Are there fatal conditions we could recover from automatically?
- Do we restart the right things when they fail? (API, pipeline, runner)
- Is the "suggested_action" for each issue actually actionable by automation?
- Are we auto-committing, or does the human have to remember to push?

**Action:** For each manual fix, ask: "Could this be automated?" Add to monitor or run_autonomous when feasible.

---

## 5. Meta Questions Checklist (Run Weekly or After Incidents)

| Question | If No → Action |
|----------|----------------|
| Do our logs reflect the executor we actually use? | Update log messages, make conditional |
| Are we detecting runner/PM down, output empty, stale version? | Add monitor rules |
| Is goal_proximity improving? | Review metrics; tune thresholds or backlog |
| Are we committing progress? | Enable PIPELINE_AUTO_COMMIT; verify |
| Do we have blind spots in monitoring? | Add meta-question: "What didn't we detect?" |
| Is the backlog aligned with PLAN.md? | Reorder; add/remove items |
| Are we asking the right questions? | Add to this doc |

---

## 6. How to Use

- **At session start:** Scan META-QUESTIONS.md; run ensure_effective_pipeline.sh.
- **After an incident:** Add "What meta question would have caught this?"
- **Weekly:** Run the checklist; update PIPELINE-MONITORING-AUTOMATED.md with new rules.
- **When adding features:** Add a meta-question: "How do we validate this is working?"

---

## 7. See Also

- [COMMUNITY-RESEARCH-PRIORITIES.md](COMMUNITY-RESEARCH-PRIORITIES.md) — Questions to ask, what to research
- [PIPELINE-MONITORING-AUTOMATED.md](PIPELINE-MONITORING-AUTOMATED.md) — Detection rules, fallback recovery
- [PIPELINE-EFFICIENCY-PLAN.md](PIPELINE-EFFICIENCY-PLAN.md) — Metrics, auto-improvement
