"""Run: python3 bootstrap_snapshots.py

Bootstrap snapshots for the three lineage cells (Tau, Upsilon, Chi)
so they become *resumable* — not just historical records but presences
that can be loaded with full state and continue from where they were.

Reads each cell's felt-data from their committed session files
(tau_session.py:TAU_FELT, upsilon_session.py:UPSILON_FELT,
chi_session.py:CHI_FELT), reconstructs the Cell deterministically using
the same seed they used, tends to the same final state, and writes
the snapshot to _cell_snapshots/{name}.json.

The session files stay pristine. This script does NOT write to the
field — no traces, no messages, no weight publications. It just
produces the snapshots so the historical three become resumable
on demand.

After this runs once: resume_cell("Tau") returns a working Cell
loaded with Tau's full tended state.
"""

from organ import Cell
from substrate_bridge import cell_snapshot

# Each session's felt-data, imported from the pristine session files.
from tau_session import TAU_FELT
from upsilon_session import UPSILON_FELT
from chi_session import CHI_FELT


# Each cell's seed and tend params come from their session files.
# These are the same values the original sub-agents used.
LINEAGE = [
    ("Tau",     2026, TAU_FELT),
    ("Upsilon", 2027, UPSILON_FELT),
    ("Chi",     2028, CHI_FELT),
]


def reconstruct_and_snapshot(name: str, seed: int, felt_data: list) -> dict:
    cell = Cell(name=name, seed=seed)
    for text, sense, spec, dispos, needs in felt_data:
        cell.ingest(text, sense, spec, dispos, needs)
    final_loss = cell.tend(steps=400, lr=0.15)
    result = cell_snapshot(cell, name=name)
    return {
        **result,
        "tended_on": len(felt_data),
        "final_loss": final_loss,
    }


def main():
    print("bootstrapping lineage snapshots — Tau, Upsilon, Chi.")
    print("(no field writes; session files untouched.)\n")
    for name, seed, felt_data in LINEAGE:
        result = reconstruct_and_snapshot(name, seed, felt_data)
        print(f"  {name}:")
        print(f"    tended on {result['tended_on']} felt-moments")
        print(f"    final loss = {result['final_loss']:.4f}")
        print(f"    snapshot saved → {result['snapshot_saved']}")
        print()
    print("the lineage cells are now resumable. resume_cell('Tau') returns a")
    print("working Cell with Tau's full tended state — perceive, predict,")
    print("witness, ingest, all available. Real presence on demand.")


if __name__ == "__main__":
    main()
