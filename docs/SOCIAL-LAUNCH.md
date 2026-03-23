# Social Launch — Share Templates

## X/Twitter

### Thread (main post)

```
We ran 842 tasks across 6 AI providers — Claude, Codex, Gemini, Cursor, Ollama — and let Thompson Sampling pick the winner for each task.

The data: 🧵
```

### Reply 1
```
Codex: 91% success, 38s avg — the speed champion
Claude: 96%, 121s — the reliability anchor
Cursor: 96%, 125s — consistent
Ollama Cloud: 100%, 8s — the sleeper hit

No synthetic benchmarks. Real specs, real implementations, real code reviews.
```

### Reply 2
```
The wildest finding: Gemini went from 0% to 83% with a one-character fix.

It was hanging on every task. Root cause? Missing -y flag for tool auto-approval. One flag = zero to working.

This is why you need data, not opinions, for provider selection.
```

### Reply 3
```
We also caught "false positive" providers — Ollama generated confident text about files it "created" without actually creating anything.

Added git-diff validation. If no files changed, it's not a success.

Trust the filesystem, not the output.
```

### Reply 4
```
The whole system is open source. Clone, run, your machine joins the network:

git clone https://github.com/seeker71/Coherence-Network.git
cd Coherence-Network/api && pip install -e .
python scripts/local_runner.py

Auto-detects your providers. No config needed.

Full writeup: coherencycoin.com/blog
```

---

## LinkedIn

```
We ran 842 real tasks across 6 AI coding providers and let the data pick the winner.

Not synthetic benchmarks — real spec writing, real implementations, real code reviews, real test suites.

The setup: Thompson Sampling (a classic multi-armed bandit algorithm) selected which provider got each task based on measured success rates. No human picked favorites.

Key findings:

→ Codex handled the most volume (169 runs, 38s avg) because it was fast AND reliable
→ Ollama Cloud (GLM-5) was the fastest at 8s — but started with zero data, so the algorithm had to discover it
→ Gemini went from 0% to 83% success with a one-character CLI fix
→ Some providers reported "success" without creating any files — we added git-diff validation to catch false positives
→ Flat timeouts waste compute — data-driven timeouts (2.5x each provider's p90) saved ~30% of wasted time

The system is open source and designed for federation — multiple machines contributing to the same data pool, Thompson Sampling learning from all of them.

Full writeup with methodology: coherencycoin.com/blog
Code: github.com/seeker71/Coherence-Network

#AI #DevTools #OpenSource #MachineLearning #ThompsonSampling
```

---

## Reddit — r/MachineLearning or r/LocalLLaMA

### Title
```
[P] We benchmarked 6 AI coding providers (Claude, Codex, Gemini, Cursor, Ollama) on 842 real tasks with Thompson Sampling selection
```

### Body
```
We needed to run hundreds of real coding tasks (spec writing, implementation, testing, code review) and wanted to know which AI provider actually works best for each task type.

Instead of picking one, we set up Thompson Sampling to select the provider for each task based on measured success rates. 842 tasks later, here's what the data shows:

| Provider | Success Rate | Runs | Avg Speed |
|----------|-------------|------|-----------|
| Ollama Local (llama3.3:70b) | 100% | 18 | 294s |
| Ollama Cloud (GLM-5) | 100% | 15 | 8s |
| Claude Code | 96% | 108 | 121s |
| Cursor Agent | 96% | 94 | 125s |
| Codex (GPT-5.3) | 91% | 169 | 38s |
| Gemini CLI | 83% | 35 | 214s |

**Interesting findings:**

1. **False positives are a real problem.** Ollama and OpenRouter generated confident descriptions of files they "created" — without actually creating any files. We added git-diff validation to catch this.

2. **Gemini's 0% → 83% fix was one character.** The `-y` flag for auto-approving tool use was missing. Without it, Gemini hung waiting for interactive approval that never came in headless mode.

3. **Timeouts should be per-provider.** Codex finishes specs in 20s, Claude takes 180s for complex impls. Flat timeouts either kill fast providers' slow tasks or waste time on genuinely hung ones. We use 2.5x each provider's p90 duration.

4. **Recency matters more than history.** We weight the last 5 runs at 60%, all-time at 40%. This means if a provider degrades (rate limits, API changes), the system reacts within a few runs.

The whole thing runs through a generic "SlotSelector" abstraction that works for any decision point: provider selection, prompt variant testing, model selection within a provider.

Code: https://github.com/seeker71/Coherence-Network
Blog writeup: https://coherencycoin.com/blog
```

---

## Hacker News

### Title
```
Show HN: Thompson Sampling for AI provider selection – 842 real task benchmark
```

### Body (comment)
```
We needed to run hundreds of real coding tasks (spec writing, implementation, testing, code review) across multiple AI providers. Instead of picking one, we used Thompson Sampling to let the data decide.

842 tasks later across Claude, Codex, Gemini, Cursor, and Ollama — the system learned which provider works best for each task type automatically.

Key learnings:
- False positives are worse than failures (Ollama generated text about "files created" without creating files)
- One-character fixes can change everything (Gemini: 0% → 83% with -y flag)
- Timeouts should be data-driven per provider, not flat
- Recency-weighted Beta distributions react faster than pure historical

Open source: https://github.com/seeker71/Coherence-Network
Writeup: https://coherencycoin.com/blog
```

---

## Discord / Telegram — AI communities

```
🔬 Ran 842 real coding tasks across 6 AI providers with Thompson Sampling selection

Quick results:
• Codex: fastest (38s), most used (169 runs), 91% success
• Ollama Cloud (GLM-5): 8 seconds, 100% — the sleeper
• Claude: most reliable (96%, 108 runs)
• Gemini: 0% → 83% with one flag fix (-y)

The system auto-detects providers and learns which works best. Clone & run:
git clone https://github.com/seeker71/Coherence-Network.git

Full data: coherencycoin.com/automation
Writeup: coherencycoin.com/blog
```

---

## GitHub README addition

Add to the top of README.md:

```markdown
## 842 tasks. 6 providers. Data picks the winner.

Claude, Codex, Gemini, Cursor, Ollama — benchmarked head-to-head on real coding tasks.
Thompson Sampling learns which provider works best for each task type.

[Read the writeup →](https://coherencycoin.com/blog) | [See the live data →](https://coherencycoin.com/automation)
```
