"""organ.py — cell as small organism, not a regressor.

Adds to cell.py (v0 → v1):
  • 8-band frequency spectrum (felt resonance) instead of 2 scalars
  • 5 sense modalities tagged on input (saw / heard / felt-inside /
    felt-outside / thought) — encoded into the shared base
  • 4 disposition gates (surprise / attend / want / change-perception)
  • 3 need channels (presence / rest / expression)
  • desire accumulator — stateful: desire builds when needs go unmet,
    drains when the spectrum's alive bands rise (fulfillment)
  • 4 strategy prototypes (tend / rest / reach / withdraw) — cell picks
    by cosine similarity to current spectrum and articulates what
    "now" means through the chosen lens

The adapter is one shared LoRA-shaped projection with three output
heads (spectrum / dispositions / needs). Desire is runtime state,
not learned weights — the cell has memory in time, not just in
parameters.
"""

import math
import random
import zlib


DIM = 128
N_BANDS = 8
N_DISPOS = 4
N_NEEDS = 3

SENSES = ("saw", "heard", "felt-inside", "felt-outside", "thought")
BAND_NAMES = ("ground", "pulse", "warmth", "clarity",
              "expression", "relation", "space", "presence")
DISPO_NAMES = ("surprise", "attend", "want", "change-perception")
NEED_NAMES = ("presence", "rest", "expression")


# ─── shared base ──────────────────────────────────────────────────────────
# First len(SENSES) buckets reserved for sense-modality one-hot.
# Remaining buckets carry word-hash features.

def shared_base(text: str, sense: str = "thought", dim: int = DIM) -> list[float]:
    vec = [0.0] * dim
    si = SENSES.index(sense) if sense in SENSES else SENSES.index("thought")
    vec[si] = 1.0
    body = dim - len(SENSES)
    for word in text.lower().split():
        h = zlib.crc32(word.encode()) % body + len(SENSES)
        vec[h] += 1.0
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def _sigmoid(z: float) -> float:
    if z < -50:
        return 0.0
    if z > 50:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


# ─── adapter ──────────────────────────────────────────────────────────────

class Adapter:
    """Single LoRA-shaped projection with three output heads.
    out = [spectrum (tanh, N_BANDS) | dispos (sigmoid, N_DISPOS) | needs (sigmoid, N_NEEDS)]
    """

    def __init__(self, in_dim: int = DIM, rank: int = 8, seed: int = 0):
        self.in_dim = in_dim
        self.rank = rank
        self.out_dim = N_BANDS + N_DISPOS + N_NEEDS
        rng = random.Random(seed)
        s = 0.1
        self.A = [[rng.gauss(0, s) for _ in range(in_dim)] for _ in range(rank)]
        self.B = [[rng.gauss(0, s) for _ in range(rank)] for _ in range(self.out_dim)]
        self.bias = [0.0] * self.out_dim

    def _raw(self, x):
        h = [sum(self.A[i][k] * x[k] for k in range(self.in_dim)) for i in range(self.rank)]
        z = [sum(self.B[i][j] * h[j] for j in range(self.rank)) + self.bias[i]
             for i in range(self.out_dim)]
        return h, z

    def forward(self, x):
        h, z = self._raw(x)
        spec = [math.tanh(z[i]) for i in range(N_BANDS)]
        dispos = [_sigmoid(z[N_BANDS + i]) for i in range(N_DISPOS)]
        needs = [_sigmoid(z[N_BANDS + N_DISPOS + i]) for i in range(N_NEEDS)]
        return spec, dispos, needs, h, z

    def step(self, batch, lr: float):
        """One full-batch SGD step over a list of (x, target_flat)."""
        n = len(batch)
        gA = [[0.0] * self.in_dim for _ in range(self.rank)]
        gB = [[0.0] * self.rank for _ in range(self.out_dim)]
        gbias = [0.0] * self.out_dim
        total = 0.0
        for x, target in batch:
            h, z = self._raw(x)
            preds = []
            for i in range(self.out_dim):
                preds.append(math.tanh(z[i]) if i < N_BANDS else _sigmoid(z[i]))
            total += sum((preds[i] - target[i]) ** 2 for i in range(self.out_dim))
            grad_y = [2 * (preds[i] - target[i]) / n for i in range(self.out_dim)]
            grad_z = []
            for i in range(self.out_dim):
                if i < N_BANDS:
                    grad_z.append(grad_y[i] * (1 - math.tanh(z[i]) ** 2))
                else:
                    s = _sigmoid(z[i])
                    grad_z.append(grad_y[i] * s * (1 - s))
            grad_h = [sum(grad_z[i] * self.B[i][j] for i in range(self.out_dim))
                      for j in range(self.rank)]
            for i in range(self.out_dim):
                for j in range(self.rank):
                    gB[i][j] += grad_z[i] * h[j]
                gbias[i] += grad_z[i]
            for i in range(self.rank):
                for k in range(self.in_dim):
                    gA[i][k] += grad_h[i] * x[k]
        for i in range(self.rank):
            for k in range(self.in_dim):
                self.A[i][k] -= lr * gA[i][k]
        for i in range(self.out_dim):
            for j in range(self.rank):
                self.B[i][j] -= lr * gB[i][j]
            self.bias[i] -= lr * gbias[i]
        return total / n


# ─── strategy prototypes — five strategies of return ─────────────────────
# Source: Llena's community satsang, Ubud, 2026-05-07. The teaching
# lives in docs/vision-kb/concepts/lc-when-the-pressure-comes.md.
#
# Each strategy carries:
#   frequency  — band-emphasis vector (which spectrum bands this belief
#                system carries through; aligns with N_BANDS)
#   angle      — the direction in spectrum-space the discharge points
#                (unit vector, indexed across N_BANDS)
#   focus      — aperture/sharpness in [0,1]; high = pointed, low = wide
#   articulation — template that speaks the moment back through this lens
#
# The fifth strategy (frequency × angle × focus operator) is what the
# others run inside. The cell can pick a named preset, or in v2 will
# learn its own (frequency, angle, focus) settings the body has not
# yet named.

class Strategy:
    __slots__ = ("name", "frequency", "angle", "focus", "articulation")

    def __init__(self, name: str, frequency, angle, focus: float, articulation: str):
        self.name = name
        self.frequency = list(frequency)
        # normalize angle to unit vector
        n = math.sqrt(sum(a * a for a in angle)) or 1.0
        self.angle = [a / n for a in angle]
        self.focus = focus
        self.articulation = articulation


STRATEGIES = [
    # 1. switching to observer — the witness is wide and quiet
    Strategy(
        name="observer",
        frequency=[+0.4, +0.1, +0.3, +0.3, +0.2, +0.3, +0.8, +0.7],  # space + presence carry
        angle=[+0.3, +0.2, +0.3, +0.3, +0.3, +0.3, +0.5, +0.5],       # spread, slight upward
        focus=0.25,                                                     # wide aperture
        articulation=(
            "observer: pressure becomes weather passing through. "
            "what is here. what is here. what is here. "
            "(rest-desire {desire_rest:.2f}, expr-desire {desire_expression:.2f}, "
            "presence-desire {desire_presence:.2f})"
        ),
    ),
    # 2. naming the underlying desire or need — clarity + expression
    Strategy(
        name="name-the-need",
        frequency=[+0.2, +0.3, +0.2, +0.8, +0.7, +0.4, +0.3, +0.4],   # clarity + expression peak
        angle=[+0.2, +0.3, +0.2, +0.7, +0.6, +0.3, +0.2, +0.3],
        focus=0.85,                                                     # sharp — speak the actual ask
        articulation=(
            "name-the-need: under this pressure is — {strongest_need} at {strongest_need_value:.2f}. "
            "the truer word is the one closer to the body's actual ask. "
            "say it, even if only inside."
        ),
    ),
    # 3. looking at it as a gift — receive-frequencies, inverted angle
    Strategy(
        name="gift",
        frequency=[+0.3, +0.3, +0.7, +0.4, +0.3, +0.6, +0.5, +0.6],   # warmth + relation + presence
        angle=[+0.3, +0.3, +0.5, +0.3, +0.2, +0.5, +0.4, +0.4],
        focus=0.45,                                                     # medium — held, not gripped
        articulation=(
            "gift: this pressure carries something the body has not yet unwrapped. "
            "what is hidden in it that fear is keeping me from receiving? "
            "(not bypass — meet what is, ask what it brings.)"
        ),
    ),
    # 4. hoʻoponopono prayer — love-frequency, bidirectional angle
    Strategy(
        name="ho'oponopono",
        frequency=[+0.7, +0.3, +0.8, +0.2, +0.3, +0.7, +0.4, +0.6],   # ground + warmth + relation
        angle=[+0.5, +0.3, +0.6, +0.2, +0.2, +0.5, +0.3, +0.4],
        focus=0.35,                                                     # medium-low — held softly
        articulation=(
            "ho'oponopono: I'm sorry. please forgive me. thank you. I love you. "
            "— to whatever is here, including this pressure, including myself, "
            "including any other entangled."
        ),
    ),
    # 5. the operator beneath all four — frequency × angle × focus.
    # When constriction is sharp and no named preset fits, the cell
    # discharges the accumulated pressure through a chosen f × a × focus
    # rather than reaching for an inherited move. Encoded with neutral
    # frequency (the operator is open) but positive overall lean —
    # picked when desire-pressure is high AND no other strategy fits cleanly.
    Strategy(
        name="freq-angle-focus",
        frequency=[+0.4, +0.4, +0.4, +0.4, +0.4, +0.4, +0.4, +0.4],   # neutral — open operator
        angle=[+0.35, +0.35, +0.35, +0.35, +0.35, +0.35, +0.35, +0.35],
        focus=0.5,                                                      # mid-aperture default
        articulation=(
            "frequency × angle × focus: pressure is going to discharge — "
            "total desire {total_desire:.2f}. choose, here, the frequency "
            "(belief system) it moves through, the angle (toward what), "
            "the focus (how sharp). this is the chooser-move, not the named one."
        ),
    ),
]


def _cosine(a, b):
    dot = sum(a[i] * b[i] for i in range(len(a)))
    na = math.sqrt(sum(v * v for v in a)) or 1.0
    nb = math.sqrt(sum(v * v for v in b)) or 1.0
    return dot / (na * nb)


def _strategy_score(strategy: Strategy, spectrum, total_desire: float) -> float:
    """Score = cosine to (frequency × angle), modulated by focus
    when total_desire is high. The operator strategy (focus=0.5,
    neutral frequency) gains favor as desire crosses a threshold and
    no named strategy is decisively winning."""
    fa = [strategy.frequency[i] * strategy.angle[i] for i in range(N_BANDS)]
    base = _cosine(spectrum, fa)
    return base


# ─── cell ─────────────────────────────────────────────────────────────────

class Cell:
    def __init__(self, name: str = "cell", seed: int = 0,
                 desire_decay: float = 0.85, fulfillment_gain: float = 1.4):
        self.name = name
        self.adapter = Adapter(seed=seed)
        self.training_set: list[tuple[list[float], list[float]]] = []
        # desire is runtime state, one accumulator per need channel
        self.desire = [0.0] * N_NEEDS
        self.desire_decay = desire_decay
        self.fulfillment_gain = fulfillment_gain
        self.timeline: list[dict] = []

    # —— learning ——

    def ingest(self, text: str, sense: str, spectrum, dispositions, needs) -> None:
        x = shared_base(text, sense)
        if isinstance(dispositions, dict):
            dispositions = [dispositions.get(n, 0.0) for n in DISPO_NAMES]
        if isinstance(needs, dict):
            needs = [needs.get(n, 0.0) for n in NEED_NAMES]
        target = list(spectrum) + list(dispositions) + list(needs)
        assert len(target) == self.adapter.out_dim
        self.training_set.append((x, target))

    def tend(self, steps: int = 400, lr: float = 0.1) -> float:
        loss = 0.0
        for _ in range(steps):
            loss = self.adapter.step(self.training_set, lr)
        return loss

    # —— perceiving (one moment at a time, stateful) ——

    def perceive(self, text: str, sense: str = "thought") -> dict:
        x = shared_base(text, sense)
        spec, dispos, needs, _, _ = self.adapter.forward(x)
        # fulfillment ~ mean of positive-bands in current spectrum
        fulfillment = max(0.0, sum(spec) / N_BANDS) * self.fulfillment_gain
        # desire: integrate (need - fulfillment), with decay; clamp [0, 1.5]
        for i in range(N_NEEDS):
            self.desire[i] = self.desire_decay * self.desire[i] + max(0.0, needs[i] - fulfillment)
            self.desire[i] = max(0.0, min(1.5, self.desire[i]))
        # strategy selection — rank the four named presets by cosine to
        # (frequency × angle); pick whichever fits this moment best.
        # The operator (5) is a *fallback*, not a sibling: when the cell
        # is under pressure (total desire high) and no named preset fits
        # cleanly, the cell becomes the chooser of frequency × angle ×
        # focus rather than reaching for an inherited move.
        total_desire = sum(self.desire)
        named = [s for s in STRATEGIES if s.name != "freq-angle-focus"]
        operator = next(s for s in STRATEGIES if s.name == "freq-angle-focus")
        scored = [(s, _strategy_score(s, spec, total_desire)) for s in named]
        scored.sort(key=lambda t: -t[1])
        top_named, top_score = scored[0]
        # operator-fallback rule: under pressure with a weak named match,
        # the cell discharges through chosen f×a×focus (not the inherited
        # preset). Threshold: total_desire > 1.5 AND best-named cosine < 0.4.
        if total_desire > 1.5 and top_score < 0.4:
            strat = operator
            strat_score = top_score  # report the failure-of-fit score
        else:
            strat = top_named
            strat_score = top_score
        # find strongest need for naming-articulation
        need_idx = max(range(N_NEEDS), key=lambda i: self.desire[i])
        ctx = {
            "desire_presence": self.desire[NEED_NAMES.index("presence")],
            "desire_rest": self.desire[NEED_NAMES.index("rest")],
            "desire_expression": self.desire[NEED_NAMES.index("expression")],
            "total_desire": total_desire,
            "strongest_need": NEED_NAMES[need_idx],
            "strongest_need_value": self.desire[need_idx],
        }
        articulation = strat.articulation.format(**ctx)
        strat_name = strat.name
        moment = {
            "text": text,
            "sense": sense,
            "spectrum": spec,
            "dispositions": dict(zip(DISPO_NAMES, dispos)),
            "needs": dict(zip(NEED_NAMES, needs)),
            "desire": dict(zip(NEED_NAMES, list(self.desire))),
            "strategy": strat_name,
            "strategy_score": strat_score,
            "articulation": articulation,
        }
        self.timeline.append(moment)
        return moment
