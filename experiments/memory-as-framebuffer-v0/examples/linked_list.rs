//! Linked list over the framebuffer. Allocates 20 `Tracked<u32>` value cells
//! and 20 `Pointer<u32>` cells linking them in order; a head pointer lives at
//! cell index 0. The pointer chain stays static; the loop mutates value cells
//! so the colors flowing through the pointers' transparent inner regions
//! visibly drift.
//!
//! The "glass corridor" effect: 20 pointer cells laid out in a row, each
//! transparent — looking at pointer[i] you see val[i+1]'s color, not the
//! pointer's own opaque address. Aliasing is also demoed: the head pointer
//! and pointer[N-1] (the tail's "next") both target val[0] and so render the
//! same inner color.

use mfb::{init_framebuffer, shutdown_framebuffer, track, Pointer, Tracked};

const N: usize = 20;
const TOTAL: u32 = 10_000;

fn main() {
    init_framebuffer("linked_list.mp4").expect("init framebuffer");

    // Allocate the head pointer first so it lands at cell index 0.
    // It self-targets initially (cycle terminator inner) until we repoint
    // it at values[0] below.
    let mut head: Pointer<u32> = Pointer::<u32>::new_self_raw();
    assert_eq!(head.handle().index(), 0, "head must land at cell 0");

    // Allocate the 20 value cells, in order.
    let mut values: Vec<Tracked<u32>> = (0..N).map(|i| Tracked::new(i as u32)).collect();

    // Allocate the 20 pointer cells. ptr[i] -> values[(i+1) % N].
    // The wrap-around at i=N-1 (ptr[N-1] -> values[0]) gives the aliasing
    // demo: both head and ptr[N-1] target values[0], so their inner regions
    // match (same color), while their halos differ (different file:line
    // provenance).
    let pointers: Vec<Pointer<u32>> = (0..N)
        .map(|i| Pointer::<u32>::new_raw(values[(i + 1) % N].handle()))
        .collect();

    // Now repoint head at values[0] from this very call site (provenance
    // restamps so head's halo refreshes to a Box-distinct color).
    head.repoint(values[0].handle());

    // Hold pointer cells live for the duration of the run.
    let _keep_pointers = pointers;

    for n in 1..=TOTAL {
        // Mutate every value cell with a per-position spread so each cell's
        // color in the corridor visibly differs from its neighbors.
        for (i, v) in values.iter_mut().enumerate() {
            let new_val = n.wrapping_mul((i as u32).wrapping_add(1));
            track!(v, new_val);
        }
        // Pace so the snapshot thread captures meaningful change.
        std::thread::sleep(std::time::Duration::from_micros(500));
    }

    drop(_keep_pointers);
    drop(values);
    drop(head);

    shutdown_framebuffer();
}
