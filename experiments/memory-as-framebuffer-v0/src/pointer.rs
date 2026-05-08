//! Pointer cells — the first piece of the Superliminal grammar.
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
