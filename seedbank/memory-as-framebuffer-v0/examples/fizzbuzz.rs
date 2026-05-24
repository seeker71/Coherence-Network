//! Fizzbuzz over the framebuffer. Allocates 100 Tracked<u32> cells:
//! cell[0] holds the current i; cells[1..100] are a rolling history of
//! fizz/buzz/fizzbuzz/plain tags. As the loop runs, the heap visibly
//! breathes: cell[0] pulses, the history strip shifts hue, and halos
//! shimmer because each branch (plain/fizz/buzz/fizzbuzz) writes from
//! a different file:line.

use mfb::{init_framebuffer, shutdown_framebuffer, track, Tracked, GRID};

const HISTORY: usize = 99;
const TOTAL: u32 = 10_000;

/// Map sequence position 0..=99 to a 10x10 grid layout in the top-left
/// of the framebuffer. The auto-viewport then renders that 10x10 region
/// nearly full-screen, instead of a 100-wide × 1-tall horizontal sliver.
fn grid_idx(seq: usize) -> usize {
    let gx = seq % 10;
    let gy = seq / 10;
    gy * GRID + gx
}

fn main() {
    init_framebuffer("fizzbuzz.mp4").expect("init framebuffer");

    // Cell at (0, 0): current i.
    // Cells at (1..=9, 0) and (0..=9, 1..=9): rolling history (99 cells).
    let mut current: Tracked<u32> = Tracked::new_at(grid_idx(0), 0u32);
    let mut history: Vec<Tracked<u32>> = (0..HISTORY)
        .map(|i| Tracked::new_at(grid_idx(i + 1), 0u32))
        .collect();

    for n in 1..=TOTAL {
        // 1. write current i.
        track!(current, n);

        // 2. compute fizzbuzz tag.
        let tag = fizzbuzz_tag(n);

        // 3. shift history down: cells[2] = cells[1], ..., cells[99] = cells[98].
        for i in (1..HISTORY).rev() {
            let prev = history[i - 1].get();
            track!(history[i], prev);
        }

        // 4. write new tag at cells[1] (history[0]) using a branch-distinct
        //    track! call site so each tag's halo color is unique.
        match tag {
            1 => write_plain(&mut history[0], 1),
            2 => write_fizz(&mut history[0], 2),
            3 => write_buzz(&mut history[0], 3),
            4 => write_fizzbuzz(&mut history[0], 4),
            _ => write_plain(&mut history[0], 1),
        }

        // 5. pace the loop so the snapshot thread captures meaningful change.
        std::thread::sleep(std::time::Duration::from_micros(500));
    }

    // Drop everything before shutdown so cells go free.
    drop(history);
    drop(current);

    shutdown_framebuffer();
}

fn fizzbuzz_tag(n: u32) -> u32 {
    let f = n % 3 == 0;
    let b = n % 5 == 0;
    match (f, b) {
        (true, true) => 4,
        (true, false) => 2,
        (false, true) => 3,
        (false, false) => 1,
    }
}

#[inline(never)]
fn write_plain(cell: &mut Tracked<u32>, v: u32) {
    track!(cell, v);
}

#[inline(never)]
fn write_fizz(cell: &mut Tracked<u32>, v: u32) {
    track!(cell, v);
}

#[inline(never)]
fn write_buzz(cell: &mut Tracked<u32>, v: u32) {
    track!(cell, v);
}

#[inline(never)]
fn write_fizzbuzz(cell: &mut Tracked<u32>, v: u32) {
    track!(cell, v);
}
