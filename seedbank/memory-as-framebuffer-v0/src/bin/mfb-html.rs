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

/// Parse `{input}.provmap` if present, returning a JSON object string ready
/// to embed. Empty `{}` if missing or unreadable. The provmap is written by
/// `shutdown_framebuffer()` when MFB_CAPTURE was set; format is
/// `{ "<hash_decimal>": {"file": "...", "line": N}, ... }`.
fn load_provmap_json(input_path: &str) -> String {
    let provmap_path = format!("{}.provmap", input_path);
    match std::fs::read_to_string(&provmap_path) {
        Ok(content) => {
            // Sanity-check it's a JSON object — pass through verbatim if so.
            if content.trim_start().starts_with('{') {
                content
            } else {
                eprintln!(
                    "warning: {} doesn't look like JSON; ignoring",
                    provmap_path
                );
                "{}".into()
            }
        }
        Err(_) => {
            eprintln!(
                "note: no provmap sidecar at {} — recipe leaderboard will show raw hashes",
                provmap_path
            );
            "{}".into()
        }
    }
}

fn main() -> io::Result<()> {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        eprintln!("usage: mfb-html <input.mfb> <output.html>");
        std::process::exit(2);
    }
    let input = &args[1];
    let output = &args[2];

    let provmap_json = load_provmap_json(input);

    let mut reader = CaptureReader::open(input)?;
    let fps_hint = reader.fps_hint();

    // Parse all frames into delta records (relative to previous frame).
    let mut prev_state: std::collections::HashMap<usize, (u16, String, u32)> =
        std::collections::HashMap::new();
    let mut frames_json = String::from("[");
    let mut frame_count: usize = 0;
    let mut min_x = GRID;
    let mut min_y = GRID;
    let mut max_x: usize = 0;
    let mut max_y: usize = 0;

    // Vitality lens accumulators: total writes per cell + per provenance hash.
    let mut cell_writes: std::collections::HashMap<usize, u64> =
        std::collections::HashMap::new();
    let mut prov_writes: std::collections::HashMap<u32, u64> =
        std::collections::HashMap::new();

    // Nutrient-flow accumulators: directed co-occurrence between cells in
    // adjacent frames. If cell A was in frame N's changed-set and cell B is
    // in frame N+1's, that counts as one A → B flow event.
    let mut flows: std::collections::HashMap<(usize, usize), u64> =
        std::collections::HashMap::new();
    let mut cell_latest_prov: std::collections::HashMap<usize, u32> =
        std::collections::HashMap::new();
    let mut prev_changed_cells: Vec<usize> = Vec::new();

    // Compound-recipe accumulators: 3-frame patterns A → B → C. Surfaces
    // recurring multi-step co-work patterns (e.g. Edit → Bash → Bash for
    // edit-then-build-then-test) beyond what pair flows alone can name.
    // Allows A == C (loops like Bash → Read → Bash) but disallows degenerate
    // self-steps within a chain (A == B or B == C).
    let mut compound: std::collections::HashMap<(usize, usize, usize), u64> =
        std::collections::HashMap::new();
    let mut prev_prev_changed: Vec<usize> = Vec::new();

    while let Some(frame) = reader.next() {
        let frame = frame?;
        let live = live_cells(&frame);

        let mut new_state: std::collections::HashMap<usize, (u16, String, u32)> =
            std::collections::HashMap::with_capacity(live.len());
        for (idx, tag, val, prov) in &live {
            new_state.insert(*idx, (*tag, val.clone(), *prov));
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

        let mut sets: Vec<(usize, u16, String, u32)> = Vec::new();
        let mut unsets: Vec<usize> = Vec::new();
        for (&idx, val) in &new_state {
            let changed = match prev_state.get(&idx) {
                Some(prev) => prev != val,
                None => true,
            };
            if changed {
                sets.push((idx, val.0, val.1.clone(), val.2));
                // Vitality counters: count one "write" per changed cell per frame.
                *cell_writes.entry(idx).or_insert(0) += 1;
                *prov_writes.entry(val.2).or_insert(0) += 1;
                // Track this cell's most-recent provenance for flow labels.
                cell_latest_prov.insert(idx, val.2);
            }
        }
        for &idx in prev_state.keys() {
            if !new_state.contains_key(&idx) {
                unsets.push(idx);
            }
        }

        // Nutrient flow: every (a in prev frame's changed-set) → (b in this
        // frame's changed-set) is one flow event. This captures "writing X
        // tends to be followed by writing Y" — which file edits flow into
        // which other edits, which tools follow which other tools.
        if !prev_changed_cells.is_empty() && !sets.is_empty() {
            for &a in &prev_changed_cells {
                for (b_idx, _, _, _) in &sets {
                    if a != *b_idx {
                        *flows.entry((a, *b_idx)).or_insert(0) += 1;
                    }
                }
            }
        }

        // Compound recipe: every (a in prev_prev) → (b in prev) → (c in this)
        // chain is one compound event. Allows A == C (e.g. Bash → Read → Bash
        // ping-pong) but disallows A == B or B == C (degenerate self-steps).
        if !prev_prev_changed.is_empty()
            && !prev_changed_cells.is_empty()
            && !sets.is_empty()
        {
            for &a in &prev_prev_changed {
                for &b in &prev_changed_cells {
                    if a == b {
                        continue;
                    }
                    for (c_idx, _, _, _) in &sets {
                        let c = *c_idx;
                        if b != c {
                            *compound.entry((a, b, c)).or_insert(0) += 1;
                        }
                    }
                }
            }
        }

        let new_prev: Vec<usize> = sets.iter().map(|(idx, _, _, _)| *idx).collect();
        prev_prev_changed = std::mem::take(&mut prev_changed_cells);
        prev_changed_cells = new_prev;

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

    if max_x < min_x {
        min_x = 0;
        min_y = 0;
        max_x = 11;
        max_y = 11;
    }

    let bbox_w = max_x - min_x + 1;
    let bbox_h = max_y - min_y + 1;

    // Serialize vitality data to compact JSON.
    let cell_writes_json = {
        let mut s = String::from("{");
        let mut first = true;
        for (idx, count) in &cell_writes {
            if !first {
                s.push(',');
            }
            first = false;
            s.push_str(&format!("\"{}\":{}", idx, count));
        }
        s.push('}');
        s
    };
    let prov_writes_json = {
        let mut s = String::from("{");
        let mut first = true;
        for (hash, count) in &prov_writes {
            if !first {
                s.push(',');
            }
            first = false;
            s.push_str(&format!("\"{}\":{}", hash, count));
        }
        s.push('}');
        s
    };

    // Top-N nutrient flows: sort by count desc, take 50. Each entry is
    // [src_cell_idx, dst_cell_idx, src_latest_prov, dst_latest_prov, count]
    // so the JS can resolve labels via PROVMAP and rank with bars.
    const FLOW_LIMIT: usize = 50;
    let mut flow_vec: Vec<((usize, usize), u64)> = flows.into_iter().collect();
    flow_vec.sort_by(|a, b| b.1.cmp(&a.1));
    flow_vec.truncate(FLOW_LIMIT);
    let flow_count = flow_vec.len();
    let flows_json = {
        let mut s = String::from("[");
        let mut first = true;
        for ((a, b), n) in &flow_vec {
            if !first {
                s.push(',');
            }
            first = false;
            let pa = cell_latest_prov.get(a).copied().unwrap_or(0);
            let pb = cell_latest_prov.get(b).copied().unwrap_or(0);
            s.push_str(&format!("[{},{},{},{},{}]", a, b, pa, pb, n));
        }
        s.push(']');
        s
    };

    // Top-N compound recipes: sort by count desc, take 30. Each entry is
    // [a, b, c, pa, pb, pc, count]. The leaderboard surfaces 3-step
    // patterns; longer k-grams (4+) tend to be too sparse to be useful
    // in typical session sizes, so v0 stops at 3.
    const COMPOUND_LIMIT: usize = 30;
    let mut compound_vec: Vec<((usize, usize, usize), u64)> = compound.into_iter().collect();
    compound_vec.sort_by(|a, b| b.1.cmp(&a.1));
    compound_vec.truncate(COMPOUND_LIMIT);
    let compound_count = compound_vec.len();
    let compound_json = {
        let mut s = String::from("[");
        let mut first = true;
        for ((a, b, c), n) in &compound_vec {
            if !first {
                s.push(',');
            }
            first = false;
            let pa = cell_latest_prov.get(a).copied().unwrap_or(0);
            let pb = cell_latest_prov.get(b).copied().unwrap_or(0);
            let pc = cell_latest_prov.get(c).copied().unwrap_or(0);
            s.push_str(&format!("[{},{},{},{},{},{},{}]", a, b, c, pa, pb, pc, n));
        }
        s.push(']');
        s
    };

    let html = build_html(
        input,
        frame_count,
        fps_hint,
        min_x,
        min_y,
        bbox_w,
        bbox_h,
        &frames_json,
        &cell_writes_json,
        &prov_writes_json,
        &provmap_json,
        &flows_json,
        &compound_json,
    );

    let mut out_file = fs::File::create(output)?;
    out_file.write_all(html.as_bytes())?;

    eprintln!(
        "wrote {} ({} frames, bbox {}x{} at ({},{}), {} unique cells, {} unique recipes, {} top flows, {} top compounds, {} bytes)",
        output,
        frame_count,
        bbox_w,
        bbox_h,
        min_x,
        min_y,
        cell_writes.len(),
        prov_writes.len(),
        flow_count,
        compound_count,
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
    cell_writes_json: &str,
    prov_writes_json: &str,
    provmap_json: &str,
    flows_json: &str,
    compound_json: &str,
) -> String {
    // The viewer JS reconstructs full state from deltas. The PALETTE matches
    // the v0 mp4 renderer's tag colors so a viewer who's seen the mp4 has
    // continuity of identity. Vitality mode uses a heat-scale instead.
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
  header .meta {{ color: var(--muted); font-size: 13px; flex: 1; }}
  header .modes {{ display: flex; gap: 0; }}
  header .modes button {{
    background: #1f1f1f; color: var(--muted); border: 0;
    padding: 4px 10px; cursor: pointer; font-size: 12px;
    border-right: 1px solid #2a2a2a;
  }}
  header .modes button:first-child {{ border-radius: 3px 0 0 3px; }}
  header .modes button:last-child {{ border-radius: 0 3px 3px 0; border-right: 0; }}
  header .modes button.active {{ background: var(--accent); color: #000; font-weight: 500; }}
  header .modes button:hover:not(.active) {{ color: var(--fg); }}
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
  #side {{
    background: var(--panel);
    border-radius: 4px;
    padding: 16px;
    font-size: 13px;
    line-height: 1.5;
    overflow-y: auto;
    overflow-x: hidden;
  }}
  #side h3 {{ margin: 0 0 12px 0; font-weight: 500; font-size: 14px; }}
  #side .row {{ display: flex; gap: 8px; margin-bottom: 6px; }}
  #side .label {{ color: var(--muted); width: 80px; flex-shrink: 0; }}
  #side .value {{ color: var(--fg); font-family: ui-monospace, "SF Mono", monospace; word-break: break-all; }}
  #side.empty .value {{ color: var(--muted); }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; }}
  #recipes ol {{ margin: 0; padding: 0; list-style: none; counter-reset: rank; }}
  #recipes li {{
    counter-increment: rank;
    display: grid;
    grid-template-columns: 24px 1fr auto;
    gap: 8px;
    align-items: baseline;
    padding: 6px 0;
    border-bottom: 1px solid #222;
    font-size: 12px;
  }}
  #recipes li:before {{
    content: counter(rank);
    color: var(--muted);
    text-align: right;
    font-family: ui-monospace, monospace;
  }}
  #recipes .src {{ color: var(--fg); font-family: ui-monospace, monospace; word-break: break-all; }}
  #recipes .count {{
    color: var(--accent);
    font-family: ui-monospace, monospace;
    font-variant-numeric: tabular-nums;
  }}
  #recipes .bar {{
    grid-column: 1 / -1;
    height: 2px;
    background: linear-gradient(to right, var(--accent) var(--bar-pct, 0%), transparent var(--bar-pct, 0%));
    margin-top: 4px;
  }}
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
  <div class="modes">
    <button id="mode-identity" class="active" title="Color cells by their type tag">Identity</button>
    <button id="mode-vitality" title="Color cells by total write count (busy heatmap) and rank recipes by activity">Vitality</button>
  </div>
</header>
<main>
  <div id="heap"></div>
  <aside id="side" class="empty">
    <div id="inspector" class="panel active">
      <h3>Cell inspector</h3>
      <div class="row"><span class="label">Index</span><span class="value" id="cell-id">hover a cell</span></div>
      <div class="row"><span class="label">Grid (x,y)</span><span class="value" id="cell-xy">—</span></div>
      <div class="row"><span class="label">Tag</span><span class="value" id="cell-tag">—</span></div>
      <div class="row"><span class="label">Value</span><span class="value" id="cell-val">—</span></div>
      <div class="row"><span class="label">Provenance</span><span class="value" id="cell-prov">—</span></div>
      <div class="row"><span class="label">Source</span><span class="value" id="cell-src">—</span></div>
      <div class="row"><span class="label">Writes</span><span class="value" id="cell-writes">—</span></div>
      <hr style="border-color: #222; margin: 12px 0;">
      <p style="color: var(--muted); font-size: 12px;">
        Pointers show their target cell index. Provenance is the
        <code>crc32(file:line)</code> of the call site of the most recent
        <code>track!</code> on this cell. Pointer cells share inner color
        with their target — the v0/v1-pointers Superliminal idiom.
      </p>
    </div>
    <div id="recipes" class="panel">
      <h3>Most-alive recipes</h3>
      <p style="color: var(--muted); font-size: 12px; margin: 0 0 12px 0;">
        Recipes ranked by total cell-writes across the run. The bar shows
        each recipe's share of the busiest one. Click a recipe to highlight
        all cells it writes to.
      </p>
      <ol id="recipes-list"></ol>
      <hr style="border-color: #222; margin: 16px 0;">
      <h3 style="margin-top: 0;">Nutrient flows</h3>
      <p style="color: var(--muted); font-size: 12px; margin: 0 0 12px 0;">
        Where energy moves between cells turn-to-turn. A → B means cell A
        was written, then in the next frame cell B was written — co-occurrence
        across adjacent frames. Top 50 by frequency.
      </p>
      <ol id="flows-list"></ol>
      <hr style="border-color: #222; margin: 16px 0;">
      <h3 style="margin-top: 0;">Compound recipes</h3>
      <p style="color: var(--muted); font-size: 12px; margin: 0 0 12px 0;">
        3-step patterns A → B → C — recurring multi-step co-work shapes
        (e.g. <code>Edit → Bash → Bash</code> for edit-then-build-then-test,
        or <code>Bash → Read → Bash</code> for the run-read-run loop).
        Compounds name the shape of how something happens, not just what
        happens. Top 30 by frequency.
      </p>
      <ol id="compounds-list"></ol>
      <hr style="border-color: #222; margin: 12px 0;">
      <p style="color: var(--muted); font-size: 12px;">
        In Vitality mode, cells are colored by write rate (cool→hot).
        Toggle back to Identity to see type-tag coloring + cell inspector.
      </p>
    </div>
  </aside>
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
const CELL_WRITES = {cell_writes_json};
const PROV_WRITES = {prov_writes_json};
const PROVMAP = {provmap_json};
// Top nutrient flows: directed co-occurrence between cells in adjacent
// frames. Each row: [src_cell_idx, dst_cell_idx, src_latest_prov,
// dst_latest_prov, count]. Sorted desc by count, capped at 50.
const FLOWS = {flows_json};
// Top compound recipes: 3-step patterns A → B → C derived from triple
// co-occurrence across consecutive frames. Each row:
// [a, b, c, pa, pb, pc, count]. Sorted desc, capped at 30.
const COMPOUNDS = {compound_json};

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

// Heat scale for vitality coloring: 0 → invisible, max → bright orange/red.
// Uses a perceptually-decent gradient cool → green → yellow → orange → red.
function heatColor(t) {{
  // t in [0, 1]
  if (t <= 0) return "transparent";
  const stops = [
    [0.0, [10, 20, 60]],     // deep blue
    [0.15, [30, 80, 180]],   // blue
    [0.35, [50, 200, 200]],  // teal
    [0.55, [120, 230, 80]],  // green
    [0.75, [255, 220, 60]],  // yellow
    [0.9, [255, 130, 40]],   // orange
    [1.0, [255, 70, 50]],    // red
  ];
  for (let i = 1; i < stops.length; i++) {{
    if (t <= stops[i][0]) {{
      const [t0, c0] = stops[i - 1];
      const [t1, c1] = stops[i];
      const u = (t - t0) / (t1 - t0);
      const r = Math.round(c0[0] + (c1[0] - c0[0]) * u);
      const g = Math.round(c0[1] + (c1[1] - c0[1]) * u);
      const b = Math.round(c0[2] + (c1[2] - c0[2]) * u);
      return `rgb(${{r}}, ${{g}}, ${{b}})`;
    }}
  }}
  return `rgb(255, 70, 50)`;
}}

const heapEl = document.getElementById("heap");
const scrub = document.getElementById("scrubber");
const counter = document.getElementById("counter");
const playBtn = document.getElementById("play");
const sideEl = document.getElementById("side");
const inspectorPanel = document.getElementById("inspector");
const recipesPanel = document.getElementById("recipes");
const recipesList = document.getElementById("recipes-list");
const flowsList = document.getElementById("flows-list");
const compoundsList = document.getElementById("compounds-list");
const modeIdentityBtn = document.getElementById("mode-identity");
const modeVitalityBtn = document.getElementById("mode-vitality");
const info = {{
  id: document.getElementById("cell-id"),
  xy: document.getElementById("cell-xy"),
  tag: document.getElementById("cell-tag"),
  val: document.getElementById("cell-val"),
  prov: document.getElementById("cell-prov"),
  src: document.getElementById("cell-src"),
  writes: document.getElementById("cell-writes"),
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
let mode = "identity"; // or "vitality"
let highlightedProv = null;

// Pre-compute max write counts for vitality scaling.
const maxCellWrites = Math.max(1, ...Object.values(CELL_WRITES));
const maxProvWrites = Math.max(1, ...Object.values(PROV_WRITES));

function colorForCell(idx, tag) {{
  if (mode === "vitality") {{
    const writes = CELL_WRITES[idx] || 0;
    if (writes === 0) return "transparent";
    // Log-scale so a 100-write cell isn't drowned by a 1000-write cell.
    const t = Math.log1p(writes) / Math.log1p(maxCellWrites);
    return heatColor(t);
  }}
  return PALETTE[tag] || PALETTE.unknown;
}}

function setCell(idx, tag, val, prov) {{
  liveState.set(idx, {{ tag, val, prov }});
  const el = cellEls.get(idx);
  if (el) {{
    el.classList.add("live");
    el.style.setProperty("--cell-color", colorForCell(idx, tag));
    el.dataset.tag = tag;
    el.dataset.prov = prov;
    applyHighlight(el, prov);
  }}
}}

function unsetCell(idx) {{
  liveState.delete(idx);
  const el = cellEls.get(idx);
  if (el) {{
    el.classList.remove("live");
    el.style.removeProperty("--cell-color");
    delete el.dataset.tag;
    delete el.dataset.prov;
    el.style.outline = "";
  }}
}}

function applyHighlight(el, prov) {{
  if (highlightedProv !== null && Number(prov) === highlightedProv) {{
    el.style.outline = "2px solid var(--accent)";
    el.style.zIndex = "2";
  }} else {{
    el.style.outline = "";
    el.style.zIndex = "";
  }}
}}

function recolorAllLive() {{
  for (const [idx, cell] of liveState.entries()) {{
    const el = cellEls.get(idx);
    if (el) {{
      el.style.setProperty("--cell-color", colorForCell(idx, cell.tag));
    }}
  }}
}}

function applyFrameDelta(toIdx) {{
  if (toIdx === appliedFrame) return;
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

function provSourceLabel(prov) {{
  const entry = PROVMAP[String(prov)];
  if (!entry) return null;
  return `${{entry.file}}:${{entry.line}}`;
}}

function showCell(idx) {{
  const cell = liveState.get(idx);
  const x = idx % GRID;
  const y = Math.floor(idx / GRID);
  info.id.textContent = idx;
  info.xy.textContent = `(${{x}}, ${{y}})`;
  info.writes.textContent = (CELL_WRITES[idx] || 0).toLocaleString();
  if (cell) {{
    sideEl.classList.remove("empty");
    info.tag.textContent = cell.tag;
    info.val.textContent = cell.val;
    info.prov.textContent = "0x" + cell.prov.toString(16).padStart(8, "0");
    info.src.textContent = provSourceLabel(cell.prov) || "(unmapped)";
  }} else {{
    sideEl.classList.add("empty");
    info.tag.textContent = "(free)";
    info.val.textContent = "—";
    info.prov.textContent = "—";
    info.src.textContent = "—";
  }}
}}

// Recipes leaderboard: rank by write count, show file:line, click to highlight.
function buildRecipesList() {{
  const ranked = Object.entries(PROV_WRITES)
    .map(([hash, count]) => ({{ hash: Number(hash), count }}))
    .sort((a, b) => b.count - a.count);
  const top = maxProvWrites;
  recipesList.innerHTML = "";
  for (const {{ hash, count }} of ranked) {{
    const li = document.createElement("li");
    li.dataset.prov = hash;
    const src = provSourceLabel(hash) || `0x${{hash.toString(16).padStart(8, "0")}}`;
    const pct = ((count / top) * 100).toFixed(1);
    li.innerHTML =
      `<span class="src">${{escapeHtml(src)}}</span>` +
      `<span class="count">${{count.toLocaleString()}}</span>` +
      `<div class="bar" style="--bar-pct: ${{pct}}%"></div>`;
    li.style.cursor = "pointer";
    li.addEventListener("click", () => toggleRecipeHighlight(hash));
    recipesList.appendChild(li);
  }}
}}

function escapeHtml(s) {{
  return String(s).replace(/[&<>"']/g, c => ({{
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }})[c]);
}}

function toggleRecipeHighlight(prov) {{
  highlightedProv = (highlightedProv === prov) ? null : prov;
  for (const [idx, cell] of liveState.entries()) {{
    const el = cellEls.get(idx);
    if (el) applyHighlight(el, cell.prov);
  }}
  // Visual feedback on the recipes list.
  for (const li of recipesList.children) {{
    li.style.background = (Number(li.dataset.prov) === highlightedProv) ? "#222" : "";
  }}
}}

function setMode(newMode) {{
  if (newMode === mode) return;
  mode = newMode;
  modeIdentityBtn.classList.toggle("active", mode === "identity");
  modeVitalityBtn.classList.toggle("active", mode === "vitality");
  inspectorPanel.classList.toggle("active", mode === "identity");
  recipesPanel.classList.toggle("active", mode === "vitality");
  recolorAllLive();
}}

// Nutrient-flow leaderboard: rank by adjacent-frame co-occurrence, show
// resolved labels via PROVMAP. Cells with no provenance map fall back to
// "cell N". Hovering a flow row highlights both source and destination
// cells in the heap.
function buildFlowsList() {{
  flowsList.innerHTML = "";
  if (!Array.isArray(FLOWS) || FLOWS.length === 0) {{
    const li = document.createElement("li");
    li.style.color = "var(--muted)";
    li.style.fontSize = "12px";
    li.textContent = "No flows captured (need ≥2 adjacent frames with changed cells).";
    flowsList.appendChild(li);
    return;
  }}
  const top = FLOWS[0][4] || 1;
  for (const [a, b, pa, pb, n] of FLOWS) {{
    const li = document.createElement("li");
    li.dataset.srcCell = a;
    li.dataset.dstCell = b;
    const labelA = provSourceLabel(pa) || `cell ${{a}}`;
    const labelB = provSourceLabel(pb) || `cell ${{b}}`;
    const pct = ((n / top) * 100).toFixed(1);
    li.innerHTML =
      `<span class="src">${{escapeHtml(labelA)}} → ${{escapeHtml(labelB)}}</span>` +
      `<span class="count">${{n.toLocaleString()}}</span>` +
      `<div class="bar" style="--bar-pct: ${{pct}}%"></div>`;
    li.style.cursor = "pointer";
    li.addEventListener("mouseenter", () => highlightFlow(a, b));
    li.addEventListener("mouseleave", () => highlightFlow(null, null));
    flowsList.appendChild(li);
  }}
}}

function highlightFlow(srcIdx, dstIdx) {{
  for (const [idx, _] of liveState.entries()) {{
    const el = cellEls.get(idx);
    if (!el) continue;
    if (idx === srcIdx) {{
      el.style.outline = "2px solid #ff7050";
      el.style.zIndex = "3";
    }} else if (idx === dstIdx) {{
      el.style.outline = "2px solid #50ffa0";
      el.style.zIndex = "3";
    }} else if (highlightedProv === null) {{
      el.style.outline = "";
      el.style.zIndex = "";
    }}
  }}
}}

// Compound-recipe leaderboard: rank by triple co-occurrence across three
// consecutive frames. Each row shows label_a → label_b → label_c with
// the count and a bar. Hovering highlights all three cells in the heap
// (red src, yellow middle, green dst).
function buildCompoundsList() {{
  compoundsList.innerHTML = "";
  if (!Array.isArray(COMPOUNDS) || COMPOUNDS.length === 0) {{
    const li = document.createElement("li");
    li.style.color = "var(--muted)";
    li.style.fontSize = "12px";
    li.textContent = "No compounds captured (need ≥3 adjacent frames with changed cells).";
    compoundsList.appendChild(li);
    return;
  }}
  const top = COMPOUNDS[0][6] || 1;
  for (const [a, b, c, pa, pb, pc, n] of COMPOUNDS) {{
    const li = document.createElement("li");
    li.dataset.aCell = a;
    li.dataset.bCell = b;
    li.dataset.cCell = c;
    const labelA = provSourceLabel(pa) || `cell ${{a}}`;
    const labelB = provSourceLabel(pb) || `cell ${{b}}`;
    const labelC = provSourceLabel(pc) || `cell ${{c}}`;
    const pct = ((n / top) * 100).toFixed(1);
    li.innerHTML =
      `<span class="src">${{escapeHtml(labelA)}} → ${{escapeHtml(labelB)}} → ${{escapeHtml(labelC)}}</span>` +
      `<span class="count">${{n.toLocaleString()}}</span>` +
      `<div class="bar" style="--bar-pct: ${{pct}}%"></div>`;
    li.style.cursor = "pointer";
    li.addEventListener("mouseenter", () => highlightCompound(a, b, c));
    li.addEventListener("mouseleave", () => highlightCompound(null, null, null));
    compoundsList.appendChild(li);
  }}
}}

function highlightCompound(aIdx, bIdx, cIdx) {{
  for (const [idx, _] of liveState.entries()) {{
    const el = cellEls.get(idx);
    if (!el) continue;
    if (idx === aIdx) {{
      el.style.outline = "2px solid #ff7050";
      el.style.zIndex = "3";
    }} else if (idx === bIdx) {{
      el.style.outline = "2px solid #ffd050";
      el.style.zIndex = "3";
    }} else if (idx === cIdx) {{
      el.style.outline = "2px solid #50ffa0";
      el.style.zIndex = "3";
    }} else if (highlightedProv === null) {{
      el.style.outline = "";
      el.style.zIndex = "";
    }}
  }}
}}

modeIdentityBtn.addEventListener("click", () => setMode("identity"));
modeVitalityBtn.addEventListener("click", () => setMode("vitality"));
buildRecipesList();
buildFlowsList();
buildCompoundsList();

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
        cell_writes_json = cell_writes_json,
        prov_writes_json = prov_writes_json,
        provmap_json = provmap_json,
        flows_json = flows_json,
        compound_json = compound_json,
        GRID = GRID,
    )
}
