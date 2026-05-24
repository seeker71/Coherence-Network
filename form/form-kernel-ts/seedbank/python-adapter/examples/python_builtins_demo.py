# python_builtins_demo.py — exercises sum, min, max, abs builtins +
# augmented assignment (+=, *=). Pure Python; identical results across
# CPython and the native kernel.

def stats(values):
    total = sum(values)
    smallest = min(values)
    biggest = max(values)
    return total + smallest + biggest

def absolute_distance_from_target(values, target):
    d = 0
    for v in values:
        d += abs(v - target)
    return d

values = [3, 17, 8, 22, 5, 14]
target = 10

s = stats(values)
dist = absolute_distance_from_target(values, target)

s + dist
