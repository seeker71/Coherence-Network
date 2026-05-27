// ts_recursion_demo.ts — function declaration with recursion. Cross-language
// identity test: this compiles to the same CTOR.def_/CTOR.call shape as
// the Python `def fact(n)`; the .fk emission and the kernel arm trace
// agree across siblings.

function fact(n) {
    return n < 2 ? 1 : n * fact(n - 1);
}

fact(8)
