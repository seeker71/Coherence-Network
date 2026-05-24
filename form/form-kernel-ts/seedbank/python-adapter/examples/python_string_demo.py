# python_string_demo.py — Python strings through the native kernel.
# Exercises string concat (Python `+` overloaded), len(s), conditional
# selection. Polymorphic `_plus` kernel native dispatches at runtime —
# emitFk routes `+` to `_plus` when any operand is string-like.

def greet(name):
    return "hello, " + name

def banner_length(name, decoration):
    msg = greet(name) + decoration
    return len(msg)

a = banner_length("world", "!")             # len("hello, world!") = 13
b = banner_length("substrate", "!!!")       # len("hello, substrate!!!") = 19
c = banner_length("kernel", "")             # len("hello, kernel") = 13

a + b + c
