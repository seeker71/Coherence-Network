//! Pointer cells — the first piece of the Superliminal grammar.
//!
//! Also exposes [`render_pointer_cell`], the cell-altitude rendering function
//! for a single pointer cell: resolves through the chain (bounded by
//! [`POINTER_FOLLOW_CAP`], cycle-safe via a visited set), composes the
//! kind-encoded halo around the resolved inner color, and emits an RGBA
//! buffer for that one cell at a caller-chosen pixel size. The frame-altitude
//! renderer (`render::render_frame`) inlines the same logic across the grid;
//! `render_pointer_cell` is the symbol the spec contract names — and the
//! shape future per-cell update / damage-rect renderers will reach for.
//!
//!
//! A pointer cell stores a 2-byte type tag (one of 0x000A..0x000D), a 2-byte
//! target `CellHandle` index, and 12 reserved bytes. Render-time, the inner
//! 2x2 px region of a pointer cell is populated from the *target* cell's
//! inner color rather than the pointer's own payload — transparency *is*
//! indirection. The halo encodes the pointer-kind:
//!
//! - raw  (0x000A) — plain hash-color halo (like a primitive)
//! - Box  (0x000B) — solid white outer ring
//! - Rc   (0x000C) — dotted (alternating bright/dim) outer ring
//! - Weak (0x000D) — half-brightness outer ring
//!
//! Follow-depth is capped at 4 hops at render time. A cycle (visited-set
//! triggers) renders a deterministic "cycle terminator" shade.
//!
//! Single mutator. Cross-thread pointer mutation is a v2 concern.

use crate::allocator::CellHandle;
use crate::{framebuffer, FRAMEBUFFER};

/// Pointer-kind type tags. These live in a separate range from the nine
/// primitive tags (0x0001..0x0009) so the renderer can route on tag.
pub const TAG_PTR_RAW: u16 = 0x000A;
pub const TAG_PTR_BOX: u16 = 0x000B;
pub const TAG_PTR_RC: u16 = 0x000C;
pub const TAG_PTR_WEAK: u16 = 0x000D;

/// Maximum follow-depth at render time. Cycles or deeper chains terminate
/// in the reserved cycle-terminator shade.
pub const POINTER_FOLLOW_CAP: usize = 4;

/// The reserved "cycle terminator" RGB. Distinct from every primitive
/// palette entry and from black-free. Mid-grey-purple — a deliberately
/// non-primitive frequency.
pub const CYCLE_TERMINATOR_RGB: [u8; 3] = [70, 60, 90];

/// Returns true if the given tag is one of the four pointer-kind tags.
#[inline]
pub fn is_pointer_tag(tag: u16) -> bool {
    matches!(tag, TAG_PTR_RAW | TAG_PTR_BOX | TAG_PTR_RC | TAG_PTR_WEAK)
}

/// Pointer-kind enum mirroring the four tags. Used by render and by
/// the typed wrappers below.
#[derive(Copy, Clone, Debug, Eq, PartialEq)]
pub enum PointerKind {
    Raw,
    Box_,
    Rc,
    Weak,
}

impl PointerKind {
    pub fn tag(self) -> u16 {
        match self {
            PointerKind::Raw => TAG_PTR_RAW,
            PointerKind::Box_ => TAG_PTR_BOX,
            PointerKind::Rc => TAG_PTR_RC,
            PointerKind::Weak => TAG_PTR_WEAK,
        }
    }

    pub fn from_tag(tag: u16) -> Option<Self> {
        match tag {
            TAG_PTR_RAW => Some(PointerKind::Raw),
            TAG_PTR_BOX => Some(PointerKind::Box_),
            TAG_PTR_RC => Some(PointerKind::Rc),
            TAG_PTR_WEAK => Some(PointerKind::Weak),
            _ => None,
        }
    }
}

/// Encode a pointer payload: 2 bytes target index (LE u16) + 12 reserved zero.
pub fn encode_pointer_payload(target: CellHandle) -> [u8; 14] {
    let mut payload = [0u8; 14];
    let idx = target.index() as u16;
    let bytes = idx.to_le_bytes();
    payload[0] = bytes[0];
    payload[1] = bytes[1];
    payload
}

/// Decode the target index from a pointer cell's 14-byte payload.
pub fn decode_pointer_target(payload: &[u8; 14]) -> u32 {
    u16::from_le_bytes([payload[0], payload[1]]) as u32
}

/// Generic pointer cell. Owns its own cell. Targets a `CellHandle` which is
/// not lifetime-tracked at runtime — the caller is responsible for keeping
/// the target alive (just like a raw `&` reference would be in idiomatic Rust,
/// minus the borrow checker — this is a visualization, not a memory model).
pub struct Pointer<T> {
    handle: CellHandle,
    target: CellHandle,
    kind: PointerKind,
    _phantom: std::marker::PhantomData<T>,
}

impl<T> Pointer<T> {
    /// Allocate a pointer cell of the given kind targeting `target`.
    /// Provenance is stamped at the call site like every other write.
    #[track_caller]
    fn new_kind(kind: PointerKind, target: CellHandle) -> Self {
        let caller = std::panic::Location::caller();
        let prov = crc32fast::hash(format!("{}:{}", caller.file(), caller.line()).as_bytes());

        let fb = framebuffer();
        let handle = {
            let mut data = fb.data.lock().unwrap();
            let h = data.alloc_cell(kind.tag());
            let payload = encode_pointer_payload(target);
            data.write_payload(h, &payload);
            h
        };
        {
            let mut prov_plane = fb.provenance.lock().unwrap();
            prov_plane[handle.index() as usize] = prov;
        }

        Self {
            handle,
            target,
            kind,
            _phantom: std::marker::PhantomData,
        }
    }

    /// Allocate a raw pointer cell targeting `target`.
    #[track_caller]
    pub fn new_raw(target: CellHandle) -> Self {
        Self::new_kind(PointerKind::Raw, target)
    }

    /// Allocate a pointer cell whose initial target is *itself* (self-reference).
    /// Useful when you need the pointer cell to land at a known low cell
    /// index before the real targets exist; repoint later. Inner color
    /// renders as the cycle terminator until repointed.
    #[track_caller]
    pub fn new_self_targeting(kind: PointerKind) -> Self {
        let caller = std::panic::Location::caller();
        let prov = crc32fast::hash(format!("{}:{}", caller.file(), caller.line()).as_bytes());

        let fb = framebuffer();
        let handle = {
            let mut data = fb.data.lock().unwrap();
            let h = data.alloc_cell(kind.tag());
            let payload = encode_pointer_payload(h);
            data.write_payload(h, &payload);
            h
        };
        {
            let mut prov_plane = fb.provenance.lock().unwrap();
            prov_plane[handle.index() as usize] = prov;
        }

        Self {
            handle,
            target: handle,
            kind,
            _phantom: std::marker::PhantomData,
        }
    }

    /// Self-targeting raw pointer (convenience).
    #[track_caller]
    pub fn new_self_raw() -> Self {
        Self::new_self_targeting(PointerKind::Raw)
    }

    /// This pointer cell's own handle.
    pub fn handle(&self) -> CellHandle {
        self.handle
    }

    /// The target this pointer currently points at.
    pub fn target(&self) -> CellHandle {
        self.target
    }

    pub fn kind(&self) -> PointerKind {
        self.kind
    }

    /// Repoint at a different target. Provenance is restamped at the call
    /// site so the halo refreshes.
    #[track_caller]
    pub fn repoint(&mut self, target: CellHandle) {
        let caller = std::panic::Location::caller();
        let prov = crc32fast::hash(format!("{}:{}", caller.file(), caller.line()).as_bytes());

        let fb = framebuffer();
        {
            let mut data = fb.data.lock().unwrap();
            let payload = encode_pointer_payload(target);
            data.write_payload(self.handle, &payload);
        }
        {
            let mut prov_plane = fb.provenance.lock().unwrap();
            prov_plane[self.handle.index() as usize] = prov;
        }
        self.target = target;
    }
}

/// Render one pointer cell into a per-cell RGBA buffer of size
/// `cell_px * cell_px * 4` bytes. The function:
///
/// - Follows the pointer chain at most [`POINTER_FOLLOW_CAP`] hops; on cycle
///   (the cell index re-appears in `visited`) or depth overflow the inner
///   color is the reserved [`CYCLE_TERMINATOR_RGB`].
/// - On reaching a primitive (or free) cell, samples its base palette
///   modulated by payload entropy (delegated to `render::resolve_inner_color`
///   via the snapshot bytes).
/// - Composes a halo around the inner: the halo encodes the pointer kind
///   per [`PointerKind`] — raw uses the source-location hash hue, Box solid
///   white, Rc dotted (alternating bright/dim), Weak half-brightness.
///
/// The single source of truth for the chain-follow is `render::resolve_inner_color`
/// to avoid two divergent implementations of the cycle / cap rules; this
/// function focuses on the *cell-altitude* composition (halo around inner).
///
/// `visited` is a `HashSet<u32>` the caller may share across sibling pointer
/// renders to detect cycles that span multiple top-level cells. Passing a
/// fresh empty set is the common case (cycle detection within the chain
/// rooted at `pointer_handle`).
///
/// `data_bytes` and `provenance` are snapshots of the slab and the
/// source-location plane respectively (same shapes as `render::render_frame`
/// expects). Callers driving rendering off the global framebuffer can produce
/// them with `framebuffer().data.lock().unwrap().snapshot_bytes()` and a
/// clone of the provenance plane; tests can hand-build them.
///
/// Panics if the cell at `pointer_handle` is not a pointer cell.
pub fn render_pointer_cell(
    data_bytes: &[u8],
    provenance: &[u32],
    pointer_handle: CellHandle,
    cell_px: usize,
    visited: &mut std::collections::HashSet<u32>,
) -> Vec<u8> {
    let cell_px = cell_px.max(1);
    let idx = pointer_handle.index() as usize;
    let tag = {
        let base = idx * crate::allocator::CELL_BYTES;
        u16::from_le_bytes([data_bytes[base], data_bytes[base + 1]])
    };
    assert!(
        is_pointer_tag(tag),
        "render_pointer_cell: cell {} has tag 0x{:04x}, not a pointer tag",
        idx,
        tag
    );

    // Walk the chain with the caller's visited set so cycles spanning sibling
    // pointer cells are still detected. The depth cap mirrors
    // POINTER_FOLLOW_CAP exactly: at most that many hops past the starting
    // pointer cell are followed.
    let inner = resolve_with_visited(data_bytes, idx, visited);

    // Kind-encoded halo pair (color_a, color_b). Re-implements the small
    // local rule from render.rs so this function stays self-contained at
    // the pointer-altitude — the renderer's frame-walk doesn't have to be
    // imported here.
    let kind = PointerKind::from_tag(tag).expect("pointer tag without kind");
    let prov_for_cell = provenance.get(idx).copied().unwrap_or(0);
    let (halo_a, halo_b) = halo_pair_for_kind(kind, prov_for_cell);

    // Compose the cell: outer ring = halo (a/b dotted alternation), inner
    // square = resolved inner color. Inner size matches the frame-altitude
    // convention (cell_px / 2, at least 1).
    let inner_size = (cell_px / 2).max(1);
    let inner_offset = (cell_px - inner_size) / 2;
    let mut out = vec![0u8; cell_px * cell_px * 4];
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
            let i = (dy * cell_px + dx) * 4;
            out[i] = rgb[0];
            out[i + 1] = rgb[1];
            out[i + 2] = rgb[2];
            out[i + 3] = 255;
        }
    }
    out
}

/// Local chain-follow that honors the caller's shared `visited` set. The
/// frame-altitude renderer uses a fresh per-cell visited array; this version
/// lets a caller (e.g. a test driving render_pointer_cell over sibling
/// pointers in a cycle) prove cap-bounded termination across the group.
fn resolve_with_visited(
    data_bytes: &[u8],
    start: usize,
    visited: &mut std::collections::HashSet<u32>,
) -> [u8; 3] {
    let mut cur = start;
    for _hop in 0..=POINTER_FOLLOW_CAP {
        if cur >= crate::allocator::NUM_CELLS {
            return CYCLE_TERMINATOR_RGB;
        }
        if !visited.insert(cur as u32) {
            return CYCLE_TERMINATOR_RGB;
        }
        let base = cur * crate::allocator::CELL_BYTES;
        let tag = u16::from_le_bytes([data_bytes[base], data_bytes[base + 1]]);
        if !is_pointer_tag(tag) {
            // Reached a primitive (or free). Delegate inner-color
            // computation to the renderer so palette + modulation rules
            // live in exactly one place.
            let mut payload = [0u8; 14];
            payload.copy_from_slice(
                &data_bytes[base + 2..base + crate::allocator::CELL_BYTES],
            );
            return crate::render::primitive_inner_for_test(tag, &payload);
        }
        let mut payload = [0u8; 14];
        payload.copy_from_slice(
            &data_bytes[base + 2..base + crate::allocator::CELL_BYTES],
        );
        cur = decode_pointer_target(&payload) as usize;
    }
    CYCLE_TERMINATOR_RGB
}

/// Kind-encoded halo color pair. Mirrors `render::pointer_halo_pair` so the
/// per-cell renderer doesn't reach into render's private API. Both implementations
/// agree pixel-exact for any (kind, prov) pair — kept in one tested place would
/// be cleaner; left as-mirror until a v2 renderer collapses them.
fn halo_pair_for_kind(kind: PointerKind, prov: u32) -> ([u8; 3], [u8; 3]) {
    let base = crate::render::provenance_halo(prov);
    match kind {
        PointerKind::Raw => (base, base),
        PointerKind::Box_ => ([240, 240, 240], [240, 240, 240]),
        PointerKind::Rc => ([240, 240, 240], [60, 60, 60]),
        PointerKind::Weak => {
            let half = [base[0] / 2, base[1] / 2, base[2] / 2];
            (half, half)
        }
    }
}

impl<T> Drop for Pointer<T> {
    fn drop(&mut self) {
        if let Some(fb) = FRAMEBUFFER.get() {
            if let Ok(mut data) = fb.data.lock() {
                data.free_cell(self.handle);
            }
            if let Ok(mut prov) = fb.provenance.lock() {
                prov[self.handle.index() as usize] = 0;
            }
        }
    }
}

/// Visual variant: solid white halo. Same data layout as `Pointer<T>`.
pub struct BoxPtr<T> {
    inner: Pointer<T>,
}

impl<T> BoxPtr<T> {
    #[track_caller]
    pub fn new(target: CellHandle) -> Self {
        Self {
            inner: Pointer::new_kind(PointerKind::Box_, target),
        }
    }
    pub fn handle(&self) -> CellHandle {
        self.inner.handle()
    }
    pub fn target(&self) -> CellHandle {
        self.inner.target()
    }
    #[track_caller]
    pub fn repoint(&mut self, target: CellHandle) {
        self.inner.repoint(target);
    }
}

/// Visual variant: dotted halo (alternating bright/dim). Same data layout.
pub struct RcPtr<T> {
    inner: Pointer<T>,
}

impl<T> RcPtr<T> {
    #[track_caller]
    pub fn new(target: CellHandle) -> Self {
        Self {
            inner: Pointer::new_kind(PointerKind::Rc, target),
        }
    }
    pub fn handle(&self) -> CellHandle {
        self.inner.handle()
    }
    pub fn target(&self) -> CellHandle {
        self.inner.target()
    }
    #[track_caller]
    pub fn repoint(&mut self, target: CellHandle) {
        self.inner.repoint(target);
    }
}

/// Visual variant: half-brightness halo. Same data layout.
pub struct WeakPtr<T> {
    inner: Pointer<T>,
}

impl<T> WeakPtr<T> {
    #[track_caller]
    pub fn new(target: CellHandle) -> Self {
        Self {
            inner: Pointer::new_kind(PointerKind::Weak, target),
        }
    }
    pub fn handle(&self) -> CellHandle {
        self.inner.handle()
    }
    pub fn target(&self) -> CellHandle {
        self.inner.target()
    }
    #[track_caller]
    pub fn repoint(&mut self, target: CellHandle) {
        self.inner.repoint(target);
    }
}
