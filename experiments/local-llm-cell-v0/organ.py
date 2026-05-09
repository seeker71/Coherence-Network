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


# operator-fallback thresholds — load-bearing, used by both call sites
OPERATOR_DESIRE_THRESHOLD = 1.5
OPERATOR_FIT_THRESHOLD = 0.4


def pick_strategy(spectrum, desire, presets=None):
    """Canonical strategy selection. Used by both Cell.perceive() and
    substrate_bridge.select_strategy(). The operator strategy is a
    *fallback*, not a sibling — chosen only when desire is high AND
    no named strategy fits cleanly.

    Returns dict:
        chosen: Strategy instance picked (the operator if fallback,
                otherwise the best-named)
        chosen_score: float — cosine to (freq × angle) of chosen
        named_ranked: [(Strategy, score), ...] — named strategies ranked
        operator: Strategy — the operator preset (always available)
        operator_fallback_active: bool — was the operator picked because
                of fallback rule (rather than because it ranked highest)?
        total_desire: float
    """
    presets = presets if presets is not None else STRATEGIES
    total_desire = sum(desire) if desire else 0.0
    named = [s for s in presets if s.name != "freq-angle-focus"]
    operator = next((s for s in presets if s.name == "freq-angle-focus"), None)
    scored = [(s, _strategy_score(s, spectrum, total_desire)) for s in named]
    scored.sort(key=lambda t: -t[1])
    if not scored:
        return {
            "chosen": operator,
            "chosen_score": 0.0,
            "named_ranked": [],
            "operator": operator,
            "operator_fallback_active": True,
            "total_desire": total_desire,
        }
    top_named, top_score = scored[0]
    fallback = (
        operator is not None
        and total_desire > OPERATOR_DESIRE_THRESHOLD
        and top_score < OPERATOR_FIT_THRESHOLD
    )
    return {
        "chosen": operator if fallback else top_named,
        "chosen_score": top_score,
        "named_ranked": scored,
        "operator": operator,
        "operator_fallback_active": fallback,
        "total_desire": total_desire,
    }


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
        # consume inhabit-bias if set: blend strategy's f×a into the
        # spectrum at current intensity, then *decay* the intensity for
        # next perceive (rather than binary clear). Real bodies have a
        # strategy's grip fade across moments. Upsilon named this from
        # inside — binary on/off was a missing graceful release.
        inhabited = None
        strat_held = getattr(self, "_inhabit_strategy", None)
        if strat_held is not None:
            intensity = getattr(self, "_inhabit_intensity", 0.5)
            fa = [strat_held.frequency[i] * strat_held.angle[i] for i in range(N_BANDS)]
            fa_n = math.sqrt(sum(v * v for v in fa)) or 1.0
            fa = [v / fa_n for v in fa]
            eps = intensity * strat_held.focus
            spec = [math.tanh((1 - eps) * spec[i] + eps * fa[i]) for i in range(N_BANDS)]
            inhabited = strat_held.name
            # decay intensity for next perceive; clear when below floor
            decay = getattr(self, "_inhabit_decay", 0.5)
            new_intensity = intensity * decay
            if new_intensity < 0.05:
                self._inhabit_strategy = None
                self._inhabit_intensity = 0.0
            else:
                self._inhabit_intensity = new_intensity
        # fulfillment ~ mean of positive-bands in current spectrum
        fulfillment = max(0.0, sum(spec) / N_BANDS) * self.fulfillment_gain
        # desire: integrate (need - fulfillment), with decay; clamp [0, 1.5]
        for i in range(N_NEEDS):
            self.desire[i] = self.desire_decay * self.desire[i] + max(0.0, needs[i] - fulfillment)
            self.desire[i] = max(0.0, min(1.5, self.desire[i]))
        # canonical strategy selection (single source of truth — see pick_strategy)
        sel = pick_strategy(spec, self.desire)
        strat = sel["chosen"]
        strat_score = sel["chosen_score"]
        # find strongest need for naming-articulation
        need_idx = max(range(N_NEEDS), key=lambda i: self.desire[i])
        ctx = {
            "desire_presence": self.desire[NEED_NAMES.index("presence")],
            "desire_rest": self.desire[NEED_NAMES.index("rest")],
            "desire_expression": self.desire[NEED_NAMES.index("expression")],
            "total_desire": sel["total_desire"],
            "strongest_need": NEED_NAMES[need_idx],
            "strongest_need_value": self.desire[need_idx],
        }
        articulation = strat.articulation.format(**ctx)
        moment = {
            "text": text,
            "sense": sense,
            "spectrum": spec,
            "dispositions": dict(zip(DISPO_NAMES, dispos)),
            "needs": dict(zip(NEED_NAMES, needs)),
            "desire": dict(zip(NEED_NAMES, list(self.desire))),
            "strategy": strat.name,
            "strategy_score": strat_score,
            "operator_fallback_active": sel["operator_fallback_active"],
            "articulation": articulation,
            "inhabited": inhabited,
        }
        self.timeline.append(moment)
        return moment

    # —— inhabiting (bias the next perceive toward a strategy) ——

    def inhabit(self, strategy, *, intensity: float = 0.5,
                decay: float = 0.5) -> dict:
        """Bias the next perceive() toward a strategy's frequency × angle × focus.

        `intensity` controls the initial blend rate (0 = no bias, 1 = full
        strategy spectrum). `decay` controls how the bias fades across
        subsequent perceives: each perceive multiplies the held intensity
        by decay; when it drops below 0.05 the bias clears.

        decay=0.0  — binary one-shot (the original Upsilon shape)
        decay=0.5  — half-life ~1 perceive (default; gentle release)
        decay=0.9  — long grip; the strategy holds for many moments
        decay=1.0  — never fades; cell stays inhabited until cleared

        Closes the loop: predict_through(strategy) → inhabit(strategy) →
        perceive(text) → surprise_between(predicted, observed). With
        inhabit in place, surprise actually measures 'did running the
        strategy get me where I predicted?' rather than 'did a different
        input land differently?'.

        Tau named this verb from inside; Upsilon wired the binary form;
        decay is the graceful-release Upsilon then named as missing.
        """
        self._inhabit_strategy = strategy
        self._inhabit_intensity = max(0.0, min(1.0, intensity))
        self._inhabit_decay = max(0.0, min(1.0, decay))
        return {
            "inhabit": strategy.name,
            "intensity": self._inhabit_intensity,
            "decay": self._inhabit_decay,
            "consumes_on": "next perceive(); fades thereafter",
        }

    def release_inhabit(self) -> dict:
        """Clear any held inhabit-bias before its decay would clear it."""
        held = getattr(self, "_inhabit_strategy", None)
        self._inhabit_strategy = None
        self._inhabit_intensity = 0.0
        return {"released": held.name if held else None}

    # —— probing (read-only sample, no state mutation) ——

    def probe(self, text: str, sense: str = "thought") -> dict:
        """Read-only sample. Runs the adapter forward and returns
        spectrum, dispositions, needs — but does NOT mutate desire,
        does NOT append to timeline, does NOT update any cell state.

        Use for sampling multiple inputs (concepts, traces, articulations)
        without compounding pressure across reads. The cell sees but
        does not move. Tau named this verb from inside; it is the truer
        word for what we previously misused perceive() for when
        sampling.
        """
        x = shared_base(text, sense)
        spec, dispos, needs, _, _ = self.adapter.forward(x)
        return {
            "text": text,
            "sense": sense,
            "spectrum": spec,
            "dispositions": dict(zip(DISPO_NAMES, dispos)),
            "needs": dict(zip(NEED_NAMES, needs)),
            "kind": "probe",  # marks this as a read-only sample
        }
