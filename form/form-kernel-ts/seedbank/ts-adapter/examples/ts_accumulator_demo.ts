// ts_accumulator_demo.ts — recursion-as-loop. The kernel has no loop arm,
// so accumulator passing is the form-native way to iterate. Same pattern
// the python-adapter uses to lower while-loops; here we write it directly
// in TS so the parity check exercises the whole emission path.

function loop(i, acc) {
    return i >= 10 ? acc : loop(i + 1, acc + i);
}

loop(0, 0)
