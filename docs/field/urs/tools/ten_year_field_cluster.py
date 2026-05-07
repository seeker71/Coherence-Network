#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
import re
import tempfile
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path("/Users/ursmuff/CoherenceFieldAnalysis")
TAKEOUT_WINDOW_START = datetime(2024, 5, 7).date()
TAKEOUT_WINDOW_END = datetime(2026, 5, 7).date()


FREQUENCY_RULES = {
    "devotional-body": [
        "breath",
        "healing",
        "mantra",
        "sita ram",
        "hare krishna",
        "aum",
        "shiva",
        "chant",
        "ceremonial",
        "medicine",
        "hathor",
        "chakra",
        "mose",
        "porang",
        "ayla",
        "yaima",
        "liquid bloom",
        "chantress",
    ],
    "roots-resilience": [
        "roots",
        "reggae",
        "sun",
        "jah",
        "humbled",
        "humble",
        "forgive",
        "family tree",
        "sugarshack",
        "xavier rudd",
        "soja",
        "iya terra",
        "mike love",
        "rising appalachia",
        "damian marley",
    ],
    "ai-systems": [
        "ai",
        "llm",
        "claude",
        "agent",
        "mentor",
        "compiler",
        "git",
        "linus",
        "karpathy",
        "coding",
        "stochastic",
        "hallucinate",
        "automation",
    ],
    "consciousness-threshold": [
        "arctur",
        "angel",
        "telepathy",
        "pineal",
        "light body",
        "disclosure",
        "new earth",
        "orion",
        "akashic",
        "frequency",
        "1111",
        "robert edward grant",
        "anne tucker",
        "bioelectric",
        "levin",
    ],
    "fictional-systems": [
        "daemon",
        "ringworld",
        "expanse",
        "viridian",
        "kingkiller",
        "sword of truth",
        "first law",
        "spellmonger",
        "frontiers",
        "hamilton",
        "world",
        "magic",
        "fleet",
        "civilization",
    ],
    "shadow-power": [
        "war",
        "emergency",
        "warning",
        "split",
        "final choice",
        "power",
        "shadow",
        "demon",
        "hard road",
        "pressure",
        "cancer",
        "godfather",
    ],
    "time-attention": [
        "time",
        "momo",
        "history",
        "memory",
        "attention",
        "watch history",
        "listening log",
    ],
}

AXIS_RULES = {
    "pressure": [
        "emergency",
        "warning",
        "war",
        "split",
        "final",
        "cancer",
        "problem",
        "hard",
        "pressure",
        "godfather of ai",
        "before everything changes",
        "demon",
    ],
    "inspiration": [
        "dream",
        "blessing",
        "love",
        "sun",
        "healing",
        "awaken",
        "harmonize",
        "pure light",
        "roots",
        "grandmother",
        "oracle",
        "rise",
        "freedom",
        "surrender",
    ],
    "insight": [
        "lecture",
        "talk",
        "analysis",
        "analyzed",
        "history",
        "linus",
        "git",
        "bioelectric",
        "llm",
        "ai",
        "compiler",
        "why",
        "evidence",
        "research",
    ],
    "vitality": [
        "breath",
        "body",
        "healing",
        "sun",
        "roots",
        "heart",
        "dance",
        "music",
        "mantra",
        "water",
        "flow",
        "ceremony",
        "journey",
    ],
}


@dataclass
class Event:
    source: str
    timestamp: str | None
    platform_space: str
    author: str
    work: str
    url: str | None
    duration_seconds: int | None
    frequency: list[str]
    pressure: int
    intensity: int
    inspiration: int
    insight: int
    vitality: int
    evidence_level: str


def clean(value: object) -> str:
    return html.unescape(str(value or "")).strip()


def parse_duration(value: str | None) -> int | None:
    if not value:
        return None
    parts = [int(x) for x in re.findall(r"\d+", value)]
    if not parts:
        return None
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return None


def matches_term(text: str, term: str) -> bool:
    if re.search(r"\W", term):
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def score_terms(text: str, words: list[str]) -> int:
    lowered = text.lower()
    return min(10, sum(2 if matches_term(lowered, word) else 0 for word in words))


def classify_frequency(text: str) -> list[str]:
    lowered = text.lower()
    out = [name for name, words in FREQUENCY_RULES.items() if any(matches_term(lowered, word) for word in words)]
    return out or ["unclassified"]


def infer_space(source: str, url: str | None) -> str:
    if "music" in source:
        return "youtube-music"
    if "youtube" in source:
        return "youtube"
    if "audible" in source:
        return "audible"
    if source == "manual-anchor":
        return "manual-lineage"
    host = urlparse(url or "").netloc
    return host or source


def takeout_html_blocks(raw: str) -> list[str]:
    return re.findall(r'<div class="outer-cell\b.*?(?=<div class="outer-cell\b|</body>)', raw, flags=re.S)


def parse_takeout_date(value: str | None):
    value = clean(value).replace("\u202f", " ").replace("\xa0", " ")
    match = re.search(r"([A-Z][a-z]+ \d{1,2}, 20\d\d, \d{1,2}:\d{2}:\d{2}\s*[AP]M)\s*([A-Z]+)?", value)
    if not match:
        return None
    for fmt in ("%B %d, %Y, %I:%M:%S %p", "%b %d, %Y, %I:%M:%S %p"):
        try:
            return datetime.strptime(match.group(1), fmt).date()
        except ValueError:
            continue
    return None


def in_takeout_window(timestamp: str | None) -> bool:
    parsed = parse_takeout_date(timestamp)
    if parsed is None:
        return False
    return TAKEOUT_WINDOW_START <= parsed <= TAKEOUT_WINDOW_END


def event_from_parts(
    *,
    source: str,
    timestamp: str | None,
    author: str | None,
    work: str,
    url: str | None = None,
    duration: str | None = None,
    evidence_level: str,
) -> Event:
    text = " ".join([author or "", work, url or ""])
    duration_seconds = parse_duration(duration)
    pressure = score_terms(text, AXIS_RULES["pressure"])
    inspiration = score_terms(text, AXIS_RULES["inspiration"])
    insight = score_terms(text, AXIS_RULES["insight"])
    vitality = score_terms(text, AXIS_RULES["vitality"])
    intensity = min(10, 1 + pressure // 2 + insight // 3 + vitality // 4 + (2 if duration_seconds and duration_seconds >= 1800 else 0))
    return Event(
        source=source,
        timestamp=timestamp,
        platform_space=infer_space(source, url),
        author=clean(author) or "unknown",
        work=clean(work),
        url=url,
        duration_seconds=duration_seconds,
        frequency=classify_frequency(text),
        pressure=pressure,
        intensity=intensity,
        inspiration=inspiration,
        insight=insight,
        vitality=vitality,
        evidence_level=evidence_level,
    )


def audible_date(value: str | None) -> str | None:
    value = clean(value)
    match = re.match(r"^(\d{2})-(\d{2})-(\d{2}|\d{4})$", value)
    if not match:
        return value or None
    month, day, year = match.groups()
    if len(year) == 2:
        year = f"20{year}"
    return f"{year}-{month}-{day}"


def load_myactivity_raw(path: Path) -> list[Event]:
    data = json.load(path.open(encoding="utf-8"))
    out = []
    for row in data.get("events", []):
        out.append(
            event_from_parts(
                source=row.get("source") or "youtube-myactivity",
                timestamp=row.get("absoluteTime") or row.get("timeLine"),
                author=row.get("creator"),
                work=row.get("title") or "",
                url=row.get("url"),
                duration=row.get("duration"),
                evidence_level="authenticated-myactivity-visible-feed",
            )
        )
    return out


def load_audible_exports(root: Path) -> list[Event]:
    out = []
    for path in (root / "input" / "audible").rglob("*.json"):
        if {"pages", "purchase-years"} & set(path.parts):
            continue
        if path.name.endswith("auth-state.json"):
            continue
        data = json.load(path.open(encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("Books") or data.get("books") or []
        for row in rows:
            source = row.get("source") or "audible"
            timestamp = audible_date(row.get("listened_date") or row.get("purchased_date") or row.get("date_added"))
            out.append(
                event_from_parts(
                    source=source,
                    timestamp=timestamp,
                    author=row.get("author") or row.get("Author") or row.get("Authors"),
                    work=row.get("title") or row.get("Title") or "",
                    url=row.get("product_url") or row.get("url"),
                    duration=row.get("duration"),
                    evidence_level=source,
                )
            )
    return out


def load_browser_jsonl(path: Path) -> list[Event]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out.append(
            event_from_parts(
                source=row.get("source") or "browser",
                timestamp=row.get("timestamp"),
                author=row.get("domain"),
                work=row.get("normalized_title") or row.get("title") or "",
                url=row.get("url"),
                duration=None,
                evidence_level="local-browser-history",
            )
        )
    return out


def load_manual_anchors(path: Path) -> list[Event]:
    data = json.load(path.open(encoding="utf-8"))
    out = []
    ident = data.get("early_online_identity") or {}
    if ident:
        out.append(
            event_from_parts(
                source="manual-anchor",
                timestamp=None,
                author="Urs",
                work=ident.get("handle") or "TheSeeker",
                evidence_level="manual-anchor",
            )
        )
    for row in data.get("early_childhood_reading", []):
        out.append(
            event_from_parts(
                source="manual-anchor",
                timestamp=None,
                author="unknown",
                work=row.get("title") or "",
                evidence_level="manual-anchor",
            )
        )
    for row in data.get("later_series", []):
        out.append(
            event_from_parts(
                source="manual-anchor",
                timestamp=None,
                author=row.get("author"),
                work=row.get("series") or "",
                evidence_level="manual-anchor",
            )
        )
    return out


def load_takeout_file(path: Path) -> list[Event]:
    out = []
    if path.suffix.lower() == ".json":
        data = json.load(path.open(encoding="utf-8"))
        if isinstance(data, list):
            for row in data:
                title = clean(row.get("title")).removeprefix("Watched ")
                subtitles = row.get("subtitles") or []
                author = subtitles[0].get("name") if subtitles else None
                out.append(
                    event_from_parts(
                        source="youtube-takeout",
                        timestamp=row.get("time"),
                        author=author,
                        work=title,
                        url=row.get("titleUrl"),
                        duration=None,
                        evidence_level="google-takeout",
                    )
                )
    elif path.suffix.lower() == ".html":
        raw = path.read_text(encoding="utf-8", errors="ignore")
        for block in takeout_html_blocks(raw):
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
            text = clean(re.sub(r"<[^>]+>", " ", content)).replace("\u202f", " ").replace("\xa0", " ")
            time = re.search(r"([A-Z][a-z]+ \d{1,2}, 20\d\d, \d{1,2}:\d{2}:\d{2}\s*[AP]M\s*[A-Z]+)", text)
            timestamp = clean(time.group(1)) if time else None
            if not in_takeout_window(timestamp):
                continue
            product = re.search(r"<b>Products:</b><br>&emsp;([^<]+)", block)
            product_text = clean(product.group(1)).lower() if product else ""
            source = "youtube-music-takeout" if "music" in product_text else "youtube-takeout"
            author = clean(links[1][1]) if len(links) > 1 and "watch?" not in links[1][0] else None
            out.append(
                event_from_parts(
                    source=source,
                    timestamp=timestamp,
                    author=author,
                    work=clean(links[0][1]).removeprefix("Watched "),
                    url=html.unescape(links[0][0]),
                    duration=None,
                    evidence_level="google-takeout-2024-05-07-to-2026-05-07",
                )
            )
    return out


def load_takeout_zips(root: Path) -> list[Event]:
    out = []
    seen: set[tuple[str | None, str, str | None]] = set()
    for zip_path in (root / "input" / "youtube").glob("*.zip"):
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(zip_path) as zf:
                wanted = [
                    name
                    for name in zf.namelist()
                    if name.lower().endswith(("watch-history.json", "watch-history.html", "myactivity.json", "myactivity.html"))
                ]
                for name in wanted:
                    zf.extract(name, tmp)
                    for event in load_takeout_file(Path(tmp) / name):
                        key = (event.timestamp, event.work, event.url)
                        if key not in seen:
                            seen.add(key)
                            out.append(event)
    for path in (root / "input" / "youtube").rglob("*"):
        if path.suffix.lower() in {".json", ".html"} and path.name != "myactivity-playwright-raw.json":
            if "history" in path.name.lower() or "myactivity" in path.name.lower():
                for event in load_takeout_file(path):
                    key = (event.timestamp, event.work, event.url)
                    if key not in seen:
                        seen.add(key)
                        out.append(event)
    return out


def load_events(root: Path) -> list[Event]:
    events: list[Event] = []
    p = root / "input" / "youtube" / "myactivity-playwright-raw.json"
    if p.exists():
        events.extend(load_myactivity_raw(p))
    p = root / "input" / "browser" / "local_browser_events.jsonl"
    if p.exists():
        events.extend(load_browser_jsonl(p))
    events.extend(load_audible_exports(root))
    p = root / "anchors" / "manual_reading_anchors.json"
    if p.exists():
        events.extend(load_manual_anchors(p))
    events.extend(load_takeout_zips(root))
    return [event for event in events if event.work]


def time_bucket(timestamp: str | None) -> str:
    if not timestamp:
        return "undated"
    if re.match(r"^\d{4}-\d{2}", timestamp):
        return timestamp[:7]
    parsed_takeout = parse_takeout_date(timestamp)
    if parsed_takeout:
        return parsed_takeout.strftime("%Y-%m")
    year = re.search(r"\b(20\d\d)\b", timestamp)
    if year:
        return year.group(1)
    return "visible-feed-no-date"


def write_report(root: Path, events: list[Event]) -> None:
    out = root / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ten_year_events.jsonl").write_text(
        "\n".join(json.dumps(asdict(e), ensure_ascii=False) for e in events) + "\n",
        encoding="utf-8",
    )

    by_time = defaultdict(list)
    by_space = defaultdict(list)
    by_author = defaultdict(list)
    by_work = defaultdict(list)
    by_frequency = defaultdict(list)
    for event in events:
        by_time[time_bucket(event.timestamp)].append(event)
        by_space[event.platform_space].append(event)
        by_author[event.author].append(event)
        by_work[event.work].append(event)
        for frequency in event.frequency:
            by_frequency[frequency].append(event)

    def top(counter_map: dict[str, list[Event]], n: int = 20) -> list[tuple[str, int]]:
        return sorted(((k, len(v)) for k, v in counter_map.items()), key=lambda x: (-x[1], x[0]))[:n]

    axis_totals = {
        "pressure": sum(e.pressure for e in events),
        "intensity": sum(e.intensity for e in events),
        "inspiration": sum(e.inspiration for e in events),
        "insight": sum(e.insight for e in events),
        "vitality": sum(e.vitality for e in events),
    }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(events),
        "evidence_levels": dict(Counter(e.evidence_level for e in events)),
        "time_clusters": top(by_time, 60),
        "space_clusters": top(by_space),
        "author_clusters": top(by_author, 40),
        "work_clusters": top(by_work, 60),
        "frequency_clusters": top(by_frequency, 30),
        "axis_totals": axis_totals,
        "youtube_takeout_window": {
            "start": TAKEOUT_WINDOW_START.isoformat(),
            "end": TAKEOUT_WINDOW_END.isoformat(),
            "evidence_level": "google-takeout-2024-05-07-to-2026-05-07",
        },
        "data_gap": "YouTube watch history from the completed history-only Google Takeout archive is loaded for the requested two-year window. The 10-part full export in Downloads exposes YouTube search history in part 001, but no watch-history file was found in those parts. Audible web contributes purchase/library/listen-history evidence; the detailed per-title mobile Listening Log remains app-only.",
    }
    (out / "ten_year_cluster_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Ten-Year Field Cluster Analysis",
        "",
        f"Generated: {summary['generated_at']}",
        f"Events/anchors analyzed: {len(events)}",
        "",
        "## Coverage",
    ]
    for level, count in Counter(e.evidence_level for e in events).most_common():
        lines.append(f"- {level}: {count}")
    lines.extend(
        [
            "",
            "Coverage note: YouTube watch history is loaded from the completed history-only Google Takeout archive for 2024-05-07 through 2026-05-07. The 10-part full export in Downloads exposes YouTube search history in part 001, but no watch-history file was found in those parts. Audible web now contributes authenticated purchase, library, and visible listen-history evidence, while the detailed per-title mobile Listening Log remains app-only.",
            "",
            "## Time Clusters",
        ]
    )
    for key, count in summary["time_clusters"]:
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Space Clusters"])
    for key, count in summary["space_clusters"]:
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Author / Channel Clusters"])
    for key, count in summary["author_clusters"]:
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Work Clusters"])
    for key, count in summary["work_clusters"]:
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Frequency Clusters"])
    for key, count in summary["frequency_clusters"]:
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Axis Totals"])
    for key, count in axis_totals.items():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Highest Pressure Events"])
    for event in sorted(events, key=lambda e: (-e.pressure, -e.intensity))[:20]:
        lines.append(f"- P{event.pressure} I{event.intensity}: {event.work} — {event.author} [{event.platform_space}]")
    lines.extend(["", "## Highest Inspiration / Vitality Events"])
    for event in sorted(events, key=lambda e: (-(e.inspiration + e.vitality), -e.intensity))[:25]:
        lines.append(
            f"- S{event.inspiration} V{event.vitality} I{event.intensity}: {event.work} — {event.author} [{', '.join(event.frequency)}]"
        )
    lines.extend(["", "## Highest Insight Events"])
    for event in sorted(events, key=lambda e: (-e.insight, -e.intensity))[:20]:
        lines.append(f"- N{event.insight} I{event.intensity}: {event.work} — {event.author} [{event.platform_space}]")
    (out / "ten_year_cluster_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    events = load_events(ROOT)
    write_report(ROOT, events)
    print(f"events={len(events)}")
    print(ROOT / "output" / "ten_year_cluster_report.md")


if __name__ == "__main__":
    main()
