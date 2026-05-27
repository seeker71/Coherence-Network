// ts_arith_demo.ts — pure-arithmetic round trip; the simplest closing breath
// through the TS → .fk → kernel pipeline.
//
// The trailing bare expression is the value all three runtimes converge on.

const a = 7;
const b = 3;
const c = a * b + (a - b);

c
