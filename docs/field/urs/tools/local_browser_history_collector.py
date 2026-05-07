#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path("/Users/ursmuff/CoherenceFieldAnalysis")
HOME = Path.home()


@dataclass
class BrowserEvent:
    source: str
    browser: str
    profile: str
    trace_kind: str
    timestamp: str | None
    url: str
    title: str
    normalized_title: str
    domain: str
    video_id: str | None = None


def chrome_time(value: int | None) -> str | None:
    if not value:
        return None
    dt = datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=int(value))
    return dt.isoformat()


def candidates() -> list[tuple[str, str, Path]]:
    roots = [
        ("chrome", HOME / "Library/Application Support/Google/Chrome"),
        ("chromium", HOME / "Library/Application Support/Chromium"),
        ("brave", HOME / "Library/Application Support/BraveSoftware/Brave-Browser"),
        ("edge", HOME / "Library/Application Support/Microsoft Edge"),
        ("arc", HOME / "Library/Application Support/Arc/User Data"),
    ]
    out: list[tuple[str, str, Path]] = []
    for browser, root in roots:
        if not root.exists():
            continue
        for path in root.glob("*/History"):
            out.append((browser, path.parent.name, path))
    return out


def classify_url(url: str, title: str) -> str | None:
    host = urlparse(url).netloc.lower()
    lowered = f"{url} {title}".lower()
    if "music.youtube.com" in host:
        return "youtube-music-browser"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube-browser"
    if "audible." in host or "audible " in lowered:
        return "audible-browser"
    return None


def video_id(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.netloc.lower() == "youtu.be":
        return parsed.path.strip("/") or None
    qs = parse_qs(parsed.query)
    return (qs.get("v") or [None])[0]


def normalize_title(title: str, trace_kind: str) -> str:
    cleaned = (title or "").strip()
    for suffix in (" - YouTube", " - YouTube Music", " | Audible.com", " | Audible"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    if trace_kind == "audible-browser" and cleaned in {"Audible.com", "Audible"}:
        return cleaned
    return cleaned


def collect_chromium(browser: str, profile: str, history_path: Path) -> list[BrowserEvent]:
    events: list[BrowserEvent] = []
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / f"{browser}-{profile}-History.sqlite"
        shutil.copy2(history_path, copy)
        con = sqlite3.connect(copy)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            select urls.url, urls.title, visits.visit_time
            from visits
            join urls on urls.id = visits.url
            where lower(urls.url) like '%youtube%'
               or lower(urls.url) like '%youtu.be%'
               or lower(urls.url) like '%music.youtube%'
               or lower(urls.url) like '%audible%'
               or lower(urls.title) like '%audible%'
            order by visits.visit_time asc
            """
        ).fetchall()
        con.close()
    for row in rows:
        url = str(row["url"] or "")
        title = str(row["title"] or "")
        trace_kind = classify_url(url, title)
        if not trace_kind:
            continue
        parsed = urlparse(url)
        events.append(
            BrowserEvent(
                source=trace_kind,
                browser=browser,
                profile=profile,
                trace_kind=trace_kind,
                timestamp=chrome_time(row["visit_time"]),
                url=url,
                title=title,
                normalized_title=normalize_title(title, trace_kind),
                domain=parsed.netloc.lower(),
                video_id=video_id(url),
            )
        )
    return events


def main() -> None:
    all_events: list[BrowserEvent] = []
    errors: list[str] = []
    for browser, profile, path in candidates():
        try:
            all_events.extend(collect_chromium(browser, profile, path))
        except Exception as exc:
            errors.append(f"{browser}/{profile}: {exc}")

    out_dir = ROOT / "input" / "browser"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "local_browser_events.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for event in all_events:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "event_count": len(all_events),
        "by_source": dict(Counter(event.source for event in all_events)),
        "by_browser": dict(Counter(event.browser for event in all_events)),
        "errors": errors,
        "output": str(out_path),
    }
    (ROOT / "output" / "browser_trace_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
