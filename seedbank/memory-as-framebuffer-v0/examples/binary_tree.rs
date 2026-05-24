//! Balanced binary tree over the framebuffer. 15 nodes total (1 + 2 + 4 + 8 =
//! depth-4 perfect tree). Each node has a `Tracked<u32>` value cell. Each
//! *internal* node (the 7 non-leaf nodes) holds two `Pointer<u32>` cells —
//! `left` and `right` — pointing at its two children's value cells.
//!
//! The loop mutates only the 8 leaf values. The 7 internal value cells stay
//! fixed; their inner colors don't change. But each internal node's two
//! pointer cells *do* shift: their inner regions show whichever subtree
//! they target, so as the leaf values drift, so does the color seen
//! through every pointer in the tree. Branching glass.
//!
//! Indices in `values`: 0 = root, 1 = root.left, 2 = root.right, then
//! children of node i live at 2i+1 (left) and 2i+2 (right). Leaves are
//! indices 7..15 (8 cells).

use mfb::{init_framebuffer, shutdown_framebuffer, track, Pointer, Tracked};

const N: usize = 15;
const NUM_INTERNAL: usize = 7;
const TOTAL: u32 = 10_000;

fn main() {
    init_framebuffer("binary_tree.mp4").expect("init framebuffer");

    // Allocate the 15 value cells (root first, breadth-first).
    let mut values: Vec<Tracked<u32>> = (0..N).map(|i| Tracked::new(i as u32 + 1)).collect();

    // For each internal node 0..7, allocate (left, right) pointer cells
    // pointing at its two children's value cells (indices 2i+1 and 2i+2).
    let mut pointers: Vec<Pointer<u32>> = Vec::with_capacity(NUM_INTERNAL * 2);
    for i in 0..NUM_INTERNAL {
        let left_target = values[2 * i + 1].handle();
        let right_target = values[2 * i + 2].handle();
        pointers.push(Pointer::<u32>::new_raw(left_target));
        pointers.push(Pointer::<u32>::new_raw(right_target));
    }

    // Sanity: 15 + 14 = 29 cells now allocated.
    assert_eq!(pointers.len(), NUM_INTERNAL * 2);

    for n in 1..=TOTAL {
        // Mutate leaf values only (indices 7..15). The 7 internal value
        // cells stay fixed at their initial values.
        for leaf_idx in 7..N {
            let new_val = n
                .wrapping_mul((leaf_idx as u32).wrapping_add(1))
                .wrapping_add(((leaf_idx as u32) << 8) ^ n);
            track!(values[leaf_idx], new_val);
        }
        std::thread::sleep(std::time::Duration::from_micros(500));
    }

    drop(pointers);
    drop(values);

    shutdown_framebuffer();
}
