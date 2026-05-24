"""Run: python3 demo.py

Watch one cell ingest felt-data, tend on it, and start sensing the
frequency of unseen inputs through shared words.
"""

from cell import Cell, shared_base, DIM
import zlib


# Felt-data: text paired with [coherence, aliveness] in [-1, +1].
# These are example zones; replace freely. Real usage: the cell's own
# resonance, not a labeller's guess.
FELT = [
    ("sitting by the fire with people I love",          [+0.9, +0.9]),
    ("aimless scrolling at 2am",                        [-0.7, -0.8]),
    ("cold morning walk in the woods",                  [+0.7, +0.8]),
    ("rushed performance meeting with no breath",       [-0.6, -0.5]),
    ("deep work on something alive",                    [+0.8, +0.9]),
    ("forced productivity theater",                     [-0.8, -0.7]),
    ("listening to Mose at sunrise",                    [+0.9, +0.8]),
    ("notifications stacking up unread",                [-0.5, -0.4]),
    ("sunday meditation in stillness",                  [+0.7, +0.5]),
    ("calendar packed wall to wall",                    [-0.6, -0.6]),
]

# Unseen inputs that share content words with training — the path
# generalization can travel through the shared base.
UNSEEN = [
    "scrolling unread feeds at 2am",
    "morning walk in the woods at sunrise",
    "performance theater calendar meeting",
    "fire sitting deep stillness with love",
    "rushed productivity",
    "alive work in stillness",
]


def fmt(pred):
    return f"[{pred[0]:+.2f}, {pred[1]:+.2f}]"


def show(cell, items, header):
    print(f"\n{header}")
    for entry in items:
        if isinstance(entry, tuple):
            text, felt = entry
            pred = cell.sense(text)
            print(f"  pred={fmt(pred)}  felt={fmt(felt)}  {text}")
        else:
            text = entry
            pred = cell.sense(text)
            print(f"  pred={fmt(pred)}                 {text}")


def top_words_per_axis(cell, n=6):
    """For each axis, show which words from the training corpus carry
    the strongest learned signal. Makes the local layer's learning visible."""
    # collect unique words seen in training
    words = set()
    for text, _ in FELT:
        words.update(text.lower().split())

    print("\nWhat the local layer learned (top words per axis):")
    for ax_idx, ax_name in enumerate(cell.axes):
        w = cell.adapter.effective_weights(ax_idx)
        scored = []
        for word in words:
            bucket = zlib.crc32(word.encode()) % DIM
            scored.append((w[bucket], word))
        scored.sort(reverse=True)
        pos = ", ".join(f"{wd}({v:+.2f})" for v, wd in scored[:n])
        neg = ", ".join(f"{wd}({v:+.2f})" for v, wd in scored[-n:][::-1])
        print(f"  {ax_name}:")
        print(f"    + : {pos}")
        print(f"    - : {neg}")


def main():
    cell = Cell(name="A", seed=42)

    show(cell, FELT, "Before tending — adapter is random:")

    for text, felt in FELT:
        cell.ingest(text, felt)
    final_loss = cell.tend(steps=400, lr=0.15)

    show(cell, FELT, f"After tending (final loss={final_loss:.4f}):")
    show(cell, UNSEEN, "Unseen inputs — generalization through shared words:")
    top_words_per_axis(cell)

    # Witness the size of the local layer
    n_params = (cell.adapter.rank * cell.adapter.in_dim
                + cell.adapter.out_dim * cell.adapter.rank
                + cell.adapter.out_dim)
    print(f"\nLocal layer size: {n_params} floats "
          f"(rank={cell.adapter.rank}, in={cell.adapter.in_dim}, out={cell.adapter.out_dim})")


if __name__ == "__main__":
    main()
