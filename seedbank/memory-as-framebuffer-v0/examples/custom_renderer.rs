//! Custom renderer example — a `Matrix3x3` type that renders as a labeled
//! 3×3 grid via the Render trait, instead of nine disconnected float cells.
//!
//! Demonstrates the v1-render-trait surface end-to-end:
//!
//! 1. Define a struct whose storage is a fixed number of cells.
//! 2. Register a kernel under a user-tag (0x1001) before `init_framebuffer`.
//! 3. The kernel reaches across to sibling cells via
//!    `RenderCtx::sibling_payload` to read all nine entries and draw the
//!    matrix as a single visible composite — sign → hue, magnitude →
//!    brightness, with a labeled border around the whole region.
//!
//! The demo runs a small linear-algebra loop (matrix scaling per step) for
//! n=1..=10000 and produces `matrix3x3.mp4`.

use mfb::allocator::GRID;
use mfb::pointer::encode_pointer_payload;
use mfb::{
    framebuffer, init_framebuffer, register_kernel, shutdown_framebuffer, track, CellHandle, Lod,
    Render, RenderCtx, Tracked,
};

/// User-tag for the Matrix3x3 header cell. Must be in 0x1000..=0xFFFF.
pub const MATRIX_TAG: u16 = 0x1001;

/// A 3×3 matrix backed by 9 `Tracked<f32>` entry cells plus 1 header cell.
/// The header cell carries `MATRIX_TAG`; the kernel registered under that
/// tag reaches across to the eight sibling cells to draw the whole matrix.
pub struct Matrix3x3 {
    header_handle: CellHandle,
    entries: [Tracked<f32>; 9],
}

impl Matrix3x3 {
    /// Allocate the header at `(gx, gy)` and the 9 entries at
    /// `(gx + 1 + col, gy + row)` for row, col in 0..3.
    pub fn new(gx: usize, gy: usize) -> Self {
        // Allocate the 9 entry cells first so we know their indices.
        let entries: [Tracked<f32>; 9] = std::array::from_fn(|i| {
            let ex = gx + 1 + (i % 3);
            let ey = gy + i / 3;
            Tracked::new_at(ey * GRID + ex, 0.0_f32)
        });

        // The header carries MATRIX_TAG with the top-left entry's index
        // encoded in the first two payload bytes (for future kernels that
        // want to chase a pointer; the v1 kernel just steps by grid layout).
        let header_idx = gy * GRID + gx;
        let header_handle = {
            let fb = framebuffer();
            let mut data = fb.data.lock().unwrap();
            let h = data.alloc_at(header_idx, MATRIX_TAG);
            let payload = encode_pointer_payload(entries[0].handle());
            data.write_payload(h, &payload);
            h
        };

        Self {
            header_handle,
            entries,
        }
    }

    pub fn header(&self) -> CellHandle {
        self.header_handle
    }

    pub fn set(&mut self, row: usize, col: usize, value: f32) {
        assert!(row < 3 && col < 3);
        let cell = &mut self.entries[row * 3 + col];
        track!(cell, value);
    }

    pub fn get(&self, row: usize, col: usize) -> f32 {
        self.entries[row * 3 + col].get()
    }
}

impl Drop for Matrix3x3 {
    fn drop(&mut self) {
        // Free the header explicitly — entry cells free via their Tracked
        // drops. The framebuffer is still alive here (we're dropping before
        // shutdown_framebuffer).
        let fb = framebuffer();
        if let Ok(mut data) = fb.data.lock() {
            data.free_cell(self.header_handle);
        }
        if let Ok(mut prov) = fb.provenance.lock() {
            prov[self.header_handle.index() as usize] = 0;
        }
    }
}

/// Render kernel for `Matrix3x3`. When the renderer encounters the matrix
/// header cell, this kernel draws the matrix as a single labeled 3×3
/// composite within the header's pixel region.
pub struct Matrix3x3Render;

impl Render for Matrix3x3Render {
    fn render(&self, ctx: &mut RenderCtx, _lod: Lod) {
        let cell_px = ctx.cell_px;
        let header_px = ctx.px;
        let header_py = ctx.py;

        // Soft white border outline (1 px) around the header cell.
        let border = [220, 220, 220];
        for d in 0..cell_px {
            ctx.fill_rect(header_px + d, header_py, 1, 1, border);
            ctx.fill_rect(header_px + d, header_py + cell_px - 1, 1, 1, border);
            ctx.fill_rect(header_px, header_py + d, 1, 1, border);
            ctx.fill_rect(header_px + cell_px - 1, header_py + d, 1, 1, border);
        }

        // Read all 9 entries from the sibling cells: header at (gx, gy);
        // entries at (gx + 1 + col, gy + row).
        let mut values = [0.0_f32; 9];
        for i in 0..9 {
            let row = i / 3;
            let col = i % 3;
            let sibling_idx = (ctx.gy + row) * GRID + (ctx.gx + 1 + col);
            let payload = ctx.sibling_payload(sibling_idx);
            let mut buf = [0u8; 4];
            buf.copy_from_slice(&payload[..4]);
            values[i] = f32::from_le_bytes(buf);
        }

        // Lay out the 3×3 inside the header cell with a small gutter.
        let gutter = (cell_px / 16).max(1);
        let inner_w = cell_px.saturating_sub(2 * gutter);
        let entry_side = (inner_w / 3).max(1);

        for row in 0..3 {
            for col in 0..3 {
                let v = values[row * 3 + col];
                let cell_color = entry_color(v);
                let x = header_px + gutter + col * entry_side;
                let y = header_py + gutter + row * entry_side;
                let draw = entry_side.saturating_sub(1).max(1);
                ctx.fill_rect(x, y, draw, draw, cell_color);
            }
        }
    }
}

/// Map a matrix entry to RGB: sign → hue (positive blue, negative red),
/// magnitude → brightness.
fn entry_color(v: f32) -> [u8; 3] {
    let mag = v.abs().min(1.0);
    let brightness = (80.0 + mag * 175.0) as u8;
    if v >= 0.0 {
        [40, 80, brightness]
    } else {
        [brightness, 60, 40]
    }
}

fn main() {
    // Register the kernel *before* init_framebuffer — v1 contract is
    // startup-only registration.
    register_kernel(MATRIX_TAG, Box::new(Matrix3x3Render))
        .expect("register Matrix3x3 kernel");

    init_framebuffer("matrix3x3.mp4").expect("init framebuffer");

    // Place a single Matrix3x3 in the visible area of the heap. With one
    // matrix the auto-viewport zooms in close, so the composite is visibly
    // a 3×3 grid rather than a tiny smudge.
    let mut m = Matrix3x3::new(2, 2);

    // Small linear-algebra-style loop: drive each entry through a smooth
    // trigonometric trajectory so the matrix visibly breathes frame to frame.
    for n in 1u32..=10_000 {
        let t = (n as f32) * 0.001;
        m.set(0, 0, t.sin());
        m.set(0, 1, (t * 1.3).sin());
        m.set(0, 2, (t * 1.7).sin());
        m.set(1, 0, (t * 0.7).cos());
        m.set(1, 1, t.cos());
        m.set(1, 2, (t * 1.1).cos());
        m.set(2, 0, ((t + 0.5).sin()) * 0.8);
        m.set(2, 1, ((t + 1.0).cos()) * 0.6);
        m.set(2, 2, (t * 0.5).tan().tanh());

        std::thread::sleep(std::time::Duration::from_micros(500));
    }

    drop(m);
    shutdown_framebuffer();
}
