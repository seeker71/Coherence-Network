//! Render trait — the dispatch surface that lets any type override how its
//! cells appear on screen.
//!
//! The frame-altitude renderer (`render::render_frame`) walks every cell of
//! the active viewport and, per cell, dispatches through this trait. A
//! built-in `DefaultPrimitiveRender(tag)` covers the nine primitive type
//! tags and reproduces the v0 output exactly (palette base color + payload
//! brightness modulation + provenance halo). User-defined types implement
//! `Render` and register a kernel under a user-tag in 0x1000..=0xFFFF; that
//! kernel beats the default whenever the renderer encounters a cell carrying
//! that tag.
//!
//! Two surfaces:
//!
//! - [`Render`] — trait every renderable type implements. Object-safe so we
//!   can stash impls behind `Box<dyn Render>` in the registry.
//! - [`RenderCtx`] — what the trait method writes into. Carries the active
//!   region of the output frame, geometry (cell pixel position + size +
//!   inner offset), the resolved inner color (for pointers — already chain-
//!   walked), and provenance hash (for the halo). Helpers (`fill_rect`,
//!   `draw_halo`, `composite_target_color`) keep the common compositions
//!   one-line.
//!
//! The intentional shape: a kernel renders *one cell's region* into the
//! frame buffer. Multi-cell renderers (a Matrix3x3 that spans 9 cells)
//! register under the user-tag of their *header* cell and reach across to
//! sibling cells via the snapshot bytes the ctx exposes — see
//! `examples/custom_renderer.rs` for the worked pattern. Pointer-following
//! kernels are a follow-up (need v1-pointers' RenderCtx extensions).

use crate::allocator::{CELL_BYTES, GRID, NUM_CELLS};
use once_cell::sync::OnceCell;
use std::collections::HashMap;
use std::sync::RwLock;

/// Level-of-detail. v1 has a single variant; v1-3d extends with Far/Mid/Near
/// and 3D-projected variants. Kernels accept `Lod` so they can cheap-out at
/// distance and bloom into detail up close — at v1 the parameter is always
/// `Lod::Default` and most kernels ignore it.
#[derive(Copy, Clone, Debug, Eq, PartialEq)]
pub enum Lod {
    Default,
}

/// Reserved user-tag range. Tags below this are reserved for primitives
/// (0x0001..0x000F) and pointer kinds (0x000A..0x000D).
pub const USER_TAG_MIN: u16 = 0x1000;
pub const USER_TAG_MAX: u16 = 0xFFFF;

/// One render intent. Captured by kernels via the `RenderCtx::push_op` helper
/// for callers that want to inspect what a kernel produced without committing
/// to the frame buffer (used by tests). The common path is to call the
/// composition helpers directly — they write to the buffer and append the
/// matching `RenderOp` so both surfaces stay in sync.
#[derive(Clone, Debug)]
pub enum RenderOp {
    /// Fill a rectangle (in frame-pixel coords) with a solid RGB color.
    FillRect {
        x: usize,
        y: usize,
        w: usize,
        h: usize,
        rgb: [u8; 3],
    },
    /// Paint a halo ring around the cell using an alternating `(a, b)` color
    /// pair (the dotted pattern used by pointer kinds — `a == b` for solid).
    Halo {
        x: usize,
        y: usize,
        cell_px: usize,
        inner_offset: usize,
        inner_size: usize,
        color_a: [u8; 3],
        color_b: [u8; 3],
    },
    /// Composite the inner region of the cell using the already-resolved
    /// target color. Used by pointer kernels — the chain-walk happens above
    /// the trait dispatch and the resolved color arrives in the ctx.
    CompositeTargetColor { rgb: [u8; 3] },
}

/// Render context — everything a kernel needs to draw one cell's region.
///
/// Fields are intentionally read-only references except `frame`, which the
/// kernel writes through. The geometry (`cell_px`, `inner_offset`,
/// `inner_size`, `frame_w`, `frame_h`) is computed once per frame by
/// `render_frame` and reused for every cell — kernels don't need to know the
/// viewport math.
pub struct RenderCtx<'a> {
    /// Cell index in the slab (0..NUM_CELLS). Lets kernels reach across to
    /// sibling cells via `data_bytes` when their type spans multiple cells.
    pub cell_idx: usize,
    /// Grid coordinate of this cell.
    pub gx: usize,
    pub gy: usize,
    /// Top-left pixel of this cell in the output frame.
    pub px: usize,
    pub py: usize,
    /// Pixel side of one cell in the output frame.
    pub cell_px: usize,
    /// Inner-region offset and size (matches v0 geometry: `cell_px / 2`
    /// centered within the cell).
    pub inner_offset: usize,
    pub inner_size: usize,
    /// Output frame dimensions.
    pub frame_w: usize,
    pub frame_h: usize,
    /// Raw data plane snapshot (`NUM_CELLS * CELL_BYTES`). Kernels read
    /// sibling cells through this — never write.
    pub data_bytes: &'a [u8],
    /// Provenance plane (`NUM_CELLS` entries). Kernels read for halo
    /// coloring — never write.
    pub provenance: &'a [u32],
    /// Type tag of *this* cell, pulled once before dispatch.
    pub tag: u16,
    /// Raw payload of this cell (14 bytes).
    pub payload: [u8; 14],
    /// Resolved inner color when this cell is a pointer — the chain-walk has
    /// already happened in the renderer; the kernel sees the destination
    /// color. None for non-pointer cells (the kernel computes its own inner).
    pub resolved_target: Option<[u8; 3]>,
    /// LOD level for this dispatch.
    pub lod: Lod,
    /// Output frame buffer (RGBA, `frame_w * frame_h * 4` bytes).
    pub frame: &'a mut [u8],
    /// Optional sink for the render ops the kernel produced. None in
    /// release; Some(&mut Vec) in tests that want to inspect intent.
    pub ops: Option<&'a mut Vec<RenderOp>>,
}

impl<'a> RenderCtx<'a> {
    /// Read a sibling cell's 14-byte payload through the snapshot bytes.
    /// Returns the zero payload if the index is out of range.
    pub fn sibling_payload(&self, idx: usize) -> [u8; 14] {
        if idx >= NUM_CELLS {
            return [0u8; 14];
        }
        let base = idx * CELL_BYTES;
        let mut out = [0u8; 14];
        out.copy_from_slice(&self.data_bytes[base + 2..base + CELL_BYTES]);
        out
    }

    /// Read a sibling cell's type tag through the snapshot bytes.
    pub fn sibling_tag(&self, idx: usize) -> u16 {
        if idx >= NUM_CELLS {
            return 0;
        }
        let base = idx * CELL_BYTES;
        u16::from_le_bytes([self.data_bytes[base], self.data_bytes[base + 1]])
    }

    /// Convenience: this cell's grid index computed from gx/gy.
    pub fn grid_index(&self) -> usize {
        self.gy * GRID + self.gx
    }

    /// Fill a rectangle of the output frame. Clips silently to frame bounds.
    pub fn fill_rect(&mut self, x: usize, y: usize, w: usize, h: usize, rgb: [u8; 3]) {
        let frame_w = self.frame_w;
        let frame_h = self.frame_h;
        for dy in 0..h {
            let py = y + dy;
            if py >= frame_h {
                break;
            }
            for dx in 0..w {
                let px = x + dx;
                if px >= frame_w {
                    break;
                }
                let i = (py * frame_w + px) * 4;
                self.frame[i] = rgb[0];
                self.frame[i + 1] = rgb[1];
                self.frame[i + 2] = rgb[2];
                self.frame[i + 3] = 255;
            }
        }
        if let Some(ops) = self.ops.as_deref_mut() {
            ops.push(RenderOp::FillRect { x, y, w, h, rgb });
        }
    }

    /// Paint the dotted halo + inner region using v0's composition rule.
    /// The default kernel uses this to keep its output exactly v0-equivalent.
    pub fn draw_halo(&mut self, color_a: [u8; 3], color_b: [u8; 3], inner: [u8; 3]) {
        let cell_px = self.cell_px;
        let inner_offset = self.inner_offset;
        let inner_size = self.inner_size;
        let px = self.px;
        let py = self.py;
        let frame_w = self.frame_w;
        let frame_h = self.frame_h;
        for dy in 0..cell_px {
            let y = py + dy;
            if y >= frame_h {
                break;
            }
            for dx in 0..cell_px {
                let x = px + dx;
                if x >= frame_w {
                    break;
                }
                let is_inner = dx >= inner_offset
                    && dx < inner_offset + inner_size
                    && dy >= inner_offset
                    && dy < inner_offset + inner_size;
                let rgb = if is_inner {
                    inner
                } else if (dx + dy) % 2 == 0 {
                    color_a
                } else {
                    color_b
                };
                let i = (y * frame_w + x) * 4;
                self.frame[i] = rgb[0];
                self.frame[i + 1] = rgb[1];
                self.frame[i + 2] = rgb[2];
                self.frame[i + 3] = 255;
            }
        }
        if let Some(ops) = self.ops.as_deref_mut() {
            ops.push(RenderOp::Halo {
                x: px,
                y: py,
                cell_px,
                inner_offset,
                inner_size,
                color_a,
                color_b,
            });
        }
    }

    /// Composite the inner region using an already-resolved target color
    /// (pointer-style transparency). Kernels that wrap pointer cells call
    /// this after `draw_halo` to overlay the target's color in the inner.
    pub fn composite_target_color(&mut self, rgb: [u8; 3]) {
        let px = self.px + self.inner_offset;
        let py = self.py + self.inner_offset;
        self.fill_rect(px, py, self.inner_size, self.inner_size, rgb);
        if let Some(ops) = self.ops.as_deref_mut() {
            ops.push(RenderOp::CompositeTargetColor { rgb });
        }
    }
}

/// Renderable type — the contract every kernel implements.
///
/// Send + Sync because kernels live in a global registry the render thread
/// reads from. Object-safe so we can stash impls behind `Box<dyn Render>`.
pub trait Render: Send + Sync {
    /// Draw one cell's region into the context. The implementation owns the
    /// rectangle from `(ctx.px, ctx.py)` to `(ctx.px + ctx.cell_px,
    /// ctx.py + ctx.cell_px)`. Multi-cell kernels read sibling cells via
    /// `ctx.sibling_payload` / `ctx.sibling_tag` but still draw only their
    /// own assigned region — the renderer dispatches per cell, so other
    /// cells in the composite group get their own dispatch.
    fn render(&self, ctx: &mut RenderCtx, lod: Lod);
}

/// Default renderer for primitive type tags (and pointer tags). Reproduces
/// v0's output exactly: palette base color + payload-derived brightness +
/// provenance halo. Pointer cells use the resolved target color from the
/// renderer's chain-walk and the kind-encoded halo.
pub struct DefaultPrimitiveRender {
    pub tag: u16,
}

impl DefaultPrimitiveRender {
    pub fn new(tag: u16) -> Self {
        Self { tag }
    }
}

impl Render for DefaultPrimitiveRender {
    fn render(&self, ctx: &mut RenderCtx, _lod: Lod) {
        // Inner color: pointer cells use the resolved-target color the
        // renderer pre-computed; primitives compute their own from the
        // payload via the same primitive_inner rule the v0 renderer used.
        let inner = if let Some(resolved) = ctx.resolved_target {
            resolved
        } else {
            crate::render::primitive_inner_for_test(self.tag, &ctx.payload)
        };

        // Halo: pointer cells get the kind-encoded (alternating) pair;
        // primitives get the provenance hash halo (color_a == color_b).
        let (halo_a, halo_b) = if let Some(kind) = crate::pointer::PointerKind::from_tag(self.tag) {
            crate::render::pointer_halo_pair_public(kind, ctx.provenance[ctx.cell_idx])
        } else {
            let h = crate::render::provenance_halo(ctx.provenance[ctx.cell_idx]);
            (h, h)
        };

        ctx.draw_halo(halo_a, halo_b, inner);
    }
}

/// Errors from `register_kernel`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum KernelRegistryError {
    /// Tag is outside the user range 0x1000..=0xFFFF.
    ReservedTag(u16),
    /// Tag already has a kernel registered.
    AlreadyRegistered(u16),
}

impl std::fmt::Display for KernelRegistryError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            KernelRegistryError::ReservedTag(t) => write!(
                f,
                "tag 0x{:04x} is reserved; user-tags must be in 0x{:04x}..=0x{:04x}",
                t, USER_TAG_MIN, USER_TAG_MAX
            ),
            KernelRegistryError::AlreadyRegistered(t) => {
                write!(f, "tag 0x{:04x} is already registered", t)
            }
        }
    }
}

impl std::error::Error for KernelRegistryError {}

/// The global kernel registry. RwLock so the render thread's reads are
/// uncontended after init (when no writes happen). OnceCell because we
/// initialize the inner HashMap exactly once on first use.
fn registry() -> &'static RwLock<HashMap<u16, Box<dyn Render>>> {
    static REGISTRY: OnceCell<RwLock<HashMap<u16, Box<dyn Render>>>> = OnceCell::new();
    REGISTRY.get_or_init(|| RwLock::new(HashMap::new()))
}

/// Register a kernel for the given user-tag. Tag must be in
/// 0x1000..=0xFFFF; re-registering an existing tag is an error (the v1
/// contract is startup-only registration — mid-run swap is undefined).
pub fn register_kernel(
    tag: u16,
    kernel: Box<dyn Render>,
) -> Result<(), KernelRegistryError> {
    if !(USER_TAG_MIN..=USER_TAG_MAX).contains(&tag) {
        return Err(KernelRegistryError::ReservedTag(tag));
    }
    let mut guard = registry()
        .write()
        .expect("kernel registry poisoned");
    if guard.contains_key(&tag) {
        return Err(KernelRegistryError::AlreadyRegistered(tag));
    }
    guard.insert(tag, kernel);
    Ok(())
}

/// Look up the kernel for a given tag. Returns a 'static reference because
/// the registry never removes entries once inserted — and `Box<dyn Render>`
/// holds a heap allocation whose address is stable for the process lifetime.
/// Returns `None` for tags with no registered kernel (the default applies).
pub fn lookup_kernel(tag: u16) -> Option<&'static dyn Render> {
    let guard = registry().read().ok()?;
    let boxed = guard.get(&tag)?;
    // SAFETY: the registry never removes entries, and Box<dyn Render>'s
    // inner allocation has a stable heap address for the process lifetime.
    // We extend the lifetime of the &dyn Render reference accordingly.
    let r: &dyn Render = boxed.as_ref();
    let extended: &'static dyn Render = unsafe { std::mem::transmute(r) };
    Some(extended)
}

/// Clear the registry. Test-only — never call from production code; the v1
/// contract is startup-only registration.
#[doc(hidden)]
pub fn _clear_registry_for_tests() {
    if let Ok(mut guard) = registry().write() {
        guard.clear();
    }
}
