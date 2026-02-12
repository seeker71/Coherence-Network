# Community, Research & Prioritization

> Asking the right questions, researching what works, prioritizing work, and building a public forum so others in this space can interact and benefit.

---

## 1. Questions to Ask Regularly

### How Are We Doing?

- **Throughput:** How many backlog items completed this week? Trend up or down?
- **Quality:** Success rate, test pass rate, spec compliance — improving?
- **Efficiency:** Time per task, cost per task — within target?
- **Bottlenecks:** Where does human time go? needs_decision? Failures? Reviews?
- **Goal alignment:** Is the backlog moving us toward MVP / Sprint goals? (See [PLAN.md](PLAN.md))

### What Works?

- **Prompt patterns:** Which directions produce first-try success?
- **Models:** Which task_type + model combinations work best?
- **Subagents:** Product-manager vs dev-engineer vs reviewer — which deliver?
- **Specs:** Which spec structures lead to clean implementation?
- **Tools:** Cursor vs Claude Code vs Ollama — when does each shine?

### What Does Not Work?

- **Failure modes:** Repeated failures on same phase? Same task_type? Unclear directions?
- **Slow paths:** Long durations — which directions or models?
- **Scope creep:** Spec drift, files outside spec — how often? Why?
- **Human friction:** What triggers needs_decision? What do we fix manually?

### Cadence

- **Daily:** Quick pipeline-status; any stuck or failed?
- **Weekly:** Aggregate metrics; what worked / didn’t this week?
- **Monthly:** Retrospective; update priorities; research new approaches

---

## 2. Research to Improve Any Part of the System

### What to Research

| Area | Research Question | Where to Look |
|------|-------------------|---------------|
| **Agent orchestration** | How do others run multi-agent pipelines? | OpenClaw, Agent Zero, LangGraph, CrewAI, AutoGen |
| **Prompt engineering** | Best practices for spec→impl, test-first? | Anthropic, OpenAI guides; papers on chain-of-thought, tool use |
| **Model routing** | Cost vs quality tradeoffs; when to use which model? | MODEL-ROUTING.md; provider docs; community benchmarks |
| **Backlog management** | How to structure work for AI agents? | Agile for AI; agentic workflows; product backlogs |
| **Spec-driven dev** | Contract-first, spec-as-oracle patterns? | API-first, OpenAPI, TDD; Living Codex, crypo-coin references |
| **OSS health metrics** | Coherence-like scores; existing frameworks? | CHAOSS, OpenSSF, deps.dev, Libraries.io, Tidelift |
| **Funding flows** | How others distribute funding to maintainers? | GitHub Sponsors, Tidelift, tea.xyz, OCEAN |

### How to Research

1. **Literature / docs:** Search for “AI agent pipeline”, “multi-agent software development”, “spec-driven AI”
2. **GitHub / OSS:** Browse repos tagged agent, orchestration, AI-assisted dev; read their docs
3. **Communities:** Discord, Slack, forums for Cursor, Claude, LangChain, etc.
4. **Papers:** arXiv, ACL, NeurIPS on agentic systems, code generation, tool use
5. **Benchmarks:** SWE-bench, HumanEval, agent evaluation datasets
6. **Internal experiments:** A/B test prompts, models, directions; log and compare

### Turning Research Into Action

- Add findings to `docs/` (e.g. AGENT-FRAMEWORKS-RESEARCH.md)
- Propose specs for changes: new routing, new prompts, new tools
- Run small experiments before broad rollout

---

## 3. Prioritization: What to Work On

### Frameworks

**Impact × Effort**
- High impact, low effort → do first
- High impact, high effort → plan and sequence
- Low impact → defer or drop

**Goal alignment**
- Does it move us toward MVP, Sprint 1/2/3, or product goals?
- If not, is it blocking something that does?

**Risk reduction**
- Does it reduce failure rate, cost, or human time?
- Does it unblock the pipeline or a key feature?

### Prioritization Checklist

1. **Goal:** Which product/sprint goal does this serve?
2. **Impact:** How much does it improve throughput, quality, or cost?
3. **Effort:** Rough estimate (hours / days)
4. **Dependencies:** Blocked by or blocking something else?
5. **Reversibility:** Easy to undo if it doesn’t work?

### Practical Ordering

- **Urgent:** Pipeline broken, CI red, blocker for others
- **High value:** Clear improvement to success rate or efficiency
- **Tech debt:** Pay down when it slows iteration
- **Nice-to-have:** When core path is solid

---

## 4. Similar Public Work & Integration

### Finding Related Work

- **Keywords:** “AI agent pipeline”, “autonomous software development”, “spec-driven AI”, “OSS health scoring”, “maintainer funding”
- **GitHub topics:** `ai-agents`, `agent-orchestration`, `open-source`, `funding`, `chaoss`
- **Communities:** OSS sustainability (TODO Group, CHAOSS), AI dev tools (Cursor, Windsurf, Cody)
- **Conferences / meetups:** OSS summits, AI engineering, maintainer sustainability

### Integration Points

- **Standards:** OpenAPI, CHAOSS metrics, deps.dev API — align with existing ecosystems
- **APIs:** Consume public APIs (deps.dev, GitHub, Libraries.io) for data; expose our API for others
- **Formats:** JSON, OpenAPI, common schema (e.g. SPDX, CycloneDX for dependencies)
- **Protocols:** Webhooks, web subscriptions — enable external integrations

### Publishing What We’re Doing

- **Docs:** Clear README, SETUP, RUNBOOK; link from main docs
- **Blog / posts:** Short write-ups on approach, results, lessons
- **Talks / videos:** Share pipeline design, metrics, failures
- **Specs:** Keep specs readable; they describe the system for outsiders
- **Code:** Clean, commented; easy to run and extend

---

## 5. Traction & Public Forum

### Building Traction

- **Visibility:** Consistent releases, changelog, status updates
- **Use cases:** Concrete examples — “we indexed 5K packages”, “pipeline ran overnight”
- **Metrics:** Share (anonymized) success rates, time savings — builds credibility
- **Invitations:** “Try this”, “Run our pipeline”, “Extend our API”

### Public Forum Options

| Option | Pros | Cons |
|--------|------|------|
| **GitHub Discussions** | Tied to repo, searchable | Requires GitHub users |
| **Discord** | Real-time, channels | Extra place to maintain |
| **Mailing list** | Async, archival | Lower engagement |
| **Twitter / X** | Broad reach | Ephemeral, noisy |
| **LinkedIn / blog** | Professional, long-form | Slower feedback |
| **OSS community events** | In-person, deep dives | Less frequent |

### Suggested Approach

1. **GitHub Discussions** as primary forum — Q&A, ideas, show-and-tell
2. **README / docs** with clear “Join the conversation” link
3. **Occasional posts** (blog, LinkedIn) on milestones and learnings
4. **Talks / workshops** at OSS or AI dev events when possible

### Who Benefits

- **Maintainers** exploring OSS health and funding
- **Teams** building AI-assisted dev pipelines
- **Researchers** studying agent orchestration or OSS sustainability
- **Enterprises** evaluating OSS risk and maintainer support

### Forum Content Ideas

- “How we run an overnight agent pipeline”
- “Spec-driven AI: what works, what doesn’t”
- “Coherence scores: our approach and gaps”
- “Integrating with deps.dev and CHAOSS”

---

## 6. See Also

- [PIPELINE-EFFICIENCY-PLAN.md](PIPELINE-EFFICIENCY-PLAN.md) — Measurement and improvement
- [PLAN.md](PLAN.md) — Product vision and roadmap
- [AGENT-DEBUGGING.md](AGENT-DEBUGGING.md) — Debugging the pipeline
- [REFERENCE-REPOS.md](REFERENCE-REPOS.md) — Source material and related work
