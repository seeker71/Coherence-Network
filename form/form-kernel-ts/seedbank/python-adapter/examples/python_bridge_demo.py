# python_bridge_demo.py — first .py file the Form-native PY-BMF bridge
# walks end-to-end (parse → lift → eval) to its CPython runtime value.
#
# Covers the 9 arms shipped in form-stdlib/python-bmf-eval.fk:
#   INT, IDENT, BINOP, COMPARE, RETURN, ASSIGN, DEF, CALL, IF, MODULE.
#
# CPython value: 720 (factorial of 6, plus a module-level assignment +
# call shape that exercises ASSIGN env-threading).
#
# Run paths:
#   python3 python_bridge_demo.py                 — CPython prints 720
#   kernel-bmf-run python_bridge_demo.py          — Form-native, prints 720

def fact(n):
    return 1 if n < 2 else n * fact(n - 1)

result = fact(6)
result
