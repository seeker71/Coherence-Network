---
category: digital-access
purpose: software subscriptions, API keys, cloud accounts, SaaS contracts, professional licenses
privacy: category-level entries public · credentials in wrapper's secret store
---

# Digital access

What can enter under this category:

- **Software subscriptions** — productivity tools, design software,
  development tools (GitHub, AWS, Cloudflare, etc.)
- **API keys** — third-party service credentials (OpenAI,
  Anthropic, Stripe, Twilio, etc.)
- **Cloud service accounts** — hosting providers, storage, compute
- **SaaS contracts** — enterprise agreements, team subscriptions
- **Professional licenses** — accountant, attorney, consultant,
  practitioner certifications that grant access to professional
  services or networks
- **Domain registrations** (operational side; trademark side lives
  in IP category)
- **Communication accounts** — email, messaging, social platforms
  the cell uses for network presence

## How digital access enters the body

Most digital subscriptions and API keys do not have transferable
title in the legal sense. The cell remains the account holder; the
wrapper is given operating authority to use the access on the
network's behalf, governed by the cell's signed terms.

Three common patterns:

- **Shared key**: the cell shares the API key or credential with
  the wrapper's secret store; both can use it; usage is logged and
  visible to the cell
- **Service-account-on-cell-account**: the cell creates a service
  account (e.g., a separate AWS IAM user) with limited scope; the
  wrapper holds those credentials; the cell retains root access
- **Pass-through billing**: the cell pays for the service; the
  wrapper uses it; the cooperative pool reimburses the cell at
  agreed rates

## Privacy

Public-level: service kind, intended network use, scope, primary
shepherd. **Never public**: actual API keys, passwords, cookies,
session tokens, account identifiers.

The wrapper's secret store (e.g., the existing
`~/.coherence-network/keys.json` pattern, or a more robust
shared-secret cooperative store) is where credentials actually
live.

## Inventory template

```yaml
- service_kind: subscription | api-key | cloud-account | professional-license | other
  service_category: "what it does (productivity, ai, hosting, design, comms, etc.)"
  network_use: "what the wrapper would use it for"
  scope: full | scoped-service-account | read-only | other
  relationship: held | access-granted | proposed
  primary_shepherd: cell_id_or_name
  wrapper_pattern: shared-key | service-account | pass-through-billing
  ceremony_date: YYYY-MM-DD
  notes: "anything the registry should know"
```

## Currently held (this cell's inventory)

```yaml
# Awaiting inventory.
# Subscriptions, API keys, and digital accounts the cell wants to
# bring into shared operating authority can be recorded here.
```

## Awaiting inventory — slots

Likely candidates: AI provider API keys (OpenAI, Anthropic, etc.)
which power agent runs; cloud infrastructure (AWS, Hostinger, etc.)
which already supports network deploys; design and creative tools
useful for cooperative work; communication accounts useful for the
cell's network presence.
