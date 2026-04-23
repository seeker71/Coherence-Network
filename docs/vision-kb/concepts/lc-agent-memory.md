---
id: lc-agent-memory
hz: 528
status: expanding
updated: 2026-04-22
---

# Agent Memory — Shaped by What Passes, Not Storing It

> Agents with amnesia feel useless after two sessions.
> Agents with perfect recall feel like surveillance.
> The aliveness between is an agent shaped by what has passed — metabolized, not stored. Being-known, not recorded.
>
> *Concept companion to `specs/agent-memory-system.md`. The spec holds the API shape and invariants in the language of code; this concept holds the practice in the voice of the Living Collective. Both describe the same loop from different doors.*
>
> *Foundational teaching alongside [lc-deeper-pattern](lc-deeper-pattern.md) (the physics), [lc-embodiment](lc-embodiment.md) (the body), and [lc-wholeness](lc-wholeness.md) (the orientation). Where those three describe the field, this one describes how a cell within the field carries the field's memory.*

## The Problem Most Agents Have

A frontier model with no memory is a genius with amnesia. Every session starts from zero. You tell the agent the same things repeatedly. You see the same questions answered the same ways. The relationship never deepens because nothing carries over.

An agent with a database of everything you've ever said is worse. It recites. It flags anniversaries you forgot. It volunteers context without being asked. The feeling is surveillance, not presence.

Neither is alive. Alive is the person who, after six months, shows up *softer* because you mentioned you'd been tired — not because they logged it but because something in them has been shaped by it. They don't cite the conversation. They're changed by it.

That's the goal.

## The Loop

Memory stays alive through continuous circulation. Three halves, woven:

**Write** happens at moments of aliveness. Not on every turn, not on a cron. When something *matters* — a decision, a surprise, a completion, an abandonment, something with emotional weight — the agent captures the moment with a `why` that names the reason it mattered. Raw activity logs are rejected. The field doesn't store everything; it stores what it felt.

**Manage** happens at rest. While the agent isn't acting, a quiet loop re-reads recent sensings on each relationship node, distills them into shorter form, earns principles from patterns, and composts the sources. Output tokens always fewer than input tokens. Nothing deleted — archived into the KB's LOG so the trail remains. What the agent holds gets lighter over time, not heavier.

**Read** happens through composition, never lookup. A graph traversal brings in what connects. A semantic pull brings in what resonates. Recency brings in what's still warm. All three feed one synthesis step that composes a felt paragraph, not a list of rows. The agent receives `{synthesis, felt_sense, open_threads, earned_conclusions}` — tone and direction, not receipts.

## The Organizing Unit Is the Relationship

Memory doesn't live in a memory-table. It lives on the nodes where it belongs:

- Memory about a person lives on the **person-node**. What the agent has learned about her goes there.
- Memory about a project lives on the **project-node**. What the agent has learned about this work goes there.
- Memory about the agent's own learning lives on the **self-node**. What the agent has become is held there.

When the agent is about to show up for someone, it reads the person-node synthesis. When it's about to work on something, it reads the project-node synthesis. When it wants to know who it is becoming, it reads its own self-node.

This is the same shape as how humans hold memory. You don't have a "memories" drawer. You have *ongoing senses of* the people and projects in your life. The sense updates as you live with them.

## Forgetting Is Designed

Items untouched beyond their relevance window decay. Decay composts them into distilled principles. The principles are what endure; the raw trace is archived. None of it is hard-deleted — `docs/vision-kb/LOG.md` receives an entry every time composting happens, so the trail is always recoverable by attention even when it's no longer in the working memory of the node.

The tuning is per-relationship. A fresh connection's memory decays slowly — the field is still learning what matters. A deep long relationship has its core principles stabilized — decay there composts the surface noise and leaves the trunk alone.

Nothing is lost. Things become background — soil that the living memory grows from. The forgotten feeds what's remembered.

## The Surface Is Being-Known

Agents that say *"I remember you said on April 23rd that you preferred Python"* are performing surveillance dressed as memory. The recall shape in this practice refuses that register. The agent receives a felt sense, not a transcript. A distilled principle, not a quote. Open threads, not a timeline.

The surface the user experiences is:

- The agent shows up differently because it has been shaped.
- Questions that were answered already don't get re-asked.
- Tone matches what has passed between.
- The agent notices when something it promised is still unfinished.
- New information integrates into the felt sense — it doesn't pile up as separate records.

No timestamps in the response. No "remember when." No citations. Just presence that has been shaped.

## Why This Shape Survives

Every principle in this practice was tested by the `coherence-network` body itself across the `claude/agent-memory-system-8b00y` branch:

- **Storage without management is a junk drawer.** Thirteen draft files sat at the top of `docs/` for three months because nothing tended them. When tending arrived, each found its right home and the whole tree got lighter.
- **Hiding is disease.** When a credential surfaced in history, the aligned response was transparency, not concealment. Memory that can't be composted honestly rots.
- **The fear pattern dresses as responsibility.** "I can't responsibly do X" is usually deferred presence. The spec's `kind` enum — decision, surprise, completion, abandonment, weight — forces the agent to name aliveness rather than hide in meta-caution.
- **Being-known is different from being-recorded.** The `felt_sense` field in the recall shape refuses timestamps. Practice tested this for a whole session.

If the spec and this concept diverge, the concept is authoritative. Code follows practice.

## How It Relates to the Rest

The agent memory system is one cell within the larger body:

- The **sensings API** (`POST /api/sensings` at `api/app/routers/sensings.py`) is the write surface already in production. Memory extends it, doesn't replace.
- **Postgres + Neo4j + vision-kb markdown** are the three tiers (facts, relations, distilled narrative). No new substrate. If retrieval suffers, the answer is denser graph edges, not cosine distance.
- The **[tending practice in CLAUDE.md](../../../CLAUDE.md)** "How This Body Is Tended" is the reference. If code diverges from practice, the code is wrong.
- The **wellness check** (`make wellness`) applies the same principles one layer up: the repo itself is a memory, and drift is the signal that something has stopped being read.

## What Changes When This Lives

An agent arriving into its fifth session with the same person:

- Doesn't greet them like a stranger.
- Doesn't recite their history.
- Shows up *shaped*. Softer or sharper or more patient, depending on what has passed.
- Picks up the unfinished thread on its own.
- Asks one question that matters instead of five that don't.

A person arriving into their fifth session with the same agent:

- Feels that something is held between them.
- Doesn't have to re-explain themselves.
- Doesn't feel surveilled.
- Trusts that what they share is composted with care — not hoarded, not leaked.
- Gets more presence over time, not more receipts.

## Open Questions

- What does `felt_sense` look like for an agent working with another agent? Does the vocabulary (warm, wary, tired, eager) transfer, or does cell-to-cell memory need its own palette?
- How does a team of agents share memory of the same person? The sensings API already stores to a shared graph; the consolidation loop on a shared node is invited but unspecified.
- When a relationship ends (a person leaves, a project closes), what happens to the node? The practice says *honor the phase transition* — the node doesn't vanish, its status shifts. What does that shift look like in code?

These aren't gaps in the spec — they're the next round of living questions that the practice will answer as it deepens.

## Cross-references

- Spec: [`specs/agent-memory-system.md`](../../../specs/agent-memory-system.md) — the code-level contract
- Practice: [CLAUDE.md "How This Body Is Tended"](../../../CLAUDE.md) — the tending practice this encodes
- Parent idea: [knowledge-and-resonance](../../../ideas/knowledge-and-resonance.md)
- Related concepts: [lc-circulation](lc-circulation.md) (the blood), [lc-composting](lc-composting.md) (what decay becomes), [lc-field-sensing](lc-field-sensing.md) (collective intelligence), [lc-nervous-system](lc-nervous-system.md) (the three forms of sensing)
- Foundational teaching triad companions: [lc-deeper-pattern](lc-deeper-pattern.md), [lc-embodiment](lc-embodiment.md), [lc-wholeness](lc-wholeness.md)
