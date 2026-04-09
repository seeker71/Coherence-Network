---
idea_id: contributor-experience
status: done
source:
  - file: api/app/routers/onboarding.py
    symbols: [register, get_session, list_contributors]
  - file: api/app/services/onboarding_service.py
    symbols: [register, resolve_session, list_contributors]
  - file: api/app/routers/governance.py
    symbols: [create_change_request, cast_vote]
  - file: api/app/services/governance_service.py
    symbols: [create_change_request, vote_on_change_request]
  - file: api/app/routers/contributor_identity.py
    symbols: [link_identity, get_identities, lookup_identity]
  - file: api/app/routers/memberships.py
    symbols: [list_members, invite_member, accept_invite]
  - file: api/app/routers/messages.py
    symbols: [send_message, get_inbox]
requirements:
  - New contributor can register with zero friction (TOFU -- handle-based, no password)
  - Contributors can link 37+ identity providers (GitHub, Discord, Ethereum, etc.)
  - Contributors can submit governed change requests for ideas/specs
  - Contributors can vote on change requests with attribution
  - Contributors can join workspaces via invite/accept flow
  - Contributors can message each other directly or in workspace boards
  - Contributor portfolio shows CC balance, stakes, contributions, tasks
done_when:
  - POST /api/onboarding/register creates session in under 1 second
  - GET /api/onboarding/contributors lists registered contributors
  - POST /api/governance/change-requests stores proposer attribution
  - POST /api/governance/change-requests/{id}/votes records vote with rationale
  - Approved change requests auto-apply
  - GET /api/messages/inbox/{contributor_id} returns messages
  - All tests pass
test: "python3 -m pytest api/tests/test_governance_change_flow.py api/tests/test_flow_memberships.py api/tests/test_flow_messages.py -q"
---

> **Parent idea**: [contributor-experience](../ideas/contributor-experience.md)
> **Source**: [`api/app/routers/onboarding.py`](../api/app/routers/onboarding.py) | [`api/app/services/onboarding_service.py`](../api/app/services/onboarding_service.py) | [`api/app/routers/governance.py`](../api/app/routers/governance.py) | [`api/app/services/governance_service.py`](../api/app/services/governance_service.py) | [`api/app/routers/contributor_identity.py`](../api/app/routers/contributor_identity.py) | [`api/app/routers/memberships.py`](../api/app/routers/memberships.py) | [`api/app/routers/messages.py`](../api/app/routers/messages.py)

# Contributor Journey -- From Registration to Recognized Participation

## Goal

Define the complete contributor experience from zero-friction TOFU registration through identity linking, governance participation, workspace membership, and direct messaging -- the full path from first visit to recognized, attributed participation in the network.

## What's Built

The contributor journey spans seven source files across three layers (registration, governance, social).

**Registration and identity**: `onboarding.py` and `onboarding_service.py` implement Trust On First Use (TOFU) -- a contributor claims a handle, receives a session token, and starts contributing immediately. No password, no email verification, no OAuth dance. The `contributor_identity.py` router supports linking 37+ identity providers across 6 categories (Social, Dev, Crypto/Web3, Professional, Identity, Platform) so identity strengthens over time without gating first interaction.

**Governance**: `governance.py` and `governance_service.py` implement the propose-review-approve-apply pipeline. Any contributor can submit change requests for ideas, specs, or questions. Every change request stores proposer attribution. Reviewers (human or machine) cast yes/no votes with rationale. Approved requests auto-apply by default with the result recorded.

**Social layer**: `memberships.py` implements workspace membership via invite/accept flow -- contributors join workspaces to collaborate on related ideas. `messages.py` provides direct messaging between contributors and workspace board messages, enabling asynchronous coordination without leaving the platform.

## Requirements

1. New contributor can register with zero friction (TOFU -- handle-based, no password)
2. Contributors can link 37+ identity providers (GitHub, Discord, Ethereum, etc.)
3. Contributors can submit governed change requests for ideas/specs
4. Contributors can vote on change requests with attribution
5. Contributors can join workspaces via invite/accept flow
6. Contributors can message each other directly or in workspace boards
7. Contributor portfolio shows CC balance, stakes, contributions, tasks

## Acceptance Tests

```bash
python3 -m pytest api/tests/test_governance_change_flow.py api/tests/test_flow_memberships.py api/tests/test_flow_messages.py -q
```
