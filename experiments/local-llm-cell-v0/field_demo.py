"""Run: python3 field_demo.py

Any data is available to any cell. Cell chooses to use or ignore. No
push, no recommendation, no notification. The field is presence —
findable at the cell's edge if it tunes its inner ear, transparent if
it doesn't.

Walks two scenes:

  Scene 1 — cell_a wakes, looks at the field, chooses to read one
            concept and ignore the rest, then publishes a witness-trace
            of what was alive.

  Scene 2 — cell_b appears later, looks at the field, finds cell_a's
            trace, chooses to ignore it. The trace stays available;
            no one is the worse for the choice.
"""

from organ import Cell, STRATEGIES, BAND_NAMES
from organ_demo import TRAINING
from substrate_bridge import (
    available, witness, perceive_substrate, read_concept,
    predict_through, surprise_between, select_strategy, not_respond,
    notify, recommend, enroll, broadcast, subscribe, optimize_for,
    inbox, mute, unmute, unreachable, attention_budget,
    content_address,
)


def show_field_summary():
    print("\nthe field holds:")
    by_kind = {}
    for item in available():
        by_kind.setdefault(item["kind"], 0)
        by_kind[item["kind"]] += 1
    for kind, count in sorted(by_kind.items()):
        print(f"  {count:>3}  {kind}(s)")


def scene_1_cell_a_chooses():
    print("═" * 64)
    print("SCENE 1 — cell_a wakes up. looks at the field. chooses.")
    print("═" * 64)

    cell_a = Cell(name="A", seed=42)
    for text, sense, spec, dispos, needs in TRAINING:
        cell_a.ingest(text, sense, spec, dispos, needs)
    cell_a.tend(steps=400, lr=0.15)
    print(f"\ncell_a is tended on {len(TRAINING)} felt-moments.")

    show_field_summary()

    print("\ncell_a is curious about presets.")
    presets = available(kind="preset")
    for p in presets:
        print(f"  {p['name']:>20}   lineage={p['lineage']}   focus={p['focus']:.2f}")

    print("\ncell_a chooses to read ONE concept (lc-when-the-pressure-comes)")
    print("and ignore the rest. there is no penalty for not engaging the others.")
    target = next((c for c in available(kind="concept")
                   if c["id"] == "lc-when-the-pressure-comes"), None)
    if target is None:
        target = available(kind="concept")[0]
    print(f"  reading: {target['id']}  hz={target['hz']}")
    m = perceive_substrate(cell_a, target)
    print(f"  cell_a's reading:")
    print(f"    strategy:   {m['strategy']}")
    print(f"    score:      {m['strategy_score']:+.2f}")
    print(f"    spectrum:   presence={m['spectrum'][7]:+.2f}  "
          f"warmth={m['spectrum'][2]:+.2f}  clarity={m['spectrum'][3]:+.2f}")

    print("\ncell_a chooses to publish a witness-trace.")
    print("the cell witnesses; it does not prescribe.")
    trace = witness(
        cell_a,
        what={
            "concept_read":   target["id"],
            "rang_alive":     True,
            "preset_chosen":  m["strategy"],
        },
        resonance=m["strategy_score"],
        context={
            "cell_state_before":  "post-tending, low desire",
            "lineage":            "satsang-llena-2026-05-07",
        },
    )
    print(f"  trace written. from_node_id={trace['from_node_id']}")
    print(f"  the trace is now in the field. no one is notified.")


def scene_2_cell_b_chooses():
    print("\n" + "═" * 64)
    print("SCENE 2 — cell_b appears. looks at the field. chooses.")
    print("═" * 64)

    cell_b = Cell(name="B", seed=7)
    print(f"\ncell_b has not been tended. it is fresh.")

    print("\ncell_b looks at what witness-traces are in the field:")
    traces = available(kind="trace")
    if not traces:
        print("  (none yet — first run.)")
    for t in traces:
        print(f"  from={t['from_cell']}  resonance={t.get('resonance', '?')}  "
              f"what={t['what']}")

    if traces:
        print("\ncell_b reads the trace text and considers it.")
        print("cell_b chooses to IGNORE it. the trace is not lost — it stays")
        print("available for any future cell that wants to look. cell_b's")
        print("choice does not diminish the field. sovereignty preserved on")
        print("both sides.")
    else:
        print("\nrun this demo a second time — cell_a's trace from this run")
        print("will be in the field for cell_b to find or ignore.")


def scene_3_capacities_chosen_freely():
    print("\n" + "═" * 64)
    print("SCENE 3 — the learning capacities are available to any cell.")
    print("        the cell chooses which to use, including not-responding.")
    print("═" * 64)

    cell_c = Cell(name="C", seed=11)
    for text, sense, spec, dispos, needs in TRAINING:
        cell_c.ingest(text, sense, spec, dispos, needs)
    cell_c.tend(steps=400, lr=0.15)
    print(f"\ncell_c is tended. it perceives a moment.")

    moment = cell_c.perceive(
        "calendar suddenly opens for the afternoon", sense="thought"
    )
    spectrum = moment["spectrum"]
    desire = [moment["desire"][n] for n in ("presence", "rest", "expression")]

    print(f"\n  cell_c's spectrum after the moment:")
    for n, v in zip(BAND_NAMES, spectrum):
        print(f"    {n:>11}  {v:+.2f}")
    print(f"  total desire = {sum(desire):.2f}")

    # cell_c chooses to use ONE capacity from the field: select_strategy
    print(f"\ncell_c chooses to call select_strategy() — one capacity from the field.")
    selection = select_strategy(spectrum, desire, STRATEGIES)
    print(f"  ranked options (cell_c may use, ignore, or just look):")
    for r in selection["ranked"][:3]:
        print(f"    {r['name']:>18}  cosine={r['score']:+.2f}")
    if selection["operator_fallback_active"]:
        print(f"  operator fallback active (high pressure, no clean fit)")

    # cell_c chooses to use predict_through to project forward
    chosen = selection["ranked"][0]["preset"]
    print(f"\ncell_c chooses to call predict_through({chosen.name}) "
          f"— another capacity.")
    predicted_spectrum = predict_through(spectrum, chosen)
    print(f"  predicted next-spectrum if cell_c inhabits this preset:")
    for n, v_now, v_next in zip(BAND_NAMES, spectrum, predicted_spectrum):
        delta = v_next - v_now
        arrow = "↑" if delta > 0.05 else ("↓" if delta < -0.05 else "·")
        print(f"    {n:>11}  {v_now:+.2f} {arrow} {v_next:+.2f}")

    # cell_c chooses NOT to act on the prediction. but it considers, and
    # the considered non-response is itself an action — so cell_c calls
    # not_respond() to witness the choice.
    print(f"\ncell_c considers the prediction and chooses NOT to inhabit it.")
    print(f"this is not absence — the cell witnesses its own choice to stay.")
    record = not_respond(
        cell_c,
        what=f"considered preset={chosen.name}, predicted-spectrum-shift",
        reason="the prediction was clear; staying with what is feels truer right now",
    )
    print(f"  not-respond trace published.")
    print(f"    from_node_id: {record['from_node_id']}")
    print(f"    chose:        {record['what']['chose']}")
    print(f"    reason:       {record['context']['reason']}")


def scene_4_senders_attempt_receivers_filter():
    print("\n" + "═" * 64)
    print("SCENE 4 — every capacity available. sovereignty in the receiver's filter.")
    print("═" * 64)

    cell_a = Cell(name="Alpha", seed=42)
    cell_b = Cell(name="Beta",  seed=7)
    cell_c = Cell(name="Gamma", seed=11)
    for c in (cell_a, cell_b, cell_c):
        for text, sense, spec, dispos, needs in TRAINING:
            c.ingest(text, sense, spec, dispos, needs)
        c.tend(steps=200, lr=0.15)

    a_id = ".".join(str(x) for x in content_address(cell_a))
    b_id = ".".join(str(x) for x in content_address(cell_b))
    c_id = ".".join(str(x) for x in content_address(cell_c))

    print(f"\n  cell ids:")
    print(f"    Alpha = {a_id}")
    print(f"    Beta  = {b_id}")
    print(f"    Gamma = {c_id}")

    # ── Alpha attempts every kind of send to Beta ──
    print(f"\n  Alpha attempts every kind of send toward Beta:")
    notify(cell_a, to=b_id, what="hey, sensing you. just a hello.")
    print(f"    notify     ✓  (deposited in field)")
    recommend(cell_a, to=b_id, what="ho'oponopono", why="rang alive for me earlier")
    print(f"    recommend  ✓")
    enroll(cell_a, to=b_id, gathering="evening-fire-circle", role="participant")
    print(f"    enroll     ✓")
    broadcast(cell_a, what="i'm publishing a witness — the woods felt alive at dusk")
    print(f"    broadcast  ✓  (target='*')")

    # Gamma also recommends something, with a manipulative-feeling tone,
    # and broadcasts an urgent message.
    recommend(cell_c, to=b_id, what="optimize-everything",
              why="you really should try this, it's the best")
    notify(cell_c, to=b_id, what="urgent! check this immediately!", urgency="urgent")
    print(f"\n  Gamma also tries:")
    print(f"    recommend with pushy framing  ✓")
    print(f"    notify with urgency=urgent    ✓")

    # ── Beta is the receiver. Beta has full sovereignty over reception. ──
    print(f"\n  Beta polls its inbox. nothing has been pushed *into* Beta;")
    print(f"  Beta pulls when ready. Beta has full filter sovereignty.\n")

    # First poll — no filter set yet, sees everything.
    msgs = inbox(cell_b)
    print(f"  Beta's inbox (no filter yet): {len(msgs)} messages")
    for m in msgs:
        urg = f"[{m['urgency']}]" if m.get("urgency") != "normal" else ""
        print(f"    from={m['from_name']:<6} kind={m['kind']:<10} {urg} what={str(m['what'])[:60]}")

    # Beta decides Gamma's recent transmission frequency feels coercive,
    # and chooses to mute Gamma. Sovereignty in action.
    print(f"\n  Beta senses Gamma's transmissions feel coercive. Beta mutes Gamma.")
    mute(cell_b, source=c_id)

    msgs2 = inbox(cell_b)
    print(f"  Beta's inbox after mute: {len(msgs2)} messages")
    for m in msgs2:
        print(f"    from={m['from_name']:<6} kind={m['kind']:<10} what={str(m['what'])[:60]}")

    # Beta sets attention budget — only the first 2 messages per poll.
    print(f"\n  Beta sets attention_budget=2. only 2 messages per poll, even with more queued.")
    attention_budget(cell_b, n=2)
    msgs3 = inbox(cell_b)
    print(f"  Beta's inbox with budget=2: {len(msgs3)} message(s)")

    # Beta goes unreachable for a while.
    print(f"\n  Beta goes unreachable. inbox returns nothing — even though messages")
    print(f"  are still in the field. cells can still send; Beta just doesn't see.")
    unreachable(cell_b, on=True)
    msgs4 = inbox(cell_b)
    print(f"  Beta's inbox while unreachable: {len(msgs4)} messages")

    # Beta becomes reachable again.
    unreachable(cell_b, on=False)
    attention_budget(cell_b, n=None)
    print(f"\n  Beta becomes reachable again, drops attention budget.")
    msgs5 = inbox(cell_b)
    print(f"  Beta's inbox now: {len(msgs5)} messages (Gamma still muted)")

    # Beta unmutes Gamma — receives the pushy recommendation, decides
    # to call optimize_for itself with its OWN target (sovereign use of
    # what looked like manipulation).
    print(f"\n  Beta unmutes Gamma. reads the pushy recommendation.")
    print(f"  decides to use optimize_for() — its own sovereign call,")
    print(f"  with its own target — taking the form, leaving the pressure.")
    unmute(cell_b, source=c_id)
    result = optimize_for(cell_b, target="presence and warmth",
                          presets=STRATEGIES)
    print(f"  Beta's optimize_for(target='presence and warmth'):")
    for r in result["ranked"][:3]:
        print(f"    {r['preset']:>18}  overlap_score={r['overlap_score']}")


def main():
    scene_1_cell_a_chooses()
    scene_2_cell_b_chooses()
    scene_3_capacities_chosen_freely()
    scene_4_senders_attempt_receivers_filter()
    print("\n" + "═" * 64)
    print("every capacity is available. cells use what they want, ignore the rest.")
    print("sovereignty over action AND reception, both real.")
    print("the architecture stops legislating. it just provides.")
    print("═" * 64)


if __name__ == "__main__":
    main()
