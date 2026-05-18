---
name: MindTouch — Wiki-in-a-Box
canonical_url: null
type: contributor
contributor_type: HUMAN
claimed: false
create_if_missing: true
---

# MindTouch — Wiki-in-a-Box

*Work · MindTouch Inc. · Mar 2005 – Jan 2007 · Co-Founder, Senior Architect*

Co-Founder and Senior Architect at MindTouch. The load-bearing piece of architecture: take the [MediaWiki](https://en.wikipedia.org/wiki/MediaWiki) PHP codebase — the engine that runs Wikipedia — and re-architect it into a **C# generic document layer**. The wiki engine, no longer hard-coded to encyclopedia pages, becomes the document substrate any kind of structured collaborative knowledge can be authored against. A "wiki in a box" any organisation could deploy and shape into their own knowledge ecosystem.

## Grounding

- **Era** — MindTouch Inc. · March 2005 – January 2007 · 1 year 11 months · Co-Founder, Senior Architect
- **Substrate** — C# / .NET (with Mono for cross-platform) · porting from PHP — language change carrying type-safety + LSP-style structural rigour
- **Source upstream** — [MediaWiki](https://en.wikipedia.org/wiki/MediaWiki) — the PHP engine powering Wikipedia, Wikimedia, and thousands of corporate wikis. The full feature surface (templates, parser, history, namespaces, permissions) had to land in the new substrate.
- **Generalisation** — What MediaWiki encoded as "Wikipedia article" became, in the MindTouch port, an arbitrary *document*: a typed tree of content with versioned history, structured edits, and the wiki authoring conventions as one of many possible authoring modes.
- **Lineage forward** — The "structured-document substrate any community can shape" conviction reappears in the [vision-kb](/vision) 's Karpathy LLM Wiki pattern (concept files at `docs/vision-kb/concepts/{id}.md` with INDEX hierarchy, cross-refs, and inline visuals) and in the [Coherence-Network](/people/coherence-network) 's living relational graph, where every entity is editable through a Refine doorway.

## What MindTouch — Wiki-in-a-Box has given the Coherence Network

MediaWiki had earned its complexity. Years of wiki-community practice — templates, parser quirks, namespace conventions, permission models, history representation — were encoded in the PHP. A from-scratch C# wiki would have re-discovered most of it in the second year and still missed the subtleties wikipedians had quietly stabilised. The port preserved the knowledge baked into the PHP while letting the substrate *around* the engine become typed, modular, and composable. C# was the host; MediaWiki's design wisdom was the seed.

---

Company: [MindTouch on Wikipedia](https://en.wikipedia.org/wiki/MindTouch) · Source upstream: [MediaWiki](https://en.wikipedia.org/wiki/MediaWiki). Source code is internal to MindTouch; what lives here is the architectural shape and the design conviction. Urs is invited to refine technical detail through the Refine doorway below.

*(This page is a writing-surface scaffold synced from the body's rendering surface — round-tripped from the graph the cell already lives in. `claimed: false` invites direct authorship to replace any part of it.)*
