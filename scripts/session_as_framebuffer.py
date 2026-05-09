#!/usr/bin/env python3
"""Render a Claude session as a memory-as-framebuffer .mfb capture.

Reads a session JSONL (e.g. ``~/.claude/projects/<slug>/<uuid>.jsonl``)
and emits the same lossless .mfb substrate format the Rust crate writes
(see ``experiments/memory-as-framebuffer-v0/src/capture.rs`` for the spec).
The existing ``mfb-html`` viewer renders it unchanged — Identity mode
shows the heap of things-touched, Vitality mode shows the busy heatmap
+ recipes leaderboard.

Cell layout (256×256 grid, 16 bytes per cell):
    Row 0           — tool cells (one per unique tool name; type tag = u8;
                      payload byte 0 = invocation count clamped to 255)
    Rows 1..8       — file cells (one per unique file path; type tag = u32;
                      payload bytes 0..3 = u32 edit count)
    Rows 9..12      — commit cells (one per commit SHA mentioned by Bash;
                      type tag = u16)
    Rows 13..14     — PR cells (one per PR number mentioned; type tag = bool)

A frame is emitted on every assistant turn that produces at least one
cell write. Provenance per write is ``crc32("turn=N tool=Edit")`` (or
``"turn=N user"`` for user-message events); the provmap maps each hash
back to a human-readable label so the recipe leaderboard reads
"turn=47 tool=Edit" instead of opaque hex.

Usage:
    python3 scripts/session_as_framebuffer.py <session.jsonl> <output_base>

Produces:
    <output_base>.mfb            — the substrate
    <output_base>.mfb.provmap    — provenance hash -> label JSON sidecar

Then:
    cargo run --release --bin mfb-html -- <output_base>.mfb <output_base>.html
    open <output_base>.html
"""

from __future__ import annotations

import json
import os
import re
import struct
import sys
import zlib
from datetime import datetime
from pathlib import Path

# ---- .mfb format constants (must match src/capture.rs) ----
MAGIC = b"MFB0\0\0\0\0"
VERSION = 1
GRID = 256
CELL_BYTES = 16
NUM_CELLS = GRID * GRID
FRAME_MARKER = b"FRM\0"

# ---- type tags (must match src/lib.rs) ----
TAG_FREE = 0x0000
TAG_U8 = 0x0001
TAG_U16 = 0x0002
TAG_U32 = 0x0003
TAG_BOOL = 0x0007

# ---- cell-band layout ----
TOOLS_OFFSET = 0
TOOLS_BAND_SIZE = GRID  # 256 unique tool names max
FILES_OFFSET = GRID
FILES_BAND_SIZE = GRID * 8  # 2048 unique files max
COMMITS_OFFSET = GRID * 9
COMMITS_BAND_SIZE = GRID * 4  # 1024 commits
PRS_OFFSET = GRID * 13
PRS_BAND_SIZE = GRID * 2  # 512 PRs

# Bash output sometimes mentions commits / PRs — extract via regex.
SHA_RE = re.compile(r"\b([0-9a-f]{7,40})\b")
PR_RE = re.compile(r"#(\d{2,5})\b|/pull/(\d{2,5})\b")


def crc32_hash(s: str) -> int:
    return zlib.crc32(s.encode("utf-8")) & 0xFFFFFFFF


def pack_u8_payload(v: int) -> bytes:
    p = bytearray(14)
    p[0] = v & 0xFF
    return bytes(p)


def pack_u16_payload(v: int) -> bytes:
    p = bytearray(14)
    p[0] = v & 0xFF
    p[1] = (v >> 8) & 0xFF
    return bytes(p)


def pack_u32_payload(v: int) -> bytes:
    p = bytearray(14)
    for i in range(4):
        p[i] = (v >> (i * 8)) & 0xFF
    return bytes(p)


def pack_bool_payload(v: bool) -> bytes:
    p = bytearray(14)
    p[0] = 1 if v else 0
    return bytes(p)


class Plane:
    """In-memory data + provenance planes; tracks dirty cells per frame."""

    def __init__(self) -> None:
        self.data = bytearray(NUM_CELLS * CELL_BYTES)
        self.prov = [0] * NUM_CELLS
        self.dirty: set[int] = set()

    def write_cell(self, idx: int, tag: int, payload: bytes, prov: int) -> None:
        off = idx * CELL_BYTES
        self.data[off] = tag & 0xFF
        self.data[off + 1] = (tag >> 8) & 0xFF
        self.data[off + 2 : off + CELL_BYTES] = payload
        self.prov[idx] = prov
        self.dirty.add(idx)

    def take_dirty(self) -> list[int]:
        out = sorted(self.dirty)
        self.dirty.clear()
        return out


def parse_ts(ts_str: str) -> int:
    """ISO8601 → microseconds since epoch."""
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts_str)
    return int(dt.timestamp() * 1_000_000)


def convert_session(session_path: Path, output_base: str) -> dict:
    """Read a session JSONL, write {output_base}.mfb + .mfb.provmap.

    Returns a dict with stats: frames, tools, files, commits, prs, prov_entries,
    plus top_tools and top_files for logging.
    """
    mfb_path = f"{output_base}.mfb"
    provmap_path = f"{mfb_path}.provmap"

    plane = Plane()
    tool_idx: dict[str, int] = {}
    file_idx: dict[str, int] = {}
    commit_idx: dict[str, int] = {}
    pr_idx: dict[str, int] = {}
    tool_count: dict[str, int] = {}
    file_count: dict[str, int] = {}
    prov_registry: dict[int, tuple[str, int]] = {}

    def register_prov(label: str, line: int) -> int:
        h = crc32_hash(f"{label}:{line}")
        prov_registry.setdefault(h, (label, line))
        return h

    def assign_tool(name: str) -> int | None:
        if name not in tool_idx:
            slot = TOOLS_OFFSET + len(tool_idx)
            if slot >= TOOLS_OFFSET + TOOLS_BAND_SIZE:
                return None
            tool_idx[name] = slot
        return tool_idx[name]

    def assign_file(path: str) -> int | None:
        if path not in file_idx:
            slot = FILES_OFFSET + len(file_idx)
            if slot >= FILES_OFFSET + FILES_BAND_SIZE:
                return None
            file_idx[path] = slot
        return file_idx[path]

    def assign_commit(sha: str) -> int | None:
        if sha not in commit_idx:
            slot = COMMITS_OFFSET + len(commit_idx)
            if slot >= COMMITS_OFFSET + COMMITS_BAND_SIZE:
                return None
            commit_idx[sha] = slot
        return commit_idx[sha]

    def assign_pr(num: str) -> int | None:
        if num not in pr_idx:
            slot = PRS_OFFSET + len(pr_idx)
            if slot >= PRS_OFFSET + PRS_BAND_SIZE:
                return None
            pr_idx[num] = slot
        return pr_idx[num]

    # First pass: parse + accumulate frames
    frames: list[tuple[int, int, list[int], bytes, list[int]]] = []
    # Each frame stores (frame_index, ts_us, dirty_indices_list, data_snapshot, prov_snapshot)
    # We snapshot the FULL planes per frame; delta diffing happens at write time below.

    # Track session start so timestamps are micros since session start.
    session_start_us: int | None = None
    turn_index = 0

    with open(session_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            rtype = rec.get("type")
            if rtype != "assistant":
                continue

            ts = rec.get("timestamp")
            if ts:
                ts_us = parse_ts(ts)
                if session_start_us is None:
                    session_start_us = ts_us
                rel_us = ts_us - session_start_us
            else:
                rel_us = turn_index * 16_667  # fallback: pretend 60fps

            msg = rec.get("message", {})
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue

            for c in content:
                if not isinstance(c, dict) or c.get("type") != "tool_use":
                    continue

                tool_name = c.get("name", "?")
                tool_input = c.get("input", {}) or {}

                # 1. Touch the tool cell. Provenance is just the tool name —
                #    every Bash invocation shares the same prov hash so the
                #    recipe leaderboard aggregates them. TAG_U32 so the
                #    count goes well past 255 without saturating (Bash alone
                #    fires hundreds of times in a long session).
                tidx = assign_tool(tool_name)
                if tidx is not None:
                    tool_count[tool_name] = tool_count.get(tool_name, 0) + 1
                    p = register_prov(f"tool={tool_name}", 1)
                    plane.write_cell(
                        tidx,
                        TAG_U32,
                        pack_u32_payload(min(tool_count[tool_name], 0xFFFFFFFF)),
                        p,
                    )

                # 2. If the tool involves a file path, touch the file cell.
                #    Provenance combines tool + file so each (tool,file)
                #    pair becomes a recipe — the leaderboard shows e.g.
                #    "Edit /path/render.rs — 47 writes".
                fp = tool_input.get("file_path") or tool_input.get("path")
                if fp and tool_name in ("Read", "Edit", "Write"):
                    fidx = assign_file(str(fp))
                    if fidx is not None:
                        file_count[fp] = file_count.get(fp, 0) + 1
                        p = register_prov(f"{tool_name} {fp}", 1)
                        plane.write_cell(
                            fidx,
                            TAG_U32,
                            pack_u32_payload(min(file_count[fp], 0xFFFFFFFF)),
                            p,
                        )

                # 3. If the tool is Bash, scan the command for SHA / PR mentions.
                if tool_name == "Bash":
                    cmd = tool_input.get("command", "") or ""
                    for m in SHA_RE.finditer(cmd):
                        sha = m.group(1)
                        if len(sha) >= 7 and any(c.isdigit() for c in sha) and any(
                            c.isalpha() for c in sha
                        ):
                            cidx = assign_commit(sha)
                            if cidx is not None:
                                p = register_prov("commit", 1)
                                plane.write_cell(
                                    cidx,
                                    TAG_U32,
                                    pack_u32_payload(turn_index & 0xFFFFFFFF),
                                    p,
                                )
                    for m in PR_RE.finditer(cmd):
                        num = m.group(1) or m.group(2)
                        if num:
                            pidx = assign_pr(num)
                            if pidx is not None:
                                p = register_prov("PR", 1)
                                plane.write_cell(pidx, TAG_BOOL, pack_bool_payload(True), p)

            dirty = plane.take_dirty()
            if dirty:
                frames.append(
                    (
                        turn_index,
                        rel_us,
                        dirty,
                        bytes(plane.data),
                        list(plane.prov),
                    )
                )
                turn_index += 1

    # Second pass: write the .mfb file with delta-encoded frames.
    prev_data = bytearray(NUM_CELLS * CELL_BYTES)
    prev_prov = [0] * NUM_CELLS

    with open(mfb_path, "wb") as f:
        # Header (24 bytes).
        f.write(MAGIC)
        f.write(struct.pack("<I", VERSION))
        f.write(struct.pack("<I", GRID))
        f.write(struct.pack("<I", CELL_BYTES))
        f.write(struct.pack("<I", 60))  # fps_hint — informational only

        for frame_idx, ts_us, candidate_dirty, data_snap, prov_snap in frames:
            # Diff against previous frame (the candidate_dirty list is the
            # superset; the actual delta might be smaller if some writes
            # produced identical bytes).
            delta = []
            for idx in candidate_dirty:
                off = idx * CELL_BYTES
                cell_changed = (
                    data_snap[off : off + CELL_BYTES]
                    != prev_data[off : off + CELL_BYTES]
                )
                prov_changed = prov_snap[idx] != prev_prov[idx]
                if cell_changed or prov_changed:
                    delta.append(idx)

            f.write(FRAME_MARKER)
            f.write(struct.pack("<Q", frame_idx))
            f.write(struct.pack("<Q", ts_us))
            f.write(struct.pack("<I", len(delta)))
            for idx in delta:
                off = idx * CELL_BYTES
                f.write(struct.pack("<I", idx))
                f.write(data_snap[off : off + CELL_BYTES])
                f.write(struct.pack("<I", prov_snap[idx]))

            prev_data[:] = data_snap
            prev_prov[:] = prov_snap

    # Write provmap sidecar.
    pm = {
        str(h): {"file": label, "line": line}
        for h, (label, line) in prov_registry.items()
    }
    with open(provmap_path, "w") as f:
        json.dump(pm, f)

    return {
        "mfb_path": mfb_path,
        "provmap_path": provmap_path,
        "frames": len(frames),
        "tools": len(tool_idx),
        "files": len(file_idx),
        "commits": len(commit_idx),
        "prs": len(pr_idx),
        "prov_entries": len(prov_registry),
        "top_tools": dict(sorted(tool_count.items(), key=lambda x: -x[1])[:5]),
        "top_files": dict(
            sorted(
                ((Path(p).name, c) for p, c in file_count.items()),
                key=lambda x: -x[1],
            )[:5]
        ),
    }


# ---- Live preview helpers ----

AUTO_REFRESH_SCRIPT = """<script>
(function() {
  let lastModified = null;
  async function check() {
    try {
      const r = await fetch(window.location.href, { method: 'HEAD', cache: 'no-store' });
      const m = r.headers.get('last-modified');
      if (lastModified && m && m !== lastModified) {
        const scrub = document.getElementById('scrubber');
        const max = scrub ? parseInt(scrub.max, 10) : 0;
        const cur = scrub ? parseInt(scrub.value, 10) : 0;
        const wasAtEnd = cur >= max - 1;
        const activeMode = document.querySelector('.modes button.active');
        sessionStorage.setItem('mfb_resume_pos', cur.toString());
        sessionStorage.setItem('mfb_was_at_end', wasAtEnd ? '1' : '0');
        sessionStorage.setItem('mfb_mode', activeMode ? activeMode.id : '');
        location.reload();
      }
      lastModified = m;
    } catch (e) {}
  }
  setInterval(check, 2000);
  window.addEventListener('load', () => {
    const wasAtEnd = sessionStorage.getItem('mfb_was_at_end') === '1';
    const resumePos = sessionStorage.getItem('mfb_resume_pos');
    const scrub = document.getElementById('scrubber');
    if (scrub) {
      if (wasAtEnd) {
        scrub.value = scrub.max;
      } else if (resumePos !== null) {
        const v = Math.min(parseInt(resumePos, 10), parseInt(scrub.max, 10));
        scrub.value = v;
      }
      scrub.dispatchEvent(new Event('input'));
    }
    // Restore mode (Identity / Vitality) if it was set before reload.
    const savedMode = sessionStorage.getItem('mfb_mode');
    if (savedMode) {
      const btn = document.getElementById(savedMode);
      if (btn && !btn.classList.contains('active')) btn.click();
    }
    // Live indicator on the meta line
    const meta = document.querySelector('header .meta');
    if (meta && !document.getElementById('live-indicator')) {
      const live = document.createElement('span');
      live.id = 'live-indicator';
      live.textContent = ' \\u2022 \\u25cf LIVE';
      live.style.color = '#79ffe1';
      live.style.fontWeight = '500';
      meta.appendChild(live);
    }
  });
})();
</script>"""


def find_mfb_html_bin() -> str | None:
    """Locate the mfb-html binary in the repo's experiments dir, building if needed."""
    repo_root = Path(__file__).resolve().parent.parent
    crate_dir = repo_root / "experiments" / "memory-as-framebuffer-v0"
    bin_path = crate_dir / "target" / "release" / "mfb-html"
    if not crate_dir.exists():
        return None
    if not bin_path.exists():
        import subprocess as _sp
        print("[mfb-html] building binary (one-time)...", file=sys.stderr)
        try:
            _sp.run(
                ["cargo", "build", "--release", "--bin", "mfb-html"],
                cwd=str(crate_dir),
                check=True,
            )
        except Exception as e:
            print(f"[mfb-html] build failed: {e}", file=sys.stderr)
            return None
    return str(bin_path)


def render_html(mfb_path: str, html_path: str, mfb_html_bin: str) -> bool:
    import subprocess as _sp
    try:
        _sp.run([mfb_html_bin, mfb_path, html_path], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"[mfb-html] render failed: {e}", file=sys.stderr)
        return False


def inject_autorefresh(html_path: str) -> None:
    """Inject the live-reload <script> just before </body>. Idempotent."""
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        return
    marker = "let lastModified = null;"
    if marker in html:
        return  # already injected
    if "</body>" not in html:
        return
    html = html.replace("</body>", AUTO_REFRESH_SCRIPT + "</body>")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


def serve_dir(directory: str, port: int) -> None:
    import http.server
    import socketserver

    os.chdir(directory)

    class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Cache-Control", "no-store, max-age=0")
            super().end_headers()

        def log_message(self, format, *args):
            return  # silence default access logs

    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("0.0.0.0", port), NoCacheHandler)
    print(f"[serve] http://localhost:{port}  (cwd: {directory})", file=sys.stderr)
    httpd.serve_forever()


def main() -> int:
    import argparse
    import os as _os
    import threading
    import time

    parser = argparse.ArgumentParser(
        description="Convert a Claude session JSONL to a memory-as-framebuffer .mfb capture. "
        "With --watch + --serve, runs as a live preview daemon."
    )
    parser.add_argument("session_jsonl", help="Path to ~/.claude/projects/<slug>/<uuid>.jsonl")
    parser.add_argument("output_base", help="Output basename (no extension); writes .mfb + .mfb.provmap")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Tail the JSONL and regenerate .mfb (and .html if --render-html or default in --serve) on growth",
    )
    parser.add_argument(
        "--serve",
        type=int,
        default=None,
        metavar="PORT",
        help="Run an http.server on PORT serving the output directory (auto-implies --render-html and live-reload injection)",
    )
    parser.add_argument(
        "--render-html",
        action="store_true",
        help="Also produce <output_base>.html via the mfb-html binary",
    )
    parser.add_argument(
        "--mfb-html-bin",
        default=None,
        help="Path to mfb-html binary (auto-detected if omitted)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Poll interval (seconds) for --watch (default: 2.0)",
    )
    args = parser.parse_args()

    session_path = Path(args.session_jsonl)
    output_base = args.output_base
    output_dir = str(Path(output_base).resolve().parent or Path("."))

    render_html_flag = args.render_html or args.serve is not None
    bin_path: str | None = None
    if render_html_flag:
        bin_path = args.mfb_html_bin or find_mfb_html_bin()
        if not bin_path:
            print(
                "[warn] mfb-html binary not found; .html will not be regenerated. "
                "Run `cargo build --release --bin mfb-html` in experiments/memory-as-framebuffer-v0/",
                file=sys.stderr,
            )

    def regen() -> dict:
        result = convert_session(session_path, output_base)
        if render_html_flag and bin_path:
            html_path = output_base + ".html"
            if render_html(result["mfb_path"], html_path, bin_path):
                if args.serve is not None or args.watch:
                    inject_autorefresh(html_path)
                result["html_path"] = html_path
        return result

    # Initial conversion.
    result = regen()
    print(
        f"[init] {result['frames']} frames · {result['tools']} tools · "
        f"{result['files']} files · {result['commits']} commits · "
        f"{result['prs']} PRs · {result['prov_entries']} prov entries",
        file=sys.stderr,
    )
    print(f"[init] top tools: {result['top_tools']}", file=sys.stderr)

    # Background HTTP server.
    if args.serve is not None:
        server_thread = threading.Thread(
            target=serve_dir, args=(output_dir, args.serve), daemon=True
        )
        server_thread.start()

    # Watch loop.
    if args.watch:
        try:
            last_size = _os.path.getsize(session_path)
        except FileNotFoundError:
            last_size = 0

        try:
            while True:
                time.sleep(args.interval)
                try:
                    size = _os.path.getsize(session_path)
                except FileNotFoundError:
                    continue
                if size != last_size:
                    last_size = size
                    result = regen()
                    print(
                        f"[watch] {time.strftime('%H:%M:%S')} {size} bytes · "
                        f"{result['frames']} frames · {result['tools']} tools · "
                        f"{result['files']} files",
                        file=sys.stderr,
                    )
        except KeyboardInterrupt:
            print("\n[watch] stopping", file=sys.stderr)
    elif args.serve is not None:
        # Serving but not watching — keep main thread alive.
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n[serve] stopping", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
