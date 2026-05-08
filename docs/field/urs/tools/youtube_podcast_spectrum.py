#!/usr/bin/env python3
"""Build a compact YouTube podcast influence spectrum from normalized history."""
from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FIELD_DIR = Path("docs/field/urs")
EVENTS_PATH = FIELD_DIR / "output" / "ten_year_events.jsonl"
AXES = ("pressure", "intensity", "inspiration", "insight", "vitality")
WAVE_SCHEMA = ["month", "events", "influence_hours", *AXES]

TAKEOUT_DATE_RE = re.compile(r"([A-Z][a-z]+ \d{1,2}, 20\d\d, \d{1,2}:\d{2}:\d{2}\s*[AP]M)\s*([A-Z]+)?")
VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{6,})")

KNOWN_PODCAST_CHANNELS = {
    "align podcast",
    "all-in podcast",
    "aubrey marcus",
    "big think",
    "danny morel",
    "dr brian keating",
    "emilio ortiz",
    "farzad",
    "heart coherence collaborative",
    "jesse michels",
    "lex clips",
    "lex fridman",
    "love & philosophy with andrea hiott",
    "michael levin's academic content",
    "next level soul podcast",
    "pam gregory",
    "robert edward grant",
    "soma flow: somatic biogeometric harmonics",
    "theories of everything with curt jaimungal",
    "third eye drops with michael phillip",
    "tom bilyeu",
    "wes roth",
    "ziva meditation",
}

ANCHOR_TERMS = {
    "aubrey marcus",
    "donald hoffman",
    "dr joe dispenza",
    "elon musk",
    "lex fridman",
    "matias de stefano",
    "matthias de stefano",
    "michael levin",
    "next level soul",
    "ramtha",
    "robert edward grant",
    "veda austin",
    "zach bush",
}

PODCAST_TERMS = {
    "podcast",
    "interview",
    "conversation",
    "discussion",
    "talk with",
    "talks with",
    "think tank",
    "episode",
    "debate",
    "roundtable",
    "lecture",
}

NON_PODCAST_AUTHORS = {
    "hbo max",
    "jai-jagdeesh - topic",
    "little whale - topic",
    "mose",
    "mose - topic",
}


@dataclass
class PodcastEvent:
    source: str
    timestamp: str | None
    month: str | None
    author: str
    work: str
    url: str | None
    video_id: str | None
    duration_seconds: int | None
    influence_seconds: int
    influence_basis: str
    match_reasons: list[str]
    frequency: list[str]
    pressure: int
    intensity: int
    inspiration: int
    insight: int
    vitality: int
    evidence_level: str


def clean(value: Any) -> str:
    value = html.unescape(str(value or ""))
    value = value.replace("\u202f", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def parse_datetime(value: str | None) -> datetime | None:
    text = clean(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    match = TAKEOUT_DATE_RE.search(text)
    if not match:
        return None
    for fmt in ("%B %d, %Y, %I:%M:%S %p", "%b %d, %Y, %I:%M:%S %p"):
        try:
            return datetime.strptime(match.group(1), fmt)
        except ValueError:
            continue
    return None


def video_id(url: str | None) -> str | None:
    match = VIDEO_ID_RE.search(url or "")
    return match.group(1) if match else None


def is_search_url(url: str | None) -> bool:
    return "results?search_query" in (url or "")


def match_reasons(row: dict[str, Any]) -> list[str]:
    author = clean(row.get("author")).casefold()
    work = clean(row.get("work")).casefold()
    text = f" {author} {work} "
    if is_search_url(row.get("url")) or row.get("platform_space") != "youtube":
        return []
    if author in NON_PODCAST_AUTHORS or author.endswith(" - topic"):
        return []
    reasons: list[str] = []
    if author in KNOWN_PODCAST_CHANNELS:
        reasons.append("known-youtube-podcast-channel")
    if any(term in text for term in PODCAST_TERMS):
        reasons.append("podcast-title-shape")
    anchors = [term for term in sorted(ANCHOR_TERMS) if term in text]
    duration = row.get("duration_seconds")
    if anchors and (reasons or (isinstance(duration, int) and duration >= 1800)):
        reasons.append("named-influence-anchor:" + ",".join(anchors[:4]))
    if reasons and isinstance(duration, int) and duration >= 1800:
        reasons.append("long-form-youtube-duration")
    return reasons


def estimate_seconds(row: dict[str, Any], reasons: list[str]) -> tuple[int, str]:
    duration = row.get("duration_seconds")
    if isinstance(duration, int) and duration > 0:
        return duration, "direct-youtube-duration"
    work = clean(row.get("work")).casefold()
    if "clip" in work or "shorts" in work:
        return 20 * 60, "clip-estimate"
    if any(reason.startswith("named-influence-anchor") for reason in reasons) and "podcast-title-shape" in reasons:
        return 90 * 60, "podcast-episode-length-estimate"
    if "known-youtube-podcast-channel" in reasons:
        return 75 * 60, "podcast-channel-length-estimate"
    return 45 * 60, "long-form-title-estimate"


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def build_events(rows: list[dict[str, Any]]) -> list[PodcastEvent]:
    duration_by_video: dict[str, int] = {}
    for row in rows:
        vid = video_id(row.get("url"))
        duration = row.get("duration_seconds")
        if vid and isinstance(duration, int) and duration > 0:
            duration_by_video[vid] = duration

    events: list[PodcastEvent] = []
    seen: set[tuple[str | None, str | None, str, str]] = set()
    for row in rows:
        reasons = match_reasons(row)
        if not reasons:
            continue
        when = parse_datetime(row.get("timestamp"))
        month = when.strftime("%Y-%m") if when else None
        vid = video_id(row.get("url"))
        duration = row.get("duration_seconds")
        if vid and vid in duration_by_video and not duration:
            duration = duration_by_video[vid]
            influence_seconds = duration_by_video[vid]
            basis = "known-video-duration-from-visible-feed"
        else:
            influence_seconds, basis = estimate_seconds(row, reasons)
        key = (month, vid, clean(row.get("author")), clean(row.get("work")))
        if key in seen:
            continue
        seen.add(key)
        events.append(
            PodcastEvent(
                source=clean(row.get("source")),
                timestamp=clean(row.get("timestamp")) or None,
                month=month,
                author=clean(row.get("author")) or "unknown",
                work=clean(row.get("work")),
                url=clean(row.get("url")) or None,
                video_id=vid,
                duration_seconds=duration if isinstance(duration, int) else None,
                influence_seconds=influence_seconds,
                influence_basis=basis,
                match_reasons=reasons,
                frequency=list(row.get("frequency") or ["unclassified"]),
                pressure=int(row.get("pressure") or 0),
                intensity=int(row.get("intensity") or 0),
                inspiration=int(row.get("inspiration") or 0),
                insight=int(row.get("insight") or 0),
                vitality=int(row.get("vitality") or 0),
                evidence_level=clean(row.get("evidence_level")),
            )
        )
    return events


def top(counter: Counter[Any], limit: int = 20) -> list[dict[str, Any]]:
    out = []
    for key, count in counter.most_common(limit):
        if isinstance(key, tuple):
            out.append({"value": key[0], "by": key[1], "count": count})
        else:
            out.append({"value": key, "count": count})
    return out


def top_weighted(rows: list[PodcastEvent], attr: str, limit: int = 20) -> list[dict[str, Any]]:
    weights: dict[Any, int] = defaultdict(int)
    counts: Counter[Any] = Counter()
    for row in rows:
        value = getattr(row, attr)
        if attr == "work":
            value = (row.work, row.author)
        weights[value] += row.influence_seconds
        counts[value] += 1
    out = []
    for value, seconds in sorted(weights.items(), key=lambda item: (-item[1], str(item[0])))[:limit]:
        item = {"hours": round(seconds / 3600, 2), "events": counts[value]}
        if isinstance(value, tuple):
            item.update({"value": value[0], "by": value[1]})
        else:
            item["value"] = value
        out.append(item)
    return out


def wave(rows: list[PodcastEvent]) -> list[list[Any]]:
    by_month: dict[str, list[PodcastEvent]] = defaultdict(list)
    for row in rows:
        if row.month:
            by_month[row.month].append(row)
    out = []
    for month, month_rows in sorted(by_month.items()):
        seconds = sum(row.influence_seconds for row in month_rows)
        out.append(
            [
                month,
                len(month_rows),
                round(seconds / 3600, 2),
                *[
                    round(sum(row.influence_seconds * getattr(row, axis) for row in month_rows) / 3600, 2)
                    for axis in AXES
                ],
            ]
        )
    return out


def record_waves(events: list[PodcastEvent], attr: str, limit: int = 80) -> list[dict[str, Any]]:
    by_value: dict[str, list[PodcastEvent]] = defaultdict(list)
    for event in events:
        by_value[getattr(event, attr)].append(event)
    records = []
    for value, rows in sorted(by_value.items(), key=lambda item: (-sum(row.influence_seconds for row in item[1]), item[0]))[:limit]:
        records.append(
            {
                "value": value,
                "events": len(rows),
                "dated_events": sum(1 for row in rows if row.month),
                "influence_hours": round(sum(row.influence_seconds for row in rows) / 3600, 2),
                "duration_basis": dict(Counter(row.influence_basis for row in rows).most_common()),
                "frequency": top(Counter(label for row in rows for label in row.frequency), 8),
                "peak_months": top(Counter(row.month for row in rows if row.month), 8),
                "top_works_by_hours": top_weighted(rows, "work", 8),
                "wave_schema": WAVE_SCHEMA,
                "wave": wave(rows),
            }
        )
    return records


def monthly_summary(events: list[PodcastEvent]) -> dict[str, dict[str, Any]]:
    by_month: dict[str, list[PodcastEvent]] = defaultdict(list)
    for event in events:
        if event.month:
            by_month[event.month].append(event)
    out = {}
    for month, rows in sorted(by_month.items()):
        out[month] = {
            "events": len(rows),
            "influence_hours": round(sum(row.influence_seconds for row in rows) / 3600, 2),
            "duration_basis": dict(Counter(row.influence_basis for row in rows).most_common()),
            "top_authors_by_hours": top_weighted(rows, "author", 12),
            "top_works_by_hours": top_weighted(rows, "work", 12),
            "frequency": top(Counter(label for row in rows for label in row.frequency), 10),
            "axes_by_hours": {
                axis: round(sum(row.influence_seconds * getattr(row, axis) for row in rows) / 3600, 2)
                for axis in AXES
            },
        }
    return out


def build(events_path: Path) -> dict[str, Any]:
    rows = load_rows(events_path)
    youtube_rows = [row for row in rows if "youtube" in clean(row.get("source")) and row.get("platform_space") == "youtube"]
    events = build_events(youtube_rows)
    dated = [event for event in events if event.month]
    return {
        "schema_version": "youtube-podcast-spectrum/v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "source": str(events_path),
        "capture_shape": {
            "youtube_rows_seen": len(youtube_rows),
            "podcast_like_events": len(events),
            "dated_podcast_like_events": len(dated),
            "unique_video_ids": len({event.video_id for event in events if event.video_id}),
            "direct_duration_rows": sum(1 for event in events if event.influence_basis == "direct-youtube-duration"),
            "known_video_duration_rows": sum(1 for event in events if event.influence_basis == "known-video-duration-from-visible-feed"),
            "estimated_duration_rows": sum(1 for event in events if event.influence_basis.endswith("estimate")),
            "influence_hours": round(sum(event.influence_seconds for event in events) / 3600, 2),
            "first_month": min((event.month for event in dated), default=None),
            "last_month": max((event.month for event in dated), default=None),
            "publication_note": "Podcast influence is derived from YouTube watch-history rows. Direct durations are used where the authenticated visible feed contains them; matching Takeout rows reuse known video duration when possible; otherwise the trace uses conservative episode-length estimates marked in influence_basis.",
        },
        "duration_basis": dict(Counter(event.influence_basis for event in events).most_common()),
        "match_reasons": dict(Counter(reason for event in events for reason in event.match_reasons).most_common()),
        "monthly": monthly_summary(events),
        "author_waves": record_waves(events, "author"),
        "events": [asdict(event) for event in events],
        "top_authors_by_hours": top_weighted(events, "author", 30),
        "top_works_by_hours": top_weighted(events, "work", 30),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    capture = payload["capture_shape"]
    lines = [
        "# YouTube Podcast Spectrum",
        "",
        "This is the podcast-shaped influence layer derived from YouTube history. RSS-era subscriptions are not present in the local source body yet; this report treats YouTube as the current podcast surface.",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        "## Capture Shape",
        "",
        f"- YouTube rows scanned: `{capture['youtube_rows_seen']}`",
        f"- Podcast-like events: `{capture['podcast_like_events']}`, `{capture['first_month']}` to `{capture['last_month']}`",
        f"- Unique video IDs: `{capture['unique_video_ids']}`",
        f"- Direct duration rows: `{capture['direct_duration_rows']}`",
        f"- Known-video duration rows: `{capture['known_video_duration_rows']}`",
        f"- Estimated duration rows: `{capture['estimated_duration_rows']}`",
        f"- Duration-weighted podcast influence: `{capture['influence_hours']}` hours",
        "",
        capture["publication_note"],
        "",
        "## Duration Basis",
        "",
    ]
    for basis, count in payload["duration_basis"].items():
        lines.append(f"- `{basis}`: {count}")
    lines.extend(["", "## Strongest Podcast Months", ""])
    for month, row in sorted(payload["monthly"].items(), key=lambda item: (-item[1]["influence_hours"], item[0]))[:24]:
        authors = ", ".join(f"{item['value']} ({item['hours']}h)" for item in row["top_authors_by_hours"][:4])
        lines.append(f"- `{month}`: {row['influence_hours']} hours across {row['events']} rows; {authors}")
    lines.extend(["", "## Top Podcast Authors / Channels", ""])
    for row in payload["top_authors_by_hours"][:30]:
        lines.append(f"- {row['value']}: {row['hours']} hours across {row['events']} rows")
    lines.extend(["", "## Query Shapes", ""])
    lines.append("- Month: load `trace/youtube_podcast_spectrum.json` then read `monthly[YYYY-MM]`.")
    lines.append("- Channel/person wave: search `author_waves[]` by `value`, then read `wave`.")
    lines.append("- Main influence uses `*_by_hours`; row counts and `duration_basis` explain evidence shape.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build YouTube podcast spectrum artifacts.")
    parser.add_argument("--field-dir", type=Path, default=FIELD_DIR)
    parser.add_argument("--events", type=Path, default=EVENTS_PATH)
    args = parser.parse_args()
    payload = build(args.events)
    write_json(args.field_dir / "trace" / "youtube_podcast_spectrum.json", payload)
    write_markdown(args.field_dir / "output" / "youtube_podcast_spectrum.md", payload)
    shape = payload["capture_shape"]
    print(f"podcast_like_events={shape['podcast_like_events']}")
    print(f"influence_hours={shape['influence_hours']}")
    print(f"estimated_duration_rows={shape['estimated_duration_rows']}")
    print(args.field_dir / "output" / "youtube_podcast_spectrum.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
