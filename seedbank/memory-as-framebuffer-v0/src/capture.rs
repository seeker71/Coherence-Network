//! Lossless binary capture of framebuffer state per snapshot.
//!
//! The mp4 produced by the snapshot thread is a *preview* — h264 + the
//! current rendering math (palette + brightness + halo) are both lossy,
//! so a downstream consumer can't reconstruct (tag, payload, provenance)
//! from rendered pixels. This module captures the substrate itself: the
//! raw `(data_plane, provenance_plane)` for every snapshot, written to
//! a `.mfb` file, so future renderers can produce any view they want
//! (3D, Superliminal, charts, hover-to-inspect, anything) from canonical
//! data.
//!
//! Format (little-endian throughout):
//!
//! ```text
//! HEADER (24 bytes):
//!   magic         : b"MFB0\0\0\0\0"   (8 bytes — 4-byte tag + reserved padding)
//!   version       : u32 = 1            (4 bytes)
//!   grid          : u32 = 256          (4 bytes — cells per side)
//!   cell_bytes    : u32 = 16           (4 bytes — bytes per cell)
//!   fps_hint      : u32                (4 bytes — capture cadence; informational)
//!
//! FRAME (variable; emitted every snapshot tick):
//!   marker        : b"FRM\0"           (4 bytes)
//!   frame_index   : u64                (8 bytes — monotonically increasing)
//!   timestamp_us  : u64                (8 bytes — micros since capture start)
//!   num_changed   : u32                (4 bytes — cells whose state differs from prev frame)
//!   for each changed cell:
//!     cell_idx    : u32                (4 bytes — index into the 256x256 grid)
//!     cell_bytes  : [u8; 16]           (16 bytes — type tag + payload)
//!     provenance  : u32                (4 bytes — last-write source hash)
//!   -- per-cell record: 24 bytes
//! ```
//!
//! The first frame is always a "full" frame: every allocated cell appears
//! in num_changed, so a reader can reconstruct the initial state without
//! needing prior frames. Subsequent frames are deltas — only cells that
//! changed since the previous emitted frame are written.

use std::fs::File;
use std::io::{BufReader, BufWriter, Read, Write};
use std::path::Path;

use crate::allocator::{CELL_BYTES, GRID, NUM_CELLS};

pub const MFB_MAGIC: &[u8; 8] = b"MFB0\0\0\0\0";
pub const MFB_VERSION: u32 = 1;
const FRAME_MARKER: &[u8; 4] = b"FRM\0";
const HEADER_BYTES: usize = 24;
const PER_CELL_RECORD_BYTES: usize = 4 + CELL_BYTES + 4; // 24

/// One snapshot of the substrate at a given frame.
#[derive(Clone, Debug)]
pub struct FrameSnapshot {
    pub frame_index: u64,
    pub timestamp_us: u64,
    pub data: Vec<u8>,        // NUM_CELLS * CELL_BYTES
    pub provenance: Vec<u32>, // NUM_CELLS
}

impl FrameSnapshot {
    pub fn empty(frame_index: u64, timestamp_us: u64) -> Self {
        Self {
            frame_index,
            timestamp_us,
            data: vec![0u8; NUM_CELLS * CELL_BYTES],
            provenance: vec![0u32; NUM_CELLS],
        }
    }
}

/// Writes a `.mfb` capture file. One sink lives behind the snapshot thread
/// when `MFB_CAPTURE` is set; each snapshot tick calls `write_frame`.
pub struct CaptureSink {
    writer: BufWriter<File>,
    prev_data: Vec<u8>,
    prev_prov: Vec<u32>,
    frames_written: u64,
}

impl CaptureSink {
    /// Open `path` and write the header. Subsequent calls to `write_frame`
    /// emit per-frame records (full first, deltas after).
    pub fn open(path: impl AsRef<Path>, fps_hint: u32) -> std::io::Result<Self> {
        let file = File::create(path)?;
        let mut writer = BufWriter::new(file);
        writer.write_all(MFB_MAGIC)?;
        writer.write_all(&MFB_VERSION.to_le_bytes())?;
        writer.write_all(&(GRID as u32).to_le_bytes())?;
        writer.write_all(&(CELL_BYTES as u32).to_le_bytes())?;
        writer.write_all(&fps_hint.to_le_bytes())?;
        Ok(Self {
            writer,
            // Pre-fill with zeros so the first frame's "delta vs prev" surfaces
            // every non-zero cell as changed (full reconstructable initial state).
            prev_data: vec![0u8; NUM_CELLS * CELL_BYTES],
            prev_prov: vec![0u32; NUM_CELLS],
            frames_written: 0,
        })
    }

    /// Emit a frame record. Diffs against the previous frame; only cells
    /// whose data bytes or provenance differ get written.
    pub fn write_frame(
        &mut self,
        frame_index: u64,
        timestamp_us: u64,
        data: &[u8],
        provenance: &[u32],
    ) -> std::io::Result<()> {
        debug_assert_eq!(data.len(), NUM_CELLS * CELL_BYTES);
        debug_assert_eq!(provenance.len(), NUM_CELLS);

        // Find changed cells.
        let mut changed: Vec<u32> = Vec::new();
        for i in 0..NUM_CELLS {
            let cell_off = i * CELL_BYTES;
            let cell_changed = data[cell_off..cell_off + CELL_BYTES]
                != self.prev_data[cell_off..cell_off + CELL_BYTES];
            let prov_changed = provenance[i] != self.prev_prov[i];
            if cell_changed || prov_changed {
                changed.push(i as u32);
            }
        }

        // Frame header.
        self.writer.write_all(FRAME_MARKER)?;
        self.writer.write_all(&frame_index.to_le_bytes())?;
        self.writer.write_all(&timestamp_us.to_le_bytes())?;
        self.writer.write_all(&(changed.len() as u32).to_le_bytes())?;

        // Per-cell records.
        for &idx in &changed {
            let i = idx as usize;
            let cell_off = i * CELL_BYTES;
            self.writer.write_all(&idx.to_le_bytes())?;
            self.writer
                .write_all(&data[cell_off..cell_off + CELL_BYTES])?;
            self.writer.write_all(&provenance[i].to_le_bytes())?;
        }

        // Update state for next delta computation.
        self.prev_data.copy_from_slice(data);
        self.prev_prov.copy_from_slice(provenance);
        self.frames_written += 1;
        Ok(())
    }

    pub fn frames_written(&self) -> u64 {
        self.frames_written
    }

    /// Flush and close. Idempotent in the sense that subsequent calls to
    /// `write_frame` will fail (the writer is consumed).
    pub fn finalize(mut self) -> std::io::Result<()> {
        self.writer.flush()
    }
}

impl Drop for CaptureSink {
    fn drop(&mut self) {
        let _ = self.writer.flush();
    }
}

/// Reads a `.mfb` file frame-by-frame, yielding fully-reconstructed
/// `FrameSnapshot`s (state is reconstructed by applying each frame's delta
/// to a running cumulative buffer). Use this to build any visualization.
///
/// ```ignore
/// for frame in CaptureReader::open("fizzbuzz.mfb")? {
///     let frame = frame?;
///     // frame.data and frame.provenance are the full state at this tick.
///     render_my_view(&frame);
/// }
/// ```
pub struct CaptureReader {
    reader: BufReader<File>,
    cumulative_data: Vec<u8>,
    cumulative_prov: Vec<u32>,
    fps_hint: u32,
    eof: bool,
}

impl CaptureReader {
    pub fn open(path: impl AsRef<Path>) -> std::io::Result<Self> {
        let file = File::open(path)?;
        let mut reader = BufReader::new(file);
        let mut header = [0u8; HEADER_BYTES];
        reader.read_exact(&mut header)?;

        if &header[0..8] != MFB_MAGIC {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "not an .mfb file (magic mismatch)",
            ));
        }
        let version = u32::from_le_bytes(header[8..12].try_into().unwrap());
        let grid = u32::from_le_bytes(header[12..16].try_into().unwrap()) as usize;
        let cell_bytes = u32::from_le_bytes(header[16..20].try_into().unwrap()) as usize;
        let fps_hint = u32::from_le_bytes(header[20..24].try_into().unwrap());

        if version != MFB_VERSION {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                format!("unsupported .mfb version {} (expected {})", version, MFB_VERSION),
            ));
        }
        if grid != GRID || cell_bytes != CELL_BYTES {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                format!(
                    ".mfb geometry mismatch: file says grid={} cell_bytes={}, this build expects {} {}",
                    grid, cell_bytes, GRID, CELL_BYTES
                ),
            ));
        }

        Ok(Self {
            reader,
            cumulative_data: vec![0u8; NUM_CELLS * CELL_BYTES],
            cumulative_prov: vec![0u32; NUM_CELLS],
            fps_hint,
            eof: false,
        })
    }

    pub fn fps_hint(&self) -> u32 {
        self.fps_hint
    }

    fn read_one_frame(&mut self) -> std::io::Result<Option<FrameSnapshot>> {
        let mut marker = [0u8; 4];
        match self.reader.read_exact(&mut marker) {
            Ok(()) => {}
            Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => {
                self.eof = true;
                return Ok(None);
            }
            Err(e) => return Err(e),
        }
        if &marker != FRAME_MARKER {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                format!("frame marker mismatch: got {:?}", marker),
            ));
        }
        let mut buf8 = [0u8; 8];
        self.reader.read_exact(&mut buf8)?;
        let frame_index = u64::from_le_bytes(buf8);
        self.reader.read_exact(&mut buf8)?;
        let timestamp_us = u64::from_le_bytes(buf8);
        let mut buf4 = [0u8; 4];
        self.reader.read_exact(&mut buf4)?;
        let num_changed = u32::from_le_bytes(buf4) as usize;

        for _ in 0..num_changed {
            self.reader.read_exact(&mut buf4)?;
            let cell_idx = u32::from_le_bytes(buf4) as usize;
            if cell_idx >= NUM_CELLS {
                return Err(std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    format!("cell_idx {} out of bounds", cell_idx),
                ));
            }
            let mut cell = [0u8; CELL_BYTES];
            self.reader.read_exact(&mut cell)?;
            self.reader.read_exact(&mut buf4)?;
            let prov = u32::from_le_bytes(buf4);

            let off = cell_idx * CELL_BYTES;
            self.cumulative_data[off..off + CELL_BYTES].copy_from_slice(&cell);
            self.cumulative_prov[cell_idx] = prov;
        }

        Ok(Some(FrameSnapshot {
            frame_index,
            timestamp_us,
            data: self.cumulative_data.clone(),
            provenance: self.cumulative_prov.clone(),
        }))
    }
}

impl Iterator for CaptureReader {
    type Item = std::io::Result<FrameSnapshot>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.eof {
            return None;
        }
        match self.read_one_frame() {
            Ok(Some(snap)) => Some(Ok(snap)),
            Ok(None) => None,
            Err(e) => Some(Err(e)),
        }
    }
}

/// Bytes per cell record in a frame's delta block. Exposed for size estimation.
pub const fn per_cell_record_bytes() -> usize {
    PER_CELL_RECORD_BYTES
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::NamedTempFile;

    fn make_state(seed: u8) -> (Vec<u8>, Vec<u32>) {
        let mut data = vec![0u8; NUM_CELLS * CELL_BYTES];
        let mut prov = vec![0u32; NUM_CELLS];
        // Plant a few cells.
        for i in 0..5usize {
            let off = i * CELL_BYTES;
            data[off] = 0x03; // TAG_U32
            data[off + 2] = seed.wrapping_add(i as u8);
            prov[i] = 0x1000_0000 + i as u32;
        }
        (data, prov)
    }

    #[test]
    fn roundtrip_two_frames_reconstructs_state() {
        let tmp = NamedTempFile::new().unwrap();
        let path = tmp.path().to_path_buf();

        let (d0, p0) = make_state(1);
        let (d1, p1) = make_state(7);

        // Write
        {
            let mut sink = CaptureSink::open(&path, 60).unwrap();
            sink.write_frame(0, 0, &d0, &p0).unwrap();
            sink.write_frame(1, 16_667, &d1, &p1).unwrap();
            assert_eq!(sink.frames_written(), 2);
            sink.finalize().unwrap();
        }

        // Read
        let mut reader = CaptureReader::open(&path).unwrap();
        assert_eq!(reader.fps_hint(), 60);
        let f0 = reader.next().unwrap().unwrap();
        assert_eq!(f0.frame_index, 0);
        assert_eq!(f0.timestamp_us, 0);
        assert_eq!(f0.data, d0);
        assert_eq!(f0.provenance, p0);

        let f1 = reader.next().unwrap().unwrap();
        assert_eq!(f1.frame_index, 1);
        assert_eq!(f1.timestamp_us, 16_667);
        assert_eq!(f1.data, d1);
        assert_eq!(f1.provenance, p1);

        assert!(reader.next().is_none());
    }

    #[test]
    fn delta_encoding_skips_unchanged_cells() {
        let tmp = NamedTempFile::new().unwrap();
        let path = tmp.path().to_path_buf();

        let (d0, p0) = make_state(1);
        // Frame 1: identical to frame 0.
        let d1 = d0.clone();
        let p1 = p0.clone();

        {
            let mut sink = CaptureSink::open(&path, 60).unwrap();
            sink.write_frame(0, 0, &d0, &p0).unwrap();
            sink.write_frame(1, 1000, &d1, &p1).unwrap();
            sink.finalize().unwrap();
        }

        // The second frame should have written 0 cell records (just its
        // 24-byte header). File size = HEADER + frame0_records + frame1_header.
        let len = std::fs::metadata(&path).unwrap().len() as usize;
        let frame_header_bytes = 4 + 8 + 8 + 4; // 24
        let frame0_changed = 5; // we planted 5 cells, all "new" relative to all-zero baseline
        let expected = HEADER_BYTES
            + (frame_header_bytes + frame0_changed * PER_CELL_RECORD_BYTES)
            + frame_header_bytes;
        assert_eq!(len, expected, "frame 1 should write zero cell records");
    }

    #[test]
    fn rejects_bad_magic() {
        let tmp = NamedTempFile::new().unwrap();
        let path = tmp.path().to_path_buf();
        std::fs::write(&path, b"NOTMFB00").unwrap();
        assert!(CaptureReader::open(&path).is_err());
    }
}
