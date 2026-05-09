//! memory-as-framebuffer v0 — the heap as a recordable framebuffer.
//!
//! A 256x256 grid of 16-byte cells (1MB) holds `Tracked<T>` values for nine
//! primitive types. A parallel u32 plane stores `crc32(file:line)` for each
//! cell's last write. A snapshot thread renders both planes to RGBA frames
//! at 60 fps and pipes them to ffmpeg, producing an mp4 of the heap breathing.
//!
//! Single mutator thread + one internal snapshot thread. v0 does not include
//! pointer windows, 3D, LOD, navigation, or substrate integration.

pub mod allocator;
pub mod capture;
pub mod ffmpeg;
pub mod pointer;
pub mod render;
pub mod snapshot;

use once_cell::sync::OnceCell;
use std::collections::HashMap;
use std::sync::Mutex;

pub use allocator::{CellHandle, SlabFramebuffer, CELL_BYTES, GRID, NUM_CELLS};
pub use capture::{CaptureReader, CaptureSink, FrameSnapshot, MFB_MAGIC, MFB_VERSION};
pub use ffmpeg::FfmpegPipe;
pub use pointer::{
    is_pointer_tag, BoxPtr, Pointer, PointerKind, RcPtr, WeakPtr, CYCLE_TERMINATOR_RGB,
    POINTER_FOLLOW_CAP, TAG_PTR_BOX, TAG_PTR_RAW, TAG_PTR_RC, TAG_PTR_WEAK,
};
pub use render::FrameRgba;
pub use snapshot::SnapshotThread;

/// Type tag = 0 means free slot.
pub const TAG_FREE: u16 = 0x0000;
pub const TAG_U8: u16 = 0x0001;
pub const TAG_U16: u16 = 0x0002;
pub const TAG_U32: u16 = 0x0003;
pub const TAG_U64: u16 = 0x0004;
pub const TAG_I32: u16 = 0x0005;
pub const TAG_I64: u16 = 0x0006;
pub const TAG_BOOL: u16 = 0x0007;
pub const TAG_F32: u16 = 0x0008;
pub const TAG_F64: u16 = 0x0009;

/// Trait implemented for every primitive that fits in a 14-byte payload
/// and has a deterministic 2-byte type tag.
pub trait TrackedPrimitive: Copy + 'static {
    const TAG: u16;
    fn write_payload(self, dst: &mut [u8; 14]);
    fn read_payload(src: &[u8; 14]) -> Self;
}

macro_rules! impl_primitive {
    ($t:ty, $tag:expr) => {
        impl TrackedPrimitive for $t {
            const TAG: u16 = $tag;
            fn write_payload(self, dst: &mut [u8; 14]) {
                let bytes = self.to_le_bytes();
                for b in dst.iter_mut() {
                    *b = 0;
                }
                dst[..bytes.len()].copy_from_slice(&bytes);
            }
            fn read_payload(src: &[u8; 14]) -> Self {
                let mut buf = [0u8; std::mem::size_of::<$t>()];
                buf.copy_from_slice(&src[..std::mem::size_of::<$t>()]);
                <$t>::from_le_bytes(buf)
            }
        }
    };
}

impl_primitive!(u8, TAG_U8);
impl_primitive!(u16, TAG_U16);
impl_primitive!(u32, TAG_U32);
impl_primitive!(u64, TAG_U64);
impl_primitive!(i32, TAG_I32);
impl_primitive!(i64, TAG_I64);
impl_primitive!(f32, TAG_F32);
impl_primitive!(f64, TAG_F64);

impl TrackedPrimitive for bool {
    const TAG: u16 = TAG_BOOL;
    fn write_payload(self, dst: &mut [u8; 14]) {
        for b in dst.iter_mut() {
            *b = 0;
        }
        dst[0] = if self { 1 } else { 0 };
    }
    fn read_payload(src: &[u8; 14]) -> Self {
        src[0] != 0
    }
}

/// The global framebuffer (data plane + provenance plane + snapshot thread + ffmpeg pipe).
pub struct Framebuffer {
    pub data: Mutex<SlabFramebuffer>,
    pub provenance: Mutex<Vec<u32>>, // length = NUM_CELLS
    snapshot: Mutex<Option<SnapshotThread>>,
}

impl Framebuffer {
    fn new() -> Self {
        Self {
            data: Mutex::new(SlabFramebuffer::new()),
            provenance: Mutex::new(vec![0u32; NUM_CELLS]),
            snapshot: Mutex::new(None),
        }
    }
}

impl Drop for Framebuffer {
    fn drop(&mut self) {
        // Stop the snapshot thread (which closes ffmpeg stdin and waits).
        if let Ok(mut guard) = self.snapshot.lock() {
            if let Some(thread) = guard.take() {
                thread.shutdown();
            }
        }
    }
}

static FRAMEBUFFER: OnceCell<Framebuffer> = OnceCell::new();

/// Process-global registry mapping `crc32(file:line)` provenance hashes back
/// to their `(file, line)` origin. Populated by `compute_and_register_prov()`
/// every time a `track!` or `Tracked::new[_at]()` runs. Dumped to a
/// `{MFB_CAPTURE}.provmap` JSON sidecar at `shutdown_framebuffer()` so any
/// downstream renderer (mfb-html, future 3D, etc.) can resolve hashes back
/// to source locations and group cells by recipe.
static PROV_REGISTRY: OnceCell<Mutex<HashMap<u32, (String, u32)>>> = OnceCell::new();

fn prov_registry() -> &'static Mutex<HashMap<u32, (String, u32)>> {
    PROV_REGISTRY.get_or_init(|| Mutex::new(HashMap::new()))
}

/// Compute the provenance hash for a `(file, line)` source location AND
/// register the mapping in the global registry. All three primitive write
/// sites (`Tracked::new`, `Tracked::new_at`, `track!` via
/// `write_with_provenance`) route through this so the registry is complete
/// at shutdown time.
fn compute_and_register_prov(file: &str, line: u32) -> u32 {
    let hash = crc32fast::hash(format!("{}:{}", file, line).as_bytes());
    if let Ok(mut reg) = prov_registry().lock() {
        reg.entry(hash)
            .or_insert_with(|| (file.to_string(), line));
    }
    hash
}

/// Initialize the global framebuffer. Spawns the snapshot thread which spawns ffmpeg
/// and pipes RGBA frames at MFB_FPS (default 60) to OUTPUT (default "framebuffer.mp4").
///
/// If `MFB_CAPTURE` env var is set, the snapshot thread *also* writes a
/// lossless `.mfb` binary capture to that path — every snapshot's raw
/// `(data_plane, provenance_plane)` is recorded, so future renderers can
/// reconstruct any view from canonical data instead of from h264-lossy
/// rendered pixels.
///
/// Returns an error if ffmpeg is not on PATH or already initialized.
pub fn init_framebuffer(output_path: &str) -> Result<(), String> {
    let fps: u32 = std::env::var("MFB_FPS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(60);

    // Probe ffmpeg before constructing anything.
    ffmpeg::ensure_ffmpeg_available()?;

    let fb = Framebuffer::new();

    // Optional lossless substrate capture, opened *before* spawning the
    // snapshot thread so any open() failure surfaces immediately.
    let capture_sink = if let Ok(capture_path) = std::env::var("MFB_CAPTURE") {
        Some(
            CaptureSink::open(&capture_path, fps)
                .map_err(|e| format!("failed to open MFB_CAPTURE={}: {}", capture_path, e))?,
        )
    } else {
        None
    };

    // Spawn ffmpeg + snapshot thread.
    let pipe = FfmpegPipe::spawn(output_path, fps)?;
    let thread = SnapshotThread::spawn(fps, pipe, capture_sink);
    *fb.snapshot.lock().unwrap() = Some(thread);

    FRAMEBUFFER
        .set(fb)
        .map_err(|_| "framebuffer already initialized".to_string())?;
    Ok(())
}

/// Look up the global framebuffer. Panics if not initialized.
pub fn framebuffer() -> &'static Framebuffer {
    FRAMEBUFFER
        .get()
        .expect("framebuffer not initialized; call init_framebuffer() first")
    }

/// Shut down the global framebuffer (closes ffmpeg, finalizes mp4 + .mfb).
/// Also dumps the provenance registry to a `{MFB_CAPTURE}.provmap` JSON
/// sidecar so downstream renderers can resolve provenance hashes back to
/// `(file, line)` source locations.
///
/// Idempotent. Should be called at the end of main; otherwise the OnceCell
/// is leaked at process exit and ffmpeg may not flush cleanly.
pub fn shutdown_framebuffer() {
    if let Some(fb) = FRAMEBUFFER.get() {
        if let Ok(mut guard) = fb.snapshot.lock() {
            if let Some(thread) = guard.take() {
                thread.shutdown();
            }
        }
    }
    if let Ok(capture_path) = std::env::var("MFB_CAPTURE") {
        let provmap_path = format!("{}.provmap", capture_path);
        if let Err(e) = write_provmap_json(&provmap_path) {
            eprintln!(
                "memory-as-framebuffer: failed to write {}: {}",
                provmap_path, e
            );
        }
    }
}

/// Serialize the provenance registry to a JSON file at `path`. Manual
/// serialization avoids pulling serde into the crate just for this.
fn write_provmap_json(path: &str) -> std::io::Result<()> {
    let reg = prov_registry()
        .lock()
        .map_err(|_| std::io::Error::new(std::io::ErrorKind::Other, "provmap mutex poisoned"))?;
    let mut s = String::from("{");
    let mut first = true;
    for (hash, (file, line)) in reg.iter() {
        if !first {
            s.push(',');
        }
        first = false;
        let escaped = file.replace('\\', "\\\\").replace('"', "\\\"");
        s.push_str(&format!(
            "\"{}\":{{\"file\":\"{}\",\"line\":{}}}",
            hash, escaped, line
        ));
    }
    s.push('}');
    std::fs::write(path, s)
}

/// A tracked primitive value. Construction allocates a cell; the tag and
/// payload are written immediately. Drop frees the cell.
pub struct Tracked<T: TrackedPrimitive> {
    handle: CellHandle,
    _phantom: std::marker::PhantomData<T>,
}

impl<T: TrackedPrimitive> Tracked<T> {
    /// Allocate a cell and write `value` with the type tag. The provenance
    /// for the initial write is stamped at the call site.
    #[track_caller]
    pub fn new(value: T) -> Self {
        let caller = std::panic::Location::caller();
        let prov = compute_and_register_prov(caller.file(), caller.line());

        let fb = framebuffer();
        let handle = {
            let mut data = fb.data.lock().unwrap();
            let h = data.alloc_cell(T::TAG);
            let mut payload = [0u8; 14];
            value.write_payload(&mut payload);
            data.write_payload(h, &payload);
            h
        };
        {
            let mut prov_plane = fb.provenance.lock().unwrap();
            prov_plane[handle.index() as usize] = prov;
        }

        Tracked {
            handle,
            _phantom: std::marker::PhantomData,
        }
    }

    /// Allocate at a specific cell index (rather than next-free-slot). Use
    /// this when an example wants a 2D grid layout: pass `gy * GRID + gx` to
    /// place at grid position (gx, gy). Panics if the slot is already used.
    #[track_caller]
    pub fn new_at(idx: usize, value: T) -> Self {
        let caller = std::panic::Location::caller();
        let prov = compute_and_register_prov(caller.file(), caller.line());

        let fb = framebuffer();
        let handle = {
            let mut data = fb.data.lock().unwrap();
            let h = data.alloc_at(idx, T::TAG);
            let mut payload = [0u8; 14];
            value.write_payload(&mut payload);
            data.write_payload(h, &payload);
            h
        };
        {
            let mut prov_plane = fb.provenance.lock().unwrap();
            prov_plane[handle.index() as usize] = prov;
        }

        Tracked {
            handle,
            _phantom: std::marker::PhantomData,
        }
    }

    pub fn handle(&self) -> CellHandle {
        self.handle
    }

    pub fn get(&self) -> T {
        let fb = framebuffer();
        let data = fb.data.lock().unwrap();
        let payload = data.read_payload(self.handle);
        T::read_payload(&payload)
    }

    /// Write a new value AND stamp provenance at the given file:line.
    /// Used by the `track!` macro; not normally called directly.
    pub fn write_with_provenance(&mut self, value: T, file: &str, line: u32) {
        let prov = compute_and_register_prov(file, line);
        let fb = framebuffer();
        {
            let mut data = fb.data.lock().unwrap();
            let mut payload = [0u8; 14];
            value.write_payload(&mut payload);
            data.write_payload(self.handle, &payload);
        }
        {
            let mut prov_plane = fb.provenance.lock().unwrap();
            prov_plane[self.handle.index() as usize] = prov;
        }
    }
}

impl<T: TrackedPrimitive> Drop for Tracked<T> {
    fn drop(&mut self) {
        // If the framebuffer is still alive, free the cell. If not, just leave it.
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

/// Write `expr` into a `Tracked<T>` field, stamping provenance at the call site.
///
/// Usage: `track!(my_field, new_value)` where `my_field: &mut Tracked<T>` and
/// `new_value: T`.
#[macro_export]
macro_rules! track {
    ($field:expr, $expr:expr) => {{
        let __value = $expr;
        $field.write_with_provenance(__value, file!(), line!());
    }};
}
