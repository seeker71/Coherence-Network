# The School Lunch Revolution

*A parent, 40 voters, one school board, and a 35% drop in cafeteria waste — powered by structured evidence that turned a complaint into a policy change.*

---

## The Spark

Rosa picks up her 8-year-old from school. Every day, the same conversation:

> "Did you eat lunch?"
> "I threw it away. It was gross."

Rosa looks at the cafeteria menu. Tater tots and canned peaches. Again. She's not the only parent frustrated, but complaining at school board meetings hasn't worked. The board says "we follow USDA guidelines" and moves on.

Rosa's insight: the problem isn't the guidelines. The problem is that nobody is measuring what kids actually eat versus what they throw away. The board makes decisions without data.

## Step 1: The Idea

Rosa uses ChatGPT with the Coherence Network API:

> "I want to create a system where parents and kids give feedback on school lunch menus, and we measure actual food waste, so the school board has data to improve the menu."

```
POST /api/ideas
{
  "name": "Lincoln Elementary Menu Feedback",
  "description": "Parent + student feedback system for school lunch menus.
                  Weekly ratings (1-5) per meal. Cafeteria staff photographs
                  waste bins daily. Data compiled monthly for school board.
                  Goal: reduce food waste 25% and increase student eating rate.",
  "potential_value": 70.0,
  "estimated_cost": 8.0,
  "confidence": 0.5
}
→ { "id": "lincoln-menu-feedback" }
```

Confidence is 0.5 — Rosa isn't sure the board will listen even with data.

## Step 2: The Questions That Matter

```
POST /api/ideas/lincoln-menu-feedback/questions
{ "question": "Will the school board actually look at this data?",
  "value_to_whole": 40.0, "estimated_cost": 5.0 }

POST /api/ideas/lincoln-menu-feedback/questions
{ "question": "How do we collect ratings from kids who don't have phones?",
  "value_to_whole": 25.0, "estimated_cost": 2.0 }

POST /api/ideas/lincoln-menu-feedback/questions
{ "question": "Can cafeteria staff realistically photograph waste bins?",
  "value_to_whole": 20.0, "estimated_cost": 1.0 }
```

The first question has the highest value-to-whole (40.0) — it's the existential risk. If the board won't look at data, nothing else matters.

Rosa answers it herself:

```
PATCH /api/ideas/lincoln-menu-feedback/questions/0
{
  "answer": "Board member Chen said she'd sponsor a 90-day pilot if we provide
             weekly reports. She's frustrated too — her kid throws away lunch.
             Confirmed via email 2026-03-15."
}
```

One board ally. The idea's confidence goes up:

```
PATCH /api/ideas/lincoln-menu-feedback
{ "confidence": 0.75 }
```

## Step 3: The Spec

Rosa's husband Tom is a data analyst. He writes the spec:

```
POST /api/spec-registry
{
  "spec_id": "menu-feedback-operations",
  "title": "Menu Feedback Collection & Reporting",
  "summary": "Google Form for parent ratings (weekly, anonymous, 1-5 per meal).
              Laminated paper cards for student ratings (smiley faces, collected at lunch).
              Cafeteria staff photographs waste bins at end of each lunch period.
              Tom compiles into monthly PDF report for board.",
  "idea_id": "lincoln-menu-feedback"
}
```

No software. No app. Google Forms, paper cards, phone cameras, and a PDF. The spec is about process, not technology.

## Step 4: The Governance Battle

Rosa posts the idea on the PTA Facebook group. Responses are mixed:

- 25 parents love it
- 10 parents worry about cafeteria staff feeling monitored
- 5 parents think the board will never change

She uses the governance system to build formal consensus:

```
POST /api/governance/change-requests
{
  "target_type": "idea_update",
  "target_id": "lincoln-menu-feedback",
  "proposer_id": "rosa-id",
  "change_payload": {
    "description": "Updated: cafeteria staff volunteers to participate (not monitored).
                    Waste photos taken BY staff, not of staff. Staff input on what
                    kids actually eat is the most valuable data source."
  },
  "rationale": "Addressed concerns from 10 parents about staff feeling surveilled.
                Reframed staff as partners, not subjects."
}
```

40 parents vote over a week. The governance system records every vote with rationale:

```
POST /api/governance/change-requests/{id}/votes
{ "voter_id": "parent-maria", "decision": "approve",
  "rationale": "My sister is a lunch lady at another school. She said she'd love
                to give input — nobody ever asks them." }

POST /api/governance/change-requests/{id}/votes
{ "voter_id": "parent-james", "decision": "approve",
  "rationale": "Staff involvement makes this better, not just less controversial." }
```

**Result: 38 approve, 2 abstain, 0 reject.** Auto-applied.

Rosa now has a documented record of community consensus — not "some parents said" but 38 named votes with written rationale. This goes in the board presentation.

## Step 5: Do the Work

The pilot launches. Contributions from everywhere:

```
POST /api/contributions/record
{ "contributor_display_name": "Rosa", "contribution_type": "community",
  "description": "Created Google Form, distributed to 180 parent emails",
  "idea_id": "lincoln-menu-feedback", "amount_cc": 10.0 }

POST /api/contributions/record
{ "contributor_display_name": "Tom", "contribution_type": "docs",
  "description": "Monthly report #1: 145 parent responses, waste photo analysis",
  "idea_id": "lincoln-menu-feedback", "amount_cc": 15.0 }

POST /api/contributions/record
{ "contributor_display_name": "Mrs. Garcia (cafeteria)", "contribution_type": "community",
  "description": "Daily waste photos for 30 days, notes on what kids leave vs eat",
  "idea_id": "lincoln-menu-feedback", "amount_cc": 20.0 }

POST /api/contributions/record
{ "contributor_display_name": "Student Council", "contribution_type": "community",
  "description": "Collected 400 paper rating cards over 4 weeks",
  "idea_id": "lincoln-menu-feedback", "amount_cc": 12.0 }
```

Mrs. Garcia — the cafeteria worker — becomes the most valuable contributor. Her daily photos and notes reveal the pattern nobody saw from the parent side: kids eat the entree on taco day but throw away the entree on fish stick day. The side dish doesn't matter. It's the main that decides waste.

## Step 6: The Data That Changed the Menu

Tom's monthly report:

| Menu Item | Rating (parent avg) | Rating (student avg) | Waste % |
|-----------|-------------------|---------------------|---------|
| Taco bar | 4.2 | 😊😊😊😊 | 12% |
| Pizza | 3.8 | 😊😊😊😊 | 15% |
| Chicken nuggets | 3.5 | 😊😊😊 | 22% |
| Fish sticks | 1.9 | 😐 | 61% |
| Tater tot casserole | 2.1 | 😐 | 55% |

Fish sticks: 61% waste. Taco bar: 12% waste. The data is undeniable.

Rosa presents to the board. Board member Chen sponsors the motion. The board votes to:
1. Replace fish sticks with a build-your-own salad bar (student council's suggestion)
2. Replace tater tot casserole with a soup-and-bread option (Mrs. Garcia's suggestion)
3. Continue the feedback system permanently

```
PATCH /api/ideas/lincoln-menu-feedback
{
  "actual_value": 60.0,
  "actual_cost": 6.5,
  "manifestation_status": "validated",
  "stage": "implementing"
}
```

## Step 7: The Measured Impact

Three months after the menu change:

```
PATCH /api/ideas/lincoln-menu-feedback
{
  "actual_value": 65.0,
  "actual_cost": 6.5,
  "manifestation_status": "validated"
}
```

- **Food waste dropped 35%** (from ~40% average to ~26%)
- **Student eating rate up 28%** (more kids finishing lunch)
- **Parent satisfaction: 4.1/5.0** (was 2.8)
- **Mrs. Garcia promoted** to menu planning committee
- **Cost to district: $0** (the feedback system is free; menu changes are cost-neutral)
- **ROI: 10x** on volunteer hours invested

The idea traces fully:

```
GET /api/ideas/lincoln-menu-feedback
→ {
    "stage": "implementing",
    "manifestation_status": "validated",
    "actual_value": 65.0,
    "actual_cost": 6.5,
    "open_questions": [
      { "question": "Will the board look at data?",
        "answer": "Board member Chen sponsored the pilot. Board voted to continue." }
    ]
  }
```

## What Rosa Learned

1. **The biggest risk was political, not technical.** The first question ("will the board listen?") had the highest value score. Answering it first — getting one board ally — de-risked everything else.

2. **The best contributor was the person closest to the problem.** Mrs. Garcia's daily waste photos were worth more than any parent survey. The platform's attribution system made her contribution visible. She went from invisible worker to menu planning committee member.

3. **Governance turns complaints into mandates.** "Some parents are upset" is ignorable. "38 named parents voted with written rationale" is a mandate. The governance record was what changed the board's mind.

4. **Measurement ends debates.** Fish sticks at 61% waste is not an opinion. The board couldn't argue with the data. They didn't argue with Rosa — they argued with the numbers, and the numbers won.

---

*The governance system, contribution ledger, idea lifecycle, and measurement flow are all live at `https://api.coherencycoin.com`. The 40-parent vote, the per-meal waste data, the contribution attribution — all of this runs on the same infrastructure that tracked 59 specs and 326 ideas in the Coherence Network itself.*

*The platform doesn't care if your idea is software, seeds, or school lunch. It cares that the idea gets tracked, the questions get answered, the work gets credited, and the impact gets measured.*
