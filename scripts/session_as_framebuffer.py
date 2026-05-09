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


def main() -> int:
    if len(sys.argv) < 3:
        print(f"usage: {sys.argv[0]} <session.jsonl> <output_base>", file=sys.stderr)
        return 2

    session_path = Path(sys.argv[1])
    output_base = sys.argv[2]
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

    print(
        f"wrote {mfb_path} ({len(frames)} frames, "
        f"{len(tool_idx)} tools, {len(file_idx)} files, "
        f"{len(commit_idx)} commits, {len(pr_idx)} PRs, "
        f"{len(prov_registry)} prov entries)",
        file=sys.stderr,
    )
    print(
        f"top tools: {dict(sorted(tool_count.items(), key=lambda x: -x[1])[:5])}",
        file=sys.stderr,
    )
    print(
        f"top files: {dict(sorted(((Path(p).name, c) for p, c in file_count.items()), key=lambda x: -x[1])[:5])}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
