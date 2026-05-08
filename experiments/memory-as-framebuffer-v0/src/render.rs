//! Render the slab + provenance plane into a 1024x1024 RGBA frame.
//! Each cell occupies a 4x4 px block: outer ring = provenance halo,
//! inner 2x2 = type-tagged value with brightness from payload entropy.

use crate::allocator::{CELL_BYTES, GRID, NUM_CELLS};
use crate::pointer::{
    decode_pointer_target, is_pointer_tag, PointerKind, CYCLE_TERMINATOR_RGB, POINTER_FOLLOW_CAP,
};
use crate::{
    TAG_BOOL, TAG_F32, TAG_F64, TAG_FREE, TAG_I32, TAG_I64, TAG_U16, TAG_U32, TAG_U64, TAG_U8,
};

pub const RENDER_W: usize = GRID * 4; // 1024
pub const RENDER_H: usize = GRID * 4; // 1024
pub const FRAME_BYTES: usize = RENDER_W * RENDER_H * 4; // RGBA

/// One frame's RGBA buffer (length FRAME_BYTES).
pub type FrameRgba = Vec<u8>;

/// Deterministic 9-entry palette for type tags (and one entry for "free" = black).
/// Chosen for distinctness on a black background.
pub fn type_palette(tag: u16) -> [u8; 3] {
    match tag {
        TAG_FREE => [0, 0, 0],
        TAG_U8 => [255, 80, 80],
        TAG_U16 => [255, 160, 60],
        TAG_U32 => [255, 240, 60],
        TAG_U64 => [120, 230, 80],
        TAG_I32 => [80, 230, 230],
        TAG_I64 => [80, 140, 255],
        TAG_BOOL => [200, 80, 255],
        TAG_F32 => [255, 100, 200],
        TAG_F64 => [240, 240, 240],
        _ => [128, 128, 128], // unknown
    }
}

/// Read a cell's tag at the given index from the raw data plane bytes.
fn read_tag_at(data_bytes: &[u8], idx: usize) -> u16 {
    let base = idx * CELL_BYTES;
    u16::from_le_bytes([data_bytes[base], data_bytes[base + 1]])
}

/// Read a cell's 14-byte payload at the given index from the raw data plane.
fn read_payload_at(data_bytes: &[u8], idx: usize) -> [u8; 14] {
    let base = idx * CELL_BYTES;
    let mut out = [0u8; 14];
    out.copy_from_slice(&data_bytes[base + 2..base + CELL_BYTES]);
    out
}

/// Compute the inner-region color for a primitive cell from its tag + payload.
/// Free cells render as black; primitives modulate their palette by entropy.
fn primitive_inner(tag: u16, payload: &[u8; 14]) -> [u8; 3] {
    if tag == TAG_FREE {
        [0, 0, 0]
    } else {
        modulate_brightness(type_palette(tag), payload)
    }
}

/// Resolve the inner color for a cell at `idx`, following pointers up to
/// `POINTER_FOLLOW_CAP` hops. Cycles (visited-set) and depth-overflow both
/// return `CYCLE_TERMINATOR_RGB`. A pointer whose target is out-of-range or
/// free also returns the cycle terminator (treat as broken indirection —
/// visibly distinct from any live primitive).
fn resolve_inner_color(data_bytes: &[u8], idx: usize) -> [u8; 3] {
    let mut visited: [usize; POINTER_FOLLOW_CAP + 1] = [usize::MAX; POINTER_FOLLOW_CAP + 1];
    let mut visited_len: usize = 0;
    let mut cur = idx;

    for _hop in 0..=POINTER_FOLLOW_CAP {
        if cur >= NUM_CELLS {
            return CYCLE_TERMINATOR_RGB;
        }
        // Cycle detection: have we visited this cell already?
        for k in 0..visited_len {
            if visited[k] == cur {
                return CYCLE_TERMINATOR_RGB;
            }
        }
        visited[visited_len] = cur;
        visited_len += 1;

        let tag = read_tag_at(data_bytes, cur);
        if !is_pointer_tag(tag) {
            // Reached a primitive (or free). Return its inner color.
            let payload = read_payload_at(data_bytes, cur);
            return primitive_inner(tag, &payload);
        }
        // It's a pointer — follow.
        let payload = read_payload_at(data_bytes, cur);
        let next = decode_pointer_target(&payload) as usize;
        cur = next;
    }
    // Exhausted POINTER_FOLLOW_CAP+1 hops without reaching a primitive.
    CYCLE_TERMINATOR_RGB
}

/// Compute the halo (outer-ring) color for a pointer cell of the given kind.
/// The halo encodes the pointer-kind: raw uses the plain provenance hash;
/// Box paints solid white; Rc paints alternating bright/dim (dotted); Weak
/// halves the provenance brightness.
///
/// Returns (color_a, color_b). For Rc, alternation between a and b along the
/// outer ring renders the dotted pattern. For all other kinds, color_a == color_b.
fn pointer_halo_pair(kind: PointerKind, prov: u32) -> ([u8; 3], [u8; 3]) {
    let base = provenance_halo(prov);
    match kind {
        PointerKind::Raw => (base, base),
        PointerKind::Box_ => ([240, 240, 240], [240, 240, 240]),
        PointerKind::Rc => {
            let bright = [240, 240, 240];
            let dim = [60, 60, 60];
            (bright, dim)
        }
        PointerKind::Weak => {
            let half = [base[0] / 2, base[1] / 2, base[2] / 2];
            (half, half)
        }
    }
}

/// Modulate a base RGB by payload content. Cells must be visibly bright at
/// any nonzero value (the heap is meant to be *seen*); within that floor,
/// payload content drives a hue/value flicker so the eye perceives change.
///
/// Brightness floor is 0.7 of the base palette so even a single-byte value
/// (e.g. `u32 = 1` with payload [1,0,0,...]) renders as a clearly-lit cell
/// rather than a near-black smudge. A small CRC-driven channel offset
/// (±25 per channel, anti-correlated across R/B) makes adjacent values
/// distinguishable as they change.
pub fn modulate_brightness(base: [u8; 3], payload: &[u8; 14]) -> [u8; 3] {
    let nonzero = payload.iter().filter(|b| **b != 0).count() as f32;
    let factor = 0.7 + (nonzero / 14.0) * 0.3;

    // Payload-driven channel offset for value-change flicker.
    let h = crc32fast::hash(payload);
    let offset = ((h % 51) as i16) - 25; // -25..=25

    let r = (base[0] as f32 * factor) as i16 + offset;
    let g = (base[1] as f32 * factor) as i16;
    let b = (base[2] as f32 * factor) as i16 - offset;

    [
        r.clamp(0, 255) as u8,
        g.clamp(0, 255) as u8,
        b.clamp(0, 255) as u8,
    ]
}

/// Convert a u32 provenance hash to an RGB color via HSV
/// (hue = hash % 360, saturation = 1.0, value = 0.5).
pub fn provenance_halo(prov: u32) -> [u8; 3] {
    if prov == 0 {
        return [0, 0, 0]; // no provenance => no halo
    }
    let hue = (prov % 360) as f32;
    let s = 1.0_f32;
    let v = 0.55_f32;
    hsv_to_rgb(hue, s, v)
}

fn hsv_to_rgb(h: f32, s: f32, v: f32) -> [u8; 3] {
    let c = v * s;
    let hp = h / 60.0;
    let x = c * (1.0 - ((hp % 2.0) - 1.0).abs());
    let (r1, g1, b1) = if hp < 1.0 {
        (c, x, 0.0)
    } else if hp < 2.0 {
        (x, c, 0.0)
    } else if hp < 3.0 {
        (0.0, c, x)
    } else if hp < 4.0 {
        (0.0, x, c)
    } else if hp < 5.0 {
        (x, 0.0, c)
    } else {
        (c, 0.0, x)
    };
    let m = v - c;
    [
        ((r1 + m) * 255.0).round() as u8,
        ((g1 + m) * 255.0).round() as u8,
        ((b1 + m) * 255.0).round() as u8,
    ]
}

fn put_px(buf: &mut [u8], x: usize, y: usize, rgb: [u8; 3]) {
    let i = (y * RENDER_W + x) * 4;
    buf[i] = rgb[0];
    buf[i + 1] = rgb[1];
    buf[i + 2] = rgb[2];
    buf[i + 3] = 255;
}

/// Minimum viewport side (in cells) — keeps single-cell-active frames from
/// rendering at absurd zoom (one cell filling 1024px would dominate to the
/// point of looking like a single solid color block).
pub const MIN_VIEWPORT_SIDE: usize = 12;

/// Margin in cells around the active bounding box.
pub const VIEWPORT_MARGIN: usize = 2;

/// Compute the auto-viewport for the current data plane: a square sub-region
/// of the grid that tightly bounds all non-free cells (with margin), clamped
/// to grid bounds and a minimum side. The renderer scales this viewport to
/// fill the output frame so the active heap is always visible regardless
/// of how few cells are allocated or where the allocator put them.
///
/// Returns `(top_left_x, top_left_y, side_in_cells)`.
pub fn compute_active_viewport(data_bytes: &[u8]) -> (usize, usize, usize) {
    let mut min_x: Option<usize> = None;
    let mut min_y: Option<usize> = None;
    let mut max_x: usize = 0;
    let mut max_y: usize = 0;

    for cy in 0..GRID {
        for cx in 0..GRID {
            let idx = cy * GRID + cx;
            let tag = read_tag_at(data_bytes, idx);
            if tag != crate::TAG_FREE {
                if min_x.map_or(true, |v| cx < v) {
                    min_x = Some(cx);
                }
                if min_y.map_or(true, |v| cy < v) {
                    min_y = Some(cy);
                }
                if cx > max_x {
                    max_x = cx;
                }
                if cy > max_y {
                    max_y = cy;
                }
            }
        }
    }

    // No active cells → default viewport is top-left MIN_VIEWPORT_SIDE square.
    let (mn_x, mn_y) = match (min_x, min_y) {
        (Some(x), Some(y)) => (x, y),
        _ => return (0, 0, MIN_VIEWPORT_SIDE),
    };

    // Bounding box dimensions (cells).
    let bbox_w = max_x - mn_x + 1;
    let bbox_h = max_y - mn_y + 1;

    // Square viewport with margin, at least MIN_VIEWPORT_SIDE.
    let side = (bbox_w.max(bbox_h) + 2 * VIEWPORT_MARGIN).max(MIN_VIEWPORT_SIDE);
    let side = side.min(GRID);

    // Center on bbox center, then clamp to grid.
    let center_x = (mn_x + max_x) / 2;
    let center_y = (mn_y + max_y) / 2;
    let half = side / 2;

    let mut tx = center_x.saturating_sub(half);
    let mut ty = center_y.saturating_sub(half);
    if tx + side > GRID {
        tx = GRID - side;
    }
    if ty + side > GRID {
        ty = GRID - side;
    }

    (tx, ty, side)
}

/// Render one frame from a snapshot of the data plane and provenance plane.
/// `data_bytes` must be NUM_CELLS * CELL_BYTES; `provenance` must be NUM_CELLS.
///
/// The frame auto-zooms onto the bounding box of currently-allocated cells
/// (via `compute_active_viewport`), so the active heap fills the rendered
/// frame regardless of how few cells exist or where they sit on the grid.
/// When no cells are allocated, the top-left MIN_VIEWPORT_SIDE square renders
/// as black (matching the empty-heap test contract).
pub fn render_frame(data_bytes: &[u8], provenance: &[u32]) -> FrameRgba {
    debug_assert_eq!(data_bytes.len(), NUM_CELLS * CELL_BYTES);
    debug_assert_eq!(provenance.len(), NUM_CELLS);

    // Initialize with opaque black so any padding around the viewport is
    // valid RGBA rather than fully transparent.
    let mut buf = vec![0u8; FRAME_BYTES];
    for i in (3..FRAME_BYTES).step_by(4) {
        buf[i] = 255;
    }

    let (vx, vy, vside) = compute_active_viewport(data_bytes);
    let cell_px = (RENDER_W / vside).max(1);
    let render_size = cell_px * vside;
    let pad_x = (RENDER_W - render_size) / 2;
    let pad_y = (RENDER_H - render_size) / 2;

    // Inner region: middle (cell_px / 2) × (cell_px / 2) square, at least 1 px.
    // Halo: everything outside the inner square. With small cells (4 px) this
    // matches the v0 geometry; with bigger cells (16+ px) the inner takes
    // proportionally more visual weight.
    let inner_size = (cell_px / 2).max(1);
    let inner_offset = (cell_px - inner_size) / 2;

    for cy_local in 0..vside {
        for cx_local in 0..vside {
            let cx = vx + cx_local;
            let cy = vy + cy_local;
            if cx >= GRID || cy >= GRID {
                continue;
            }
            let idx = cy * GRID + cx;
            let tag = read_tag_at(data_bytes, idx);

            let inner = if is_pointer_tag(tag) {
                resolve_inner_color(data_bytes, idx)
            } else {
                let payload = read_payload_at(data_bytes, idx);
                primitive_inner(tag, &payload)
            };

            let (halo_a, halo_b) = if let Some(kind) =
                if is_pointer_tag(tag) { PointerKind::from_tag(tag) } else { None }
            {
                pointer_halo_pair(kind, provenance[idx])
            } else {
                let h = provenance_halo(provenance[idx]);
                (h, h)
            };

            let px = pad_x + cx_local * cell_px;
            let py = pad_y + cy_local * cell_px;
            for dy in 0..cell_px {
                for dx in 0..cell_px {
                    let is_inner = dx >= inner_offset
                        && dx < inner_offset + inner_size
                        && dy >= inner_offset
                        && dy < inner_offset + inner_size;
                    let rgb = if is_inner {
                        inner
                    } else if (dx + dy) % 2 == 0 {
                        halo_a
                    } else {
                        halo_b
                    };
                    put_px(&mut buf, px + dx, py + dy, rgb);
                }
            }
        }
    }

    buf
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Compute the screen-pixel position of a cell's inner-region top-left
    /// under the auto-viewport. Used by tests that need to look at "the
    /// inner color of cell N" without hardcoding the v0 4-px geometry.
    fn cell_inner_origin(data: &[u8], cell_idx: usize) -> (usize, usize) {
        let (vx, vy, vside) = compute_active_viewport(data);
        let cell_px = (RENDER_W / vside).max(1);
        let render_size = cell_px * vside;
        let pad_x = (RENDER_W - render_size) / 2;
        let pad_y = (RENDER_H - render_size) / 2;
        let inner_size = (cell_px / 2).max(1);
        let inner_offset = (cell_px - inner_size) / 2;

        let cx = cell_idx % GRID;
        let cy = cell_idx / GRID;
        let cx_local = cx.checked_sub(vx).expect("cell out of viewport x");
        let cy_local = cy.checked_sub(vy).expect("cell out of viewport y");

        (
            pad_x + cx_local * cell_px + inner_offset,
            pad_y + cy_local * cell_px + inner_offset,
        )
    }

    fn pixel_rgb(frame: &[u8], x: usize, y: usize) -> [u8; 3] {
        let i = (y * RENDER_W + x) * 4;
        [frame[i], frame[i + 1], frame[i + 2]]
    }

    #[test]
    fn empty_frame_is_all_black() {
        let data = vec![0u8; NUM_CELLS * CELL_BYTES];
        let prov = vec![0u32; NUM_CELLS];
        let frame = render_frame(&data, &prov);
        assert_eq!(frame.len(), FRAME_BYTES);
        for i in (0..frame.len()).step_by(4) {
            assert_eq!(frame[i], 0);
            assert_eq!(frame[i + 1], 0);
            assert_eq!(frame[i + 2], 0);
            assert_eq!(frame[i + 3], 255);
        }
    }

    #[test]
    fn nonzero_cell_renders_color() {
        let mut data = vec![0u8; NUM_CELLS * CELL_BYTES];
        // Cell 0: tag = TAG_U32, payload = nonzero.
        data[0] = 0x03;
        data[1] = 0x00;
        for i in 2..16 {
            data[i] = 0xff;
        }
        let mut prov = vec![0u32; NUM_CELLS];
        prov[0] = 0xdeadbeef;
        let frame = render_frame(&data, &prov);
        let (ix, iy) = cell_inner_origin(&data, 0);
        let rgb = pixel_rgb(&frame, ix, iy);
        assert!(rgb[0] > 100, "expected bright red channel, got RGB={:?}", rgb);
    }

    #[test]
    fn small_value_cell_is_still_visibly_bright() {
        // A u32 with value 1 (payload = [1, 0, 0, 0, 0...]) is the dimmest realistic
        // fizzbuzz value — only one byte nonzero. It MUST render visibly bright,
        // otherwise the demo looks like an all-black frame to the eye.
        let mut data = vec![0u8; NUM_CELLS * CELL_BYTES];
        data[0] = 0x03;
        data[1] = 0x00;
        data[2] = 0x01;
        let prov = vec![0u32; NUM_CELLS];
        let frame = render_frame(&data, &prov);
        let (ix, iy) = cell_inner_origin(&data, 0);
        let rgb = pixel_rgb(&frame, ix, iy);
        let max_channel = rgb[0].max(rgb[1]).max(rgb[2]);
        assert!(
            max_channel > 100,
            "u32(1) inner pixel must be visibly bright; got max channel {} (RGB={:?})",
            max_channel, rgb
        );
    }

    #[test]
    fn distinct_payloads_render_distinguishable_colors() {
        let mut data = vec![0u8; NUM_CELLS * CELL_BYTES];
        // Cell 0: u32 = 1
        data[0] = 0x03;
        data[2] = 0x01;
        // Cell 1: u32 = 2
        data[CELL_BYTES] = 0x03;
        data[CELL_BYTES + 2] = 0x02;
        let prov = vec![0u32; NUM_CELLS];
        let frame = render_frame(&data, &prov);
        let (ix0, iy0) = cell_inner_origin(&data, 0);
        let (ix1, iy1) = cell_inner_origin(&data, 1);
        let rgb0 = pixel_rgb(&frame, ix0, iy0);
        let rgb1 = pixel_rgb(&frame, ix1, iy1);
        let dr = (rgb0[0] as i16 - rgb1[0] as i16).abs();
        let db = (rgb0[2] as i16 - rgb1[2] as i16).abs();
        assert!(
            dr + db > 5,
            "u32(1) and u32(2) must render distinguishable colors; got cell0={:?} cell1={:?}",
            rgb0, rgb1
        );
    }

    #[test]
    fn auto_viewport_zooms_to_active_cells() {
        // Single active cell at (10, 5): viewport should be MIN_VIEWPORT_SIDE
        // square that includes (10, 5).
        let mut data = vec![0u8; NUM_CELLS * CELL_BYTES];
        let cell_idx = 5 * GRID + 10;
        data[cell_idx * CELL_BYTES] = 0x03;
        data[cell_idx * CELL_BYTES + 2] = 0xff;
        let (vx, vy, vside) = compute_active_viewport(&data);
        assert_eq!(vside, MIN_VIEWPORT_SIDE);
        assert!(10 >= vx && 10 < vx + vside);
        assert!(5 >= vy && 5 < vy + vside);
    }

    #[test]
    fn auto_viewport_fills_frame_for_fizzbuzz_pattern() {
        // Mimic fizzbuzz: 100 cells active in row 0, indices 0..99.
        let mut data = vec![0u8; NUM_CELLS * CELL_BYTES];
        for i in 0..100 {
            data[i * CELL_BYTES] = 0x03;
            data[i * CELL_BYTES + 2] = (i + 1) as u8;
        }
        let (vx, vy, vside) = compute_active_viewport(&data);
        assert_eq!(vx, 0);
        assert_eq!(vy, 0);
        // 100-cell wide bbox + 2*MARGIN should produce a 104-side viewport
        // (max with MIN_VIEWPORT but 104 > 12 so result is 104).
        assert_eq!(vside, 100 + 2 * VIEWPORT_MARGIN);
        let cell_px = RENDER_W / vside;
        // Cells should be rendered at ~9-10 px instead of 4 px.
        assert!(cell_px >= 9, "cell pixel size should be >= 9 for visibility, got {}", cell_px);
    }
}
