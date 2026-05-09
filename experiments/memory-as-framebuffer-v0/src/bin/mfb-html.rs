//! Convert a .mfb capture into a self-contained HTML replay viewer.
//!
//! Produces a single .html file (no server, no install — open it in any
//! browser) that renders the heap as a grid of cells with:
//! - playback controls (play/pause + scrubber + frame counter)
//! - hover-to-inspect (tag name, decoded value, provenance hash)
//! - color palette matching the v0 mp4 renderer for continuity
//!
//! Usage:
//!     cargo run --release --bin mfb-html -- input.mfb output.html

use std::env;
use std::fs;
use std::io::{self, Write};

use mfb::{
    CaptureReader, FrameSnapshot, CELL_BYTES, GRID, NUM_CELLS, TAG_BOOL, TAG_F32, TAG_F64,
    TAG_FREE, TAG_I32, TAG_I64, TAG_PTR_BOX, TAG_PTR_RAW, TAG_PTR_RC, TAG_PTR_WEAK, TAG_U16,
    TAG_U32, TAG_U64, TAG_U8,
};

fn tag_name(tag: u16) -> &'static str {
    match tag {
        TAG_FREE => "free",
        TAG_U8 => "u8",
        TAG_U16 => "u16",
        TAG_U32 => "u32",
        TAG_U64 => "u64",
        TAG_I32 => "i32",
        TAG_I64 => "i64",
        TAG_BOOL => "bool",
        TAG_F32 => "f32",
        TAG_F64 => "f64",
        TAG_PTR_RAW => "ptr.raw",
        TAG_PTR_BOX => "ptr.box",
        TAG_PTR_RC => "ptr.rc",
        TAG_PTR_WEAK => "ptr.weak",
        _ => "unknown",
    }
}

fn decode_value(tag: u16, payload: &[u8]) -> String {
    fn rd<const N: usize>(p: &[u8]) -> [u8; N] {
        let mut out = [0u8; N];
        out.copy_from_slice(&p[..N]);
        out
    }
    match tag {
        TAG_U8 => format!("{}", payload[0]),
        TAG_U16 => format!("{}", u16::from_le_bytes(rd::<2>(payload))),
        TAG_U32 => format!("{}", u32::from_le_bytes(rd::<4>(payload))),
        TAG_U64 => format!("{}", u64::from_le_bytes(rd::<8>(payload))),
        TAG_I32 => format!("{}", i32::from_le_bytes(rd::<4>(payload))),
        TAG_I64 => format!("{}", i64::from_le_bytes(rd::<8>(payload))),
        TAG_BOOL => {
            if payload[0] != 0 {
                "true".into()
            } else {
                "false".into()
            }
        }
        TAG_F32 => format!("{}", f32::from_le_bytes(rd::<4>(payload))),
        TAG_F64 => format!("{}", f64::from_le_bytes(rd::<8>(payload))),
        TAG_PTR_RAW | TAG_PTR_BOX | TAG_PTR_RC | TAG_PTR_WEAK => {
            let target = u16::from_le_bytes(rd::<2>(payload));
            format!("→ cell {}", target)
        }
        TAG_FREE => "(free)".into(),
        _ => format!("0x{:04x}", tag),
    }
}

/// JSON-string-escape a value (just what we need: `\` `"` and control chars).
fn json_escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    for ch in s.chars() {
        match ch {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                out.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out
}

/// Iterate live (non-free) cells in a snapshot, yielding (idx, tag, value, prov).
fn live_cells(frame: &FrameSnapshot) -> Vec<(usize, u16, String, u32)> {
    let mut out = Vec::new();
    for i in 0..NUM_CELLS {
        let off = i * CELL_BYTES;
        let tag = u16::from_le_bytes([frame.data[off], frame.data[off + 1]]);
        if tag == TAG_FREE {
            continue;
        }
        let payload = &frame.data[off + 2..off + CELL_BYTES];
        let value = decode_value(tag, payload);
        out.push((i, tag, value, frame.provenance[i]));
    }
    out
}

fn main() -> io::Result<()> {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        eprintln!("usage: mfb-html <input.mfb> <output.html>");
        std::process::exit(2);
    }
    let input = &args[1];
    let output = &args[2];

    let mut reader = CaptureReader::open(input)?;
    let fps_hint = reader.fps_hint();

    // Parse all frames into delta records (relative to previous frame).
    // First frame is encoded as `set` containing every live cell.
    let mut prev_state: std::collections::HashMap<usize, (u16, String, u32)> =
        std::collections::HashMap::new();
    let mut frames_json = String::from("[");
    let mut frame_count: usize = 0;
    let mut min_x = GRID;
    let mut min_y = GRID;
    let mut max_x: usize = 0;
    let mut max_y: usize = 0;

    while let Some(frame) = reader.next() {
        let frame = frame?;
        let live = live_cells(&frame);

        // Build new_state map.
        let mut new_state: std::collections::HashMap<usize, (u16, String, u32)> =
            std::collections::HashMap::with_capacity(live.len());
        for (idx, tag, val, prov) in &live {
            new_state.insert(*idx, (*tag, val.clone(), *prov));
            // Track bounding box across all frames for the viewer's grid sizing.
            let x = idx % GRID;
            let y = idx / GRID;
            if x < min_x {
                min_x = x;
            }
            if y < min_y {
                min_y = y;
            }
            if x > max_x {
                max_x = x;
            }
            if y > max_y {
                max_y = y;
            }
        }

        // Diff against prev.
        let mut sets: Vec<(usize, u16, String, u32)> = Vec::new();
        let mut unsets: Vec<usize> = Vec::new();
        for (&idx, val) in &new_state {
            let changed = match prev_state.get(&idx) {
                Some(prev) => prev != val,
                None => true,
            };
            if changed {
                sets.push((idx, val.0, val.1.clone(), val.2));
            }
        }
        for &idx in prev_state.keys() {
            if !new_state.contains_key(&idx) {
                unsets.push(idx);
            }
        }

        if frame_count > 0 {
            frames_json.push(',');
        }
        frames_json.push_str(&format!(
            "{{\"i\":{},\"t\":{},\"s\":[",
            frame.frame_index, frame.timestamp_us
        ));
        let mut first = true;
        for (idx, tag, val, prov) in &sets {
            if !first {
                frames_json.push(',');
            }
            first = false;
            frames_json.push_str(&format!(
                "[{},\"{}\",\"{}\",{}]",
                idx,
                tag_name(*tag),
                json_escape(val),
                prov
            ));
        }
        frames_json.push_str("],\"u\":[");
        let mut first = true;
        for idx in &unsets {
            if !first {
                frames_json.push(',');
            }
            first = false;
            frames_json.push_str(&format!("{}", idx));
        }
        frames_json.push_str("]}");

        prev_state = new_state;
        frame_count += 1;
    }
    frames_json.push(']');

    // If no live cells ever appeared, default the bbox to the top-left 12x12.
    if max_x < min_x {
        min_x = 0;
        min_y = 0;
        max_x = 11;
        max_y = 11;
    }

    let bbox_w = max_x - min_x + 1;
    let bbox_h = max_y - min_y + 1;

    let html = build_html(
        input,
        frame_count,
        fps_hint,
        min_x,
        min_y,
        bbox_w,
        bbox_h,
        &frames_json,
    );

    let mut out_file = fs::File::create(output)?;
    out_file.write_all(html.as_bytes())?;

    eprintln!(
        "wrote {} ({} frames, bbox {}x{} at ({},{}), {} bytes)",
        output,
        frame_count,
        bbox_w,
        bbox_h,
        min_x,
        min_y,
        std::fs::metadata(output)?.len()
    );
    Ok(())
}

fn build_html(
    source: &str,
    frame_count: usize,
    fps_hint: u32,
    min_x: usize,
    min_y: usize,
    bbox_w: usize,
    bbox_h: usize,
    frames_json: &str,
) -> String {
    // The viewer JS reconstructs full state from deltas. The PALETTE matches
    // the v0 mp4 renderer's tag colors so a viewer who's seen the mp4 has
    // continuity of identity.
    format!(
        r##"<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>memory-as-framebuffer replay — {source_esc}</title>
<style>
  :root {{
    --bg: #111;
    --fg: #eee;
    --accent: #79ffe1;
    --muted: #888;
    --panel: #1a1a1a;
  }}
  html, body {{
    margin: 0; padding: 0; background: var(--bg); color: var(--fg);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    overflow: hidden;
  }}
  header {{
    padding: 12px 20px;
    border-bottom: 1px solid #222;
    display: flex; align-items: baseline; gap: 16px;
  }}
  header h1 {{ margin: 0; font-size: 16px; font-weight: 500; }}
  header .meta {{ color: var(--muted); font-size: 13px; }}
  main {{
    display: grid;
    grid-template-columns: 1fr 280px;
    gap: 16px;
    padding: 16px;
    height: calc(100vh - 100px);
  }}
  #heap {{
    display: grid;
    gap: 1px;
    background: #000;
    padding: 8px;
    border-radius: 4px;
    align-self: start;
    aspect-ratio: {bbox_w} / {bbox_h};
    width: 100%;
    max-height: 100%;
    /* Highly non-square bboxes (e.g. linked-list 41x1) render at their
       native aspect rather than getting stretched into a square. */
  }}
  .cell {{
    background: #000;
    cursor: crosshair;
    transition: outline 0.05s ease-in;
    outline: 0px solid transparent;
  }}
  .cell.live {{ background: var(--cell-color, #888); }}
  .cell:hover {{ outline: 2px solid var(--accent); z-index: 1; }}
  #info {{
    background: var(--panel);
    border-radius: 4px;
    padding: 16px;
    font-size: 13px;
    line-height: 1.5;
    overflow: hidden;
  }}
  #info h3 {{ margin: 0 0 12px 0; font-weight: 500; font-size: 14px; }}
  #info .row {{ display: flex; gap: 8px; margin-bottom: 6px; }}
  #info .label {{ color: var(--muted); width: 80px; flex-shrink: 0; }}
  #info .value {{ color: var(--fg); font-family: ui-monospace, "SF Mono", monospace; word-break: break-all; }}
  #info.empty .value {{ color: var(--muted); }}
  footer {{
    padding: 8px 20px;
    border-top: 1px solid #222;
    display: flex; align-items: center; gap: 12px;
    background: var(--panel);
  }}
  #scrubber {{ flex: 1; }}
  #play {{
    background: var(--accent); color: #000; border: 0;
    padding: 4px 12px; border-radius: 3px; font-weight: 500; cursor: pointer;
    font-size: 13px;
  }}
  #play:hover {{ filter: brightness(1.1); }}
  #counter {{ color: var(--muted); font-size: 13px; font-family: ui-monospace, monospace; min-width: 130px; }}
</style>
</head>
<body>
<header>
  <h1>memory-as-framebuffer / replay</h1>
  <span class="meta">{source_esc} · {frame_count} frames · {fps_hint} fps · viewport {bbox_w}×{bbox_h} from ({min_x},{min_y})</span>
</header>
<main>
  <div id="heap"></div>
  <div id="info" class="empty">
    <h3>Cell inspector</h3>
    <div class="row"><span class="label">Index</span><span class="value" id="cell-id">hover a cell</span></div>
    <div class="row"><span class="label">Grid (x,y)</span><span class="value" id="cell-xy">—</span></div>
    <div class="row"><span class="label">Tag</span><span class="value" id="cell-tag">—</span></div>
    <div class="row"><span class="label">Value</span><span class="value" id="cell-val">—</span></div>
    <div class="row"><span class="label">Provenance</span><span class="value" id="cell-prov">—</span></div>
    <hr style="border-color: #222; margin: 12px 0;">
    <p style="color: var(--muted); font-size: 12px;">
      Pointers show their target cell index. Provenance is the
      <code>crc32(file:line)</code> of the call site of the most recent
      <code>track!</code> on this cell. Pointer cells share inner color with
      their target — the v0/v1-pointers Superliminal idiom.
    </p>
  </div>
</main>
<footer>
  <button id="play">▶ Play</button>
  <input type="range" id="scrubber" min="0" max="{max_idx}" value="0">
  <span id="counter">Frame 0 / {max_idx}</span>
</footer>
<script>
const GRID = {GRID};
const FPS = {fps_hint};
const BBOX = {{ minX: {min_x}, minY: {min_y}, w: {bbox_w}, h: {bbox_h} }};
const FRAMES = {frames_json};

const PALETTE = {{
  free: "#000000",
  u8: "#ff5050", u16: "#ffa03c", u32: "#fff03c", u64: "#78e650",
  i32: "#50e6e6", i64: "#508cff",
  bool: "#c850ff",
  f32: "#ff64c8", f64: "#f0f0f0",
  "ptr.raw": "#888888", "ptr.box": "#ffffff",
  "ptr.rc": "#bbbbbb", "ptr.weak": "#666666",
  unknown: "#444444"
}};

const heapEl = document.getElementById("heap");
const scrub = document.getElementById("scrubber");
const counter = document.getElementById("counter");
const playBtn = document.getElementById("play");
const info = {{
  panel: document.getElementById("info"),
  id: document.getElementById("cell-id"),
  xy: document.getElementById("cell-xy"),
  tag: document.getElementById("cell-tag"),
  val: document.getElementById("cell-val"),
  prov: document.getElementById("cell-prov"),
}};

heapEl.style.gridTemplateColumns = `repeat(${{BBOX.w}}, 1fr)`;
heapEl.style.gridTemplateRows = `repeat(${{BBOX.h}}, 1fr)`;

const cellEls = new Map();
for (let y = BBOX.minY; y < BBOX.minY + BBOX.h; y++) {{
  for (let x = BBOX.minX; x < BBOX.minX + BBOX.w; x++) {{
    const idx = y * GRID + x;
    const el = document.createElement("div");
    el.className = "cell";
    el.dataset.idx = idx;
    el.dataset.x = x;
    el.dataset.y = y;
    el.addEventListener("mouseenter", () => showCell(idx));
    heapEl.appendChild(el);
    cellEls.set(idx, el);
  }}
}}

const liveState = new Map();  // idx → {{tag, val, prov}}
let appliedFrame = -1;

function setCell(idx, tag, val, prov) {{
  liveState.set(idx, {{ tag, val, prov }});
  const el = cellEls.get(idx);
  if (el) {{
    el.classList.add("live");
    el.style.setProperty("--cell-color", PALETTE[tag] || PALETTE.unknown);
    el.dataset.tag = tag;
  }}
}}

function unsetCell(idx) {{
  liveState.delete(idx);
  const el = cellEls.get(idx);
  if (el) {{
    el.classList.remove("live");
    el.style.removeProperty("--cell-color");
    delete el.dataset.tag;
  }}
}}

function applyFrameDelta(toIdx) {{
  if (toIdx === appliedFrame) return;
  // Stepping backward — replay from the start (frame 0 is full state).
  if (toIdx < appliedFrame) {{
    for (const idx of Array.from(liveState.keys())) unsetCell(idx);
    appliedFrame = -1;
  }}
  for (let f = appliedFrame + 1; f <= toIdx; f++) {{
    const fr = FRAMES[f];
    if (!fr) break;
    for (const [idx, tag, val, prov] of fr.s) setCell(idx, tag, val, prov);
    for (const idx of fr.u) unsetCell(idx);
  }}
  appliedFrame = toIdx;
  const fr = FRAMES[toIdx];
  counter.textContent = `Frame ${{toIdx}} / {max_idx} · t=${{(fr.t / 1000).toFixed(0)}}ms`;
}}

function showCell(idx) {{
  const cell = liveState.get(idx);
  const x = idx % GRID;
  const y = Math.floor(idx / GRID);
  info.id.textContent = idx;
  info.xy.textContent = `(${{x}}, ${{y}})`;
  if (cell) {{
    info.panel.classList.remove("empty");
    info.tag.textContent = cell.tag;
    info.val.textContent = cell.val;
    info.prov.textContent = "0x" + cell.prov.toString(16).padStart(8, "0");
  }} else {{
    info.panel.classList.add("empty");
    info.tag.textContent = "(free)";
    info.val.textContent = "—";
    info.prov.textContent = "—";
  }}
}}

scrub.addEventListener("input", () => {{
  applyFrameDelta(parseInt(scrub.value, 10));
}});

let playing = false;
let playTimer = null;
playBtn.addEventListener("click", () => {{
  if (playing) {{
    clearInterval(playTimer);
    playBtn.textContent = "▶ Play";
    playing = false;
  }} else {{
    playTimer = setInterval(() => {{
      let next = appliedFrame + 1;
      if (next >= FRAMES.length) next = 0;
      scrub.value = next;
      applyFrameDelta(next);
    }}, 1000 / FPS);
    playBtn.textContent = "❚❚ Pause";
    playing = true;
  }}
}});

// Keyboard: arrows step frame-by-frame; space toggles play.
window.addEventListener("keydown", (e) => {{
  if (e.target.tagName === "INPUT") return;
  if (e.code === "ArrowRight") {{
    const next = Math.min(appliedFrame + 1, FRAMES.length - 1);
    scrub.value = next;
    applyFrameDelta(next);
  }} else if (e.code === "ArrowLeft") {{
    const prev = Math.max(appliedFrame - 1, 0);
    scrub.value = prev;
    applyFrameDelta(prev);
  }} else if (e.code === "Space") {{
    e.preventDefault();
    playBtn.click();
  }}
}});

applyFrameDelta(0);
</script>
</body>
</html>
"##,
        source_esc = json_escape(source),
        frame_count = frame_count,
        fps_hint = fps_hint,
        min_x = min_x,
        min_y = min_y,
        bbox_w = bbox_w,
        bbox_h = bbox_h,
        max_idx = frame_count.saturating_sub(1),
        frames_json = frames_json,
        GRID = GRID,
    )
}
