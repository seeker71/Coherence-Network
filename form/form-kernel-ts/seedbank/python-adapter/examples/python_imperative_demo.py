# python_imperative_demo.py — imperative Python with while loops,
# assignments, and a helper function. Computes:
#   sum_to(100)           = 5050        (while-loop accumulator)
#   factorial via loop(8) = 40320       (while-loop accumulator)
#   answer = 5050 + 40320 = 45370
#
# The full pipeline through the native kernel:
#   parsePython → emitFk → form-kernel-rust executes
# No CPython runtime in the execution path.

def sum_to(n):
    total = 0
    i = 1
    while i <= n:
        total = total + i
        i = i + 1
    return total

def fact_loop(n):
    result = 1
    i = 1
    while i <= n:
        result = result * i
        i = i + 1
    return result

sum_to(100) + fact_loop(8)
