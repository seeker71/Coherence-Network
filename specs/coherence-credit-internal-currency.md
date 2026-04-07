---
idea_id: coherence-credit
status: done
source:
  - file: api/app/services/coherence_credit_service.py
    symbols: [exchange rates, CC conversion]
  - file: api/app/models/coherence_credit.py
    symbols: [CostVector, ValueVector, ExchangeRate, ProviderRate]
requirements:
  - "R1: CostVector and ValueVector Pydantic models that decompose any CC amount into resource categories"
  - "R2: ExchangeRate config loaded from `data/exchange_rates.json` with epoch-locked rates"
  - "R3: `cc_from_usd()` and `usd_from_cc()` conversion functions (verified inverses)"
  - "R4: `value_basis` field on the Idea model — dict mapping field names to human-readable rationale strings"
  - "R5: ProviderRate model for comparing providers in CC terms"
  - "R6: All existing hardcoded USD rates remain as defaults but are now mediated through the exchange rate config"
done_when:
  - "26 tests pass in test_coherence_credit.py"
  - "cc_from_usd and usd_from_cc are verified inverses"
  - "Every idea in SEED_IDEAS (scripts/seed_db.py) has value_basis with 6 required keys"
  - "Existing tests (test_ideas.py, test_idea_hierarchy.py) pass without regression"
test: "python3 -m pytest api/tests/test_idea_hierarchy.py api/tests/test_ideas.py -x -q"
constraints:
  - "Purely additive — no existing formulas or service logic modified"
  - "New Idea fields must be Optional with None defaults for backward compatibility"
---

> **Parent idea**: [coherence-credit](../ideas/coherence-credit.md)
> **Source**: [`api/app/services/coherence_credit_service.py`](../api/app/services/coherence_credit_service.py) | [`api/app/models/coherence_credit.py`](../api/app/models/coherence_credit.py)

# Coherence Credit (CC) — Internal Currency (Phase 1: Unit of Account)

## Purpose

The Coherence Network tracks ideas, specs, and value lineage but currently uses raw USD floats with hardcoded conversion rates scattered across services. This spec introduces an internal unit of account called "Coherence Credit" (CC) that represents real resource cost, preserves resource-type breakdowns, has a configurable exchange rate anchored to observable market prices, and makes all formulas dimensionally consistent. Phase 1 is purely additive: new models, config, service, and a `value_basis` field on Idea.

## Requirements

- [x] R1: CostVector and ValueVector Pydantic models that decompose any CC amount into resource categories
- [x] R2: ExchangeRate config loaded from `data/exchange_rates.json` with epoch-locked rates
- [x] R3: `cc_from_usd()` and `usd_from_cc()` conversion functions (verified inverses)
- [x] R4: `value_basis` field on the Idea model — dict mapping field names to human-readable rationale strings
- [x] R5: ProviderRate model for comparing providers in CC terms
- [x] R6: All existing hardcoded USD rates remain as defaults but are now mediated through the exchange rate config

## Research Inputs (Required)

- `2026-03-18` - OpenRouter billing data from agent_execution_service.py - anchors CC reference rate to real provider cost ($0.003/1K tokens)
- `2026-03-18` - Spec 115/116 grounded metrics pipeline - provides the data feeds that CC will denominate
- `2026-03-19` - Spec 117/118 unified store - provides the DB where CC fields will be persisted

## Task Card (Required)

```yaml
goal: Add CC unit of account models, conversion service, exchange rate config, and value_basis on all ideas
files_allowed:
  - api/app/models/coherence_credit.py
  - api/app/services/coherence_credit_service.py
  - api/app/models/idea.py
  - data/exchange_rates.json
  - scripts/seed_db.py
  - api/tests/test_coherence_credit.py
  - specs/coherence-credit-internal-currency.md
done_when:
  - 26 tests pass in test_coherence_credit.py
  - cc_from_usd and usd_from_cc are verified inverses
  - Every idea in SEED_IDEAS (scripts/seed_db.py) has value_basis with 6 required keys
  - Existing tests (test_ideas.py, test_idea_hierarchy.py) pass without regression
commands:
  - python3 -m pytest api/tests/test_coherence_credit.py -x -v
  - python3 -m pytest api/tests/test_idea_hierarchy.py api/tests/test_ideas.py -x -q
constraints:
  - Purely additive — no existing formulas or service logic modified
  - New Idea fields must be Optional with None defaults for backward compatibility
```

## API Contract (if applicable)

N/A - no API contract changes in this spec. Phase 2 will add exchange rate query endpoint.

## Data Model (if applicable)

```yaml
CostVector:
  properties:
    total_cc: { type: float, ge: 0 }
    compute_cc: { type: float, ge: 0, default: 0 }
    infrastructure_cc: { type: float, ge: 0, default: 0 }
    human_attention_cc: { type: float, ge: 0, default: 0 }
    opportunity_cc: { type: float, ge: 0, default: 0 }
    external_cc: { type: float, ge: 0, default: 0 }

ValueVector:
  properties:
    total_cc: { type: float, ge: 0 }
    adoption_cc: { type: float, ge: 0, default: 0 }
    lineage_cc: { type: float, ge: 0, default: 0 }
    friction_avoided_cc: { type: float, ge: 0, default: 0 }
    revenue_cc: { type: float, ge: 0, default: 0 }

ExchangeRate:
  properties:
    epoch: { type: string, min_length: 1 }
    cc_per_usd: { type: float, gt: 0 }
    reference_model: { type: string, default: "claude-sonnet-4-20250514" }
    reference_rate_usd: { type: float, gt: 0 }
    human_hour_cc: { type: float, gt: 0, default: 500.0 }
    locked_at: { type: datetime }
    notes: { type: string, default: "" }

ProviderRate:
  properties:
    provider_id: { type: string, min_length: 1 }
    display_name: { type: string, default: "" }
    cc_per_1k_input: { type: float, ge: 0 }
    cc_per_1k_output: { type: float, ge: 0 }
    cc_per_second: { type: float, ge: 0, default: 0 }
    quality_score: { type: float, ge: 0, le: 1, default: 0.5 }

Idea (modified):
  new_properties:
    value_basis: { type: "dict[str, str] | None", default: null }
    cost_vector: { type: "CostVector | None", default: null }
    value_vector: { type: "ValueVector | None", default: null }
```

## Files to Create/Modify

- `api/app/models/coherence_credit.py` - CC Pydantic models (CostVector, ValueVector, ProviderRate, ExchangeRate, ExchangeRateConfig)
- `api/app/services/coherence_credit_service.py` - config loading, conversion functions, vector builders
- `api/app/models/idea.py` - add value_basis, cost_vector, value_vector fields
- `data/exchange_rates.json` - default exchange rate config with providers
- `scripts/seed_db.py` - SEED_IDEAS inline constant with value_basis on all ideas
- `api/tests/test_coherence_credit.py` - 26 tests covering all requirements

## Acceptance Tests

- `api/tests/test_coherence_credit.py::TestCostVector::test_total_equals_sum`
- `api/tests/test_coherence_credit.py::TestValueVector::test_total_equals_sum`
- `api/tests/test_coherence_credit.py::TestExchangeRate::test_valid_rate`
- `api/tests/test_coherence_credit.py::TestConversions::test_inverse_cc_usd`
- `api/tests/test_coherence_credit.py::TestConversions::test_inverse_usd_cc`
- `api/tests/test_coherence_credit.py::TestProviderRate::test_cheapest_per_quality_unit`
- `api/tests/test_coherence_credit.py::TestConfigLoading::test_default_config_loads_when_no_file`
- `api/tests/test_coherence_credit.py::TestConfigLoading::test_config_file_loads_when_present`
- `api/tests/test_coherence_credit.py::TestIdeaValueBasis::test_value_basis_serialization`
- `api/tests/test_coherence_credit.py::TestSeedData::test_every_idea_has_value_basis`
- `api/tests/test_coherence_credit.py::TestSeedData::test_value_basis_has_required_keys`

## Verification

```bash
python3 -m pytest api/tests/test_coherence_credit.py -x -v
python3 -m pytest api/tests/test_idea_hierarchy.py api/tests/test_ideas.py -x -q
```

## Out of Scope

- Modifying any existing service logic or formulas (Phase 2)
- Populating cost_vector/value_vector from real data feeds (Phase 2)
- API endpoint for querying exchange rates (Phase 2)
- UI display of CC amounts (Phase 2)
- Epoch transition governance policy

## Risks and Assumptions

- **Assumption**: The reference model rate ($0.003/1K tokens) is stable enough for a quarterly epoch. If it changes mid-quarter, a new epoch must be published.
- **Risk**: Floating-point arithmetic may cause cc_from_usd/usd_from_cc to diverge at extreme values. Mitigation: round to 6 decimal places in tests.
- **Assumption**: `value_basis` strings are human-authored and not validated for correctness — they are documentation, not computation.

## Known Gaps and Follow-up Tasks

- Follow-up task: Phase 2 wire CC conversions into existing services (agent_execution_service, grounded_idea_metrics_service)
- Follow-up task: Phase 2 populate cost_vector and value_vector from real data feeds
- Follow-up task: Phase 2 API endpoint to query current exchange rates
- Follow-up task: Phase 2 UI display of CC amounts alongside USD
- Follow-up task: Define epoch transition policy (who approves, how published)

## Failure/Retry Reflection

- Failure mode: Exchange rate config file corrupt or malformed JSON
- Blind spot: No schema validation on file load beyond Pydantic parsing
- Next action: Service falls back to defaults on any load error, logged but non-fatal
