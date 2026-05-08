//! Slab framebuffer: 256x256 grid of 16-byte cells (1MB heap).
//! Each cell = 2-byte little-endian type tag + 14-byte payload.
//! Allocation order is deterministic (next-free-slot scan from index 0).

use crate::TAG_FREE;

pub const GRID: usize = 256;
pub const NUM_CELLS: usize = GRID * GRID; // 65536
pub const CELL_BYTES: usize = 16;
pub const HEAP_BYTES: usize = NUM_CELLS * CELL_BYTES; // 1 MB

/// Index into the slab. 0..NUM_CELLS.
#[derive(Copy, Clone, Debug, Eq, PartialEq)]
pub struct CellHandle(u32);

impl CellHandle {
    pub fn index(self) -> u32 {
        self.0
    }
    pub fn xy(self) -> (u32, u32) {
        (self.0 % GRID as u32, self.0 / GRID as u32)
    }
}

/// The data plane: 1 MB of bytes interpreted as `NUM_CELLS` 16-byte cells.
pub struct SlabFramebuffer {
    pub bytes: Box<[u8; HEAP_BYTES]>,
    /// Hint for the next free slot — we still scan to confirm.
    next_free_hint: usize,
}

impl SlabFramebuffer {
    pub fn new() -> Self {
        // Box::new on a stack array of 1MB would overflow the stack; build on heap.
        let v = vec![0u8; HEAP_BYTES].into_boxed_slice();
        let raw = Box::into_raw(v) as *mut [u8; HEAP_BYTES];
        // SAFETY: the boxed slice has exactly HEAP_BYTES bytes.
        let boxed: Box<[u8; HEAP_BYTES]> = unsafe { Box::from_raw(raw) };
        Self {
            bytes: boxed,
            next_free_hint: 0,
        }
    }

    fn cell_offset(handle: CellHandle) -> usize {
        handle.0 as usize * CELL_BYTES
    }

    fn read_tag(&self, idx: usize) -> u16 {
        let base = idx * CELL_BYTES;
        u16::from_le_bytes([self.bytes[base], self.bytes[base + 1]])
    }

    fn write_tag(&mut self, idx: usize, tag: u16) {
        let base = idx * CELL_BYTES;
        let bytes = tag.to_le_bytes();
        self.bytes[base] = bytes[0];
        self.bytes[base + 1] = bytes[1];
    }

    /// Allocate a fresh cell with the given type tag. Deterministic next-free-slot
    /// scan starting from `next_free_hint`. Panics with a clear message if the
    /// heap is full.
    pub fn alloc_cell(&mut self, tag: u16) -> CellHandle {
        let start = self.next_free_hint;
        for offset in 0..NUM_CELLS {
            let idx = (start + offset) % NUM_CELLS;
            if self.read_tag(idx) == TAG_FREE {
                self.write_tag(idx, tag);
                // Zero payload for cleanliness.
                let base = idx * CELL_BYTES;
                for b in &mut self.bytes[base + 2..base + CELL_BYTES] {
                    *b = 0;
                }
                self.next_free_hint = (idx + 1) % NUM_CELLS;
                return CellHandle(idx as u32);
            }
        }
        panic!(
            "memory-as-framebuffer: heap full ({} cells, {} bytes); cannot alloc tag 0x{:04x}",
            NUM_CELLS, HEAP_BYTES, tag
        );
    }

    /// Free the cell: zero all 16 bytes (tag + payload).
    pub fn free_cell(&mut self, handle: CellHandle) {
        let base = Self::cell_offset(handle);
        for b in &mut self.bytes[base..base + CELL_BYTES] {
            *b = 0;
        }
        if (handle.0 as usize) < self.next_free_hint {
            self.next_free_hint = handle.0 as usize;
        }
    }

    pub fn write_payload(&mut self, handle: CellHandle, payload: &[u8; 14]) {
        let base = Self::cell_offset(handle);
        self.bytes[base + 2..base + CELL_BYTES].copy_from_slice(payload);
    }

    pub fn read_payload(&self, handle: CellHandle) -> [u8; 14] {
        let base = Self::cell_offset(handle);
        let mut out = [0u8; 14];
        out.copy_from_slice(&self.bytes[base + 2..base + CELL_BYTES]);
        out
    }

    pub fn read_tag_at(&self, handle: CellHandle) -> u16 {
        self.read_tag(handle.0 as usize)
    }

    /// Snapshot the entire data plane into a fresh Vec.
    pub fn snapshot_bytes(&self) -> Vec<u8> {
        self.bytes.to_vec()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn alloc_and_free_roundtrip() {
        let mut slab = SlabFramebuffer::new();
        let h0 = slab.alloc_cell(0x0003);
        assert_eq!(h0.index(), 0);
        let h1 = slab.alloc_cell(0x0003);
        assert_eq!(h1.index(), 1);
        slab.free_cell(h0);
        let h2 = slab.alloc_cell(0x0003);
        assert_eq!(h2.index(), 0);
    }
}
