#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


YOUTUBE_WINDOW_START = datetime(2024, 5, 7).date()
YOUTUBE_WINDOW_END = datetime(2026, 5, 7).date()

TAXONOMY = {
    "seeking": ["seeker", "search", "quest", "truth", "meaning", "why", "mystery"],
    "sovereignty": ["sovereign", "freedom", "liberty", "autonomy", "self", "control"],
    "network-intelligence": ["network", "daemon", "distributed", "system", "platform", "protocol", "node"],
    "frontier": ["frontier", "space", "wilderness", "expanse", "ringworld", "exploration"],
    "embodiment": ["body", "breath", "somatic", "dance", "heart", "nervous", "healing"],
    "magic-and-pattern": ["magic", "spell", "name", "geometry", "pattern", "frequency", "harmonic"],
    "shadow-and-power": ["shadow", "power", "war", "empire", "law", "sword", "first law"],
    "world-building": ["world", "civilization", "kingdom", "society", "community", "city"],
    "time-and-attention": ["time", "momo", "attention", "listening", "memory", "history"],
    "ai-and-agency": ["ai", "artificial", "agent", "automation", "autonomous", "robot"],
}


@dataclass
class Event:
    source: str
    title: str
    creator: str | None = None
    series: str | None = None
    url: str | None = None
    timestamp: str | None = None
    raw_path: str | None = None
    themes: list[str] | None = None


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _clean_text(value: Any) -> str:
    return html.unescape(str(value or "")).strip()


def _takeout_html_blocks(raw: str) -> list[str]:
    return re.findall(r'<div class="outer-cell\b.*?(?=<div class="outer-cell\b|</body>)', raw, flags=re.S)


def _parse_takeout_date(value: str | None):
    value = _clean_text(value).replace("\u202f", " ").replace("\xa0", " ")
    match = re.search(r"([A-Z][a-z]+ \d{1,2}, 20\d\d, \d{1,2}:\d{2}:\d{2}\s*[AP]M)", value)
    if not match:
        return None
    for fmt in ("%B %d, %Y, %I:%M:%S %p", "%b %d, %Y, %I:%M:%S %p"):
        try:
            return datetime.strptime(match.group(1), fmt).date()
        except ValueError:
            continue
    return None


def _in_youtube_window(timestamp: str | None) -> bool:
    parsed = _parse_takeout_date(timestamp)
    return parsed is not None and YOUTUBE_WINDOW_START <= parsed <= YOUTUBE_WINDOW_END


def _matches_term(text: str, term: str) -> bool:
    if re.search(r"\W", term):
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def _takeout_html_events(path: Path) -> list[Event]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    events: list[Event] = []
    for block in _takeout_html_blocks(raw):
        content_match = re.search(
            r'<div class="content-cell[^"]*mdl-typography--body-1[^"]*">(.*?)</div>',
            block,
            flags=re.S,
        )
        if not content_match:
            continue
        content = content_match.group(1)
        links = re.findall(r'href="([^"]+)">([^<]+)</a>', content)
        if not links:
            continue
        text = _clean_text(re.sub(r"<[^>]+>", " ", content)).replace("\u202f", " ").replace("\xa0", " ")
        timestamp_match = re.search(r"([A-Z][a-z]+ \d{1,2}, 20\d\d, \d{1,2}:\d{2}:\d{2}\s*[AP]M\s*[A-Z]+)", text)
        timestamp = _clean_text(timestamp_match.group(1)) if timestamp_match else None
        if not _in_youtube_window(timestamp):
            continue
        action = "youtube-search" if "Searched for" in text else "youtube"
        title = _clean_text(links[0][1]).removeprefix("Watched ")
        creator = _clean_text(links[1][1]) if len(links) > 1 and "watch?" not in links[1][0] else None
        product_match = re.search(r"<b>Products:</b><br>&emsp;([^<]+)", block)
        product = _clean_text(product_match.group(1)).lower() if product_match else ""
        source = "youtube-music-takeout" if "music" in product else action
        events.append(
            Event(
                source=source,
                title=title,
                creator=creator,
                url=html.unescape(links[0][0]),
                timestamp=timestamp,
                raw_path=str(path),
                themes=classify(" ".join([title, creator or "", product])),
            )
        )
    return events


def classify(text: str) -> list[str]:
    lowered = text.lower()
    themes = []
    for theme, needles in TAXONOMY.items():
        if any(_matches_term(lowered, needle) for needle in needles):
            themes.append(theme)
    return themes or ["unclassified"]


def youtube_events(path: Path) -> list[Event]:
    events: list[Event] = []
    if path.suffix.lower() == ".json":
        data = _read_json(path)
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            for row in data["events"]:
                title = _clean_text(row.get("title"))
                creator = _clean_text(row.get("creator"))
                text = " ".join([title, creator, row.get("product") or ""])
                events.append(
                    Event(
                        source=row.get("source") or "youtube-myactivity",
                        title=title,
                        creator=creator or None,
                        url=row.get("url"),
                        timestamp=row.get("timeLine"),
                        raw_path=str(path),
                        themes=classify(text),
                    )
                )
            return events
        if isinstance(data, list):
            for row in data:
                title = _clean_text(row.get("title", "")).removeprefix("Watched ")
                creator = None
                subtitles = row.get("subtitles") or []
                if subtitles and isinstance(subtitles, list):
                    creator = _clean_text(subtitles[0].get("name"))
                text = " ".join([title, creator or ""])
                events.append(
                    Event(
                        source="youtube",
                        title=title,
                        creator=creator,
                        url=row.get("titleUrl"),
                        timestamp=row.get("time"),
                        raw_path=str(path),
                        themes=classify(text),
                    )
                )
    elif path.suffix.lower() == ".html":
        events.extend(_takeout_html_events(path))
    return events


def audible_events(path: Path) -> list[Event]:
    events: list[Event] = []
    if path.suffix.lower() == ".json":
        data = _read_json(path)
        rows = data if isinstance(data, list) else data.get("Books") or data.get("books") or []
        for row in rows:
            title = _clean_text(row.get("Title") or row.get("title"))
            creator = _clean_text(row.get("Author") or row.get("author") or row.get("Authors") or "")
            series = _clean_text(row.get("Series") or row.get("series") or "")
            source = _clean_text(row.get("source")) or "audible"
            timestamp = _clean_text(row.get("listened_date") or row.get("purchased_date") or row.get("date_added"))
            url = _clean_text(row.get("product_url") or row.get("url"))
            text = " ".join([title, creator, series])
            if title:
                events.append(
                    Event(
                        source,
                        title,
                        creator or None,
                        series or None,
                        url or None,
                        timestamp or None,
                        raw_path=str(path),
                        themes=classify(text),
                    )
                )
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                title = _clean_text(row.get("Title") or row.get("title"))
                creator = _clean_text(row.get("Author") or row.get("Authors") or row.get("author") or "")
                series = _clean_text(row.get("Series") or row.get("series") or "")
                text = " ".join([title, creator, series])
                if title:
                    events.append(Event("audible", title, creator or None, series or None, raw_path=str(path), themes=classify(text)))
    return events


def anchor_events(path: Path) -> list[Event]:
    data = _read_json(path)
    events: list[Event] = []
    identity = data.get("early_online_identity", {})
    if identity:
        events.append(Event("manual-anchor", identity.get("handle", "TheSeeker"), None, "online identity", themes=identity.get("themes")))
    for row in data.get("early_childhood_reading", []):
        events.append(Event("manual-anchor", row["title"], None, "early childhood reading", themes=row.get("themes")))
    for row in data.get("later_series", []):
        events.append(Event("manual-anchor", row["series"], row.get("author"), "later reading/listening", themes=row.get("themes")))
    return events


def browser_trace_events(path: Path) -> list[Event]:
    events: list[Event] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            title = _clean_text(row.get("title") or row.get("normalized_title"))
            creator = _clean_text(row.get("creator") or row.get("domain") or "")
            url = row.get("url")
            text = " ".join([title, creator, url or ""])
            if title:
                events.append(
                    Event(
                        source=row.get("source", "browser-trace"),
                        title=title,
                        creator=creator or None,
                        url=url,
                        timestamp=row.get("timestamp"),
                        raw_path=str(path),
                        themes=classify(text),
                    )
                )
    return events


def collect(root: Path) -> list[Event]:
    events: list[Event] = []
    for path in (root / "input" / "youtube").rglob("*"):
        if path.suffix.lower() in {".json", ".html"} and (
            "history" in path.name.lower() or "myactivity" in path.name.lower()
        ):
            events.extend(youtube_events(path))
    for path in (root / "input" / "audible").rglob("*"):
        if {"pages", "purchase-years"} & set(path.parts):
            continue
        if path.suffix.lower() in {".json", ".csv"}:
            events.extend(audible_events(path))
    for path in (root / "input" / "browser").rglob("*.jsonl"):
        events.extend(browser_trace_events(path))
    anchor = root / "anchors" / "manual_reading_anchors.json"
    if anchor.exists():
        events.extend(anchor_events(anchor))
    return events


def write_outputs(root: Path, events: list[Event]) -> None:
    out = root / "output"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "normalized_events.jsonl").open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

    theme_counts = Counter(theme for event in events for theme in (event.themes or []))
    source_counts = Counter(event.source for event in events)
    by_source_theme: dict[str, Counter[str]] = defaultdict(Counter)
    for event in events:
        for theme in event.themes or []:
            by_source_theme[event.source][theme] += 1

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "event_count": len(events),
        "source_counts": dict(source_counts),
        "theme_counts": dict(theme_counts.most_common()),
        "by_source_theme": {source: dict(counter.most_common()) for source, counter in by_source_theme.items()},
    }
    (out / "frequency_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Field Listening Report",
        "",
        f"Generated: {summary['generated_at']}",
        f"Events analyzed: {len(events)}",
        "",
        "## Sources",
    ]
    for source, count in source_counts.most_common():
        lines.append(f"- {source}: {count}")
    lines.extend(["", "## Dominant Frequencies"])
    for theme, count in theme_counts.most_common():
        lines.append(f"- {theme}: {count}")
    lines.extend(["", "## Strongest Manual Anchors"])
    for event in [e for e in events if e.source == "manual-anchor"][:30]:
        lines.append(f"- {event.title}" + (f" — {event.creator}" if event.creator else "") + f" ({', '.join(event.themes or [])})")
    (out / "field_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    cluster_lines = [
        "# Listening / Viewing Clusters",
        "",
        "This is source-derived clustering from available data. Browser traces prove page visits, not full listening duration.",
        "",
    ]
    for source in sorted(source_counts):
        source_events = [event for event in events if event.source == source]
        title_counts = Counter(event.title for event in source_events if event.title)
        creator_counts = Counter(event.creator for event in source_events if event.creator)
        theme_counts_for_source = Counter(theme for event in source_events for theme in (event.themes or []))
        cluster_lines.extend([f"## {source}", ""])
        cluster_lines.append("### Top Works / Pages")
        for title, count in title_counts.most_common(25):
            cluster_lines.append(f"- {count}x {title}")
        if creator_counts:
            cluster_lines.extend(["", "### Top Creators / Domains"])
            for creator, count in creator_counts.most_common(20):
                cluster_lines.append(f"- {count}x {creator}")
        cluster_lines.extend(["", "### Frequency Themes"])
        for theme, count in theme_counts_for_source.most_common(20):
            cluster_lines.append(f"- {theme}: {count}")
        cluster_lines.append("")
    (out / "clusters.md").write_text("\n".join(cluster_lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/Users/ursmuff/CoherenceFieldAnalysis"))
    args = parser.parse_args()
    events = collect(args.root)
    write_outputs(args.root, events)
    print(f"events={len(events)}")
    print(args.root / "output" / "field_report.md")


if __name__ == "__main__":
    main()
