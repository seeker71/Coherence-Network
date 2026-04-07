# The Seed Library

*A retired teacher, 15 neighbors, 200 seed packets, and $47 that turned into $2,000 of garden produce — tracked from idea to harvest.*

---

## The Spark

Margaret retired after 32 years of teaching biology. Her backyard had 40 tomato varieties. Her neighbor asked for seeds. Then another. Then the mail carrier. She thought: what if the whole neighborhood shared seeds?

She didn't know how to build an app. She didn't have a budget. She had an idea and a phone.

## Step 1: Share the Idea

From ChatGPT (using the Coherence Network integration):

> "I want to start a seed library in my neighborhood. People donate seeds they've saved, others take what they need, and we track what grows."

The AI calls the Coherence Network API:

```
POST /api/ideas
{
  "name": "Parkview Seed Library",
  "description": "Community seed exchange where neighbors donate saved seeds,
                  others take what they need, and we track what grows.
                  Goal: 200 seed packets circulating by spring.",
  "potential_value": 50.0,
  "estimated_cost": 5.0,
  "confidence": 0.7
}
→ { "id": "parkview-seed-library", "stage": "none" }
```

The idea exists. It has an ID. It's in the portfolio.

## Step 2: Ask the Hard Questions

Margaret doesn't know everything. The platform helps her figure out what she doesn't know:

```
POST /api/ideas/parkview-seed-library/questions
{
  "question": "Where do we physically store the seeds?",
  "value_to_whole": 30.0,
  "estimated_cost": 2.0
}
```

```
POST /api/ideas/parkview-seed-library/questions
{
  "question": "How do we handle seeds that might carry disease?",
  "value_to_whole": 25.0,
  "estimated_cost": 3.0
}
```

```
POST /api/ideas/parkview-seed-library/questions
{
  "question": "What happens in winter when nothing is growing?",
  "value_to_whole": 15.0,
  "estimated_cost": 1.0
}
```

Each question has a value-to-whole score (how much answering it moves the idea forward) and an estimated cost (effort to find the answer). The platform prioritizes: answer the $30-value question first.

## Step 3: Spec It

Margaret's neighbor David is a retired librarian. He loves organizing things. He writes the spec — not code, just a plan:

```
POST /api/spec-registry
{
  "spec_id": "seed-library-operations",
  "title": "Seed Library Operations Manual",
  "summary": "Physical setup, donation process, checkout process,
              disease prevention, winter storage, volunteer roles.",
  "idea_id": "parkview-seed-library"
}
```

The spec answers the open questions:
- **Storage**: Converted filing cabinet in Margaret's garage, seeds in labeled coin envelopes
- **Disease**: Visual inspection checklist (10 items), reject anything with mold or discoloration
- **Winter**: Seed saving workshops November-February, indoor starts in March

The idea advances from `none` to `specced`:

```
PATCH /api/ideas/parkview-seed-library
{ "stage": "specced" }
```

## Step 4: Do the Work

Contributions come from everywhere. The platform tracks each one:

```
POST /api/contributions/record
{
  "contributor_display_name": "Margaret",
  "contribution_type": "design",
  "description": "Donated filing cabinet, organized 40 tomato varieties into labeled packets",
  "idea_id": "parkview-seed-library",
  "amount_cc": 15.0
}
```

```
POST /api/contributions/record
{
  "contributor_display_name": "David",
  "contribution_type": "docs",
  "description": "Wrote operations manual, checkout log template, disease inspection checklist",
  "idea_id": "parkview-seed-library",
  "amount_cc": 10.0
}
```

```
POST /api/contributions/record
{
  "contributor_display_name": "The Patel Family",
  "contribution_type": "community",
  "description": "Donated 50 packets of heirloom cilantro, fenugreek, and bitter gourd seeds",
  "idea_id": "parkview-seed-library",
  "amount_cc": 8.0
}
```

Fifteen neighbors contribute over two weeks. The platform knows who did what, when, and how much value they added.

The idea advances to `implementing`:

```
PATCH /api/ideas/parkview-seed-library
{ "stage": "implementing", "manifestation_status": "partial" }
```

## Step 5: Measure What Actually Happened

Spring comes. Seeds go out. Things grow. Margaret tracks the results:

```
PATCH /api/ideas/parkview-seed-library
{
  "actual_value": 40.0,
  "actual_cost": 4.7,
  "manifestation_status": "validated"
}
```

The numbers:
- **200 seed packets** circulated to 15 households
- **$47 in materials** (coin envelopes, labels, one filing cabinet from Goodwill)
- **$2,000+ in garden produce** across the neighborhood (estimated from USDA home garden value calculators)
- **ROI: 42x** ($47 in → $2,000 out)

The idea reaches `validated` — not because someone said it was good, but because the actual measured value exceeds the estimated cost by 42x.

## Step 6: The Proof

Anyone can query the idea's full journey:

```
GET /api/ideas/parkview-seed-library
→ {
    "id": "parkview-seed-library",
    "name": "Parkview Seed Library",
    "stage": "implementing",
    "manifestation_status": "validated",
    "potential_value": 50.0,
    "actual_value": 40.0,
    "estimated_cost": 5.0,
    "actual_cost": 4.7,
    "confidence": 0.7,
    "open_questions": [
      { "question": "Where do we store seeds?", "answer": "Filing cabinet in garage" },
      { "question": "Disease prevention?", "answer": "10-item visual checklist" }
    ]
  }
```

The lineage trace shows the full chain:
```
GET /api/trace/idea/parkview-seed-library
→ Idea → Spec (operations manual) → Contributions (15) → Measurement (validated, ROI 42x)
```

## What Margaret Learned

She didn't build software. She didn't write code. She shared an idea, asked questions, let her community contribute, and measured what happened. The platform gave her:

1. **A place to hold the idea** that wasn't a sticky note or an email thread
2. **Structured questions** that surfaced what she didn't know before she started
3. **Attribution** so every contributor — from the seed donors to the librarian — got credit
4. **Measurement** that proved the idea worked, not just that it existed

The seed library still runs. Margaret added a second filing cabinet. The Patels started a sister library two blocks over. That's a fork:

```
POST /api/ideas
{
  "name": "Elm Street Seed Library",
  "description": "Sister seed library, fork of Parkview. Focus on South Asian varieties.",
  "parent_idea_id": "parkview-seed-library"
}
```

The platform tracks the lineage. Both libraries exist. Both contribute back to the same network of proven impact.

---

*This scenario uses the live Coherence Network API. Every API call shown above works at `https://api.coherencycoin.com`. Try it from ChatGPT, Grok, Claude, or curl.*
