// ts_composition_demo.ts — multi-function composition with branching.
// Exercises the full CPS-lowering path for nested if/else with early
// returns inside a function body.

function classify(n) {
    if (n < 0) {
        return -1;
    } else if (n === 0) {
        return 0;
    } else {
        return 1;
    }
}

function abs(n) {
    return n < 0 ? -n : n;
}

function combine(a, b) {
    return classify(a) * abs(b) + classify(b) * abs(a);
}

combine(-3, 5) + combine(7, -2)
