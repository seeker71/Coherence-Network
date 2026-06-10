# python_float_demo.py — float arithmetic through the full Python →
# Form → native-kernel pipeline. Closes the "kernel is int-only today"
# gap named in kernels/PYTHON_PIPELINE_STATUS.md.
#
# Every operand is chosen so the IEEE 754 result is EXACT (sums of
# binary fractions whose denominators are powers of 2). That keeps the
# three-way parity gate honest at the byte level — no precision drift
# between CPython, kernel-bmf-run, and the form-kernel-rust binary,
# regardless of how each runtime renders the final float.
#
# Runs identically under:
#   python3 python_float_demo.py             — CPython
#   kernel-bmf-run <file.py>        — kernel-bmf-run
#   form-kernel-rust python_float_demo.fk    — native kernel binary

def lerp(a, b, t):
    return a + (b - a) * t

def coherence_score(signal, vitality, weight):
    # Weighted average — the substrate's bread-and-butter shape.
    # Coherence scores live in [0.0, 1.0]; arithmetic on them was the
    # load-bearing reason floats had to land.
    return signal * weight + vitality * (1.0 - weight)

def is_above(score, threshold):
    return score >= threshold

# Mixed int / float — the int operand promotes through the MATH arm.
mixed = 2 + 0.5                              # 2.5

# Pure float arithmetic — exact in IEEE 754.
midpoint = lerp(0.25, 0.75, 0.5)             # 0.5
score    = coherence_score(0.5, 1.0, 0.25)   # 0.5 * 0.25 + 1.0 * 0.75 = 0.875
high     = is_above(score, 0.5)              # True

# Float comparison through the COMPARE arm's promotion path.
delta    = score - midpoint                   # 0.375

# Division between floats — IEEE 754 division, exact for power-of-two
# operands. (Int / int still floors to int on the kernel side; mixing
# in a float here forces the float-promotion arm.)
ratio    = (score + delta) / 2.0              # (0.875 + 0.375) / 2.0 = 0.625

# Final expression: 2.5 + 0.5 + 0.875 + 0.375 + 0.625 = 4.875.
# Both Python's `print(4.875)` and Rust's `{}` format of 4.875_f64
# produce "4.875" — no trailing-zero or scientific-notation drift.
mixed + midpoint + score + delta + ratio
