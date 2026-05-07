#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AXES = ("pressure", "intensity", "inspiration", "insight", "vitality")
WAVE_SCHEMA = ["month", "events", *AXES]
GENERIC_AUTHORS = {"unknown", "www.youtube.com", "music.youtube.com", "youtube.com"}


def slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return base[:80].strip("-") or "unknown"


def stable_id(prefix: str, *parts: str) -> str:
    raw = "::".join(part.strip().lower() for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}:{slugify(parts[-1])}-{digest}"


def parse_month(timestamp: str | None) -> str | None:
    if not timestamp:
        return None
    timestamp = timestamp.replace("\u202f", " ").replace("\xa0", " ")
    if re.match(r"^\d{4}-\d{2}", timestamp):
        return timestamp[:7]
    match = re.search(r"([A-Z][a-z]+ \d{1,2}, 20\d\d, \d{1,2}:\d{2}:\d{2}\s*[AP]M)", timestamp)
    if not match:
        return None
    for fmt in ("%B %d, %Y, %I:%M:%S %p", "%b %d, %Y, %I:%M:%S %p"):
        try:
            return datetime.strptime(match.group(1), fmt).strftime("%Y-%m")
        except ValueError:
            continue
    return None


def top_counter(counter: Counter[str], limit: int) -> list[list[Any]]:
    return [[key, count] for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def is_generic_author(name: str) -> bool:
    return name.strip().lower() in GENERIC_AUTHORS


def is_generic_work(title: str) -> bool:
    lowered = title.strip().lower()
    if lowered in {"youtube", "youtube music", "watch history"}:
        return True
    return re.fullmatch(r"\(\d+\)\s*(youtube|watch history)", lowered) is not None


def compact_axes(events: list[dict[str, Any]]) -> dict[str, int]:
    return {axis: int(sum(event.get(axis) or 0 for event in events)) for axis in AXES}


def wave(rows: dict[str, list[dict[str, Any]]]) -> list[list[Any]]:
    out: list[list[Any]] = []
    for month in sorted(rows):
        events = rows[month]
        axes = compact_axes(events)
        out.append([month, len(events), *(axes[axis] for axis in AXES)])
    return out


def load_events(path: Path) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = []
    undated = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            event = json.loads(line)
            month = parse_month(event.get("timestamp"))
            if not month:
                undated += 1
                continue
            event["_month"] = month
            event["_author_id"] = stable_id("author", event.get("author") or "unknown")
            event["_work_id"] = stable_id("work", event.get("author") or "unknown", event.get("work") or "unknown")
            events.append(event)
    return events, undated


def month_record(month: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    frequencies: Counter[str] = Counter()
    authors: Counter[str] = Counter()
    works: Counter[str] = Counter()
    platforms: Counter[str] = Counter()
    author_names: dict[str, str] = {}
    work_names: dict[str, tuple[str, str]] = {}
    for event in events:
        for frequency in event.get("frequency") or ["unclassified"]:
            frequencies[frequency] += 1
        author_id = event["_author_id"]
        work_id = event["_work_id"]
        if not is_generic_author(event.get("author") or "unknown"):
            authors[author_id] += 1
        if not is_generic_work(event.get("work") or "unknown"):
            works[work_id] += 1
        platforms[event.get("platform_space") or event.get("source") or "unknown"] += 1
        author_names[author_id] = event.get("author") or "unknown"
        work_names[work_id] = (event.get("work") or "unknown", author_id)

    top_authors = [
        {"id": item[0], "name": author_names[item[0]], "events": item[1]}
        for item in sorted(authors.items(), key=lambda entry: (-entry[1], author_names[entry[0]]))[:12]
    ]
    top_works = [
        {"id": item[0], "title": work_names[item[0]][0], "author_id": work_names[item[0]][1], "events": item[1]}
        for item in sorted(works.items(), key=lambda entry: (-entry[1], work_names[entry[0]][0]))[:12]
    ]
    top_frequency = top_counter(frequencies, 8)
    primary_frequency = next((item[0] for item in top_frequency if item[0] != "unclassified"), None)
    if not primary_frequency and top_frequency:
        primary_frequency = top_frequency[0][0]
    return {
        "month": month,
        "events": len(events),
        "platforms": dict(sorted(platforms.items())),
        "frequencies": top_frequency,
        "axes": compact_axes(events),
        "primary_influence": {
            "frequency": primary_frequency,
            "authors": [item["id"] for item in top_authors[:3]],
            "works": [item["id"] for item in top_works[:3]],
        },
        "top_authors": top_authors,
        "top_works": top_works,
    }


def build_indexes(events: list[dict[str, Any]], undated_events: int, source_path: Path) -> dict[str, Any]:
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_author: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_work: dict[str, list[dict[str, Any]]] = defaultdict(list)
    author_names: dict[str, str] = {}
    work_names: dict[str, tuple[str, str]] = {}
    for event in events:
        by_month[event["_month"]].append(event)
        by_author[event["_author_id"]].append(event)
        by_work[event["_work_id"]].append(event)
        author_names[event["_author_id"]] = event.get("author") or "unknown"
        work_names[event["_work_id"]] = (event.get("work") or "unknown", event["_author_id"])

    month_order = sorted(by_month)
    monthly = {
        "schema_version": "field-trace-index/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source_path),
        "wave_schema": WAVE_SCHEMA,
        "month_order": month_order,
        "months": {month: month_record(month, by_month[month]) for month in month_order},
    }

    authors: dict[str, Any] = {}
    author_records: list[dict[str, Any]] = []
    for author_id, rows in sorted(by_author.items(), key=lambda item: (-len(item[1]), author_names[item[0]])):
        if is_generic_author(author_names[author_id]):
            continue
        if len(rows) < 3:
            continue
        works = Counter(event["_work_id"] for event in rows)
        frequencies = Counter(freq for event in rows for freq in (event.get("frequency") or ["unclassified"]))
        grouped = defaultdict(list)
        for event in rows:
            grouped[event["_month"]].append(event)
        name = author_names[author_id]
        top_works = [
            {
                "id": work_id,
                "title": work_names[work_id][0],
                "events": count,
            }
            for work_id, count in works.most_common(10)
        ]
        author_wave = wave(grouped)
        record = {
            "id": author_id,
            "name": name,
            "events": len(rows),
            "first_month": author_wave[0][0],
            "last_month": author_wave[-1][0],
            "peak_months": [[item[0], item[1]] for item in sorted(author_wave, key=lambda row: (-row[1], row[0]))[:6]],
            "frequencies": top_counter(frequencies, 8),
            "axes": compact_axes(rows),
            "top_works": top_works,
            "wave_schema": WAVE_SCHEMA,
            "wave": author_wave,
        }
        authors[author_id] = record
        author_records.append(record)

    works: dict[str, Any] = {}
    work_records: list[dict[str, Any]] = []
    for work_id, rows in sorted(by_work.items(), key=lambda item: (-len(item[1]), work_names[item[0]][0])):
        if is_generic_work(work_names[work_id][0]):
            continue
        if len(rows) < 3:
            continue
        grouped = defaultdict(list)
        for event in rows:
            grouped[event["_month"]].append(event)
        title, author_id = work_names[work_id]
        work_wave = wave(grouped)
        record = {
            "id": work_id,
            "title": title,
            "author_id": author_id,
            "author": author_names.get(author_id, "unknown"),
            "events": len(rows),
            "first_month": work_wave[0][0],
            "last_month": work_wave[-1][0],
            "peak_months": [[item[0], item[1]] for item in sorted(work_wave, key=lambda row: (-row[1], row[0]))[:6]],
            "frequencies": top_counter(Counter(freq for event in rows for freq in (event.get("frequency") or ["unclassified"])), 8),
            "axes": compact_axes(rows),
            "wave_schema": WAVE_SCHEMA,
            "wave": work_wave,
        }
        works[work_id] = record
        work_records.append(record)

    manifest = {
        "schema_version": "field-trace-index/v1",
        "generated_at": monthly["generated_at"],
        "source": str(source_path),
        "event_count_with_month": len(events),
        "undated_event_count": undated_events,
        "month_count": len(month_order),
        "author_count": len(authors),
        "work_count": len(works),
        "thresholds": {
            "author_min_events": 3,
            "work_min_events": 3,
            "month_top_authors": 12,
            "month_top_works": 12,
        },
        "query_shapes": {
            "primary_influence_during_month": "Load monthly_spectrum.json -> months[YYYY-MM].",
        "author_influence_wave": "Search author_index.jsonl by id or exact name, then read wave.",
        "work_influence_wave": "Search work_index.jsonl by id or exact title, then read wave.",
        },
        "privacy_boundary": "Indexes are derived counts and links. Raw Google Takeout, Audible exports, browser sessions, cookies, and extracted service files remain out of repo.",
    }

    return {"manifest": manifest, "monthly": monthly, "authors": author_records, "works": work_records}


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build compact field listening trace indexes.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    events, undated_events = load_events(args.input)
    indexes = build_indexes(events, undated_events, args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "manifest.json", indexes["manifest"])
    write_json(args.output_dir / "monthly_spectrum.json", indexes["monthly"])
    write_jsonl(args.output_dir / "author_index.jsonl", indexes["authors"])
    write_jsonl(args.output_dir / "work_index.jsonl", indexes["works"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
