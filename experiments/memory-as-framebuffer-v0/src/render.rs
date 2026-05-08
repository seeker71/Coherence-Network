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

/// Render one frame from a snapshot of the data plane and provenance plane.
/// `data_bytes` must be NUM_CELLS * CELL_BYTES; `provenance` must be NUM_CELLS.
pub fn render_frame(data_bytes: &[u8], provenance: &[u32]) -> FrameRgba {
    debug_assert_eq!(data_bytes.len(), NUM_CELLS * CELL_BYTES);
    debug_assert_eq!(provenance.len(), NUM_CELLS);

    let mut buf = vec![0u8; FRAME_BYTES];

    for cy in 0..GRID {
        for cx in 0..GRID {
            let idx = cy * GRID + cx;
            let tag = read_tag_at(data_bytes, idx);

            // Inner 2x2 color: for primitives, modulate palette by payload entropy.
            // For pointer cells, follow the chain (≤4 hops) and use the target's
            // inner color — transparency *is* indirection.
            let inner = if is_pointer_tag(tag) {
                resolve_inner_color(data_bytes, idx)
            } else {
                let payload = read_payload_at(data_bytes, idx);
                primitive_inner(tag, &payload)
            };

            // Outer ring: for primitives, the provenance halo. For pointer
            // cells, a kind-specific frame palette (raw=hash, Box=white,
            // Rc=dotted, Weak=half-brightness hash).
            let (halo_a, halo_b) = if let Some(kind) =
                if is_pointer_tag(tag) { PointerKind::from_tag(tag) } else { None }
            {
                pointer_halo_pair(kind, provenance[idx])
            } else {
                let h = provenance_halo(provenance[idx]);
                (h, h)
            };

            // 4x4 block: outer ring (halo), inner 2x2 (value).
            let px = cx * 4;
            let py = cy * 4;
            for dy in 0..4 {
                for dx in 0..4 {
                    let is_inner = dx >= 1 && dx <= 2 && dy >= 1 && dy <= 2;
                    let rgb = if is_inner {
                        inner
                    } else {
                        // Alternate halo_a / halo_b along the outer ring for
                        // the Rc dotted pattern; for non-Rc kinds the two
                        // colors are equal so the alternation collapses.
                        if (dx + dy) % 2 == 0 { halo_a } else { halo_b }
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

    #[test]
    fn empty_frame_is_all_black() {
        let data = vec![0u8; NUM_CELLS * CELL_BYTES];
        let prov = vec![0u32; NUM_CELLS];
        let frame = render_frame(&data, &prov);
        assert_eq!(frame.len(), FRAME_BYTES);
        // Sample a few pixels.
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
        // Inner pixel of cell 0 = (1,1) → should be palette-bright.
        let i = (1 * RENDER_W + 1) * 4;
        let r = frame[i];
        assert!(r > 100, "expected bright red channel, got {}", r);
    }

    #[test]
    fn small_value_cell_is_still_visibly_bright() {
        // A u32 with value 1 (payload = [1, 0, 0, 0, 0...]) is the dimmest realistic
        // fizzbuzz value — only one byte nonzero. It MUST render visibly bright,
        // otherwise the demo looks like an all-black frame to the eye.
        let mut data = vec![0u8; NUM_CELLS * CELL_BYTES];
        // Cell 0: tag = TAG_U32 (0x0003), payload = [1, 0, 0, ..., 0]
        data[0] = 0x03;
        data[1] = 0x00;
        data[2] = 0x01;
        // bytes 3..15 stay 0
        let prov = vec![0u32; NUM_CELLS];
        let frame = render_frame(&data, &prov);
        // Inner pixel of cell 0 = (1,1).
        let i = (1 * RENDER_W + 1) * 4;
        let max_channel = frame[i].max(frame[i + 1]).max(frame[i + 2]);
        assert!(
            max_channel > 100,
            "u32(1) inner pixel must be visibly bright; got max channel {} (RGB={:?})",
            max_channel,
            (frame[i], frame[i + 1], frame[i + 2])
        );
    }

    #[test]
    fn distinct_payloads_render_distinguishable_colors() {
        // Two u32 cells with values 1 vs 2 should produce visibly different colors
        // (CRC-driven flicker), so changing values are perceptible across frames.
        let mut data = vec![0u8; NUM_CELLS * CELL_BYTES];
        // Cell 0: u32 = 1
        data[0] = 0x03;
        data[2] = 0x01;
        // Cell 1: u32 = 2
        data[CELL_BYTES] = 0x03;
        data[CELL_BYTES + 2] = 0x02;
        let prov = vec![0u32; NUM_CELLS];
        let frame = render_frame(&data, &prov);
        // Inner pixels of cells 0 and 1 (cells 0 at x=1,y=1; cell 1 at x=5,y=1)
        let i0 = (1 * RENDER_W + 1) * 4;
        let i1 = (1 * RENDER_W + 5) * 4;
        let dr = (frame[i0] as i16 - frame[i1] as i16).abs();
        let db = (frame[i0 + 2] as i16 - frame[i1 + 2] as i16).abs();
        assert!(
            dr + db > 5,
            "u32(1) and u32(2) must render distinguishable colors; \
             got cell0 RGB=({},{},{}) cell1 RGB=({},{},{})",
            frame[i0], frame[i0 + 1], frame[i0 + 2],
            frame[i1], frame[i1 + 1], frame[i1 + 2]
        );
    }
}
