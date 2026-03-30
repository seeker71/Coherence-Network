# Spec — identity-37-providers: 37 Identity Providers Across 6 Categories with Auto-Attach Attribution

**Idea ID:** identity-37-providers
**Parent:** identity-driven-onboarding
**Status:** draft
**Date:** 2026-03-30

---

## Purpose

Normalize the Coherence Network identity provider catalog from the current ad-hoc 40-provider / 7-category registry to a curated **37-provider / 6-category** contract. Merge the "Agent" and "Custom" categories into a new "Platform" category, drop redundant entries, and introduce **auto-attach attribution** — a mechanism that resolves contributor identity from any linked account at contribution time, so contributors are credited without explicit registration.

The current registry (`identity_providers.py`) already holds most providers, but:
1. Categories are not aligned with the spec'd 6 (Social, Dev, Crypto/Web3, Professional, Identity, Platform).
2. There is no "auto-attach" attribution — contributions require the contributor_id to be passed explicitly.
3. There are no metrics to prove the feature is working (resolution rate, provider popularity, attribution coverage).

This spec addresses all three gaps.

---

## Requirements

### R1 — Normalize Provider Registry to 37 Providers / 6 Categories

The registry in `identity_providers.py` must contain exactly the following 37 providers grouped into 6 categories:

| # | Category | Providers (key) | Count |
|---|----------|-----------------|-------|
| 1 | **Social** | github, x, discord, telegram, mastodon, bluesky, linkedin, reddit, youtube, twitch | 10 |
| 2 | **Dev** | gitlab, bitbucket, npm, crates, pypi, hackernews, stackoverflow | 7 |
| 3 | **Crypto / Web3** | ethereum, bitcoin, solana, cosmos, nostr, ens, lens | 7 |
| 4 | **Professional** | email, google, apple, microsoft, orcid | 5 |
| 5 | **Identity** | name, did, keybase, pgp, fediverse | 5 |
| 6 | **Platform** | agent, openrouter, ollama | 3 |
| | **Total** | | **37** |

**Changes from current registry:**
- Remove `instagram` and `tiktok` from Social (low developer/OSS signal).
- Merge "Agent" (3 providers) and "Custom" (1 provider: openclaw) into "Platform".
- Remove `openclaw` — it is a node identity, not a contributor identity (covered by federation spec 132).
- Total: 40 − 2 (instagram, tiktok) − 1 (openclaw) = **37**.

**Acceptance criteria:**
- `GET /api/identity/providers` returns exactly 6 category keys.
- Flat provider list has exactly 37 entries.
- Each provider has: `key`, `label`, `placeholder`, `category`, `canOAuth`, `canVerify`.
- Registry includes a `REGISTRY_VERSION = "37-v1"` constant for schema versioning.

### R2 — Auto-Attach Attribution

When a contribution is created (idea, code, review, or any `POST /api/contributions` payload), the system should attempt to resolve the contributor identity automatically from any linked account, even if the caller did not supply a `contributor_id`.

**Resolution order:**
1. `X-API-Key` header → look up contributor via `auth_keys` table.
2. `contributor_id` field in request body → use directly.
3. `provider` + `provider_id` fields in request body → reverse-lookup via `contributor_identities` table.
4. If none match → create an anonymous attribution record with `contributor_id = "anon:<provider>:<provider_id>"` and `trust_level = "unverified"`.

**Acceptance criteria:**
- `POST /api/contributions` accepts optional `provider` + `provider_id` in lieu of `contributor_id`.
- When `provider` + `provider_id` are supplied and match a linked identity, the contribution is attributed to the resolved contributor.
- When no match exists, an anonymous attribution is created and the response includes `"attribution": "auto-anon"`.
- The response always includes an `identity_resolution` object: `{ "method": "api_key"|"explicit"|"auto_attach"|"auto_anon", "provider": ..., "contributor_id": ... }`.

### R3 — Attribution Metrics & Proof Endpoint

A new endpoint reports how well auto-attach is working, enabling the open question: *"How can we prove this feature is working and make that proof clearer over time?"*

**Endpoint:** `GET /api/identity/metrics`

**Response shape:**
```json
{
  "registry_version": "37-v1",
  "total_providers": 37,
  "total_categories": 6,
  "linked_identities": 142,
  "unique_contributors_with_links": 89,
  "provider_popularity": [
    { "provider": "github", "count": 78 },
    { "provider": "ethereum", "count": 34 }
  ],
  "attribution_stats": {
    "total_contributions": 500,
    "by_method": {
      "api_key": 200,
      "explicit": 150,
      "auto_attach": 120,
      "auto_anon": 30
    },
    "auto_attach_rate": 0.24,
    "coverage_rate": 0.94
  },
  "category_coverage": {
    "Social": { "providers_used": 6, "providers_total": 10 },
    "Dev": { "providers_used": 4, "providers_total": 7 },
    "Crypto / Web3": { "providers_used": 2, "providers_total": 7 },
    "Professional": { "providers_used": 3, "providers_total": 5 },
    "Identity": { "providers_used": 1, "providers_total": 5 },
    "Platform": { "providers_used": 1, "providers_total": 3 }
  }
}
```

**Acceptance criteria:**
- `GET /api/identity/metrics` returns the shape above with live data.
- `auto_attach_rate` = auto_attach / total_contributions (0.0–1.0).
- `coverage_rate` = (contributions with known contributor) / total_contributions (0.0–1.0).
- Provider popularity is sorted descending by count.

### R4 — Provider Metadata Enhancements

Each provider entry gains two optional fields for UI rendering:
- `icon`: string — icon identifier (e.g., `"si-github"` for Simple Icons, `"eth"` for crypto).
- `url_template`: string | null — URL template for linking to the profile (e.g., `"https://github.com/{id}"`).

**Acceptance criteria:**
- `GET /api/identity/providers` returns `icon` and `urlTemplate` for every provider.
- `urlTemplate` is null for providers without a public profile URL (e.g., `name`, `pgp`).

### R5 — Web: Provider Picker Component

The web frontend displays an identity provider picker grouped by category, used during onboarding and in the contributor profile page.

**Acceptance criteria:**
- `/onboarding` page shows all 6 categories as collapsible sections.
- Each provider shows icon, label, and placeholder.
- Clicking a provider opens an input field; submitting calls `POST /api/identity/link`.
- The component fetches provider data from `GET /api/identity/providers` (not hardcoded).

---

## Data Model Changes

### `contributor_identities` table — no schema change

Existing schema is sufficient. The `provider` column already stores the key string, and the `metadata_json` column can hold `identity_resolution` context.

### New: `identity_resolution_log` table

Tracks how each contribution was attributed, enabling the metrics endpoint.

```sql
CREATE TABLE IF NOT EXISTS identity_resolution_log (
    id          TEXT PRIMARY KEY,  -- ulid or uuid
    contribution_id TEXT NOT NULL,
    method      TEXT NOT NULL,     -- api_key | explicit | auto_attach | auto_anon
    provider    TEXT,              -- null for api_key/explicit
    provider_id TEXT,              -- null for api_key/explicit
    contributor_id TEXT NOT NULL,
    resolved_at TEXT NOT NULL      -- ISO 8601 UTC
);
CREATE INDEX idx_irl_method ON identity_resolution_log(method);
CREATE INDEX idx_irl_contributor ON identity_resolution_log(contributor_id);
```

### `identity_providers.py` — schema change

Add `REGISTRY_VERSION`, `icon`, and `url_template` fields to `ProviderInfo`. Reorganize categories from 7 → 6.

---

## API Changes

| Method | Endpoint | Change |
|--------|----------|--------|
| GET | `/api/identity/providers` | Returns 6 categories, 37 providers, includes `icon` and `urlTemplate` |
| POST | `/api/identity/link` | No change (already works for all 37 providers) |
| GET | `/api/identity/metrics` | **New** — attribution metrics and proof dashboard data |
| POST | `/api/contributions` | Accept optional `provider` + `provider_id` for auto-attach resolution |
| GET | `/api/identity/{contributor_id}` | No change |
| GET | `/api/identity/lookup/{provider}/{provider_id}` | No change |

---

## Out of Scope

- OAuth flow implementation for new providers (Discord, GitLab, etc.) — separate specs per provider.
- Time-series analytics dashboard — this spec covers point-in-time metrics only.
- Provider-specific verification flows beyond existing GitHub OAuth and Ethereum signature.
- Migration of existing `instagram`, `tiktok`, or `openclaw` records — follow-up task.
- Rate limiting on auto-attach resolution — follow-up security spec.

## Files to Create or Modify

### API (Python)

| File | Action | Description |
|------|--------|-------------|
| `api/app/services/identity_providers.py` | **Modify** | Normalize to 37 providers / 6 categories; add `REGISTRY_VERSION`, `icon`, `url_template` to `ProviderInfo`; remove instagram, tiktok, openclaw; rename Agent+Custom → Platform |
| `api/app/services/contributor_identity_service.py` | **Modify** | Add `log_identity_resolution()` function; add `get_attribution_metrics()` function; create `identity_resolution_log` table in `_ensure_tables()` |
| `api/app/services/identity_resolution.py` | **Create** | Auto-attach resolution logic: `resolve_contributor(api_key, contributor_id, provider, provider_id) → (contributor_id, method)` |
| `api/app/routers/contributor_identity.py` | **Modify** | Add `GET /api/identity/metrics` endpoint; update `/providers` response to include `icon` and `urlTemplate` |
| `api/app/routers/contributions.py` | **Modify** | Wire auto-attach resolution into contribution creation flow |
| `api/app/models/contributor.py` | **No change** | Existing model sufficient |

### Web (Next.js / TypeScript)

| File | Action | Description |
|------|--------|-------------|
| `web/app/onboarding/page.tsx` | **Modify** | Integrate provider picker into onboarding flow |
| `web/components/identity/provider-picker.tsx` | **Create** | Reusable provider picker component — fetches from API, groups by category, renders icons |
| `web/components/identity/provider-icon.tsx` | **Create** | Icon resolver component for provider keys |

### Tests

| File | Action | Description |
|------|--------|-------------|
| `api/tests/test_identity_providers.py` | **Modify** | Assert exactly 37 providers, 6 categories, registry version |
| `api/tests/test_identity_resolution.py` | **Create** | Test auto-attach resolution logic (all 4 methods) |
| `api/tests/test_identity_metrics.py` | **Create** | Test metrics endpoint response shape and calculations |

---

## Acceptance Tests

- `api/tests/test_identity_providers.py` — assert exactly 37 providers, 6 categories, and `REGISTRY_VERSION == "37-v1"`.
- `api/tests/test_identity_resolution.py` — test all 4 resolution methods (api_key, explicit, auto_attach, auto_anon) including edge cases (unsupported provider, missing identity).
- `api/tests/test_identity_metrics.py` — test metrics endpoint returns correct shape, handles empty DB (no divide-by-zero), and calculates rates correctly.
- Manual validation: run all verification scenarios below against a local or staging API instance.

## Verification Scenarios

### Scenario 1: Registry Contract — 37 Providers, 6 Categories

**Setup:** API running with the updated identity_providers.py.

**Action:**
```bash
curl -s $API/api/identity/providers | python3 -c "
import sys, json
d = json.load(sys.stdin)
cats = d['categories']
print('Categories:', sorted(cats.keys()))
print('Category count:', len(cats))
total = sum(len(v) for v in cats.values())
print('Total providers:', total)
print('Registry version:', d.get('registry_version', 'MISSING'))
"
```

**Expected result:**
- Categories: `['Crypto / Web3', 'Dev', 'Identity', 'Platform', 'Professional', 'Social']`
- Category count: `6`
- Total providers: `37`
- Registry version: `37-v1`

**Edge cases:**
- `instagram`, `tiktok`, `openclaw` must NOT appear in the response (HTTP 200 but absent from payload).
- `agent`, `openrouter`, `ollama` appear under "Platform" (not "Agent" or "Custom").

---

### Scenario 2: Auto-Attach Attribution via Provider Identity

**Setup:** A contributor `alice` exists with a linked GitHub identity:
```bash
# Create contributor
curl -s $API/api/contributors -X POST \
  -H "Content-Type: application/json" \
  -d '{"name":"alice","type":"HUMAN"}'

# Link GitHub identity
curl -s $API/api/identity/link -X POST \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"alice","provider":"github","provider_id":"alice-gh"}'
```

**Action:** Submit a contribution using only the GitHub identity (no contributor_id):
```bash
curl -s $API/api/contributions -X POST \
  -H "Content-Type: application/json" \
  -d '{"type":"code","description":"Fix bug #42","provider":"github","provider_id":"alice-gh","cc":3}'
```

**Expected result:**
- HTTP 201
- Response body includes:
  - `"contributor_id": "alice"`
  - `"identity_resolution": {"method": "auto_attach", "provider": "github", "contributor_id": "alice"}`

**Edge case — unknown provider_id:**
```bash
curl -s $API/api/contributions -X POST \
  -H "Content-Type: application/json" \
  -d '{"type":"code","description":"Drive-by fix","provider":"github","provider_id":"unknown-user","cc":1}'
```
- HTTP 201
- Response includes `"identity_resolution": {"method": "auto_anon", "provider": "github", "contributor_id": "anon:github:unknown-user"}`

**Edge case — unsupported provider:**
```bash
curl -s $API/api/contributions -X POST \
  -H "Content-Type: application/json" \
  -d '{"type":"code","description":"test","provider":"myspace","provider_id":"tom","cc":1}'
```
- HTTP 422 with detail containing "Unsupported provider"

---

### Scenario 3: Attribution Metrics Prove the Feature Works

**Setup:** Several contributions exist with mixed attribution methods (from Scenarios 1-2 and production data).

**Action:**
```bash
curl -s $API/api/identity/metrics | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Registry version:', d['registry_version'])
print('Total providers:', d['total_providers'])
print('Linked identities:', d['linked_identities'])
stats = d['attribution_stats']
print('Total contributions:', stats['total_contributions'])
print('Auto-attach rate:', stats['auto_attach_rate'])
print('Coverage rate:', stats['coverage_rate'])
print('Methods:', stats['by_method'])
print('Category coverage:', json.dumps(d['category_coverage'], indent=2))
"
```

**Expected result:**
- `registry_version`: `"37-v1"`
- `total_providers`: `37`
- `auto_attach_rate`: float 0.0–1.0
- `coverage_rate`: float 0.0–1.0
- `by_method` keys: exactly `["api_key", "explicit", "auto_attach", "auto_anon"]`
- `category_coverage` has exactly 6 keys matching the 6 categories
- `provider_popularity` is sorted descending by `count`

**Edge case — empty database:**
- All counts are 0, rates are 0.0, `provider_popularity` is `[]`.
- Must not return 500 or divide-by-zero.

---

### Scenario 4: Full Create-Read-Update Cycle for Identity Links

**Setup:** Contributor `bob` exists.

**Action — Create:**
```bash
curl -s $API/api/identity/link -X POST \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"bob","provider":"ethereum","provider_id":"0xABC123","display_name":"bob.eth"}'
```
- HTTP 200, response includes `"provider": "ethereum"`, `"verified": false`

**Action — Read:**
```bash
curl -s $API/api/identity/bob
```
- Returns list with at least one entry where `provider == "ethereum"` and `provider_id == "0xABC123"`

**Action — Update (re-link with new display name):**
```bash
curl -s $API/api/identity/link -X POST \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"bob","provider":"ethereum","provider_id":"0xABC123","display_name":"bob-updated.eth"}'
```
- HTTP 200, response shows `"display_name": "bob-updated.eth"` (upsert, not duplicate)

**Action — Verify count didn't increase:**
```bash
curl -s $API/api/identity/bob | python3 -c "
import sys, json
ids = json.load(sys.stdin)
eth = [i for i in ids if i['provider'] == 'ethereum']
print('Ethereum entries:', len(eth))  # Must be 1, not 2
"
```
- Output: `Ethereum entries: 1`

**Action — Delete:**
```bash
curl -s $API/api/identity/bob/ethereum -X DELETE
```
- HTTP 200, `{"status": "unlinked"}`

**Action — Verify deletion:**
```bash
curl -s $API/api/identity/bob
```
- Returns list without any ethereum entry

**Edge case — delete nonexistent:**
```bash
curl -s -o /dev/null -w "%{http_code}" $API/api/identity/bob/ethereum -X DELETE
```
- HTTP 404

---

### Scenario 5: Reverse Lookup and Cross-Provider Attribution

**Setup:** Contributor `carol` has both GitHub and Ethereum identities linked:
```bash
curl -s $API/api/identity/link -X POST \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"carol","provider":"github","provider_id":"carol-dev"}'
curl -s $API/api/identity/link -X POST \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"carol","provider":"ethereum","provider_id":"0xCAROL"}'
```

**Action — Reverse lookup by GitHub:**
```bash
curl -s $API/api/identity/lookup/github/carol-dev
```
- HTTP 200, `{"contributor_id": "carol", "provider": "github", "provider_id": "carol-dev"}`

**Action — Reverse lookup by Ethereum:**
```bash
curl -s $API/api/identity/lookup/ethereum/0xCAROL
```
- HTTP 200, `{"contributor_id": "carol", "provider": "ethereum", "provider_id": "0xCAROL"}`

**Action — Contribute via Ethereum, attributed to same contributor as GitHub:**
```bash
curl -s $API/api/contributions -X POST \
  -H "Content-Type: application/json" \
  -d '{"type":"review","description":"Code review","provider":"ethereum","provider_id":"0xCAROL","cc":2}'
```
- HTTP 201, `contributor_id` in response is `"carol"` (same contributor resolved from either provider)

**Edge case — lookup nonexistent identity:**
```bash
curl -s -o /dev/null -w "%{http_code}" $API/api/identity/lookup/github/nonexistent
```
- HTTP 404

---

## Answering the Open Question

> *How can we improve this idea, show whether it is working yet, and make that proof clearer over time?*

The answer is the **metrics endpoint** (R3) combined with **identity resolution logging** (R2).

### Proof Strategy

1. **Day 1 — Baseline:** `GET /api/identity/metrics` shows `auto_attach_rate: 0.0` and `coverage_rate` based on explicit contributor IDs only.

2. **Week 1 — Adoption:** As contributors link identities and contributions flow through auto-attach, `auto_attach_rate` rises above 0. The `provider_popularity` list shows which providers are actually used (pruning signal for future iterations).

3. **Month 1 — Coverage:** `coverage_rate` approaching 1.0 means nearly all contributions are attributed to known contributors. `category_coverage` reveals which provider categories are underutilized.

4. **Ongoing — Dashboard:** The web dashboard (future spec) renders these metrics as time-series charts. Key indicators:
   - **Auto-attach rate trend** — proves the feature is saving contributors from manual registration.
   - **Provider diversity** — shows how many of the 37 providers are actually being used.
   - **Anonymous attribution rate** — high `auto_anon` signals drive-by contributors who could be converted.

5. **Improvement levers:**
   - Add OAuth flows for high-popularity providers (currently only GitHub + Google have `canOAuth`).
   - Prompt anonymous contributors to claim their identity post-contribution.
   - Surface "link your X account" nudges based on `category_coverage` gaps.

---

## Risks and Assumptions

### Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Removing instagram/tiktok/openclaw breaks existing linked identities | Medium | Migration: leave existing records in DB; just remove from registry. API returns them as `provider: "legacy:instagram"` on read. |
| Auto-attach allows impersonation (anyone can claim `provider_id`) | High | Auto-attached identities inherit `verified: false`. Only OAuth/signature verification sets `verified: true`. UI shows verification badges. |
| Anonymous attribution (`anon:*`) pollutes contributor namespace | Low | Anonymous IDs are namespaced with `anon:` prefix and excluded from leaderboards/rankings by default. |
| Metrics endpoint performance on large datasets | Low | Resolution log is append-only; metrics query uses indexed aggregations. Add caching if needed. |

### Assumptions

- The contribution creation endpoint (`POST /api/contributions`) exists or will be created by the time this spec is implemented.
- OAuth client credentials for GitHub are already configured in production (per existing spec 168/169).
- The `identity_resolution_log` table is acceptable as a new table in the unified database (no separate analytics store needed for MVP).
- Removing 3 providers from the registry is non-breaking because the link endpoint validates against the registry at write time, not read time — existing records are preserved.

---

## Known Gaps and Follow-up Tasks

- **OAuth flows for additional providers** — Only GitHub and Google have OAuth today. High-value additions: Discord, GitLab, LinkedIn. Separate spec per provider.
- **Verification badges in web UI** — Show verified vs. unverified identities distinctly. Part of the provider-picker component but visual design TBD.
- **Rate limiting on auto-attach** — Prevent abuse of anonymous attribution. Follow-up security spec.
- **Legacy provider migration** — Script to re-tag existing `instagram`, `tiktok`, and `openclaw` records.
- **Time-series metrics** — Current metrics endpoint is point-in-time. Historical tracking requires a separate analytics pipeline or periodic snapshots.
- **Provider deactivation** — Ability to soft-disable a provider without removing it from the registry (e.g., if an API goes offline).
