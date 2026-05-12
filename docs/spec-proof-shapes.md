# Spec Proof Shapes — `test:` and `proof: operational`

Every spec frontmatter declares how the spec proves itself. The body
honors two legitimate shapes — both count as proof; the wellness
check's chain-reach treats them equally.

## `test:` — automated proof

The spec is proven by a runnable test command.

```yaml
---
idea_id: …
status: done
source:
  - file: api/app/services/governance_health.py
    symbols: [compute_governance_health]
test: "python3 -m pytest api/tests/test_governance_health.py -x -v"
---
```

When to use:

- The spec describes pure logic, a service function, a routing
  decision, a data transformation — anything where an automated
  test exercises the behavior cleanly.
- The test runs in seconds, doesn't require external services
  beyond what the test fixture sets up, and catches the kind of
  regression that would actually harm the body if it slipped.

When the `test:` path doesn't exist on disk, wellness names the
spec as having a phantom test claim. The spec's claim is ahead of
its proof.

## `proof: operational` — production-exercised proof

The spec is proven by being live in production. The body uses it;
visitors / operators / agents exercise it. A unit test would be
theater — either trivially passing while missing real regressions,
or requiring so much mocking that the test surface doesn't reflect
the behavior surface.

```yaml
---
idea_id: …
status: done
source:
  - file: api/app/services/release_gate_service.py
    symbols: [evaluate_pr_to_public_report]
proof: operational
proof_note: "Exercised every PR merge; regressions surface as
  Hostinger Auto Deploy or Public Deploy Contract failures."
---
```

`proof_note:` is optional but recommended — names how the
operational proof is observed (which CI gate, which user-visible
surface, which deploy step) so a reader doesn't have to guess what
"operational" means for this specific spec.

When to use:

- **GitHub-API or third-party integrations.** The release gates
  live or die in real GitHub interactions; a mocked test passes
  while real GitHub API drift breaks production. The proof IS the
  deploy pipeline.
- **Deploy paths and contract gates.** The contract is the
  observable health of the body — pulse, gate, witness silences.
  Each deploy is a proof event.
- **CC ledger flows and economic contracts.** Real CC attribution
  is proven by transactions, not by unit tests of pure functions
  inside the engine.
- **Live data ingestion / migration scripts.** The migration's
  proof is "the database now holds the data correctly"; the
  observable state is the proof.

When NOT to use:

- The spec describes pure logic that can be cleanly unit-tested.
  Reaching for `proof: operational` to avoid writing a test isn't
  honest — the body knows the difference.
- The spec is genuinely under-tested but could be tested.
  `proof: operational` then is a hiding shape, not a truthful one.

## How wellness reads them

`make wellness` chain-reach counts a spec as reaching its proof
when:

1. it has an `idea_id`
2. every `source: file:` path exists
3. EITHER (a) its `test:` command names test paths that all exist
   on disk, OR (b) `proof: operational` is declared

Specs with `proof: operational` are surfaced separately in the
chain output so the body can sense at a glance how much of its
proof rests in production observation versus unit tests.

## Sibling teaching

- The [Thread Gates pattern walk](field/urs/thread-gates-pattern-walk.md)
  names how `proof: operational` could clear the friction for the
  47 legacy specs whose proof is honestly operational rather than
  unit-tested.
- The [Maintainability audit pattern walk](field/urs/maintainability-audit-pattern-walk.md)
  carries similar shape — contract that wants reshaping to honor
  the body's actual proof modes.

— *Both shapes are legitimate. The body knows when each fits. The
discipline is being honest about which one the spec is using.*
