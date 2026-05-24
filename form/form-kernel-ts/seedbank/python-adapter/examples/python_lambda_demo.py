# python_lambda_demo.py — Python lambdas through the native kernel.
# Lambdas are inline expressions in Python but the kernel's defn is
# statement-level, so emitFk lifts each lambda to a module-top
# synthetic `_lambda_N` defn and references it by name at the call site.

double = lambda x: x * 2
add = lambda a, b: a + b
sq = lambda n: n * n

result = add(double(5), sq(6))   # 10 + 36 = 46

# Lambdas can be passed as arguments and stored in lists.
fns = [double, sq, lambda x: x + 100]
out = 0
for f in fns:
    out += f(7)
# double(7) + sq(7) + (7+100) = 14 + 49 + 107 = 170

result + out   # 46 + 170 = 216
