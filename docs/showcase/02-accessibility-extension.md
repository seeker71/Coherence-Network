# The Accessibility Extension

*A blind developer, a design student, two QA testers, and 340 users who can now navigate the web by sound — built in 6 weeks by people who'd never met.*

---

## The Spark

James lost his sight at 27. He's a software developer. Screen readers work, but they read pages linearly — top to bottom, left to right. When a page has a sidebar, a nav bar, ads, a cookie banner, and the actual article buried somewhere in the middle, the screen reader makes him listen to everything before the content.

His idea: a browser extension that understands page *structure* and lets you jump directly to the main content, headings, forms, or links — by voice or keyboard.

## Step 1: Share and Decompose

James uses Grok with the Coherence Network API:

> "I want to build a browser extension that maps page structure and lets blind users navigate by landmarks instead of reading linearly."

```
POST /api/ideas
{
  "name": "Landmark Navigator",
  "description": "Browser extension that extracts page structure (headings, landmarks,
                  forms, links) and provides keyboard shortcuts + audio cues to jump
                  between them. For screen reader users who waste time on page chrome.",
  "potential_value": 80.0,
  "estimated_cost": 15.0,
  "confidence": 0.6
}
→ { "id": "landmark-navigator" }
```

Then he decomposes it into child ideas — each one independently buildable:

```
POST /api/ideas
{ "name": "ARIA Landmark Parser", "parent_idea_id": "landmark-navigator",
  "description": "Parse page DOM for ARIA roles and heading hierarchy" }

POST /api/ideas
{ "name": "Audio Landmark Cues", "parent_idea_id": "landmark-navigator",
  "description": "Distinct audio tones for nav, main, aside, form, heading levels" }

POST /api/ideas
{ "name": "Keyboard Navigation Layer", "parent_idea_id": "landmark-navigator",
  "description": "H for next heading, M for main, F for form, L for link list" }
```

Three child ideas. Each can be built by different people. The parent rolls up their progress.

## Step 2: Strangers Show Up

James posts about it on a disability tech forum. Three people find the idea via the platform:

**Priya** — a design student specializing in accessible UI. She creates a spec:

```
POST /api/spec-registry
{
  "spec_id": "audio-cue-design",
  "title": "Audio Landmark Cues — Sound Design Spec",
  "summary": "Each ARIA role gets a distinct audio cue: navigation=chime,
              main=warm tone, form=click, heading=pitch-mapped to level (h1=low, h6=high).
              Must be distinguishable in under 200ms. Must not conflict with screen reader speech.",
  "idea_id": "landmark-navigator"
}
```

**Marcus** and **Elena** — QA testers, one sighted, one low-vision. They test across screen readers (NVDA, JAWS, VoiceOver).

Everyone's contributions are tracked:

```
POST /api/contributions/record
{ "contributor_display_name": "Priya", "contribution_type": "design",
  "description": "Audio cue palette — 6 distinct tones, tested with 3 screen readers",
  "idea_id": "landmark-navigator", "amount_cc": 12.0 }

POST /api/contributions/record
{ "contributor_display_name": "Marcus", "contribution_type": "review",
  "description": "Cross-browser testing: Chrome, Firefox, Edge on Windows with NVDA",
  "idea_id": "landmark-navigator", "amount_cc": 8.0 }

POST /api/contributions/record
{ "contributor_display_name": "Elena", "contribution_type": "review",
  "description": "VoiceOver testing on macOS + iOS Safari, found 3 landmark parsing bugs",
  "idea_id": "landmark-navigator", "amount_cc": 10.0 }
```

## Step 3: Governance — What to Build First

Four contributors, limited time. What should they build first? They use the governance system:

```
POST /api/governance/change-requests
{
  "target_type": "idea_update",
  "target_id": "landmark-navigator",
  "proposer_id": "elena-id",
  "change_payload": { "priority_order": ["keyboard-nav", "aria-parser", "audio-cues"] },
  "rationale": "Keyboard shortcuts work without sound. Audio cues are a nice-to-have.
                Ship keyboard nav first so people can use it immediately."
}
```

James, Priya, and Marcus vote:

```
POST /api/governance/change-requests/{id}/votes
{ "voter_id": "james-id", "decision": "approve",
  "rationale": "Agree. I'd use keyboard nav without audio. Audio comes later." }
```

Three approvals. Auto-applied. The priority order is set. Keyboard nav ships first.

## Step 4: Measure Real Impact

Six weeks later. The extension is in the Chrome Web Store. The platform tracks what happens:

```
PATCH /api/ideas/landmark-navigator
{
  "actual_value": 65.0,
  "actual_cost": 12.0,
  "manifestation_status": "validated"
}
```

The numbers:
- **340 active users** after 6 weeks
- **Keyboard shortcuts used 12,000 times/week** (H for heading is most popular)
- **Audio cues enabled by 40% of users** (Priya's design validated — but not essential)
- **Average time to reach main content: 2 seconds** (was 45 seconds with linear reading)
- **ROI: 5.4x** on effort invested

The right-sizing service flags something interesting:

```
GET /api/ideas/right-sizing
→ { "suggestions": [
    { "idea_id": "landmark-navigator", "signal": "too_large",
      "rationale": "3 child ideas, 4 contributors, 12K weekly actions —
                    consider splitting audio-cues into its own project" }
  ]}
```

The audio cue system has become popular enough to be its own thing. Priya forks it:

```
POST /api/ideas
{
  "name": "Accessible Audio Design System",
  "description": "Reusable audio cue library for accessibility tools.
                  Extracted from Landmark Navigator's audio-cues module.",
  "parent_idea_id": "landmark-navigator"
}
```

## What the Team Learned

1. **Decomposition surfaces the real priorities.** Breaking one idea into three showed that keyboard nav was 80% of the value. Audio cues were polish. Without decomposition, they would have built everything at once.

2. **Governance prevented the loudest-voice problem.** Elena's rationale ("ship what works without sound first") was better than James's initial plan ("build the full audio experience"). The voting system let the better argument win without conflict.

3. **Measurement found the surprise.** 40% audio cue adoption meant Priya's work was validated but not dominant. This data let her fork the audio system into its own project — a move nobody would have made without numbers.

4. **Attribution matters for strangers.** Priya, Marcus, and Elena had never met James. They contributed because the platform showed exactly what was needed and promised credit. Every contribution is on the ledger. If CC ever has exchange value, their work is recorded.

---

*Every API call shown above works at `https://api.coherencycoin.com`. The governance, contribution tracking, right-sizing, and idea hierarchy systems are production-deployed. Try it from any AI assistant or HTTP client.*
