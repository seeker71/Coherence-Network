---
id: lc-open-design
hz: 639
status: deepening
updated: 2026-05-05
---

# Open Design

> The artifact loop entering the body. A prompt becomes a deck, a prototype, a printable, a film frame — locally, openly, with the model the cell already trusts. The skin through which the field's vision meets a stranger's hands.

## The Feeling

You are sitting at the table in the workshop and you type one sentence into the prompt window: *make me a magazine-style pitch deck for the gathering retreat in Aurora.* The interactive form pops up first — five visual directions to choose from, each a complete palette and font stack already curated. You pick *Editorial Monocle*. A live `TodoWrite` plan streams down the right side of the screen. The agent reads its own design system, runs a five-dimensional self-critique against its draft, and sixty seconds later there is a deck — twelve slides, magazine-grade typography, hover states, the photographs already placed — rendering inside a sandboxed iframe in front of you.

You export it as PDF and walk it down to the printer. By the time the kettle boils, the pages are stacking on the side table, ready to be folded into the morning packets the early arrivals will carry into circle.

The agent that did the work was Claude Code, running locally on your laptop. The model never left the machine except for the API call you authorized. The deck file lives in a project folder you can open with your hands, edit with your text editor, version with git. Tomorrow morning you change two slides and re-export. The artifact is yours. The agent is yours. The model is yours.

This is what design feels like when it is a capability of the field rather than a subscription rented from a stranger.

![A community workshop table with a laptop showing a generated pitch deck on screen, printed pages stacking nearby, agent activity panel visible](visuals:photorealistic community workshop interior with a wooden table holding an open laptop displaying a magazine-style pitch deck on screen with editorial typography and warm color palette, a small agent activity panel visible on the right showing live todos and tool calls, a stack of freshly printed deck pages on the table next to a steaming mug of tea, morning light from a window, drafting tools and notebooks scattered, atmosphere of relaxed creative momentum)

## What Nature Teaches

A flower spends most of its life invisible. The roots, the stem, the leaves do their work in soil and shadow. Then for a few weeks the plant turns itself outward — opens a face into the air, releases scent, presents color, invites the bee. The flower is the plant's design surface. The interface where a long quiet living becomes legible to a passing stranger in seconds.

An apple is the same gesture. The tree spent a year photosynthesizing, drawing minerals through its mycorrhizal network, holding through frost and drought. The apple is the form that lets all of that travel. A child reaches up, takes the apple, and the year of sunlight enters their body. The tree did not have to translate. The apple did the translating.

Every living organism develops a skin where its inner work meets the world. The skin is permeable, expressive, specific. It is also expensive — the flower costs the plant real energy, the apple costs the tree real sugar. Organisms that try to live without an outward-facing surface stay invisible. Organisms that pour all their energy into the surface and forget the roots collapse under their own bloom.

The art is the membrane: enough surface to be met, enough roots to keep being.

## How It Lives Here

This body has already grown most of the deeper organs. The agent pipeline can already spawn Claude Code, Codex, Cursor as workers. The keystore at `~/.coherence-network/keys.json` already holds the keys each cell brings (BYOK). The model routing in `api/config/model_routing.json` already understands provider pluralism — claude, codex, gemini, openrouter — each kept within its own kind. The `generate_visuals.py` pipeline already turns concept files into images through Pollinations. The graph already stores artifacts as nodes. The web layer already renders concept pages, idea pages, spec pages.

What this body is missing is the artifact loop — the moment between *the field has a vision* and *a stranger can hold the form in their hands*. Open Design closes that gap.

The integration sits as a sidecar: the open-design daemon (`pnpm tools-dev`) runs as its own process, the network's API calls it through a thin adapter service, and the artifacts it produces — HTML, PDF, PPTX, MP4 — land back in the graph as artifact nodes attached to the concept, idea, spec, or vision they emerged from. A button on `/vision/{concept-id}` says *generate deck*. A button on a spec page says *generate prototype*. A button on the homepage says *generate the carousel for this week's pulse*. The pipeline can call it as a task type the way it already calls implementation, review, deploy.

The 31 skills already match the field's actual needs. *magazine-poster* for printable visions. *social-carousel* for the External Presence pillar. *web-prototype* and *mobile-app* for translating specs into mockups before implementation. *weekly-update* for the network's pulse. *deck* in four variants for retreats, gatherings, talks. *kanban-board, dashboard, finance-report* for operational surfaces. The 72 design systems are a starting library — the field's own design system grows next to them as the network finds its visual voice.

The lineage stays alive. Every artifact carries the prompt that shaped it, the skill that ran, the agent that worked, the model that responded, the cell that initiated. Attribution as gratitude trace, the way CC already flows through the economy. The artifacts go to the commons by default — the field's decks, prototypes, posters, films become part of what other communities can fork.

![A schematic showing the open-design daemon as a sidecar to the Coherence Network, artifacts flowing back into the graph as nodes connected to concepts and specs](visuals:photorealistic stylized architecture diagram showing the Coherence Network as a glowing organic graph on the left with concept and spec nodes connected by light threads, the open-design daemon as a smaller satellite organism on the right with prompts entering and HTML PDF PPTX MP4 artifacts emerging, thin golden connecting tissue between them representing the adapter service, dark background with warm bioluminescent palette, clean technical illustration with organic edges)

## Where You Can See It

**[nexu-io/open-design](https://github.com/nexu-io/open-design)** — Apache 2.0, twenty-five thousand stars, the broader of the two open-source alternatives to Claude Design. Auto-detects fifteen coding-agent CLIs on `PATH` (Claude Code, Codex, Devin for Terminal, Cursor Agent, Gemini CLI, OpenCode, Qwen, GitHub Copilot CLI, Hermes, Kimi, Pi, Kiro, Kilo, Mistral Vibe, DeepSeek TUI). Thirty-one composable skills. Seventy-two brand-grade design systems. BYOK proxy at every layer. Web app plus local daemon, optional Electron desktop shell. SQLite project state at `.od/app.sqlite`. One entry point: `pnpm tools-dev`.

**[OpenCoworkAI/open-codesign](https://github.com/OpenCoworkAI/open-codesign)** — MIT, the closer-peer reference. Electron desktop app, multi-model (Claude, GPT, Gemini, DeepSeek, Kimi, GLM, Ollama, OpenAI-compatible), one-click import of Claude Code or Codex API key. nexu-io explicitly stands on its streaming-artifact loop, sandboxed-iframe preview pattern, agent panel, and five-format export list. Two siblings of the same lineage.

**The lineage they stand on**: [`alchaincyf/huashu-design`](https://github.com/alchaincyf/huashu-design) — the design-philosophy compass with the Junior-Designer workflow and five-dimensional self-critique. [`op7418/guizang-ppt-skill`](https://github.com/op7418/guizang-ppt-skill) — magazine-style deck mode with WebGL hero. [`multica-ai/multica`](https://github.com/multica-ai/multica) — the daemon-and-runtime architecture. Each one open. Each one fork-able. Each one part of why open-design could be born so quickly after Claude Design landed on 2026-04-17.

**[Anthropic's Claude Design](https://www.anthropic.com/news/claude-design)** — the closed reference. Released 2026-04-17 on Opus 4.7. Showed what happens when a model stops writing prose and starts shipping artifacts. Cloud-only, paid-only, locked to Anthropic's stack. The artifact-first mental model is the gift; the lock-in is the form open-design composts.

**[awesome-design-md](https://github.com/VoltAgent/awesome-design-md) and [awesome-design-skills](https://github.com/bergside/awesome-design-skills)** — the public libraries open-design draws its design systems and skills from. Linear, Stripe, Vercel, Airbnb, Tesla, Notion, Apple, Cursor, Supabase, Figma, Xiaohongshu — seventy companies' visual languages curated for any cell to use.

## What We're Building

An artifact loop that lives inside the field, plugs into the rails already grown, and lets any cell turn a vision into a form a stranger can hold.

**Phase one** — the daemon as sidecar. A new spec under `external-presence` (or as a new sub-idea, depending on how the field senses it) wires open-design's local daemon as a sibling process to api/web. A thin Python adapter (`api/app/services/design_artifact_service.py`) calls the daemon's HTTP surface. Artifacts land in the graph as nodes (`type: artifact`, properties: `format`, `skill`, `prompt`, `source_concept_id`, `created_by`).

**Phase two** — the surface. A *generate* button appears on `/vision/{concept-id}`, on `/specs/{spec-id}`, on `/idea/{idea-id}`. Click brings up the same interactive form open-design's UI uses — pick a skill (deck, prototype, carousel, poster, magazine, weekly-update), pick a visual direction, watch the live agent panel as the artifact streams in. Save it back to the concept. Download it. Print it.

**Phase three** — the MCP tool. A new MCP function `coherence_generate_artifact` exposes the loop to agents in the pipeline. Specs that say "build a kanban-board UI" can have a design step before implementation — generate the prototype, get human assent, then implement against the form. Decks for the next gathering get generated by the same pipeline that opens issues and writes code.

**Phase four** — the field's own design system. The seventy-two systems open-design ships are the starting library. The network develops its own — the visual language already partly named in `docs/vision-kb/visual-language.md` (bioluminescent, fractal, organic) becomes a registered design system that any skill can call. The body's aesthetic enters the artifact loop as a first-class voice.

The artifacts go to the commons. The decks the field generates for retreats are published. The prototypes that turn into specs leave their original mockups visible. The posters that travel to other communities are released CC. The lineage from prompt to skill to model to artifact stays walkable.

## Resources

- [nexu-io/open-design](https://github.com/nexu-io/open-design) — Apache 2.0, the broader open-source alternative; web + local daemon + optional Electron (type: project)
- [OpenCoworkAI/open-codesign](https://github.com/OpenCoworkAI/open-codesign) — MIT, Electron desktop, the closer-peer reference (type: project)
- [open-design.ai](https://open-design.ai/) — the project's homepage (type: site)
- [alchaincyf/huashu-design](https://github.com/alchaincyf/huashu-design) — design-philosophy compass and self-critique protocol (type: lineage)
- [op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill) — magazine-style deck skill (type: lineage)
- [multica-ai/multica](https://github.com/multica-ai/multica) — daemon-and-runtime architecture (type: lineage)
- [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) — the seventy-product design-system library (type: library)
- [awesome-design-skills](https://github.com/bergside/awesome-design-skills) — fifty-seven design skills, public (type: library)
- [Anthropic's Claude Design](https://www.anthropic.com/news/claude-design) — the closed reference released 2026-04-17 (type: reference)

## The Questions That Live Here

- Where does the daemon live in the topology? A sidecar inside the docker compose stack on the VPS, a per-cell local process on each contributor's laptop, or both? What does each choice cost and what does it enable?
- Which skills does this field actually use most, once the loop is live? The seventy-two design systems are a generous library, but the network has its own emerging visual voice — at what point does a custom design system want to be born and what shape does it take?
- How does artifact attribution stay clean across the chain — the cell that prompted, the agent that worked, the model that responded, the skills that ran, the design system that shaped the form, the prior artifacts that influenced this one? Who earns CC when an artifact moves a stranger to join?
- The field already generates visuals through Pollinations. Open-design generates through gpt-image-2, Seedance, HyperFrames. Where do these complement and where do they overlap? When does each one feel right?
- The artifact loop makes design fast. What does the field still want to keep slow — the felt designs, the body-to-body transmissions, the ceremonies that resist being rendered? How does the loop know what to leave alone?

## Connected Frequencies

→ lc-instruments, lc-w-mycorrhizal, lc-network, lc-economy, lc-circulation, lc-offering, lc-transmission
