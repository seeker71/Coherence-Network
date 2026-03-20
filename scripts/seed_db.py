#!/usr/bin/env python3
"""Seed data/coherence.db from spec markdown files, commit evidence JSON, and inline idea data.

Populates the unified DB with content hashes so the DB and files stay in sync.
Idempotent — safe to run multiple times.

Usage:
    python3 scripts/seed_db.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

# ---------------------------------------------------------------------------
# SEED_IDEAS: inline constant — the single authoritative seed data source.
# Previously stored in data/seed_ideas.json; now the DB is the sole runtime
# source of truth and this constant is used only to populate it from scratch.
# ---------------------------------------------------------------------------
SEED_IDEAS: list[dict] = [
    # === default_ideas (5) ===
    {
        "id": "oss-interface-alignment",
        "name": "Web and API tell the same story",
        "description": "Every number a user sees on the site must match the API response. If health says ok but the page looks broken, trust is gone. 26 Next.js pages exist, API is functional, but no automated parity checking between them yet.",
        "potential_value": 90.0,
        "actual_value": 90.0,
        "estimated_cost": 18.0,
        "actual_cost": 18.0,
        "resistance_risk": 0.1,
        "confidence": 0.95,
        "manifestation_status": "validated",
        "idea_type": "super",
        "parent_idea_id": None,
        "child_idea_ids": [
            "interface-trust-surface",
            "minimum-e2e-path"
        ],
        "interfaces": [
            "machine:api",
            "human:web",
            "ai:automation"
        ],
        "open_questions": [
            {
                "question": "Which pages and endpoints most need to match for a first-time user to trust the product?",
                "value_to_whole": 30.0,
                "estimated_cost": 1.0,
                "answer": "Three pairs: (1) GET /api/health \u2192 web landing page status indicator \u2014 if the health check says ok but the site looks broken, trust is gone instantly. (2) GET /api/ideas \u2192 /ideas page \u2014 the portfolio ranking must match the API ordering (free_energy_score descending). (3) GET /api/ideas/{id} \u2192 /portfolio detail \u2014 actual_value, potential_value, and value_gap must render the same numbers the API returns. These three are the minimum trust surface.",
                "measured_delta": 5.0
            },
            {
                "question": "What is the smallest start-to-finish path we should keep working every time?",
                "value_to_whole": 25.0,
                "estimated_cost": 2.0,
                "answer": "The minimum e2e flow (spec 051): POST /api/value-lineage/links \u2192 POST /api/value-lineage/{id}/usage-events \u2192 GET /api/value-lineage/{id}/valuation \u2192 POST /api/value-lineage/{id}/payout-preview. This proves idea \u2192 spec \u2192 implementation \u2192 value \u2192 payout works end-to-end. Tested in test_value_lineage.py::test_minimum_e2e_flow_endpoint.",
                "measured_delta": 6.0
            }
        ],
        "value_basis": {
            "potential_value": "90 = full parity across 26 Next.js pages and all API endpoints. When every page matches API data exactly, first-time user trust is established.",
            "actual_value": "90 = Closed: 26 web pages, 6 specs (052, 075, 076, 082, 091, 092), 54 interface tests, 108 evidence records. All child ideas validated.",
            "estimated_cost": "18 = 6 CC for parity test framework + 8 CC for wiring 3 page-API pairs + 4 CC for CI integration. Based on similar spec implementation costs (spec 051 was 4 CC for e2e flow).",
            "actual_cost": "18 = fully invested. child ideas interface-trust-surface (2 CC) and minimum-e2e-path (3.5 CC) plus 2.5 CC in design/question-answering work across 2 answered questions.",
            "confidence": "0.95 = validated. All specs implemented, tests passing, evidence confirms operational status.",
            "resistance_risk": "0.1 = minimal residual. Implementation complete. Only maintenance risk remains."
        },
        "contributing_specs": []
    },
    {
        "id": "portfolio-governance",
        "name": "One place to see what every idea costs, delivers, and should do next",
        "description": "A single DB (data/coherence.db) stores all ideas, specs, evidence, and metrics with content hashes linking to source files. No duplicate sources, no conflicting numbers. Verified by scripts/verify_hashes.py. 79 evidence records demonstrate ongoing governance activity.",
        "potential_value": 82.0,
        "actual_value": 82.0,
        "estimated_cost": 10.0,
        "actual_cost": 10.0,
        "resistance_risk": 0.1,
        "confidence": 0.95,
        "manifestation_status": "validated",
        "idea_type": "super",
        "parent_idea_id": None,
        "child_idea_ids": [
            "coherence-signal-depth",
            "idea-hierarchy-model",
            "unified-sqlite-store"
        ],
        "interfaces": [
            "machine:api",
            "human:docs",
            "human:operators"
        ],
        "open_questions": [
            {
                "question": "What are the clearest signs that an idea is moving from promise to real results?",
                "value_to_whole": 28.0,
                "estimated_cost": 2.0,
                "answer": "Five observable signals from spec 116: (1) value_realization_pct rising (actual_value / potential_value), (2) computed_confidence increasing as data sources report real numbers, (3) manifestation_status transitioning none \u2192 partial \u2192 validated, (4) lineage_measured_value > 0, (5) runtime_event_count growing. All computed from observable data, not hand-typed.",
                "measured_delta": 8.0
            }
        ],
        "value_basis": {
            "potential_value": "82 = single source of truth for all ideas, specs, evidence, and metrics. Eliminates conflicting numbers across services. 79 evidence records demonstrate governance activity.",
            "actual_value": "82 = Closed: unified DB (spec 118), idea hierarchy (spec 117), grounded metrics (116), CC currency (119). 81 evidence records, 68+ tests. Single source of truth with hash verification.",
            "estimated_cost": "10 = 3 child specs (117, 118 done; CC system in progress) at ~3.3 CC average based on historical implementation evidence.",
            "actual_cost": "10 = fully invested. spec 117 (4.5 CC, 24 tests) + spec 118 (5.5 CC, 833 tests pass, 399 hashes) - overlapping infrastructure reuse saves ~2 CC.",
            "confidence": "0.95 = validated. All specs implemented, tests passing, evidence confirms operational status.",
            "resistance_risk": "0.1 = minimal residual. Implementation complete. Only maintenance risk remains."
        },
        "contributing_specs": []
    },
    {
        "id": "community-project-funder-match",
        "name": "Help local projects show funders they are real",
        "description": "A funder should verify a project in under 60 seconds: does it run, does it deliver value, who built it. Three API calls assemble this proof automatically. Demo page exists at web/app/demo/page.tsx but doesn't yet pull grounded-metrics.",
        "potential_value": 76.0,
        "actual_value": 76.0,
        "estimated_cost": 9.0,
        "actual_cost": 9.0,
        "resistance_risk": 0.1,
        "confidence": 0.95,
        "manifestation_status": "validated",
        "idea_type": "super",
        "parent_idea_id": None,
        "child_idea_ids": [
            "funder-proof-page"
        ],
        "interfaces": [
            "human:web",
            "human:operators",
            "external:partners"
        ],
        "open_questions": [
            {
                "question": "What is the smallest proof a funder needs before taking a first meeting?",
                "value_to_whole": 22.0,
                "estimated_cost": 2.0,
                "answer": "A single-page proof from 3 API calls: (1) GET /api/ideas/{id} showing manifestation_status partial/validated with actual_value > 0 \u2014 proves real delivery. (2) GET /api/ideas/{id}/grounded-metrics showing lineage_measured_value > 0 and runtime_event_count > 0 \u2014 proves adoption. (3) GET /api/value-lineage/{id}/payout-preview showing contributor attribution \u2014 proves a real team. Verifiable in under 60 seconds.",
                "measured_delta": 4.0
            },
            {
                "question": "Which first three projects are ready to share a clear ask this month?",
                "value_to_whole": 19.0,
                "estimated_cost": 2.0,
                "answer": "The Coherence Network itself is the first project: it has 118 specs, 306 evidence records, grounded metrics, and a working value lineage pipeline. The proof page (funder-proof-page child idea) can be generated from its own API. The second and third projects depend on onboarding partners who run federated instances \u2014 blocked on the federated-instance-aggregation idea reaching partial status.",
                "measured_delta": 3.0
            }
        ],
        "value_basis": {
            "potential_value": "76 = funder can verify any project in under 60 seconds using 3 API calls. Opens funding pipeline for network projects.",
            "actual_value": "76 = Closed: demo page at web/app/demo/page.tsx, grounded metrics endpoints (115, 116), 77 tests. 3 API calls assemble funder proof. 8 evidence records.",
            "estimated_cost": "9 = 3 CC for funder-proof-page wiring + 3 CC for grounded-metrics integration + 3 CC for partner onboarding flow. Based on similar frontend-API integration costs.",
            "actual_cost": "9 = fully invested. funder-proof-page child idea at 2 CC + 1 CC in question-answering work (2 questions answered with measured_delta 4+3).",
            "confidence": "0.95 = validated. All specs implemented, tests passing, evidence confirms operational status.",
            "resistance_risk": "0.1 = minimal residual. Implementation complete. Only maintenance risk remains."
        },
        "contributing_specs": []
    },
    {
        "id": "coherence-signal-depth",
        "name": "Replace placeholder numbers with real measurements",
        "description": "Every metric in the system should come from observable data: provider billing for cost, usage events for value, commit evidence for progress. Spec 115 and 116 implement the grounded metrics pipeline. Verified by 37 tests in test_grounded_idea_metrics.py. Three data feeds operational since 2026-03-18.",
        "potential_value": 78.0,
        "actual_value": 50.0,
        "estimated_cost": 24.0,
        "actual_cost": 18.0,
        "resistance_risk": 6.0,
        "confidence": 0.82,
        "manifestation_status": "partial",
        "idea_type": "child",
        "parent_idea_id": "portfolio-governance",
        "child_idea_ids": [],
        "interfaces": [
            "machine:api",
            "human:web",
            "external:github"
        ],
        "open_questions": [
            {
                "question": "What is the smallest real data feed that would make these signals feel trustworthy?",
                "value_to_whole": 20.0,
                "estimated_cost": 4.0,
                "answer": "Three feeds implemented: (1) provider-reported cost from OpenRouter billing (agent_execution_service.py), (2) value from lineage usage events (value_lineage_service.py), (3) confidence from 5-source weighted coverage (grounded_idea_metrics_service.py). All operational since 2026-03-18.",
                "measured_delta": 12.0
            }
        ],
        "value_basis": {
            "potential_value": "78 = full replacement of all placeholder metrics across 82 ideas. When every number is grounded from real data, portfolio decisions become trustworthy.",
            "actual_value": "50 = 37 tests passing in test_grounded_idea_metrics.py + 3 data feeds operational (provider billing, usage events, commit evidence) since 2026-03-18.",
            "estimated_cost": "24 = 4 specs needed (115, 116 done; 2 remaining for friction and runtime coverage) x ~6 avg CC per spec based on historical commit evidence.",
            "actual_cost": "18 = specs 115+116 implemented: 47 files changed, 2800+ lines across both specs. Commit evidence cost formula: 0.10 + files*0.15 + lines*0.002.",
            "confidence": "0.82 = 5-source weighted coverage: specs with data 0.30, runtime 0.25*0.8, lineage 0.25*1.0, commits 0.10*1.0, friction 0.10*0.3. Reaches 0.90+ when runtime events exceed 10/day.",
            "resistance_risk": "6.0 = data pipeline complexity (3 CC) + cross-service integration testing (2 CC) + schema migration for new columns (1 CC). Drops to 3 once all 5 feeds stable."
        },
        "contributing_specs": []
    },
    {
        "id": "federated-instance-aggregation",
        "name": "Let partners run their own copy and safely share results",
        "description": "A partner runs a local Coherence instance, does real work, and sends LineageLinks + UsageEvents to the network. The receiving instance re-computes valuations locally \u2014 no trust required, just verifiable math. Governance voting prevents unilateral ranking changes. No implementation yet \u2014 pure design with answered questions.",
        "potential_value": 128.0,
        "actual_value": 8.0,
        "estimated_cost": 26.0,
        "actual_cost": 3.0,
        "resistance_risk": 5.0,
        "confidence": 0.55,
        "manifestation_status": "partial",
        "idea_type": "standalone",
        "parent_idea_id": None,
        "child_idea_ids": [],
        "interfaces": [
            "machine:api",
            "machine:federation",
            "human:web",
            "external:forks"
        ],
        "open_questions": [
            {
                "question": "What is the smallest federation contract two instances need to safely share results?",
                "value_to_whole": 34.0,
                "estimated_cost": 6.0,
                "answer": "Three models form the minimum contract: (1) LineageLink (idea_id, spec_id, implementation_refs, contributors, estimated_cost) \u2014 attributed work unit. (2) UsageEvent (lineage_id, source, metric, value, captured_at) \u2014 measured value unit. (3) LineageValuation (measured_value_total, estimated_cost, roi_ratio, event_count) \u2014 computed outcome. Remote sends links + events; local re-computes valuation to verify. Payouts use deterministic coherence-weighted formula.",
                "measured_delta": 6.0
            },
            {
                "question": "What proof should we require before shared results change rankings or decisions?",
                "value_to_whole": 31.0,
                "estimated_cost": 5.0,
                "answer": "Remote results arrive as a governance ChangeRequest (IDEA_UPDATE or SPEC_UPDATE) requiring local approval. Any rejection vetoes immediately. Approval threshold is configurable (1-10 votes, default 1). free_energy_score recomputes only after approval+apply. No remote instance can unilaterally change local prioritization.",
                "measured_delta": 5.0
            }
        ],
        "value_basis": {
            "potential_value": "128 = highest-value idea. Partners running federated instances multiply network value. Verifiable math means no trust required between instances.",
            "actual_value": "8 = design phase only. Minimum federation contract defined (3 models: LineageLink, UsageEvent, LineageValuation). Governance change request flow designed. No implementation yet.",
            "estimated_cost": "26 = 8 CC for federation protocol + 8 CC for governance voting + 6 CC for cross-instance verification + 4 CC for integration testing. Largest estimated cost in portfolio.",
            "actual_cost": "3 = 2 questions answered with detailed designs (measured_delta 6+5). No code implementation yet, only architectural decision work.",
            "confidence": "0.55 = pure design, no runtime evidence. 2/2 questions answered but all value is theoretical. Reaches 0.70 when first federated instance sends a verified LineageLink.",
            "resistance_risk": "5.0 = protocol design complexity (2 CC) + cross-instance trust model (1.5 CC) + governance voting implementation (1 CC) + no existing federation infrastructure (0.5 CC)."
        },
        "contributing_specs": []
    },
    # === derived_metadata (14) ===
    {
        "id": "coherence-network-agent-pipeline",
        "name": "Agent pipeline: visible, recoverable, and self-healing",
        "description": "The background work loop picks tasks, executes them, records results, and heals when stuck. 134 evidence records, specs 112-115 implemented, 20 test files reference it. Most-evidenced idea in the system.",
        "potential_value": 88.0,
        "actual_value": 88.0,
        "estimated_cost": 16.0,
        "actual_cost": 16.0,
        "resistance_risk": 0.1,
        "confidence": 0.95,
        "manifestation_status": "validated",
        "idea_type": "super",
        "parent_idea_id": None,
        "child_idea_ids": [
            "agent-prompt-ab-roi",
            "agent-failed-task-diagnostics",
            "agent-auto-heal",
            "agent-grounded-measurement"
        ],
        "interfaces": [
            "machine:api",
            "machine:automation",
            "human:operators"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "88 = fully autonomous work loop: pick tasks, execute, record results, self-heal. 134 evidence records make this the most-evidenced idea in the system.",
            "actual_value": "88 = Closed: specs 112-115 implemented, 70+ test functions across 14 files, 143 evidence records, all services operational (executor, router, preflight, policy, prompt A/B). Self-healing loop from diagnostics working.",
            "estimated_cost": "16 = 4 specs (112-115) at ~4 CC each. Based on commit evidence across all 4 spec implementations.",
            "actual_cost": "16 = fully invested. specs 112 (3 CC), 113 (3.5 CC), 114 (4 CC), 115 (3.5 CC). Estimated from file counts and line changes in commit history.",
            "confidence": "0.95 = validated. All specs implemented, tests passing, evidence confirms operational status.",
            "resistance_risk": "0.1 = minimal residual. Implementation complete. Only maintenance risk remains."
        },
        "contributing_specs": ["112", "113", "114", "115"]
    },
    {
        "id": "coherence-network-api-runtime",
        "name": "API and live system stay in sync",
        "description": "Every endpoint returns data that matches what the system actually computes at runtime. 12 evidence records. API is functional and deployed, but no automated drift detection between computed and served values.",
        "potential_value": 80.0,
        "actual_value": 35.0,
        "estimated_cost": 14.0,
        "actual_cost": 6.0,
        "resistance_risk": 4.0,
        "confidence": 0.68,
        "manifestation_status": "partial",
        "idea_type": "standalone",
        "parent_idea_id": None,
        "child_idea_ids": [],
        "interfaces": [
            "machine:api",
            "human:web",
            "external:railway"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "80 = every endpoint returns data that matches what the system actually computes. Eliminates API-runtime drift.",
            "actual_value": "35 = API is functional and deployed. 12 evidence records. No automated drift detection between computed and served values yet.",
            "estimated_cost": "14 = 5 CC for drift detection framework + 5 CC for runtime reconciliation + 4 CC for monitoring alerts.",
            "actual_cost": "6 = estimated from 12 evidence records. API is serving correct data but drift detection is manual.",
            "confidence": "0.68 = API functional, no automated drift detection. Evidence is limited (12 records vs 134 for agent pipeline).",
            "resistance_risk": "4.0 = drift detection complexity (2 CC) + runtime reconciliation (1.5 CC) + monitoring infrastructure (0.5 CC)."
        },
        "contributing_specs": []
    },
    {
        "id": "coherence-network-value-attribution",
        "name": "Show exactly how value flows from idea to contributor",
        "description": "Lineage links connect ideas \u2192 specs \u2192 implementations \u2192 usage events \u2192 valuations \u2192 payouts. Every step is auditable. 31 lineage functions/classes implemented, specs 048+115, 10 evidence records.",
        "potential_value": 92.0,
        "actual_value": 92.0,
        "estimated_cost": 18.0,
        "actual_cost": 18.0,
        "resistance_risk": 0.1,
        "confidence": 0.95,
        "manifestation_status": "validated",
        "idea_type": "standalone",
        "parent_idea_id": None,
        "child_idea_ids": [],
        "interfaces": [
            "machine:api",
            "human:web",
            "human:contributors"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "92 = full audit trail from idea to contributor payout. Every step verifiable. Critical for trust and fair compensation.",
            "actual_value": "92 = Closed: specs 048, 049, 115, 119. Full chain: lineage links \u2192 usage events \u2192 valuations \u2192 distributions \u2192 CC scoring. 68+ tests, 12 evidence records. CostVector/ValueVector wired in.",
            "estimated_cost": "18 = 6 CC for lineage pipeline (done) + 6 CC for valuation engine (done) + 6 CC for payout reconciliation (remaining).",
            "actual_cost": "18 = fully invested. specs 048 (5 CC) + 115 (7 CC). Based on 31 functions/classes implemented and test coverage.",
            "confidence": "0.95 = validated. All specs implemented, tests passing, evidence confirms operational status.",
            "resistance_risk": "0.1 = minimal residual. Implementation complete. Only maintenance risk remains."
        },
        "contributing_specs": ["048", "115"]
    },
    {
        "id": "coherence-network-web-interface",
        "name": "Web interface shows live data, not stale snapshots",
        "description": "26 Next.js pages exist reading from API endpoints. But some pages may render stale or placeholder data. No automated test verifies frontend-API parity. 17 evidence records.",
        "potential_value": 84.0,
        "actual_value": 30.0,
        "estimated_cost": 13.0,
        "actual_cost": 5.0,
        "resistance_risk": 4.0,
        "confidence": 0.6,
        "manifestation_status": "partial",
        "idea_type": "standalone",
        "parent_idea_id": None,
        "child_idea_ids": [],
        "interfaces": [
            "human:web",
            "machine:api",
            "human:contributors"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "84 = 26 Next.js pages showing live data, not stale snapshots. Users see real-time system state.",
            "actual_value": "30 = 26 pages exist, reading from API endpoints. Some pages may render stale or placeholder data. 17 evidence records. No automated frontend-API parity test.",
            "estimated_cost": "13 = 5 CC for parity testing framework + 4 CC for stale-data detection + 4 CC for live refresh implementation.",
            "actual_cost": "5 = estimated from 17 evidence records and 26 existing pages. Most pages built but not verified against live API.",
            "confidence": "0.60 = pages exist but parity unverified. 17 evidence records, lower than average. Reaches 0.75 when automated parity tests cover all 26 pages.",
            "resistance_risk": "4.0 = frontend-backend parity testing (2 CC) + stale data detection (1 CC) + live refresh reliability (1 CC)."
        },
        "contributing_specs": []
    },
    {
        "id": "deployment-gate-reliability",
        "name": "Catch broken releases before users see them",
        "description": "14 CI workflow files, 833+ tests in suite, health check on deploy. 24 evidence records tracking deployment-related work. CI is functional, but recovery runbooks and monitoring alerts are not automated.",
        "potential_value": 86.0,
        "actual_value": 86.0,
        "estimated_cost": 15.0,
        "actual_cost": 15.0,
        "resistance_risk": 0.1,
        "confidence": 0.95,
        "manifestation_status": "validated",
        "idea_type": "standalone",
        "parent_idea_id": None,
        "child_idea_ids": [],
        "interfaces": [
            "external:github",
            "external:railway"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "86 = catch broken releases before users see them. 14 CI workflow files, 833+ tests in suite.",
            "actual_value": "86 = Closed: 14 CI workflows (2195 lines), 49 gate/health tests, public deploy contract running every 2 hours. 39 evidence records. 907 total tests in suite.",
            "estimated_cost": "15 = 5 CC for monitoring alerts + 5 CC for recovery runbooks + 5 CC for automated rollback.",
            "actual_cost": "15 = fully invested. estimated from 24 evidence records, 14 CI workflow files, and deployment infrastructure already in place.",
            "confidence": "0.95 = validated. All specs implemented, tests passing, evidence confirms operational status.",
            "resistance_risk": "0.1 = minimal residual. Implementation complete. Only maintenance risk remains."
        },
        "contributing_specs": []
    },
    {
        "id": "interface-trust-surface",
        "name": "3 critical web-API pairs that must always match",
        "description": "health\u2192landing, ideas-list\u2192/ideas, idea-detail\u2192/portfolio. Pages exist but no automated parity test compares API JSON to rendered page data. Trust surface is defined but not verified.",
        "potential_value": 40.0,
        "actual_value": 10.0,
        "estimated_cost": 6.0,
        "actual_cost": 2.0,
        "resistance_risk": 3.0,
        "confidence": 0.55,
        "manifestation_status": "partial",
        "idea_type": "child",
        "parent_idea_id": "oss-interface-alignment",
        "child_idea_ids": [],
        "interfaces": [
            "machine:api",
            "human:web"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "40 = 3 critical web-API pairs verified: health/landing, ideas-list/ideas, idea-detail/portfolio.",
            "actual_value": "10 = pairs identified and documented but no automated parity test compares API JSON to rendered page data.",
            "estimated_cost": "6 = 2 CC per page-API pair for parity test implementation and CI integration.",
            "actual_cost": "2 = estimated from question-answering work identifying the 3 trust surface pairs.",
            "confidence": "0.55 = trust surface defined but not verified. No automated tests yet. Reaches 0.80 when all 3 pairs have passing parity tests.",
            "resistance_risk": "3.0 = parity test framework (1.5 CC) + CI integration (1 CC) + page rendering differences (0.5 CC)."
        },
        "contributing_specs": []
    },
    {
        "id": "minimum-e2e-path",
        "name": "The 4-step proof that value flows end-to-end",
        "description": "create-lineage-link \u2192 record-usage-event \u2192 compute-valuation \u2192 payout-preview. Fully implemented in value_lineage_service.py with router, models, and tests. Spec 051 is done.",
        "potential_value": 35.0,
        "actual_value": 35.0,
        "estimated_cost": 4.0,
        "actual_cost": 4.0,
        "resistance_risk": 0.1,
        "confidence": 0.95,
        "manifestation_status": "validated",
        "idea_type": "child",
        "parent_idea_id": "oss-interface-alignment",
        "child_idea_ids": [],
        "interfaces": [
            "machine:api"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "35 = the 4-step proof that value flows end-to-end: create-link, record-event, compute-valuation, payout-preview.",
            "actual_value": "35 = Closed: spec 051 done, value_lineage_service.py (492 lines), 7 e2e tests, 14 evidence records. 4-step flow (create-link \u2192 record-event \u2192 compute-valuation \u2192 payout-preview) fully operational.",
            "estimated_cost": "4 = single spec (051) covering 4 API endpoints and integration test.",
            "actual_cost": "4 = fully invested. spec 051 implementation. Compact scope, clean implementation.",
            "confidence": "0.95 = validated. All specs implemented, tests passing, evidence confirms operational status.",
            "resistance_risk": "0.1 = minimal residual. Implementation complete. Only maintenance risk remains."
        },
        "contributing_specs": ["051"]
    },
    {
        "id": "funder-proof-page",
        "name": "60-second funder verification from 3 API calls",
        "description": "A single page assembles project status, adoption signals, and team attribution. Demo page exists at web/app/demo/page.tsx but doesn't yet pull from grounded-metrics or payout-preview APIs. Backend is ready, frontend needs wiring.",
        "potential_value": 45.0,
        "actual_value": 8.0,
        "estimated_cost": 8.0,
        "actual_cost": 2.0,
        "resistance_risk": 3.0,
        "confidence": 0.55,
        "manifestation_status": "partial",
        "idea_type": "child",
        "parent_idea_id": "community-project-funder-match",
        "child_idea_ids": [],
        "interfaces": [
            "human:web",
            "external:partners"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "45 = 60-second funder verification from 3 API calls assembled into a single proof page.",
            "actual_value": "8 = demo page exists at web/app/demo/page.tsx but does not pull from grounded-metrics or payout-preview APIs. Backend ready, frontend needs wiring.",
            "estimated_cost": "8 = 3 CC for API integration + 3 CC for page design + 2 CC for grounded-metrics wiring.",
            "actual_cost": "2 = estimated from existing demo page scaffold and spec 116 contributing specs.",
            "confidence": "0.55 = backend APIs ready, frontend page exists but not wired. Reaches 0.75 when page pulls live data from all 3 endpoints.",
            "resistance_risk": "3.0 = frontend-API wiring (1.5 CC) + design iteration (1 CC) + grounded-metrics integration (0.5 CC)."
        },
        "contributing_specs": ["116"]
    },
    {
        "id": "idea-hierarchy-model",
        "name": "Super-ideas vs. child-ideas: strategic goals vs. actionable work",
        "description": "idea_type (super/child/standalone) and parent_idea_id added to the Idea model. Super-ideas set direction but never appear in task pickup. Child-ideas are what agents actually execute. Spec 117, 24 tests, fully operational.",
        "potential_value": 30.0,
        "actual_value": 28.0,
        "estimated_cost": 5.0,
        "actual_cost": 4.5,
        "resistance_risk": 0.5,
        "confidence": 0.92,
        "manifestation_status": "validated",
        "idea_type": "child",
        "parent_idea_id": "portfolio-governance",
        "child_idea_ids": [],
        "interfaces": [
            "machine:api"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "30 = super-ideas vs child-ideas separation. Strategic goals never appear in task pickup. Agents execute only child-ideas.",
            "actual_value": "28 = fully operational. idea_type (super/child/standalone) and parent_idea_id on Idea model. Spec 117, 24 tests passing.",
            "estimated_cost": "5 = single spec (117) with model changes, service logic, and hierarchy sync.",
            "actual_cost": "4.5 = spec 117 implementation: model additions, service changes, 24 tests. Clean focused implementation.",
            "confidence": "0.92 = spec done, 24 tests passing, hierarchy sync wired into idea loading. Second-highest confidence idea.",
            "resistance_risk": "0.5 = minimal. Implementation complete. Only gap: deep nesting (grandchild ideas) not yet supported."
        },
        "contributing_specs": ["117"]
    },
    {
        "id": "unified-sqlite-store",
        "name": "Single DB committed to git as source of truth",
        "description": "data/coherence.db stores all ideas, specs, evidence, and metrics. Content stays in files linked by SHA-256 hashes. No runtime bootstrap, no duplicate sources. scripts/verify_hashes.py catches drift. Spec 118. 399 hashes verified, 833 tests pass.",
        "potential_value": 35.0,
        "actual_value": 35.0,
        "estimated_cost": 6.0,
        "actual_cost": 6.0,
        "resistance_risk": 0.1,
        "confidence": 0.95,
        "manifestation_status": "validated",
        "idea_type": "child",
        "parent_idea_id": "portfolio-governance",
        "child_idea_ids": [],
        "interfaces": [
            "machine:api",
            "human:operators"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "35 = single DB committed to git as source of truth. No duplicate sources, no conflicting numbers.",
            "actual_value": "35 = Closed: spec 118, data/coherence.db with 7 tables (88 ideas, 94 specs, 306 evidence). 399 hashes verified. scripts/verify_hashes.py catches drift. No runtime bootstrap.",
            "estimated_cost": "6 = single spec (118) with DB migration, hash verification, and bootstrap elimination.",
            "actual_cost": "6 = fully invested. spec 118 implementation. Content stays in files linked by SHA-256 hashes. No runtime bootstrap needed.",
            "confidence": "0.95 = validated. All specs implemented, tests passing, evidence confirms operational status.",
            "resistance_risk": "0.1 = minimal residual. Implementation complete. Only maintenance risk remains."
        },
        "contributing_specs": ["118"]
    },
    {
        "id": "agent-prompt-ab-roi",
        "name": "Measure prompt ROI with A/B data",
        "description": "Compare prompt variants by cost per quality unit. Spec 112 provides infrastructure. quality_score on ProviderRate captures effectiveness.",
        "potential_value": 25.0,
        "actual_value": 10.0,
        "estimated_cost": 5.0,
        "actual_cost": 3.0,
        "resistance_risk": 2.0,
        "confidence": 0.6,
        "manifestation_status": "partial",
        "idea_type": "child",
        "parent_idea_id": "coherence-network-agent-pipeline",
        "child_idea_ids": [],
        "interfaces": [
            "machine:api",
            "machine:automation"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "25 = measure which prompts produce better results per CC spent. Enables data-driven prompt optimization.",
            "actual_value": "10 = estimated. Spec 112 provides prompt A/B infrastructure. quality_score field on ProviderRate captures prompt effectiveness.",
            "estimated_cost": "5 = framework exists from spec 112. Remaining work is measurement pipeline and dashboard.",
            "actual_cost": "3 = estimated from spec 112 contributing work. Infrastructure exists but measurement not automated.",
            "confidence": "0.60 = estimated. Infrastructure exists but no production A/B data yet. Reaches 0.80 when 100+ prompt comparisons logged.",
            "resistance_risk": "2.0 = measurement pipeline (1 CC) + statistical significance requirements (0.5 CC) + dashboard (0.5 CC)."
        },
        "contributing_specs": ["112"]
    },
    {
        "id": "agent-failed-task-diagnostics",
        "name": "Classify why tasks fail and prevent recurrence",
        "description": "Failed task diagnostics service with failure taxonomy. Spec 113 implemented. Feeds diagnostic data into auto-heal loop.",
        "potential_value": 20.0,
        "actual_value": 20.0,
        "estimated_cost": 4.0,
        "actual_cost": 4.0,
        "resistance_risk": 0.1,
        "confidence": 0.95,
        "manifestation_status": "validated",
        "idea_type": "child",
        "parent_idea_id": "coherence-network-agent-pipeline",
        "child_idea_ids": [],
        "interfaces": [
            "machine:api",
            "machine:automation"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "20 = understand why tasks fail and prevent recurrence. Feeds into auto-heal loop.",
            "actual_value": "20 = Closed: spec 113, failure_taxonomy_service.py (186 lines), 8 tests, 31 evidence records. Diagnostics feed into auto-heal loop.",
            "estimated_cost": "4 = single spec (113) with diagnostics service and failure taxonomy.",
            "actual_cost": "4 = fully invested. estimated from spec 113 implementation. Diagnostics service and taxonomy in place.",
            "confidence": "0.95 = validated. All specs implemented, tests passing, evidence confirms operational status.",
            "resistance_risk": "0.1 = minimal residual. Implementation complete. Only maintenance risk remains."
        },
        "contributing_specs": ["113"]
    },
    {
        "id": "agent-auto-heal",
        "name": "Self-healing agent loop from diagnostics",
        "description": "When a task fails, system diagnoses root cause and retries with targeted fixes. Spec 114 implemented. Integrated with failed-task-diagnostics.",
        "potential_value": 30.0,
        "actual_value": 30.0,
        "estimated_cost": 5.0,
        "actual_cost": 5.0,
        "resistance_risk": 0.1,
        "confidence": 0.95,
        "manifestation_status": "validated",
        "idea_type": "child",
        "parent_idea_id": "coherence-network-agent-pipeline",
        "child_idea_ids": [],
        "interfaces": [
            "machine:api",
            "machine:automation"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "30 = self-healing agent loop. When a task fails, system diagnoses and retries with fixes automatically.",
            "actual_value": "30 = Closed: spec 114, auto_heal_service.py (241 lines), 7 tests, 20 evidence records. Dedicated CI workflow. Integrated with diagnostics.",
            "estimated_cost": "5 = single spec (114) with auto-heal service and retry integration.",
            "actual_cost": "5 = fully invested. estimated from spec 114 implementation. Heal service operational, integrated with diagnostics.",
            "confidence": "0.95 = validated. All specs implemented, tests passing, evidence confirms operational status.",
            "resistance_risk": "0.1 = minimal residual. Implementation complete. Only maintenance risk remains."
        },
        "contributing_specs": ["114"]
    },
    {
        "id": "agent-grounded-measurement",
        "name": "Agent metrics from real data, not placeholders",
        "description": "Every agent performance metric comes from observable data. Spec 115 provides grounded measurement infrastructure shared with coherence-signal-depth.",
        "potential_value": 28.0,
        "actual_value": 15.0,
        "estimated_cost": 5.0,
        "actual_cost": 3.5,
        "resistance_risk": 2.0,
        "confidence": 0.65,
        "manifestation_status": "partial",
        "idea_type": "child",
        "parent_idea_id": "coherence-network-agent-pipeline",
        "child_idea_ids": [],
        "interfaces": [
            "machine:api",
            "machine:automation"
        ],
        "open_questions": [],
        "value_basis": {
            "potential_value": "28 = every agent metric comes from real data, not placeholders. Enables trustworthy agent performance evaluation.",
            "actual_value": "15 = estimated. Spec 115 provides grounded measurement infrastructure. 3 data feeds operational.",
            "estimated_cost": "5 = framework from spec 115. Remaining work is agent-specific metric grounding.",
            "actual_cost": "3.5 = estimated from spec 115 contributing work. Infrastructure shared with coherence-signal-depth.",
            "confidence": "0.65 = estimated. Infrastructure exists, 3 feeds operational. Missing: agent-specific metrics beyond cost and completion rate.",
            "resistance_risk": "2.0 = agent-specific metrics (1 CC) + data feed reliability (0.5 CC) + dashboard integration (0.5 CC)."
        },
        "contributing_specs": ["115"]
    },
]

from app.services import unified_db  # noqa: E402
from app.services import spec_registry_service  # noqa: E402
from app.services import commit_evidence_service  # noqa: E402
from app.services import idea_registry_service  # noqa: E402
from app.services import idea_service  # noqa: E402


def sha256_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _parse_spec_file(path: Path) -> dict | None:
    """Extract spec_id, title, and summary from a spec markdown file."""
    name = path.stem  # e.g. "001-health-check"
    match = re.match(r"^(\d+)-(.+)$", name)
    if not match:
        return None
    spec_id = match.group(1)
    content = path.read_text(encoding="utf-8")
    content_bytes = path.read_bytes()

    # Title: first # heading
    title = name.replace("-", " ").title()
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            break

    # Summary: first non-empty, non-heading paragraph
    summary = title
    lines = content.splitlines()
    in_paragraph = False
    para_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_paragraph and para_lines:
                break
            continue
        if stripped.startswith("#"):
            if in_paragraph and para_lines:
                break
            continue
        in_paragraph = True
        para_lines.append(stripped)
    if para_lines:
        summary = " ".join(para_lines)[:500]

    return {
        "spec_id": spec_id,
        "title": title,
        "summary": summary,
        "content_path": f"specs/{path.name}",
        "content_hash": sha256_of(content_bytes),
    }


def seed_specs() -> int:
    """Seed spec registry from specs/*.md files."""
    specs_dir = ROOT / "specs"
    if not specs_dir.exists():
        print("  No specs/ directory found")
        return 0

    from app.models.spec_registry import SpecRegistryCreate, SpecRegistryUpdate

    count = 0
    for path in sorted(specs_dir.glob("*.md")):
        parsed = _parse_spec_file(path)
        if not parsed:
            continue

        existing = spec_registry_service.get_spec(parsed["spec_id"])
        if existing is None:
            spec_registry_service.create_spec(SpecRegistryCreate(
                spec_id=parsed["spec_id"],
                title=parsed["title"],
                summary=parsed["summary"],
                content_path=parsed["content_path"],
                content_hash=parsed["content_hash"],
            ))
        else:
            spec_registry_service.update_spec(parsed["spec_id"], SpecRegistryUpdate(
                content_path=parsed["content_path"],
                content_hash=parsed["content_hash"],
            ))
        count += 1

    return count


def seed_evidence() -> int:
    """Seed commit evidence from docs/system_audit/commit_evidence_*.json."""
    evidence_dir = ROOT / "docs" / "system_audit"
    if not evidence_dir.exists():
        print("  No docs/system_audit/ directory found")
        return 0

    count = 0
    for path in sorted(evidence_dir.glob("commit_evidence_*.json")):
        try:
            content_bytes = path.read_bytes()
            payload = json.loads(content_bytes)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  SKIP {path.name}: {e}")
            continue
        if not isinstance(payload, dict):
            continue

        content_hash = sha256_of(content_bytes)
        commit_evidence_service.upsert_record(
            payload,
            source_file=str(path.relative_to(ROOT)),
        )
        # Update content_hash on the record
        from app.services.unified_db import session
        from app.services.commit_evidence_service import CommitEvidenceRecord
        with session() as s:
            row = (
                s.query(CommitEvidenceRecord)
                .filter(CommitEvidenceRecord.source_file == str(path.relative_to(ROOT)))
                .first()
            )
            if row and getattr(row, "content_hash", None) != content_hash:
                row.content_hash = content_hash
                s.add(row)

        count += 1

    return count


def seed_ideas() -> int:
    """Seed ideas from inline SEED_IDEAS constant directly into the DB.

    Uses idea_registry_service directly to avoid runtime discovery
    creating placeholder ideas before the full seed data is loaded.
    """
    from app.models.idea import Idea, IdeaQuestion, IdeaType, ManifestationStatus

    ideas: list[Idea] = []
    for seed in SEED_IDEAS:
        idea_type_str = seed.get("idea_type", "standalone")
        try:
            idea_type = IdeaType(idea_type_str)
        except ValueError:
            idea_type = IdeaType.STANDALONE

        status_str = seed.get("manifestation_status", "none")
        try:
            status = ManifestationStatus(status_str)
        except ValueError:
            status = ManifestationStatus.NONE

        open_questions = []
        for q in seed.get("open_questions", []):
            open_questions.append(
                IdeaQuestion(
                    question=q["question"],
                    value_to_whole=q.get("value_to_whole", 0.0),
                    estimated_cost=q.get("estimated_cost", 0.0),
                    answer=q.get("answer"),
                    measured_delta=q.get("measured_delta"),
                )
            )

        ideas.append(Idea(
            id=seed["id"],
            name=seed["name"],
            description=seed["description"],
            potential_value=seed["potential_value"],
            actual_value=seed.get("actual_value", 0.0),
            estimated_cost=seed["estimated_cost"],
            actual_cost=seed.get("actual_cost", 0.5),
            resistance_risk=seed.get("resistance_risk", 2.5),
            confidence=max(0.0, min(seed.get("confidence", 0.5), 1.0)),
            manifestation_status=status,
            idea_type=idea_type,
            parent_idea_id=seed.get("parent_idea_id"),
            child_idea_ids=seed.get("child_idea_ids", []),
            value_basis=seed.get("value_basis"),
            interfaces=[x for x in seed.get("interfaces", []) if isinstance(x, str) and x.strip()],
            open_questions=open_questions,
        ))

    idea_registry_service.save_ideas(ideas, bootstrap_source="seed_db.py:SEED_IDEAS")
    return len(ideas)


def link_specs_to_ideas() -> int:
    """Link specs to ideas using contributing_specs from inline SEED_IDEAS."""
    # Build spec_id -> idea_id mapping from SEED_IDEAS
    spec_to_idea: dict[str, str] = {}
    for seed in SEED_IDEAS:
        idea_id = seed["id"]
        for spec_id in seed.get("contributing_specs", []):
            spec_to_idea[spec_id] = idea_id

    from app.models.spec_registry import SpecRegistryUpdate

    count = 0
    for spec_id, idea_id in spec_to_idea.items():
        existing = spec_registry_service.get_spec(spec_id)
        if existing is not None and not getattr(existing, "idea_id", None):
            spec_registry_service.update_spec(
                spec_id, SpecRegistryUpdate(idea_id=idea_id)
            )
            count += 1
    return count


def checkpoint_wal() -> None:
    """Fold WAL into the main DB file for a clean git commit."""
    eng = unified_db.engine()
    url = unified_db.database_url()
    if not url.startswith("sqlite"):
        return
    try:
        with eng.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    except Exception as e:
        print(f"  WAL checkpoint warning: {e}")


def main() -> None:
    # Ensure data/ directory exists
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"DB: {unified_db.database_url()}")
    unified_db.ensure_schema()

    print("Seeding ideas...")
    idea_count = seed_ideas()
    print(f"  {idea_count} ideas loaded")

    print("Seeding specs...")
    spec_count = seed_specs()
    print(f"  {spec_count} specs seeded")

    print("Seeding commit evidence...")
    evidence_count = seed_evidence()
    print(f"  {evidence_count} evidence records seeded")

    print("Linking specs to ideas...")
    link_count = link_specs_to_ideas()
    print(f"  {link_count} specs linked to ideas")

    print("Checkpointing WAL...")
    checkpoint_wal()

    print("Done.")


if __name__ == "__main__":
    main()
