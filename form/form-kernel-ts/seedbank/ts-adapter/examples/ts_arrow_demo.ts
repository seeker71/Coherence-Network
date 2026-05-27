// ts_arrow_demo.ts — arrow functions captured as CTOR.lambda_, lifted to
// module-level defns the kernel can bind. Companion shape to Python's
// `lambda x: x + 1`.

const double = (x) => x * 2;
const sq = (n) => n * n;
const add = (a, b) => a + b;

add(double(5), sq(6))
