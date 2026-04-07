---
idea_id: identity-and-onboarding
title: Identity and Onboarding
stage: specced
work_type: feature
pillar: network
phase: 2
specs:
  - [identity-driven-onboarding-tofu](../specs/identity-driven-onboarding-tofu.md)
  - [investment-ux-stake-cc-on-ideas](../specs/investment-ux-stake-cc-on-ideas.md)
---

# Identity and Onboarding

How new contributors discover, understand, and join the platform. Identity is established on first interaction -- no registration wall, no OAuth flow, no email verification. Contributors bring their existing identity (GitHub, Twitter, Discord, Ethereum wallet, LinkedIn) and start contributing immediately. The system strengthens identity over time as more accounts are linked.

## Problem

Traditional platforms require registration before contribution. This creates a wall that filters out 90%+ of potential contributors who are curious but not committed. Coherence Network needs the opposite -- lower the barrier to zero so that the first interaction (posting an idea, staking CC, commenting) also establishes identity. The challenge is doing this securely without creating a spam vector.

## Key Capabilities

- **TOFU (Trust On First Use)**: Identity established on first interaction. Claim a handle, get a session token, start contributing. No password, no email verification, no OAuth dance. The handle is your identity. Trust is initially low and increases as you link more accounts and accumulate contribution history.
- **37 identity providers across 6 categories**: Social (Twitter, Discord, Reddit, Mastodon), Dev (GitHub, GitLab, Bitbucket, StackOverflow), Crypto/Web3 (Ethereum, Solana, NEAR, ENS), Professional (LinkedIn, AngelList), Identity (Keybase, PGP), Platform (Google, Apple, Microsoft). Contributors are attributed via any existing account without creating a new one.
- **Investment UX**: Stake CC on ideas you believe should be built. The staking interface shows current CC pool, expected ROI based on idea score, historical returns for similar ideas, and your current portfolio. Put your money where your belief is -- if the idea ships and creates measurable value, stakers earn proportional returns.
- **Auto-attach attribution**: Contributions are automatically linked to the contributor's identity based on session token. No manual "claim this contribution" step. If you do the work while authenticated, you get the credit.

## What Success Looks Like

- A new contributor goes from first visit to first contribution in under 60 seconds
- Zero contributors are blocked by a registration requirement
- Identity strength increases measurably as contributors link additional accounts
- At least 30% of contributors have linked 2+ identity providers within their first week

## Absorbed Ideas

- **identity-37-providers**: Contributors attributed via any existing account without registering. The 37 providers cover every major platform where developers and creators have existing identities. No contributor should need to create a new account just to participate in Coherence Network.
- **ux-new-contributor-orientation**: New contributor sees "Share your idea" but no context about what CC is, what ideas are for, or why they should participate. Needs an orientation flow that explains the value proposition in concrete terms -- show real ideas that went from inception to completion, show real CC payouts, show real contribution histories.
