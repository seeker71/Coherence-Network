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
pub mod ffmpeg;
pub mod pointer;
pub mod render;
pub mod snapshot;

use once_cell::sync::OnceCell;
use std::sync::Mutex;

pub use allocator::{CellHandle, SlabFramebuffer, CELL_BYTES, GRID, NUM_CELLS};
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

/// Initialize the global framebuffer. Spawns the snapshot thread which spawns ffmpeg
/// and pipes RGBA frames at MFB_FPS (default 60) to OUTPUT (default "framebuffer.mp4").
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

    // Spawn ffmpeg + snapshot thread.
    let pipe = FfmpegPipe::spawn(output_path, fps)?;
    let thread = SnapshotThread::spawn(fps, pipe);
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

/// Shut down the global framebuffer (closes ffmpeg, finalizes mp4).
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
        let prov = crc32fast::hash(format!("{}:{}", caller.file(), caller.line()).as_bytes());

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
        let prov = crc32fast::hash(format!("{}:{}", file, line).as_bytes());
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
