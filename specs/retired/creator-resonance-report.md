---
idea_id: value-attribution
status: done
source:
  - file: api/app/models/creator_resonance.py
    symbols: [CreatorResonanceReportRequest, CreatorResonanceReport]
  - file: api/app/services/creator_resonance_service.py
    symbols: [build_creator_resonance_report()]
  - file: api/app/routers/creator_resonance.py
    symbols: [create_creator_resonance_report()]
  - file: web/app/creators/resonance/page.tsx
    symbols: [CreatorResonancePage]
  - file: web/app/creators/resonance/_components/CreatorResonanceBuilder.tsx
    symbols: [CreatorResonanceBuilder]
requirements:
  - "POST /api/creator-economy/resonance-report accepts creator platform snapshots and returns a report"
  - "Report separates attention, engagement, conversion, relationship, income, and proof confidence"
  - "Report names evidence gaps instead of guessing missing platform data"
  - "Web /creators/resonance provides a usable creator-facing report builder"
done_when:
  - "Focused API tests pass for service scoring, evidence gaps, and route response"
  - "Creator economy regression tests still pass"
  - "Web build includes /creators/resonance without TypeScript errors"
  - 'file_exists("api/app/models/creator_resonance.py")'
  - 'symbol_in_file("api/app/services/creator_resonance_service.py", "build_creator_resonance_report")'
  - 'symbol_in_file("api/app/routers/creator_resonance.py", "create_creator_resonance_report")'
  - 'symbol_in_file("web/app/creators/resonance/_components/CreatorResonanceBuilder.tsx", "CreatorResonanceBuilder")'
  - 'pytest_passes("api/tests/test_creator_resonance_report.py")'
test: "cd api && python3 -m pytest -q tests/test_creator_resonance_report.py tests/test_creator_economy.py"
constraints:
  - "No scraping and no platform credentials in this slice"
  - "Direct Spotify, Instagram, YouTube, Bandcamp, or Patreon adapters must enter later as explicit authorized sources"
  - "Scores are directional measurement aids, not revenue predictions"
  - "Private local creator context is not surfaced in public artifacts"
---

# Spec: Creator Resonance Report

## Purpose

Artists and digital creators need a simple way to turn scattered platform
signals into an evidence-backed action loop. This report receives creator
dashboard snapshots, separates attention from conversion and income, and
returns a next move that can be validated in the next campaign window.

This is the first sellable creator slice of the value engine: it can be used
with manual exports now, and direct platform adapters can be added later
without changing the report contract.

## Requirements

- [ ] **R1**: `POST /api/creator-economy/resonance-report` accepts `artist_name`,
  `campaign_title`, one or more platform snapshots, optional costs, optional
  artifacts, and optional desired outcomes. Each snapshot names the platform,
  whether it is baseline or current, metric values, and optional evidence
  source labels or URLs.

- [ ] **R2**: The report returns separate totals and dimension scores for
  attention, engagement, conversion, relationship, and income. Raw reach alone
  is never enough to prove value; conversion and income remain visible as their
  own dimensions.

- [ ] **R3**: The report returns `proof_quality`, `confidence`, `sources`, and
  `evidence_gaps`. Missing baseline, missing source labels, missing artifacts,
  and missing revenue evidence are named directly.

- [ ] **R4**: The report returns recommended next executions with reason,
  action, and expected signal. Recommendations are derived from observed
  dimension imbalance, such as high engagement with low conversion.

- [ ] **R5**: Web `/creators/resonance` provides an actual report builder for
  Spotify, Instagram, and other platform snapshots. It posts to the API and
  renders the returned score, proof quality, dimension bars, and next action.

## Research Inputs

- `2026-06-09` - Spotify for Artists support and blog pages document creator
  campaign surfaces such as Clips, Canvas, Countdown Pages, Artist Pick, merch,
  saves, pre-saves, and streaming engagement. The report treats Spotify signals
  as creator-provided or authorized snapshots until a direct adapter exists.

- `2026-06-09` - Instagram Help Center documents creator/business account
  insights including views, accounts reached, interactions, saves, shares,
  comments, follower growth, and account-level windows. The report accepts
  those signals without requiring Meta API authorization in this slice.

## API Contract

### `POST /api/creator-economy/resonance-report`

**Request**

```json
{
  "artist_name": "Mira Sound",
  "campaign_title": "River Single",
  "snapshots": [
    {
      "platform": "Instagram",
      "kind": "baseline",
      "source_label": "IG export before release",
      "metrics": {
        "reach": 1000,
        "saves": 20,
        "shares": 10,
        "comments": 5,
        "link_clicks": 8
      }
    },
    {
      "platform": "Spotify",
      "kind": "current",
      "source_label": "Spotify for Artists current window",
      "metrics": {
        "listeners": 460,
        "streams": 2100,
        "playlist_adds": 28,
        "revenue_usd": 18.5
      }
    }
  ],
  "costs": [{"label": "Campaign cost", "amount_usd": 12}],
  "artifacts": [{"title": "River reel", "platform": "Instagram"}]
}
```

**Response 200**

```json
{
  "report_id": "creator-resonance:55b8dd7874c011be",
  "artist_name": "Mira Sound",
  "campaign_title": "River Single",
  "proof_quality": "strong",
  "resonance_score": 0.42,
  "confidence": 0.82,
  "attention_total": 2860,
  "engagement_total": 212,
  "conversion_total": 2198,
  "income_usd": 18.5,
  "cost_usd": 12,
  "recommendations": [
    {
      "priority": "income",
      "reason": "Conversion exists, but spendable value is not yet covering the campaign cost.",
      "action": "Attach one priced creator offer to the campaign.",
      "expected_signal": "Measured revenue per 1000 attention and positive net income."
    }
  ],
  "evidence_gaps": []
}
```

## Data Model

```yaml
CreatorPlatformSnapshot:
  platform: string
  kind: baseline | current | milestone
  metrics:
    followers: number
    new_followers: number
    reach: number
    views: number
    saves: number
    shares: number
    comments: number
    link_clicks: number
    streams: number
    listeners: number
    playlist_adds: number
    pre_saves: number
    revenue_usd: number
  source_label: string | null
  evidence_url: string | null

CreatorResonanceReport:
  answer: can_generate_attention_value, can_validate_generation, can_show_income, status
  proof_quality: unproven | thin | emerging | strong
  resonance_score: 0..1
  confidence: 0..1
  dimensions: attention, engagement, conversion, relationship, income
  recommendations: list
  evidence_gaps: list
```

## Files Created or Modified

- `api/app/models/creator_resonance.py` - request and response models.
- `api/app/services/creator_resonance_service.py` - scoring, proof gaps, recommendations.
- `api/app/routers/creator_resonance.py` - creator economy report route.
- `api/app/main.py` - router wiring.
- `api/tests/test_creator_resonance_report.py` - focused route and service tests.
- `web/app/creators/page.tsx` - entry link.
- `web/app/creators/resonance/page.tsx` - report page.
- `web/app/creators/resonance/_components/CreatorResonanceBuilder.tsx` - client report builder.

## Acceptance Tests

- `api/tests/test_creator_resonance_report.py::test_creator_resonance_report_scores_multiple_dimensions`
- `api/tests/test_creator_resonance_report.py::test_creator_resonance_report_names_evidence_gaps`
- `api/tests/test_creator_resonance_report.py::test_creator_resonance_report_route`
- `api/tests/test_creator_economy.py`
- `cd web && npm run build`

## Verification

```bash
cd api && python3 -m pytest -q tests/test_creator_resonance_report.py tests/test_creator_economy.py
cd api && python3 -m ruff check app/models/creator_resonance.py app/services/creator_resonance_service.py app/routers/creator_resonance.py tests/test_creator_resonance_report.py
cd web && npm run build
```

## Out of Scope

- Direct OAuth/API adapters for Spotify, Instagram, YouTube, Bandcamp, Patreon,
  or Shopify.
- Scraping public creator pages.
- Persisted public report URLs.
- Revenue prediction.

## Gaps

- Follow-up task `creator-resonance-persisted-report-urls`: persist report
  payload hashes and returned reports so creators can share stable public proof
  URLs.
- Follow-up task `creator-resonance-authorized-platform-adapters`: add direct
  authorized adapters for Spotify, Instagram, YouTube, Bandcamp, Patreon, and
  Shopify as explicit source cells.
- Follow-up task `creator-resonance-score-calibration`: calibrate deterministic
  weights against a larger creator-campaign corpus while keeping the visible
  five-dimension score shape.

## Risks and Assumptions

- **Risk**: Manual snapshots can be wrong. Mitigation: the report carries
  `sources`, `confidence`, and `evidence_gaps`; direct adapters can raise
  confidence later.
- **Risk**: Platform metric names change. Mitigation: all platform-specific
  adapters will translate into this stable internal metric vocabulary.
- **Assumption**: The creator can access or export their own dashboard metrics.
