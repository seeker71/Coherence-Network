# python_demo.py — non-trivial Python parsed and executed through the
# form-kernel-ts BMF Python language cell. BMF coverage today is
# functional Python: def, recursion, conditional expressions, arithmetic,
# comparisons, logic, function calls. Assignment + iteration land in a
# follow-up breath; this demo stays pure-recursive to exercise the surface
# that's actually shipped.
#
# The whole program runs through the Form-kernel walker (for native
# dispatches) and the Python CTOR evaluator (for Form-shape dispatches);
# both surfaces are visible in the python-trace JSON output.
#
# Usage:
#   python3 scripts/viz_kernel_trace.py seedbank/python-adapter/examples/python_demo.py

def fact(n):
    return 1 if n < 2 else n * fact(n - 1)

def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)

def ackermann(m, n):
    return n + 1 if m == 0 else ackermann(m - 1, 1) if n == 0 else ackermann(m - 1, ackermann(m, n - 1))

def is_prime_helper(n, i):
    return True if i * i > n else False if n % i == 0 else is_prime_helper(n, i + 1)

def is_prime(n):
    return False if n < 2 else is_prime_helper(n, 2)

def count_primes_helper(n, limit, count):
    return count if n >= limit else count_primes_helper(n + 1, limit, count + (1 if is_prime(n) else 0))

def count_primes(limit):
    return count_primes_helper(2, limit, 0)

count_primes(30) + fact(8) + fib(15) + ackermann(2, 3)
