#!/usr/bin/env python3
"""Inventory local digital-history sources into compact influence summaries."""
from __future__ import annotations

import argparse
import html
import json
import re
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


GENERIC_AUTHORS = {"here", "unknown", "empty artist - topic"}
TAKEOUT_DATE_RE = re.compile(r"([A-Z][a-z]+ \d{1,2}, \d{4}, \d{1,2}:\d{2}:\d{2}\s*[AP]M)\s*([A-Z]+)?")
PUBLISHED_TRACE_START = datetime(2024, 5, 7)


def clean(value: str | None) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("\u202f", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def parse_takeout_datetime(value: str | None) -> datetime | None:
    match = TAKEOUT_DATE_RE.search(clean(value))
    if not match:
        return None
    for fmt in ("%B %d, %Y, %I:%M:%S %p", "%b %d, %Y, %I:%M:%S %p"):
        try:
            return datetime.strptime(match.group(1), fmt)
        except ValueError:
            continue
    return None


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def top(counter: Counter[Any], limit: int = 20) -> list[dict[str, Any]]:
    rows = []
    for key, count in counter.most_common(limit):
        if isinstance(key, tuple):
            rows.append({"value": key[0], "by": key[1], "count": count})
        else:
            rows.append({"value": key, "count": count})
    return rows


def takeout_blocks(raw: str) -> list[str]:
    return re.findall(r'<div class="outer-cell\b.*?(?=<div class="outer-cell\b|</body>)', raw, flags=re.S)


def parse_youtube_watch_history(zip_path: Path) -> list[dict[str, Any]]:
    if not zip_path.exists():
        return []
    events: list[dict[str, Any]] = []
    with zipfile.ZipFile(zip_path) as archive:
        names = [name for name in archive.namelist() if name.endswith("YouTube and YouTube Music/history/watch-history.html")]
        for name in names:
            raw = archive.read(name).decode("utf-8", errors="ignore")
            for block in takeout_blocks(raw):
                links = re.findall(r'href="([^"]+)">([^<]+)</a>', block)
                if not links:
                    continue
                text = clean(block)
                when = parse_takeout_datetime(text)
                title = clean(links[0][1]).removeprefix("Watched ")
                author = "unknown"
                if len(links) > 1 and "watch?" not in links[1][0]:
                    author = clean(links[1][1])
                events.append(
                    {
                        "timestamp": when.isoformat() if when else None,
                        "year_month": when.strftime("%Y-%m") if when else None,
                        "author": author,
                        "work": title,
                        "product": "youtube-music" if "YouTube Music" in text[:120] else "youtube",
                        "source_zip": zip_path.name,
                    }
                )
    return events


def summarize_youtube_full(events: list[dict[str, Any]], story_text: str) -> dict[str, Any]:
    dated = [event for event in events if event.get("timestamp")]
    dates = [datetime.fromisoformat(event["timestamp"]) for event in dated]
    periods = {
        "all_available": (None, None),
        "before_published_trace": (None, PUBLISHED_TRACE_START),
        "year_2023": (datetime(2023, 1, 1), datetime(2024, 1, 1)),
        "early_2024_before_published_trace": (datetime(2024, 1, 1), PUBLISHED_TRACE_START),
        "published_trace_window": (PUBLISHED_TRACE_START, None),
    }
    out: dict[str, Any] = {
        "events": len(events),
        "dated_events": len(dated),
        "first": min(dates).isoformat() if dates else None,
        "last": max(dates).isoformat() if dates else None,
        "periods": {},
    }
    for label, (start, end) in periods.items():
        rows = []
        for event in dated:
            when = datetime.fromisoformat(event["timestamp"])
            if start and when < start:
                continue
            if end and when >= end:
                continue
            rows.append(event)
        authors: Counter[str] = Counter(event["author"] for event in rows)
        works: Counter[tuple[str, str]] = Counter((event["work"], event["author"]) for event in rows)
        months: Counter[str] = Counter(event["year_month"] for event in rows if event.get("year_month"))
        products: Counter[str] = Counter(event["product"] for event in rows)
        filtered_authors = Counter({k: v for k, v in authors.items() if k.strip().casefold() not in GENERIC_AUTHORS})
        out["periods"][label] = {
            "events": len(rows),
            "products": dict(products.most_common()),
            "top_months": top(months, 10),
            "top_authors": [
                {
                    **item,
                    "already_in_story": item["value"].replace(" - Topic", "").casefold() in story_text.casefold(),
                }
                for item in top(filtered_authors, 25)
            ],
            "top_works": top(works, 20),
            "unresolved_or_generic_events": sum(count for name, count in authors.items() if name.strip().casefold() in GENERIC_AUTHORS),
        }
    return out


def summarize_youtube_upload_parts(downloads_dir: Path) -> dict[str, Any]:
    audio_exts = {".mp3", ".m4a", ".flac", ".wav", ".aac"}
    video_exts = {".mp4", ".mov", ".m4v"}
    audio: Counter[str] = Counter()
    video: Counter[str] = Counter()
    zips = sorted(downloads_dir.glob("takeout-20260506T023119Z-3-*.zip"))
    for zip_path in zips:
        with zipfile.ZipFile(zip_path) as archive:
            for name in archive.namelist():
                suffix = Path(name).suffix.lower()
                title = Path(name).stem.replace("_", "'").strip()
                if suffix in audio_exts:
                    audio[title] += 1
                elif suffix in video_exts:
                    video[title] += 1
    return {
        "archives": len(zips),
        "audio_upload_files": sum(audio.values()),
        "video_upload_files": sum(video.values()),
        "sample_audio_titles": [row["value"] for row in top(audio, 25)],
        "sample_video_titles": [row["value"] for row in top(video, 15)],
        "date_span": "not available from upload filenames alone",
    }


def audible_date(value: str | None) -> str | None:
    value = clean(value)
    match = re.match(r"^(\d{2})-(\d{2})-(\d{2}|\d{4})$", value)
    if not match:
        return value or None
    month, day, year = match.groups()
    if len(year) == 2:
        year = f"20{year}"
    return f"{year}-{month}-{day}"


def summarize_audible(analysis_root: Path) -> dict[str, Any]:
    base = analysis_root / "input" / "audible" / "playwright"
    files = {
        "library": base / "audible-library.json",
        "listen_history": base / "audible-listen-history.json",
        "purchase_history": base / "audible-purchase-history-2016-2026.json",
    }
    out: dict[str, Any] = {}
    for label, path in files.items():
        rows = read_json(path) if path.exists() else []
        dates = []
        authors: Counter[str] = Counter()
        titles: Counter[str] = Counter()
        for row in rows:
            title = clean(row.get("title"))
            author = clean(row.get("author"))
            if " By " in title and not author:
                title, author = title.rsplit(" By ", 1)
            authors[author or "unknown"] += 1
            titles[title or "unknown"] += 1
            raw_date = row.get("purchased_date") or row.get("listened_date")
            normalized = audible_date(raw_date)
            if normalized and re.match(r"^\d{4}-\d{2}-\d{2}$", normalized):
                dates.append(normalized)
        out[label] = {
            "events": len(rows),
            "first": min(dates) if dates else None,
            "last": max(dates) if dates else None,
            "top_authors": top(Counter({k: v for k, v in authors.items() if k != "unknown"}), 25),
            "top_titles": top(titles, 25),
        }
    return out


def summarize_browser(analysis_root: Path) -> dict[str, Any]:
    path = analysis_root / "input" / "browser" / "local_browser_events.jsonl"
    rows = read_jsonl(path) if path.exists() else []
    dates = [row.get("timestamp") for row in rows if row.get("timestamp")]
    domains: Counter[str] = Counter(row.get("domain") or "unknown" for row in rows)
    titles: Counter[str] = Counter(clean(row.get("normalized_title") or row.get("title")) or "unknown" for row in rows)
    sources: Counter[str] = Counter(row.get("source") or "unknown" for row in rows)
    return {
        "events": len(rows),
        "first": min(dates) if dates else None,
        "last": max(dates) if dates else None,
        "sources": dict(sources.most_common()),
        "top_domains": top(domains, 20),
        "top_titles": top(Counter({k: v for k, v in titles.items() if k != "unknown"}), 25),
    }


def summarize_photos(downloads_dir: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for zip_path in [downloads_dir / "Photos-3-001.zip"]:
        if not zip_path.exists():
            continue
        dates = []
        exts: Counter[str] = Counter()
        with zipfile.ZipFile(zip_path) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            for name in names:
                exts[Path(name).suffix.lower() or "no-extension"] += 1
                match = re.search(r"(20\d{6})[_-]", Path(name).name)
                if match:
                    dates.append(match.group(1))
        out[zip_path.name] = {
            "files": len(names),
            "first_date_from_filename": min(dates) if dates else None,
            "last_date_from_filename": max(dates) if dates else None,
            "extensions": dict(exts.most_common()),
        "publication_boundary": "filenames and counts only in this compact inventory; image pixels can be handled in a later image-specific breath",
        }
    return out


def summarize_project_archives(downloads_dir: Path) -> dict[str, Any]:
    archives = {}
    for name in ["Angelic-20260507T052334Z-3-001.zip", "Water Project.zip"]:
        path = downloads_dir / name
        if not path.exists():
            continue
        with zipfile.ZipFile(path) as archive:
            names = [entry for entry in archive.namelist() if not entry.endswith("/")]
            suffixes = Counter(Path(entry).suffix.lower() or "no-extension" for entry in names)
        archives[name] = {
            "files": len(names),
            "extensions": dict(suffixes.most_common(15)),
            "sample_paths": names[:20],
        }
    return archives


def summarize_agent_history() -> dict[str, Any]:
    root = Path.home() / ".gemini" / "history"
    if not root.exists():
        return {"present": False}
    files = [path for path in root.rglob("*") if path.is_file()]
    project_roots = []
    for marker in root.rglob(".project_root"):
        try:
            project_roots.append(marker.read_text(encoding="utf-8", errors="ignore").strip())
        except OSError:
            pass
    return {
        "present": True,
        "files": len(files),
        "project_roots": sorted(set(project_roots))[:25],
        "publication_boundary": "inventory only in this compact pass; conversation bodies can be handled by a later source-specific breath",
    }


def summarize_published_trace(field_dir: Path) -> dict[str, Any]:
    path = field_dir / "output" / "ten_year_events.jsonl"
    rows = read_jsonl(path) if path.exists() else []
    sources: Counter[str] = Counter(row.get("source") or "unknown" for row in rows)
    return {"events": len(rows), "sources": dict(sources.most_common())}


def build(field_dir: Path, analysis_root: Path, downloads_dir: Path) -> dict[str, Any]:
    story_text = (field_dir / "output" / "chronological_story_with_frequency.md").read_text(encoding="utf-8")
    full_history = parse_youtube_watch_history(downloads_dir / "takeout-20260506T165642Z-3-001.zip")
    part_history = parse_youtube_watch_history(downloads_dir / "takeout-20260506T023119Z-3-012.zip")
    youtube_full = summarize_youtube_full(full_history, story_text)
    youtube_part = summarize_youtube_full(part_history, story_text)
    missing_period = youtube_full["periods"]["before_published_trace"]
    return {
        "schema_version": "digital-influence-inventory/v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "publication_boundary": "This compact artifact publishes source counts, date spans, filenames, and aggregate influence candidates. Watch and listen history are allowed to be public by contributor direction; bulky raw exports stay as source files unless a later breath decides their size and shape belong directly in the repo.",
        "source_roots": {
            "field_dir": str(field_dir),
            "analysis_root": str(analysis_root),
            "downloads_dir": str(downloads_dir),
        },
        "published_trace": summarize_published_trace(field_dir),
        "youtube": {
            "history_only_takeout": youtube_full,
            "full_takeout_part_012": youtube_part,
            "uploads_and_library_parts": summarize_youtube_upload_parts(downloads_dir),
            "published_gap": {
                "integrated_before_2024_05_07_events": missing_period["events"],
                "integrated_2023_events": youtube_full["periods"]["year_2023"]["events"],
                "integrated_early_2024_events": youtube_full["periods"]["early_2024_before_published_trace"]["events"],
                "highest_signal_expansion_authors": missing_period["top_authors"][:20],
                "missing_before_2024_05_07_events": missing_period["events"],
                "missing_2023_events": youtube_full["periods"]["year_2023"]["events"],
                "missing_early_2024_events": youtube_full["periods"]["early_2024_before_published_trace"]["events"],
                "highest_signal_missing_authors": missing_period["top_authors"][:20],
            },
        },
        "audible": summarize_audible(analysis_root),
        "browser": summarize_browser(analysis_root),
        "photos": summarize_photos(downloads_dir),
        "project_archives": summarize_project_archives(downloads_dir),
        "agent_history": summarize_agent_history(),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    gap = payload["youtube"]["published_gap"]
    full = payload["youtube"]["history_only_takeout"]
    lines = [
        "# Digital Influence Inventory",
        "",
        "This inventory maps the local digital-history sources available for the Urs field story without committing bulky raw archives.",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        "## Publication Boundary",
        "",
        payload["publication_boundary"],
        "",
        "## Source Coverage",
        "",
        f"- Published repo trace: {payload['published_trace']['events']} events.",
        f"- Full YouTube history-only Takeout: {full['events']} events, `{full['first']}` to `{full['last']}`.",
        f"- Full YouTube part 012 watch history: {payload['youtube']['full_takeout_part_012']['events']} events, `{payload['youtube']['full_takeout_part_012']['first']}` to `{payload['youtube']['full_takeout_part_012']['last']}`.",
        f"- YouTube uploads/library archives: {payload['youtube']['uploads_and_library_parts']['audio_upload_files']} audio files and {payload['youtube']['uploads_and_library_parts']['video_upload_files']} video files across {payload['youtube']['uploads_and_library_parts']['archives']} archives.",
        f"- Audible library/listen/purchase captures: {payload['audible']['library']['events']} library, {payload['audible']['listen_history']['events']} listen-history, {payload['audible']['purchase_history']['events']} purchase-history rows.",
        f"- Local browser trace: {payload['browser']['events']} events, `{payload['browser']['first']}` to `{payload['browser']['last']}`.",
        "",
        "## Expanded Trace Before The Former Window",
        "",
        f"- YouTube events before the former `2024-05-07` trace window now present in the repo trace: {gap['integrated_before_2024_05_07_events']}.",
        f"- 2023 YouTube events now present: {gap['integrated_2023_events']}.",
        f"- Early 2024 YouTube events before `2024-05-07` now present: {gap['integrated_early_2024_events']}.",
        "",
        "## Highest-Signal Expansion YouTube Authors",
        "",
    ]
    for item in gap["highest_signal_expansion_authors"]:
        marker = "already in story" if item.get("already_in_story") else "needs room"
        lines.append(f"- {item['value']} — {item['count']} events ({marker})")
    lines.extend(["", "## 2023 Wave", ""])
    for item in full["periods"]["year_2023"]["top_authors"][:20]:
        lines.append(f"- {item['value']} — {item['count']} events")
    lines.extend(["", "## Early 2024 Wave Before Published Trace", ""])
    for item in full["periods"]["early_2024_before_published_trace"]["top_authors"][:20]:
        lines.append(f"- {item['value']} — {item['count']} events")
    lines.extend(["", "## Audible Shape", ""])
    for section in ["purchase_history", "listen_history", "library"]:
        row = payload["audible"][section]
        lines.append(f"- `{section}`: {row['events']} rows, `{row['first']}` to `{row['last']}`")
    lines.extend(["", "## Browser Shape", ""])
    for item in payload["browser"]["top_domains"][:12]:
        lines.append(f"- {item['value']} — {item['count']} events")
    lines.extend(["", "## Photo And Project Archives", ""])
    for name, row in payload["photos"].items():
        lines.append(f"- `{name}`: {row['files']} files, filename dates `{row['first_date_from_filename']}` to `{row['last_date_from_filename']}`")
    for name, row in payload["project_archives"].items():
        lines.append(f"- `{name}`: {row['files']} files")
    lines.extend(["", "## Next Breath", ""])
    lines.append("- Use `trace/monthly_spectrum.json`, `trace/author_index.jsonl`, and `trace/work_index.jsonl` as the compact query layer for the expanded YouTube trace.")
    lines.append("- Add a 2023/early-2024 transition room for the flamenco/Spanish-guitar body wave and its bridge into devotional-body music.")
    lines.append("- Add a separate unresolved-author cleanup for `here` YouTube rows before treating them as real influence presences.")
    lines.append("- Keep Photos and Gmail at metadata/header level in this compact pass; deeper source-specific analysis can happen when that breath is useful.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field-dir", type=Path, default=Path("docs/field/urs"))
    parser.add_argument("--analysis-root", type=Path, default=Path.home() / "CoherenceFieldAnalysis")
    parser.add_argument("--downloads-dir", type=Path, default=Path.home() / "Downloads")
    args = parser.parse_args()
    payload = build(args.field_dir, args.analysis_root, args.downloads_dir)
    write_json(args.field_dir / "trace" / "digital_influence_inventory.json", payload)
    write_markdown(args.field_dir / "output" / "digital_influence_inventory.md", payload)
    print(f"youtube_full_events={payload['youtube']['history_only_takeout']['events']}")
    print(f"integrated_before_2024_05_07={payload['youtube']['published_gap']['integrated_before_2024_05_07_events']}")
    print(args.field_dir / "output" / "digital_influence_inventory.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
