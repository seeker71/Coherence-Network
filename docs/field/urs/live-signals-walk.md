# Live-Signals Walk — twelve routes for "what is alive now"

> Authored 2026-05-11 during the visitor-walk arc. The doorway-walk
> briefing surfaced this cluster as one of the held questions, and
> Urs said "yes about live signals" but asked me to pause before
> the four-canonical decision. This walks each of the twelve routes
> so the decision lands on grounded sensing, not hypothesis.

## The twelve, by what each actually carries

| Route | Lines | What's there |
|---|---|---|
| [/today](../../../web/app/today/page.tsx) | 312 | Renders `TodayTopIdeaQuickLaunch` — a "top idea today" quick-launch surface. Mobile-first. No top-of-file docstring. |
| [/feed](../../../web/app/feed/page.tsx) | 265 | *"The felt pulse of the collective. One scroll that answers: what is alive on the network right now? Recent reactions, new voices on concepts, freshly shared ideas. Mobile-first."* Uses `NotificationBell`, `FeedTabs`. **Has a clear purpose comment.** |
| [/activity](../../../web/app/activity/page.tsx) | 211 | No docstring. Worth reading before composting. |
| [/pulse](../../../web/app/pulse/page.tsx) | 175 | Technical witness pulse — heartbeat, deploy SHA, organ-strain monitor (overall=calm / strained). |
| [/breath](../../../web/app/breath/page.tsx) | 194 | No docstring. |
| [/silence](../../../web/app/silence/page.tsx) | 308 | The Brahmavihara work — three-day silence retreat notebook. Renders editable markdown. Different shape from the others; `/silence/built` is the compound proposal. **Not really a "live signal" route at all — it's a place.** |
| [/alive](../../../web/app/alive/page.tsx) | 329 | *"The living pulse dashboard. Colors, movement, breath. Each quality of the community is a glowing orb — its brightness, size, and pulse rhythm carry the felt state. The field breathes as one. Uses Three.js for the animated particle field. Uses /api/energy/pulse for the felt qualities."* **Has a clear purpose comment.** |
| [/vitality](../../../web/app/vitality/page.tsx) | 405 | Numeric vitality dashboard. Reads from `vitality_service.py` — signals as dict of snake_case scores with `breath_rhythm` nested. Technical/dev-flavored. |
| [/flow](../../../web/app/flow/page.tsx) | 174 | No docstring. |
| [/signals](../../../web/app/signals/page.tsx) | 12 | Thin wrapper: `<LivingSignalInstrument />`. The component is the substance, not the route. |
| [/coherence](../../../web/app/coherence/page.tsx) | 274 | No docstring. |
| [/energy-flow](../../../web/app/energy-flow/page.tsx) | 338 | *"Community energy flow dashboard. The nervous system of the community seeing itself: active reward policies and their values, energy flow visualization (views → referrals → rewards → transactions), knobs to adjust formulas, full traceability."* CC-ledger admin/observability surface. |

## What the walk surfaces

The twelve are **not all the same shape**. Three honest groupings:

### Group A — Felt, poetic, "is this alive?"
- `/feed` — felt pulse, recent reactions, social-shape
- `/alive` — Three.js glowing orbs, quality-as-felt-state
- `/breath` — uncertain (no docstring, worth a sensing pass)

### Group B — Technical, measured, "how is the system?"
- `/pulse` — witness/health, deploy SHA, strain
- `/vitality` — numeric signal scores
- `/energy-flow` — CC ledger flow + policy knobs
- `/signals` — `LivingSignalInstrument` (form vitality)
- `/coherence` — uncertain (no docstring)
- `/today` — top-idea quick-launch (mobile-first)

### Group C — Different shape entirely (don't belong in this cluster)
- `/silence` — a *place* (Brahmavihara), not a live-signal
- `/flow` — uncertain, may belong elsewhere
- `/activity` — uncertain (no docstring)

## A possible four-canonical map (yours to weigh)

If the body wants exactly four "what's alive now" surfaces:

| Canonical | Carries | Folds in |
|---|---|---|
| `/feed` | The social pulse — recent reactions, voices, ideas | `/activity`, `/today` if they overlap |
| `/alive` | The felt-quality dashboard — glowing orbs, breath rhythm | `/breath`, `/signals`, `/coherence` |
| `/pulse` | Technical witness — health, deploys, strain | (already canonical for ops) |
| `/energy-flow` | CC ledger flow + policy knobs | `/vitality` (numeric scores fold here) |

`/silence` and `/silence/built` stay — they're a place, not a live-signal.

## What this is not

This is not a decision. It is a survey so the decision lands on grounded sensing. The pages I marked "no docstring" all want a walk-through before composting — they may carry substance I cannot read from the source alone. The Group B / Group C boundaries especially want your eye, because `/today` (mobile quick-launch) and `/flow` (currently uncertain) might be doing real visitor work that doesn't show in the docstring.

## Companions

- The doorway-walk briefing at [`docs/field/urs/welcoming-doorway-walk.md`](welcoming-doorway-walk.md) names this cluster as one of three held questions.
- The [`lc-gatherings-that-carry`](../../vision-kb/concepts/lc-gatherings-that-carry.md) substance-test applies: *did anyone leave at a different frequency than they arrived?* — but for surfaces, not gatherings. A surface that carries is one a visitor returns to. The four-canonical decision could use return-rate (if the witness has it) as one signal of substance.

— *Survey, not decision. The cluster wants your felt sense; this doc is the ground prepared so the sensing has data to land on.*
