# python_import_demo.py — `import math` end-to-end through the full
# Python → Form → native-kernel pipeline. Closes the "imports parsed but
# not wired" gap named in kernels/PYTHON_PIPELINE_STATUS.md.
#
# Two reachable import shapes both compile to noops at runtime — the
# parser rewrites attribute / name lookups to call kernel-native
# bindings directly. The `math` module is the proof-of-shape; user-
# defined module imports remain a separate breath.
#
# Every operand is chosen so the IEEE 754 result is reproducible to the
# bit. Three runtimes (CPython, TS evalPython, form-kernel-rust) walk
# the same expression and produce the same final string.
#
# Runs identically under:
#   python3 python_import_demo.py             — CPython
#   npm run kernel -- python-eval ...         — TS evalPython
#   form-kernel-rust python_import_demo.fk    — native kernel binary

import math
from math import sqrt, pi

# `math.sqrt` — module-attribute access (exact for power-of-two operand).
r = math.sqrt(2.25)              # 1.5

# `from math import sqrt` — direct name binding.
s = sqrt(0.25)                   # 0.5

# `math.pi` and `pi` resolve to the same kernel native, returning the
# IEEE 754 PI constant exactly.
diameter = 2.0 * math.pi         # 6.283185307179586
half     = pi / 2.0              # 1.5707963267948966

# `math.floor` — Python 3 returns int. Promotes to int in the kernel
# return value so the parity gate's string compare stays honest.
quarter  = math.floor(3.7)       # 3

# `math.pow` — returns float (CPython parity; the built-in `pow()` for
# int args would return int — that path isn't part of this demo).
cube     = math.pow(2.0, 3.0)    # 8.0

# Final expression: 1.5 + 0.5 + 6.283185307179586 + 1.5707963267948966
#                  + 3 + 8.0 = 20.853981633974485
r + s + diameter + half + quarter + cube
