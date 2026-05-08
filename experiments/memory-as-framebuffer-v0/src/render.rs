//! Render the slab + provenance plane into a 1024x1024 RGBA frame.
//! Each cell occupies a 4x4 px block: outer ring = provenance halo,
//! inner 2x2 = type-tagged value with brightness from payload entropy.

use crate::allocator::{CELL_BYTES, GRID, NUM_CELLS};
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

/// Modulate a base RGB by payload entropy. More nonzero bytes = brighter,
/// all zeros = dim (15% of base).
pub fn modulate_brightness(base: [u8; 3], payload: &[u8; 14]) -> [u8; 3] {
    let nonzero = payload.iter().filter(|b| **b != 0).count() as f32;
    let factor = 0.15 + (nonzero / 14.0) * 0.85;
    [
        ((base[0] as f32) * factor) as u8,
        ((base[1] as f32) * factor) as u8,
        ((base[2] as f32) * factor) as u8,
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
            let base = idx * CELL_BYTES;
            let tag = u16::from_le_bytes([data_bytes[base], data_bytes[base + 1]]);
            let mut payload = [0u8; 14];
            payload.copy_from_slice(&data_bytes[base + 2..base + CELL_BYTES]);

            let palette_color = type_palette(tag);
            let inner = if tag == TAG_FREE {
                [0u8, 0, 0]
            } else {
                modulate_brightness(palette_color, &payload)
            };
            let halo = provenance_halo(provenance[idx]);

            // 4x4 block: outer ring (halo), inner 2x2 (value).
            let px = cx * 4;
            let py = cy * 4;
            for dy in 0..4 {
                for dx in 0..4 {
                    let is_inner = dx >= 1 && dx <= 2 && dy >= 1 && dy <= 2;
                    let rgb = if is_inner { inner } else { halo };
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
}
