# python_range_demo.py — exercises range() across the kernel.
# Computes Σ(i² + i) for i in [0, 50). Uses range native shipped in
# this breath. Pure Python + native kernel agree.

def sq(n):
    return n * n

def sum_squares_plus_self(limit):
    total = 0
    for i in range(limit):
        total = total + sq(i) + i
    return total

sum_squares_plus_self(50)
