# python_assign_demo.py — exercises the assign + subscript surface
# shipped in PR #1793. Computes through assignment, list indexing,
# def, return, conditional expression, arithmetic. Result: 45.
#
# Runs identically under:
#   python3 python_assign_demo.py        — CPython
#   kernel-bmf-run <file.py>     — kernel-bmf-run
#   form-kernel-rust python_assign_demo.fk — native kernel binary

def add(a, b):
    return a + b

result = add(10, 20)
xs = [1, 2, 3, 4, 5]
total = xs[0] + xs[1] + xs[2] + xs[3] + xs[4]
result + total
