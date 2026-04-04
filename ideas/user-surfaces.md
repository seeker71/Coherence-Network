---
idea_id: user-surfaces
title: User Surfaces
stage: implementing
work_type: feature
specs:
  - 148-coherence-cli-comprehensive
  - 075-web-ideas-specs-usage-pages
  - 161-node-task-visibility
  - 162-meta-self-discovery
  - 165-ux-homepage-readability
  - 180-mcp-skill-registry-submission
---

# User Surfaces

CLI, web, and MCP surfaces that make the platform usable.

## What It Does

- Coherence CLI: 35+ commands for idea, task, pipeline, and node management
- Web pages: browsable ideas, specs, usage, and pipeline dashboards
- Node and task visibility: `cc tasks`, `cc task <id>`, web /pipeline
- Self-discovery: every endpoint/module navigable back to idea/spec
- Homepage: WCAG AA readable, real data not placeholders
- MCP skill registry: registered on discovery platforms for tool use

## API

- CLI: `cc ideas`, `cc tasks`, `cc ops`, `cc nodes`
- Web: `/ideas`, `/specs`, `/pipeline`, `/diagnostics`
- MCP: tool registration on Smithery, Glama, PulseMCP, etc.

## Why It Matters

The platform is useless if nobody can interact with it. These are the access points.
