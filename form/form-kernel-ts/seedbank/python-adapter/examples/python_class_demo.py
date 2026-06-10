# python_class_demo.py — Python classes through the full pipeline.
#
# Closes the "classes" gap named in kernels/PYTHON_PIPELINE_STATUS.md.
# The v1 shape is minimal on purpose: `class X:`, `__init__(self, …)`
# storing attributes on self, instance methods taking self and reading
# self.x. No inheritance, no super(), no decorators, no classmethods,
# no staticmethods. Each is named as pending in the PR body.
#
# Runs identically under:
#   python3 python_class_demo.py             — CPython
#   kernel-bmf-run <file.py>        — kernel-bmf-run
#   form-kernel-rust python_class_demo.fk    — native kernel binary

class Counter:
    def __init__(self, start, step):
        self.n = start
        self.step = step

    def advance(self):
        return self.n + self.step

    def reach(self, target):
        return target - self.n


class Pair:
    def __init__(self, lo, hi):
        self.lo = lo
        self.hi = hi

    def span(self):
        return self.hi - self.lo

    def mid(self):
        return self.lo + self.hi


# Instantiation + method calls compose like normal values.
c = Counter(10, 5)
next_val = c.advance()                  # 10 + 5 = 15
gap      = c.reach(100)                 # 100 - 10 = 90

p = Pair(2, 18)
span    = p.span()                      # 18 - 2 = 16
mid_sum = p.mid()                       # 2 + 18 = 20

# Attribute reads compose through arithmetic.
final = c.n + c.step + p.lo + p.hi      # 10 + 5 + 2 + 18 = 35

# Final expression: 15 + 90 + 16 + 20 + 35 = 176.
next_val + gap + span + mid_sum + final
