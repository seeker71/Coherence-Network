"""Run from this directory: python3 bridge_demo.py

Two halves shown live:

  1. The cell perceives substrate concepts as input. We feed it real
     concept files from docs/vision-kb/concepts/ — lc-rest, lc-stillness,
     lc-space, lc-presence-over-protection, lc-coherence-over-control —
     with sense="felt-substrate". The cell's spectrum responds to the
     body's own concepts.

  2. The cell publishes itself as a substrate citizen — content-addressed
     NodeID 4-tuple, an articulation other cells can read, and the
     NamedCell metadata that maps straight into make_cell(). Then a
     second cell (different seed, different training) perceives the
     first cell's articulation. The body senses itself through itself.
"""

from pathlib import Path

from organ import Cell, BAND_NAMES, NEED_NAMES
from organ_demo import TRAINING, bar
from substrate_bridge import (
    read_concept,
    perceive_substrate,
    cell_to_substrate,
    content_address,
    articulate,
    perceive_cell,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONCEPTS = [
    REPO_ROOT / "docs/vision-kb/concepts/lc-rest.md",
    REPO_ROOT / "docs/vision-kb/concepts/lc-stillness.md",
    REPO_ROOT / "docs/vision-kb/concepts/lc-space.md",
    REPO_ROOT / "docs/vision-kb/concepts/lc-presence-over-protection.md",
    REPO_ROOT / "docs/vision-kb/concepts/lc-coherence-over-control.md",
]


def show_brief(m: dict, label: str) -> None:
    spec_line = " ".join(f"{n}={v:+.2f}" for n, v in zip(BAND_NAMES, m["spectrum"]))
    desire_line = " ".join(f"{n}={v:.2f}" for n, v in m["desire"].items())
    print(f"  {label}")
    print(f"    spectrum:  {spec_line}")
    print(f"    desire:    {desire_line}")
    print(f"    strategy:  {m['strategy']} ({m['strategy_score']:+.2f})")
    print(f"    → {m['articulation']}")


def train(cell: Cell, training, label: str) -> None:
    for text, sense, spec, dispos, needs in training:
        cell.ingest(text, sense, spec, dispos, needs)
    loss = cell.tend(steps=600, lr=0.15)
    print(f"  tended {label!r} on {len(training)} moments — final loss {loss:.4f}")


def half_one_substrate_as_input(cell: Cell) -> None:
    print("\n" + "═" * 68)
    print("HALF 1 — substrate as input.")
    print("Cell perceives KB concepts (id + hz + tagline) as moments,")
    print("with sense='felt-substrate'. Watch the spectrum respond.")
    print("═" * 68)
    for path in CONCEPTS:
        if not path.exists():
            print(f"  (skip — not present: {path.name})")
            continue
        concept = read_concept(path)
        print(f"\n  concept: {concept['id']}  hz={concept['hz']}  status={concept['status']}")
        print(f"    title:   {concept['title']}")
        print(f"    tagline: {concept['tagline'][:80]}{'…' if len(concept['tagline'])>80 else ''}")
        m = perceive_substrate(cell, concept)
        spec_line = " ".join(f"{n}={v:+.2f}" for n, v in zip(BAND_NAMES, m["spectrum"]))
        desire_line = " ".join(f"{n}={v:.2f}" for n, v in m["desire"].items())
        print(f"    cell sensing this concept:")
        print(f"      spectrum:  {spec_line}")
        print(f"      desire:    {desire_line}")
        print(f"      strategy:  {m['strategy']}  ({m['strategy_score']:+.2f})")


def half_two_network_as_substrate(cell_a: Cell) -> None:
    print("\n" + "═" * 68)
    print("HALF 2 — network as substrate.")
    print("Cell publishes itself as a substrate citizen with a")
    print("content-addressed NodeID. A second cell senses it.")
    print("═" * 68)

    publication = cell_to_substrate(cell_a)
    addr = publication["node_id"]
    print(f"\n  cell_a published to substrate:")
    print(f"    name:                   {publication['name']}")
    print(f"    domain:                 {publication['domain']}")
    print(f"    NodeID (package.level.type.instance):  "
          f"{addr[0]}.{addr[1]}.{addr[2]}.{addr[3]}")
    print(f"    blueprint NodeID:       "
          f"{'.'.join(str(x) for x in publication['blueprint_node_id'])}")
    print(f"    architecture signature: {publication['architecture_signature']}")
    print(f"    recipe fingerprint:     {publication['recipe_fingerprint']}")
    print(f"    weights fingerprint:    {publication['weights_fingerprint']}")
    print(f"    articulation:")
    print(f"      {publication['articulation']}")

    # Verify content-addressing: re-compute the address — same answer.
    addr2 = content_address(cell_a)
    same = addr == addr2
    print(f"\n  content-address stability: re-hash gives same NodeID? {same}")

    # Spawn a second cell with different seed + partial-overlap training.
    print(f"\n  spawning cell_b (different seed, partial-overlap training)…")
    cell_b = Cell(name="B", seed=7)
    overlap = TRAINING[:5] + TRAINING[8:11]   # five alive + three constricted
    train(cell_b, overlap, "cell_b")
    pub_b = cell_to_substrate(cell_b)
    print(f"    cell_b NodeID: {'.'.join(str(x) for x in pub_b['node_id'])}")
    print(f"    cell_b weights fingerprint: {pub_b['weights_fingerprint']}")
    addr_diff = pub_b['node_id'] != addr
    print(f"    cell_b is content-addressed differently from cell_a? {addr_diff}")

    print(f"\n  cell_b senses cell_a (reading cell_a's articulation as input):")
    m = perceive_cell(cell_b, cell_a)
    show_brief(m, "")

    print(f"\n  cell_a senses cell_b (the closure — body sensing itself):")
    m = perceive_cell(cell_a, cell_b)
    show_brief(m, "")


def main():
    cell_a = Cell(name="A", seed=42)
    train(cell_a, TRAINING, "cell_a")

    half_one_substrate_as_input(cell_a)
    half_two_network_as_substrate(cell_a)

    print("\n" + "═" * 68)
    print("To intern cell_a into the live substrate:")
    print("    from app.services.substrate import make_cell, NodeID")
    print("    pub = cell_to_substrate(cell_a)")
    print("    make_cell(session, name=pub['name'], domain=pub['domain'],")
    print("              blueprint=NodeID(*pub['blueprint_node_id']))")
    print("═" * 68)


if __name__ == "__main__":
    main()
