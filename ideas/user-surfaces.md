---
idea_id: user-surfaces
title: User Surfaces
stage: implementing
work_type: feature
pillar: surfaces
specs:
  - [148-coherence-cli-comprehensive](../specs/148-coherence-cli-comprehensive.md)
  - [075-web-ideas-specs-usage-pages](../specs/075-web-ideas-specs-usage-pages.md)
  - [161-node-task-visibility](../specs/161-node-task-visibility.md)
  - [162-meta-self-discovery](../specs/162-meta-self-discovery.md)
  - [165-ux-homepage-readability](../specs/165-ux-homepage-readability.md)
  - [180-mcp-skill-registry-submission](../specs/180-mcp-skill-registry-submission.md)
---

# User Surfaces

Web and CLI interfaces that make the platform usable by humans, agents, and scripts. The platform is useless if nobody can interact with it. These surfaces are the access points -- a web dashboard for browsing and exploration, a CLI for power users and automation, and an MCP skill registry for AI agent discovery.

## Problem

The platform has rich data (ideas, specs, tasks, contributions, coherence scores) but limited ways to access it. The web homepage has warm amber text on a dark background that is nearly invisible (fails WCAG AA contrast). The CLI exists but task visibility is limited -- you cannot easily see what nodes are running or drill into task details. The MCP server exists but is not registered on discovery platforms, so AI agents cannot find it. The system cannot describe its own capabilities to new users or agents.

## Key Capabilities

- **Web pages**: Browsable ideas list with free-energy scores, spec viewer with status indicators, usage dashboard with provider metrics, diagnostics page with failure breakdowns, pipeline view with task status. All pages use real data from the API, not placeholder content.
- **CLI (35+ commands)**: Full API surface coverage -- `cc ideas` (list/create/advance), `cc tasks` (list/detail/claim), `cc ops` (pipeline status, metrics), `cc nodes` (runner status), `cc diagnostics` (failure analysis), `cc stake` (invest CC), `cc fork` (branch ideas).
- **Homepage readability**: WCAG AA contrast compliance. The current warm amber palette is beautiful but the hero text is nearly invisible on the dark background. Fix contrast ratios to meet 4.5:1 minimum for normal text, 3:1 for large text, while preserving the visual identity.
- **MCP skill registry**: Submit the MCP server to Smithery, Glama, PulseMCP, and other discovery platforms. AI agents searching for "idea management" or "coherence scoring" tools should find Coherence Network's MCP server.
- **Node and task visibility**: See what runner nodes are active, what tasks each node is executing, drill into task details including execution time, provider, status, and error info. Both CLI (`cc tasks`, `cc task <id>`) and web (`/pipeline`) surfaces.
- **Metadata self-discovery**: The system describes its own capabilities. Every API endpoint links back to the idea and spec that defined it. New users and agents can explore the platform's capabilities without reading documentation.

## What Success Looks Like

- Homepage passes WCAG AA contrast checks on all text elements
- Every API endpoint is discoverable via the self-discovery system
- MCP server appears in search results on at least 2 discovery platforms
- Task visibility shows real-time status with under 5 seconds latency
- A new user can navigate from any page to the idea and spec that created it

## Absorbed Ideas

- **web-news-resonance-page**: `/news` page showing a daily resonance feed matched to ideas with relevance scores. External news articles and events are matched against active ideas to surface opportunities and threats. Helps contributors understand the broader context of their work.
- **ux-homepage-readability**: Hero text nearly invisible on dark background. Warm amber palette (`#D4A574` on `#1a1a2e`) gives approximately 3.2:1 contrast ratio -- below the 4.5:1 WCAG AA minimum. Fix by either lightening the text or adding a semi-transparent background behind text blocks.

## Open Questions

- Light mode toggle vs just fixing dark mode contrast? A toggle adds complexity but serves users in bright environments. Fixing dark mode alone is simpler and addresses the immediate problem.
