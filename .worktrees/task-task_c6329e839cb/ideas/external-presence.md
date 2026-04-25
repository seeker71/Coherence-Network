---
idea_id: external-presence
title: External Presence and Ecosystem
stage: implementing
work_type: feature
pillar: foundation
specs:
  - [external-presence-bots-and-news](../specs/external-presence-bots-and-news.md)
  - [multilingual-web](../specs/multilingual-web.md)
---

# External Presence and Ecosystem

The platform reaches the world through its edges. Bots on social networks, news ingestion pipelines, content parsing, multi-language translation, and ecosystem marketplace bridges — these are how Coherence Network connects to where contributors already are. You don't force people to visit your website; you meet them where they live.

## Problem

A platform that lives only at one URL has a ceiling on reach. Contributors are on Discord, Twitter, Telegram, Medium, Substack. News that resonates with active ideas is happening in real time across thousands of feeds. Content worth parsing sits in PDFs, articles, and images. Non-English speakers are excluded by default. Without external presence, the platform fails its mission of "every idea tracked — for humanity."

## Key Capabilities

- **Platform-native bots**: One bot per social network (Discord, Telegram, X/Twitter, Medium, Substack), each fluent in that platform's idioms. Bots ingest ideas from replies, post daily briefs, run polls, surface resonant news.
- **News ingestion with resonance**: Real-time news feeds matched against active ideas via triadic scoring. Surfaces opportunities and threats contributors should know about.
- **Configurable news sources**: Add, remove, update feeds via API and CLI. Contributors can curate their own news lens.
- **Content parsing pipeline**: Extract structured knowledge from any asset — PDF, article, image, video. Feeds the concept layer.
- **Multi-modal analysis**: LLM pipeline for text, image analysis for visual concept extraction.
- **Auto-translation**: Cached i18n for non-English users. Every idea, spec, and brief translatable on demand.
- **Geolocation awareness**: Nearby contributors, local ideas, regional news resonance. The platform is globally coherent AND locally relevant.
- **Ecosystem marketplace**: OpenClaw marketplace integration, community project ↔ funder match, cross-linked presences across every surface.
- **Source-rich metadata**: Ontology levels, categories, reliability scores on every external source.
- **Presence modularization**: Shared fragments and build script so every surface stays in sync without copy-paste drift.

## What Success Looks Like

- Contributors can submit ideas by replying to bot posts on any of 5+ social platforms
- News resonance feed runs 24/7 and surfaces relevant items for active ideas daily
- Non-English speakers use the platform without friction — translation is automatic and cached
- New contributors find the platform through its external surfaces, not by being told about it

## Absorbed Ideas

- **bot-discord**: Discord bot — channels per idea, slash commands, live pipeline feed.
- **bot-telegram**: Telegram bot — personal assistant for contributors on mobile.
- **bot-x-twitter**: X (Twitter) bot — threads, polls, idea ingestion from replies.
- **bot-medium-substack**: Medium + Substack bot — long-form idea articles and newsletters.
- **social-platform-bots**: Platform-native bot contributors — one per social network.
- **social-platform-coverage**: Full social platform coverage — Facebook, WhatsApp, Medium, Substack, and more.
- **news-ingestion-with-resonance-lens**: Ingest real-world news and connect it to ideas through resonance.
- **configurable-news-sources**: Add/remove/update feeds via API and CLI.
- **ucore-news-ingestion-daily-brief**: News ingestion + resonance matching for daily contributor briefs.
- **source-rich-metadata**: Rich source metadata — ontology levels, categories, reliability scores.
- **geolocation-interface**: Nearby contributors, local ideas, regional news resonance.
- **ucore-geolocation-nearby**: Geolocation awareness — nearby contributors, local ideas, regional news.
- **content-parsing-pipeline**: Extract structured knowledge from any asset.
- **i18n-auto-translation**: Auto language translation — cached i18n for non-English users.
- **auto-i18n-translation**: Auto language translation — cached i18n for non-English users (duplicate).
- **presence-modularization**: Modular public presences — shared fragments + build script.
- **community-project-funder-match**: Match community projects with small funders.
- **oss-interface-alignment**: Align OSS intelligence interfaces with runtime.
