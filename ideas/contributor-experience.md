---
idea_id: contributor-experience
title: Contributor Experience
stage: specced
work_type: feature
pillar: network
specs:
  - [contributor-onboarding-and-governed-change-flow](../specs/contributor-onboarding-and-governed-change-flow.md)
  - [identity-driven-onboarding-tofu](../specs/identity-driven-onboarding-tofu.md)
  - [investment-ux-stake-cc-on-ideas](../specs/investment-ux-stake-cc-on-ideas.md)
  - [contributor-journey](../specs/contributor-journey.md)
---

# Contributor Experience

Make it obvious what the platform is, how to contribute, and how contributions are rewarded. A new contributor who lands on the site should understand within 30 seconds what Coherence Network is, what ideas are, what CC means, and how to participate. The current state -- "Share your idea" with no context -- is not enough.

## Problem

New contributors arrive and see a "Share your idea" prompt but have no context about what CC is, what ideas are for, or why they should participate. The onboarding flow assumes familiarity that does not exist. Contributors who do figure it out face a registration wall before they can do anything. The governed change flow (propose -> review -> approve -> implement) exists but is not surfaced in the UI.

## Key Capabilities

- **Contributor onboarding flow**: Step-by-step guided experience from first visit to first contribution. Identity verification happens in the background via TOFU -- no registration form, no OAuth dance. Contributors are productive immediately.
- **Governed change flow**: propose -> review -> approve -> implement. Every change goes through this pipeline. Quality is maintained without blocking contributors -- reviews happen asynchronously and contributors can work on the next thing while waiting.
- **Identity-driven onboarding (TOFU)**: Trust On First Use. Claim a handle, get a session token, start contributing. No password, no email verification, no OAuth. Identity is established on first interaction and strengthened over time as the contributor links more accounts.
- **Investment UX**: Stake CC on ideas you believe in. The staking interface shows expected ROI, current CC flow, and historical returns. Put your money where your belief is -- if the idea ships and creates value, stakers earn proportional returns.

## What Success Looks Like

- New contributor goes from landing page to first recorded contribution in under 3 minutes
- Zero contributors bounce because they do not understand what CC is or what ideas are for
- Governed change flow is visible and intuitive -- contributors know their proposal status at all times
- At least 20% of active contributors have staked CC on at least one idea

## Absorbed Ideas

- **ux-new-contributor-orientation**: Landing page needs context -- what is Coherence Network, what are ideas for, what does CC mean, why participate. "How it works" section (Share -> Grow -> Value) needs real examples, not abstract descriptions. Should show actual ideas that went from inception to completion with real CC payouts.
- **identity-37-providers**: 37 identity providers across 6 categories (Social, Dev, Crypto/Web3, Professional, Identity, Platform). Contributors attributed via any existing account without registering. GitHub, Twitter, Discord, Ethereum wallet, LinkedIn -- any existing identity is sufficient.
- **contributor-discovery**: unshipped attempt — contributor discovery (lineage: see `docs/lineage/unshipped-digest-2026-04-27.md`)
- **contributor-messaging**: unshipped attempt — contributor messaging (lineage: see `docs/lineage/unshipped-digest-2026-04-27.md`)

## Open Questions

- Should orientation be a permanent section on the homepage or a dismissible overlay for first-time visitors?
- How do we handle identity conflicts when a contributor claims a handle that maps to an existing account via a different provider?
