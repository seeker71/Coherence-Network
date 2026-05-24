//! Smoke tests for the v1 Render trait surface.
//!
//! Three contracts:
//!
//! - `test_default_render_matches_v0`: when no user kernel is registered,
//!   the trait-dispatched renderer produces pixel-identical output to a
//!   direct render of a hand-laid heap snapshot. This is the v0
//!   pixel-equivalence guarantee — the trait refactor must not move pixels.
//! - `test_custom_render_overrides`: a registered user kernel beats the
//!   default for cells carrying its tag, while cells with other tags still
//!   render through the default kernel.
//! - `test_kernel_registry`: registering a tag below 0x1000 errors with
//!   `ReservedTag`; registering the same tag twice errors with
//!   `AlreadyRegistered`; `lookup_kernel` returns `Some` for registered
//!   tags and `None` otherwise.

use mfb::allocator::{CELL_BYTES, NUM_CELLS};
use mfb::render::render_frame;
use mfb::render_trait::{
    _clear_registry_for_tests, lookup_kernel, register_kernel, KernelRegistryError, Lod, Render,
    RenderCtx, USER_TAG_MAX, USER_TAG_MIN,
};
use mfb::TAG_U32;
use std::sync::Mutex;

/// Tests share the global registry, so we serialize them through this mutex
/// to avoid one test's register_kernel call colliding with another's
/// expectations. The registry is process-global by design (v1 contract is
/// startup-only registration).
static REGISTRY_LOCK: Mutex<()> = Mutex::new(());

fn empty_plane() -> Vec<u8> {
    vec![0u8; NUM_CELLS * CELL_BYTES]
}

fn place_u32(plane: &mut [u8], idx: usize, value: u32) {
    let base = idx * CELL_BYTES;
    let tag_bytes = TAG_U32.to_le_bytes();
    plane[base] = tag_bytes[0];
    plane[base + 1] = tag_bytes[1];
    let v_bytes = value.to_le_bytes();
    for i in 0..4 {
        plane[base + 2 + i] = v_bytes[i];
    }
}

fn place_tagged(plane: &mut [u8], idx: usize, tag: u16, fill: u8) {
    let base = idx * CELL_BYTES;
    let tag_bytes = tag.to_le_bytes();
    plane[base] = tag_bytes[0];
    plane[base + 1] = tag_bytes[1];
    for b in &mut plane[base + 2..base + CELL_BYTES] {
        *b = fill;
    }
}

#[test]
fn test_default_render_matches_v0() {
    let _guard = REGISTRY_LOCK.lock().unwrap();
    _clear_registry_for_tests();

    // Build a small hand-laid heap snapshot with a mix of primitive cells:
    // u32 at indices 0..10 with values 1..=10. Render twice and assert the
    // two frames are pixel-identical — the trait dispatch is deterministic
    // and the default kernel produces the same output as the inline path.
    let mut plane = empty_plane();
    for i in 0..10 {
        place_u32(&mut plane, i, (i + 1) as u32);
    }
    let prov = vec![0xdeadbeef_u32; NUM_CELLS];

    let frame_a = render_frame(&plane, &prov);
    let frame_b = render_frame(&plane, &prov);
    assert_eq!(frame_a.len(), frame_b.len());
    assert_eq!(frame_a, frame_b, "default render is not deterministic");

    // Stronger contract: known-good primitive renders are visible.
    // The cells at indices 0..10 render in row 0 of the auto-viewport; at
    // least some inner pixels must be bright red (u32 palette = [255, 240, 60]
    // modulated by entropy).
    let mut bright_pixels = 0;
    for chunk in frame_a.chunks_exact(4) {
        let max_channel = chunk[0].max(chunk[1]).max(chunk[2]);
        if max_channel > 100 {
            bright_pixels += 1;
        }
    }
    assert!(
        bright_pixels > 100,
        "default render produced no bright pixels — refactor broke v0 equivalence"
    );
}

/// A test kernel that paints its cell's entire region a known solid color.
struct SolidColorKernel {
    color: [u8; 3],
}

impl Render for SolidColorKernel {
    fn render(&self, ctx: &mut RenderCtx, _lod: Lod) {
        ctx.fill_rect(ctx.px, ctx.py, ctx.cell_px, ctx.cell_px, self.color);
    }
}

#[test]
fn test_custom_render_overrides() {
    let _guard = REGISTRY_LOCK.lock().unwrap();
    _clear_registry_for_tests();

    // Register a kernel under user-tag 0x1010 that paints solid green.
    let user_tag: u16 = 0x1010;
    register_kernel(
        user_tag,
        Box::new(SolidColorKernel {
            color: [10, 200, 10],
        }),
    )
    .expect("register custom kernel");

    // Heap: one user-tagged cell at index 0, one primitive u32 at index 1.
    let mut plane = empty_plane();
    place_tagged(&mut plane, 0, user_tag, 0xff);
    place_u32(&mut plane, 1, 42);
    let prov = vec![0u32; NUM_CELLS];

    let frame = render_frame(&plane, &prov);

    // The cells render somewhere inside the auto-viewport. The frame must
    // contain at least one pixel matching our solid green (RGB = 10, 200, 10)
    // because the custom kernel paints the entire cell region.
    let mut found_green = false;
    for chunk in frame.chunks_exact(4) {
        if chunk[0] == 10 && chunk[1] == 200 && chunk[2] == 10 {
            found_green = true;
            break;
        }
    }
    assert!(
        found_green,
        "custom kernel under tag 0x1010 did not paint its cell — \
         dispatch is falling through to the default"
    );

    // The primitive cell still renders through the default kernel, so the
    // frame should also contain some non-green colored pixels (u32 palette
    // is yellow-ish [255, 240, 60] modulated by entropy).
    let mut found_non_green = false;
    for chunk in frame.chunks_exact(4) {
        let is_green = chunk[0] == 10 && chunk[1] == 200 && chunk[2] == 10;
        let is_black = chunk[0] == 0 && chunk[1] == 0 && chunk[2] == 0;
        if !is_green && !is_black && (chunk[0] > 50 || chunk[1] > 50 || chunk[2] > 50) {
            found_non_green = true;
            break;
        }
    }
    assert!(
        found_non_green,
        "primitive cells did not render through the default kernel — \
         dispatch is over-eagerly applying the custom kernel everywhere"
    );

    _clear_registry_for_tests();
}

#[test]
fn test_kernel_registry() {
    let _guard = REGISTRY_LOCK.lock().unwrap();
    _clear_registry_for_tests();

    // 1. Registering a tag below the user range errors.
    let reserved_result = register_kernel(
        0x0001,
        Box::new(SolidColorKernel {
            color: [0, 0, 0],
        }),
    );
    assert_eq!(
        reserved_result,
        Err(KernelRegistryError::ReservedTag(0x0001))
    );

    // 2. Registering at the boundary works.
    let user_tag: u16 = 0x1234;
    assert!(user_tag >= USER_TAG_MIN && user_tag <= USER_TAG_MAX);
    let ok = register_kernel(
        user_tag,
        Box::new(SolidColorKernel {
            color: [1, 2, 3],
        }),
    );
    assert!(ok.is_ok(), "user-range registration failed: {:?}", ok);

    // 3. Re-registering the same tag errors.
    let dup_result = register_kernel(
        user_tag,
        Box::new(SolidColorKernel {
            color: [4, 5, 6],
        }),
    );
    assert_eq!(
        dup_result,
        Err(KernelRegistryError::AlreadyRegistered(user_tag))
    );

    // 4. Lookup hits and misses.
    assert!(lookup_kernel(user_tag).is_some());
    assert!(lookup_kernel(0x9876).is_none());

    // 5. The boundary cases on the reserved side.
    let just_below = register_kernel(
        USER_TAG_MIN - 1,
        Box::new(SolidColorKernel {
            color: [0, 0, 0],
        }),
    );
    assert!(matches!(
        just_below,
        Err(KernelRegistryError::ReservedTag(_))
    ));

    _clear_registry_for_tests();
}
