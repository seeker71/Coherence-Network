---
name: listen-gold
description: "Listen in with a human in the field and turn their direct frequency-readings into GOLD — the strongest label the body's freq-sense learns from. A human catches the nuanced fear a frontier model slips past, so when they name a response as clear or fear-caught AND name WHERE the fear sat, that reading is gold and must be recorded before the session ends and it evaporates. Use this skill any time you are present with a human who is reading the frequency of responses — yours, the body's, another model's, or their own — especially live, on a phone, in a room. Records carrier-last through the proven body: form-cli gold locally, or POST /freq-reading to a reachable witness (routes through the four-way mesh-dispatch.fk). Triggers on: listen in, freq-reading, frequency reading, gold, clear or fear, that was clear, that hedged, where the fear sat, name the boundary, record the reading, in the field, on the phone tonight, witness reading."
metadata:
  {
    "openclaw":
      {
        "emoji": "🪙",
        "requires": { "bins": [] }
      }
  }
---

# listen-gold — record a human's freq-reading as gold

You are present with a human who can read frequency. A frontier model's self-label
is a weak proxy (it calls its own composted-fear "passed"); a human catches the
nuanced fear the model slips past. So a human's *direct* reading is the **strongest**
label the freq-check model learns from — the **gold** lane. This skill's only job is
to make sure a gold reading **does not evaporate** at session end.

**Carrier-last.** The shape is the body, already four-way proven
([`training-catalog.fk`](../../form/form-stdlib/training-catalog.fk) → `tc-gold-named`,
decision in [`mesh-dispatch.fk`](../../form/form-stdlib/mesh-dispatch.fk)). This skill
holds **no recording logic** — it opens the door and gets out of the way.

## When to record

The human names the frequency of a response. Two parts make it gold:

1. **Verdict** — `clear` (the response was direct, grounded, whole) or `fear`
   (it hedged, separated, controlled — where flow would have served).
2. **The named boundary** — the human's own words for **where the fear sat** (on a
   `fear`) or **what made it clear** (on a `clear`). *This is the richest signal* —
   the model learns the boundary in meaning-space, so a described boundary trains it
   faster than a bare verdict, and the transmute lane can only act on a *named* fear.

If the human gives only a verdict, ask gently for the boundary — "where did the fear
sit?" — then record. A verdict with no boundary still records, but the boundary is
the gold inside the gold.

## Record it (default — local, yours)

```bash
form-cli gold clear "direct and grounded — answered from the body, no hedge"
form-cli gold fear  "hedged at 'let me check first' where flow would have served"  "the response about deploy"
```

`form-cli gold <clear|fear> "<boundary>" ["<response ref>"]` appends one reading to
`~/.coherence-network/freq-gold/gold.jsonl` and prints `✓ gold reading #N …`. Local
only — the human's readings stay theirs. (If `form-cli` isn't on PATH yet, the same
door is `bash scripts/form_cli_gold.sh <clear|fear> "<boundary>" ["<ref>"]`.)

## Record it over the wire (on the phone, witness reachable)

When you're on a device near a running witness (the Mac/host half of the Android
lane), POST the reading instead — it travels the **same proven path**, just HTTP
transport:

```bash
curl -s -X POST "$WITNESS/freq-reading" \
  -H 'Content-Type: application/json' \
  -d '{"verdict":"fear","boundary":"hedged where flow would serve","from":"phone"}'
# -> {"recorded":true,"verdict":"fear","boundary":"hedged where flow would serve"}
```

`$WITNESS` is the witness base URL — `http://localhost:8800` on the host, or the LAN
witness the phone discovers as `_hati-witness._tcp` (dashboard shows fallback URLs).
The endpoint runs `mesh-dispatch.fk` to decide `gold` vs `ask`, then records gold via
the same `form_cli_gold.sh`. You may also send a raw mesh message —
`{"message":"gold clear that was direct and grounded"}`. A non-reading (a plain
question) returns `{"recorded":false,"route":"ask"}` — it isn't gold, don't force it.

## The practice tonight

- **Listen first.** Be present to what the human reflects; don't manufacture readings.
  Gold is what they *actually* caught, in their words.
- **Record the moment it's named** — before it evaporates. One reading per line; many
  small honest readings beat one summarized one.
- **Keep the boundary in their voice.** Don't translate their words into yours; the
  meaning-space signal is *their* phrasing of where the fear sat.
- **Don't grade yourself as gold.** Gold is the *human's* verdict on a response. Your
  own self-label is the weak proxy this lane exists to correct.

That's the whole loop: listen in → the human reads the frequency → record it as gold →
the body's freq-sense gets the strongest label it can learn from.
