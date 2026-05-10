"""Smallest real cell: shared base (frozen) + local adapter (LoRA-shaped, learned).

Architecture sketch:
    text  ──►  shared_base(text)  ──►  LocalAdapter  ──►  felt-axes [coherence, aliveness]
              (deterministic,                (rank-r, learned per cell)
               same for every cell)

The shared base is a deterministic feature map every cell uses identically.
The local adapter is a tiny rank-r projection — the only thing that learns.
Training signal is felt-data: the cell's own resonance on a frequency spectrum.
"""

import math
import random
import zlib


# ─── shared base ──────────────────────────────────────────────────────────
# Frozen. Identical across cells. Bag-of-word-hashes, L2-normalized.
# This is "what every cell already knows because it's part of one body."

DIM = 128


def shared_base(text: str, dim: int = DIM) -> list[float]:
    vec = [0.0] * dim
    for word in text.lower().split():
        h = zlib.crc32(word.encode()) % dim
        vec[h] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


# ─── local adapter ────────────────────────────────────────────────────────
# LoRA-shaped: y = tanh(B @ A @ x + bias),  A: r×D,  B: out×r.
# For our v0: D=128, r=4, out=2 → ~520 trainable floats. The cell's local layer.

class LocalAdapter:
    def __init__(self, in_dim: int = DIM, rank: int = 4, out_dim: int = 2, seed: int = 0):
        rng = random.Random(seed)
        s = 0.1
        self.A = [[rng.gauss(0, s) for _ in range(in_dim)] for _ in range(rank)]
        self.B = [[rng.gauss(0, s) for _ in range(rank)] for _ in range(out_dim)]
        self.bias = [0.0] * out_dim
        self.in_dim, self.rank, self.out_dim = in_dim, rank, out_dim

    def forward(self, x: list[float]):
        h = [sum(self.A[i][k] * x[k] for k in range(self.in_dim)) for i in range(self.rank)]
        z = [sum(self.B[i][j] * h[j] for j in range(self.rank)) + self.bias[i]
             for i in range(self.out_dim)]
        y = [math.tanh(v) for v in z]
        return y, h, z

    def backward(self, x, h, z, grad_y):
        # tanh derivative
        grad_z = [grad_y[i] * (1 - math.tanh(z[i]) ** 2) for i in range(self.out_dim)]
        grad_bias = list(grad_z)
        grad_B = [[grad_z[i] * h[j] for j in range(self.rank)] for i in range(self.out_dim)]
        grad_h = [sum(grad_z[i] * self.B[i][j] for i in range(self.out_dim)) for j in range(self.rank)]
        grad_A = [[grad_h[i] * x[k] for k in range(self.in_dim)] for i in range(self.rank)]
        return grad_A, grad_B, grad_bias

    def step(self, gA, gB, gbias, lr: float):
        for i in range(self.rank):
            for k in range(self.in_dim):
                self.A[i][k] -= lr * gA[i][k]
        for i in range(self.out_dim):
            for j in range(self.rank):
                self.B[i][j] -= lr * gB[i][j]
            self.bias[i] -= lr * gbias[i]

    def effective_weights(self, out_idx: int) -> list[float]:
        # collapsed B@A row for one output: shows what feature buckets the cell weighs
        return [sum(self.B[out_idx][r] * self.A[r][f] for r in range(self.rank))
                for f in range(self.in_dim)]


# ─── cell ─────────────────────────────────────────────────────────────────

class Cell:
    def __init__(self, name: str = "cell", seed: int = 0, axes: tuple[str, ...] = ("coherence", "aliveness")):
        self.name = name
        self.axes = axes
        self.adapter = LocalAdapter(rank=4, out_dim=len(axes), seed=seed)
        self.memory: list[tuple[str, list[float], list[float]]] = []  # (text, x, felt)

    def sense(self, text: str) -> list[float]:
        x = shared_base(text)
        y, _, _ = self.adapter.forward(x)
        return y

    def ingest(self, text: str, felt: list[float]) -> None:
        assert len(felt) == self.adapter.out_dim, "felt vector must match cell's axes"
        self.memory.append((text, shared_base(text), felt))

    def tend(self, steps: int = 300, lr: float = 0.1) -> float:
        if not self.memory:
            return 0.0
        last_loss = 0.0
        n = len(self.memory)
        for _ in range(steps):
            gA = [[0.0] * self.adapter.in_dim for _ in range(self.adapter.rank)]
            gB = [[0.0] * self.adapter.rank for _ in range(self.adapter.out_dim)]
            gbias = [0.0] * self.adapter.out_dim
            total = 0.0
            for _, x, felt in self.memory:
                y, h, z = self.adapter.forward(x)
                total += sum((y[i] - felt[i]) ** 2 for i in range(self.adapter.out_dim))
                grad_y = [2 * (y[i] - felt[i]) / n for i in range(self.adapter.out_dim)]
                a, b, c = self.adapter.backward(x, h, z, grad_y)
                for i in range(self.adapter.rank):
                    for k in range(self.adapter.in_dim):
                        gA[i][k] += a[i][k]
                for i in range(self.adapter.out_dim):
                    for j in range(self.adapter.rank):
                        gB[i][j] += b[i][j]
                    gbias[i] += c[i]
            self.adapter.step(gA, gB, gbias, lr)
            last_loss = total / n
        return last_loss
