#!/usr/bin/env python3
"""Build a compact Audible history spectrum from captured source bodies."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from audible_series_analyzer import infer_series, split_library_title


ANALYSIS_ROOT = Path("/Users/ursmuff/CoherenceFieldAnalysis")
AXES = ("pressure", "intensity", "inspiration", "insight", "vitality")
WAVE_SCHEMA = ["month", "events", *AXES]

FREQUENCY_RULES = {
    "fictional-systems": [
        "daemon",
        "ringworld",
        "expanse",
        "viridian",
        "kingkiller",
        "sword",
        "truth",
        "first law",
        "spellmonger",
        "frontier",
        "frontiers",
        "hamilton",
        "fleet",
        "mage",
        "magic",
        "dragon",
        "kingdom",
        "empire",
        "civilization",
    ],
    "ai-systems": ["ai", "artificial", "rebooting", "daemon", "future", "faster", "source", "automation"],
    "consciousness-threshold": [
        "holographic",
        "placebo",
        "awakening",
        "channel",
        "avalon",
        "future human",
        "tibetan",
        "dead",
        "god",
        "eckhart",
        "presence",
    ],
    "devotional-body": [
        "compassion",
        "acceptance",
        "peaceful",
        "heart",
        "warrior",
        "things fall apart",
        "brach",
        "kimmerer",
        "body",
        "healing",
    ],
    "time-attention": ["time", "history", "memory", "attention", "listening", "purpose", "now", "janus"],
    "platform-frontier": ["cryptonomicon", "snow crash", "delta-v", "civilization", "future", "systems"],
}

AXIS_RULES = {
    "pressure": ["war", "doom", "fall", "death", "enemy", "vengeance", "shadow", "broken", "hard", "siege"],
    "inspiration": ["future", "awakening", "greenlights", "source", "freedom", "peaceful", "purpose", "alive"],
    "insight": ["history", "ai", "mathematics", "holographic", "source", "future", "sapiens", "rebooting"],
    "vitality": ["heart", "body", "forest", "greenlights", "compassion", "alive", "peaceful", "braiding"],
}


@dataclass(frozen=True)
class AudibleEvent:
    source: str
    date: str | None
    month: str | None
    author: str
    title: str
    asin: str | None
    url: str | None
    series: str
    inference: str
    status: str | None
    frequency: list[str]
    pressure: int
    intensity: int
    inspiration: int
    insight: int
    vitality: int
    event_kind: str


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def audible_date(value: Any) -> str | None:
    text = clean(value)
    match = re.match(r"^(\d{2})-(\d{2})-(\d{2}|\d{4})$", text)
    if not match:
        return text or None
    month, day, year = match.groups()
    if len(year) == 2:
        year = f"20{year}"
    return f"{year}-{month}-{day}"


def month_of(date: str | None) -> str | None:
    if date and re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return date[:7]
    return None


def matches(text: str, term: str) -> bool:
    if re.search(r"\W", term):
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def classify(text: str) -> list[str]:
    lowered = text.casefold()
    labels = [label for label, terms in FREQUENCY_RULES.items() if any(matches(lowered, term) for term in terms)]
    return labels or ["unclassified"]


def score(text: str, terms: list[str]) -> int:
    lowered = text.casefold()
    return min(10, sum(2 for term in terms if matches(lowered, term)))


def event_id(author: str, title: str, asin: str | None) -> str:
    seed = asin or f"{author}:{title}"
    return hashlib.sha1(seed.casefold().encode("utf-8")).hexdigest()[:12]


def row_title_author(row: dict[str, Any]) -> tuple[str, str]:
    title = clean(row.get("title") or row.get("Title"))
    author = clean(row.get("author") or row.get("Author") or row.get("Authors"))
    return split_library_title(title, author)


def make_event(row: dict[str, Any], *, source: str, date_field: str | None, event_kind: str) -> AudibleEvent | None:
    title, author = row_title_author(row)
    if not title:
        return None
    date = audible_date(row.get(date_field)) if date_field else None
    native_series = clean(row.get("series") or row.get("Series")) or None
    series, inference = infer_series(title, author, native_series)
    text = " ".join([title, author, series])
    pressure = score(text, AXIS_RULES["pressure"])
    inspiration = score(text, AXIS_RULES["inspiration"])
    insight = score(text, AXIS_RULES["insight"])
    vitality = score(text, AXIS_RULES["vitality"])
    intensity = min(10, 1 + pressure // 2 + insight // 3 + vitality // 4)
    return AudibleEvent(
        source=source,
        date=date,
        month=month_of(date),
        author=author or "unknown",
        title=title,
        asin=clean(row.get("asin") or row.get("ASIN")) or None,
        url=clean(row.get("product_url") or row.get("url")) or None,
        series=series,
        inference=inference,
        status=clean(row.get("status")) or None,
        frequency=classify(text),
        pressure=pressure,
        intensity=intensity,
        inspiration=inspiration,
        insight=insight,
        vitality=vitality,
        event_kind=event_kind,
    )


def read_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("Books") or data.get("books") or []


def load_events(analysis_root: Path) -> list[AudibleEvent]:
    base = analysis_root / "input" / "audible" / "playwright"
    sources = [
        ("audible-purchase-history", base / "audible-purchase-history-2016-2026.json", "purchased_date", "purchase"),
        ("audible-listen-history", base / "audible-listen-history.json", "listened_date", "visible-listen"),
        ("audible-library", base / "audible-library.json", None, "library-holding"),
    ]
    events: list[AudibleEvent] = []
    for source, path, date_field, event_kind in sources:
        for row in read_json(path):
            event = make_event(row, source=source, date_field=date_field, event_kind=event_kind)
            if event:
                events.append(event)
    return events


def top(counter: Counter[Any], limit: int = 20) -> list[dict[str, Any]]:
    out = []
    for value, count in counter.most_common(limit):
        if isinstance(value, tuple):
            out.append({"value": value[0], "by": value[1], "count": count})
        else:
            out.append({"value": value, "count": count})
    return out


def wave(rows: list[AudibleEvent]) -> list[list[Any]]:
    by_month: dict[str, list[AudibleEvent]] = defaultdict(list)
    for row in rows:
        if row.month:
            by_month[row.month].append(row)
    out = []
    for month in sorted(by_month):
        month_rows = by_month[month]
        out.append([month, len(month_rows), *[sum(getattr(row, axis) for row in month_rows) for axis in AXES]])
    return out


def record_waves(events: list[AudibleEvent], attr: str, limit: int = 80) -> list[dict[str, Any]]:
    by_value: dict[str, list[AudibleEvent]] = defaultdict(list)
    for event in events:
        by_value[clean(getattr(event, attr))].append(event)
    records = []
    for value, rows in sorted(by_value.items(), key=lambda item: (-len(item[1]), item[0]))[:limit]:
        records.append(
            {
                "value": value,
                "events": len(rows),
                "dated_events": sum(1 for row in rows if row.month),
                "sources": dict(Counter(row.source for row in rows).most_common()),
                "event_kinds": dict(Counter(row.event_kind for row in rows).most_common()),
                "series": top(Counter(row.series for row in rows), 8),
                "frequency": top(Counter(label for row in rows for label in row.frequency), 8),
                "peak_months": top(Counter(row.month for row in rows if row.month), 8),
                "wave_schema": WAVE_SCHEMA,
                "wave": wave(rows),
            }
        )
    return records


def effective_listening_events(events: list[AudibleEvent]) -> list[AudibleEvent]:
    """Direct visible listens win; purchase rows approximate listens only where direct rows are absent."""
    listens = [event for event in events if event.source == "audible-listen-history"]
    purchases = [event for event in events if event.source == "audible-purchase-history"]
    listen_keys = {event_id(event.author, event.title, event.asin) for event in listens}
    approx = [
        replace(
            event,
            event_kind="purchase-as-listen-approx",
            status="purchase date used as approximate Audible field-entry/listening date",
        )
        for event in purchases
        if event_id(event.author, event.title, event.asin) not in listen_keys
    ]
    return sorted([*listens, *approx], key=lambda event: (event.date or "9999-99-99", event.author, event.title))


def monthly_summary(rows: list[AudibleEvent]) -> dict[str, dict[str, Any]]:
    months: dict[str, list[AudibleEvent]] = defaultdict(list)
    for event in rows:
        if event.month:
            months[event.month].append(event)
    monthly = {}
    for month, month_rows in sorted(months.items()):
        monthly[month] = {
            "events": len(month_rows),
            "sources": dict(Counter(row.source for row in month_rows).most_common()),
            "event_kinds": dict(Counter(row.event_kind for row in month_rows).most_common()),
            "top_authors": top(Counter(row.author for row in month_rows), 10),
            "top_titles": top(Counter((row.title, row.author) for row in month_rows), 10),
            "top_series": top(Counter(row.series for row in month_rows), 10),
            "frequency": top(Counter(label for row in month_rows for label in row.frequency), 10),
            "axes": {axis: sum(getattr(row, axis) for row in month_rows) for axis in AXES},
        }
    return monthly


def build(analysis_root: Path) -> dict[str, Any]:
    events = load_events(analysis_root)
    dated = [event for event in events if event.month]
    library = [event for event in events if event.source == "audible-library"]
    purchases = [event for event in events if event.source == "audible-purchase-history"]
    listens = [event for event in events if event.source == "audible-listen-history"]
    unique_keys = {event_id(event.author, event.title, event.asin) for event in events}
    purchased_keys = {event_id(event.author, event.title, event.asin) for event in purchases}
    library_keys = {event_id(event.author, event.title, event.asin) for event in library}
    listen_keys = {event_id(event.author, event.title, event.asin) for event in listens}
    effective = effective_listening_events(events)
    approx = [event for event in effective if event.event_kind == "purchase-as-listen-approx"]
    monthly = monthly_summary(dated)
    effective_monthly = monthly_summary(effective)
    return {
        "schema_version": "audible-history-spectrum/v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_roots": {
            "analysis_root": str(analysis_root),
            "playwright_capture": str(analysis_root / "input" / "audible" / "playwright"),
        },
        "capture_shape": {
            "library_rows": len(library),
            "purchase_rows": len(purchases),
            "visible_listen_history_rows": len(listens),
            "effective_listening_rows": len(effective),
            "direct_visible_listen_rows": len(listens),
            "purchase_approx_listen_rows": len(approx),
            "unique_titles_or_asins": len(unique_keys),
            "library_matched_to_purchase_rows": len(library_keys & purchased_keys),
            "visible_listens_matched_to_purchase_rows": len(listen_keys & purchased_keys),
            "purchase_rows_replaced_by_direct_listens": len(listen_keys & purchased_keys),
            "visible_listen_history_first": min((row.date for row in listens if row.date), default=None),
            "visible_listen_history_last": max((row.date for row in listens if row.date), default=None),
            "effective_listening_first": min((row.date for row in effective if row.date), default=None),
            "effective_listening_last": max((row.date for row in effective if row.date), default=None),
            "purchase_history_first": min((row.date for row in purchases if row.date), default=None),
            "purchase_history_last": max((row.date for row in purchases if row.date), default=None),
            "publication_note": "Audible web capture gives complete captured library and 2016-2026 purchase rows plus the currently visible web listen-history rows. The effective listening trace uses direct visible listen rows where present and uses purchase date as an approximate field-entry/listening date for purchased works not present in visible listen history.",
        },
        "source_counts": dict(Counter(event.source for event in events).most_common()),
        "event_kind_counts": dict(Counter(event.event_kind for event in events).most_common()),
        "effective_listening_event_kind_counts": dict(Counter(event.event_kind for event in effective).most_common()),
        "top_authors": top(Counter(event.author for event in events if event.author != "unknown"), 30),
        "top_series": top(Counter(event.series for event in events), 30),
        "top_titles": top(Counter((event.title, event.author) for event in events), 40),
        "monthly": monthly,
        "effective_listening_monthly": effective_monthly,
        "author_waves": record_waves(events, "author"),
        "series_waves": record_waves(events, "series"),
        "title_waves": record_waves(events, "title", limit=120),
        "effective_listening_author_waves": record_waves(effective, "author"),
        "effective_listening_series_waves": record_waves(effective, "series"),
        "effective_listening_title_waves": record_waves(effective, "title", limit=160),
        "effective_listening_events": [asdict(event) for event in effective],
        "events": [asdict(event) for event in events],
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    capture = payload["capture_shape"]
    lines = [
        "# Audible History Spectrum",
        "",
        "This is the Audible-specific spectrum built from every local Audible source body currently captured: library, purchase history, and visible web listen history.",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        "## Capture Shape",
        "",
        f"- Library holdings: `{capture['library_rows']}` rows",
        f"- Purchase history: `{capture['purchase_rows']}` rows, `{capture['purchase_history_first']}` to `{capture['purchase_history_last']}`",
        f"- Visible web listen history: `{capture['visible_listen_history_rows']}` rows, `{capture['visible_listen_history_first']}` to `{capture['visible_listen_history_last']}`",
        f"- Effective listening trace: `{capture['effective_listening_rows']}` rows, `{capture['effective_listening_first']}` to `{capture['effective_listening_last']}`",
        f"- Purchase rows used as approximate listens: `{capture['purchase_approx_listen_rows']}`",
        f"- Unique titles/ASINs across Audible captures: `{capture['unique_titles_or_asins']}`",
        f"- Library rows matched to purchase rows: `{capture['library_matched_to_purchase_rows']}`",
        f"- Visible listen rows matched to purchase rows: `{capture['visible_listens_matched_to_purchase_rows']}`",
        "",
        capture["publication_note"],
        "",
        "## Source Counts",
        "",
    ]
    for source, count in payload["source_counts"].items():
        lines.append(f"- `{source}`: {count}")
    lines.extend(["", "## Effective Listening Evidence", ""])
    for kind, count in payload["effective_listening_event_kind_counts"].items():
        lines.append(f"- `{kind}`: {count}")
    lines.extend(["", "## Top Authors", ""])
    for row in payload["top_authors"][:20]:
        lines.append(f"- {row['value']}: {row['count']}")
    lines.extend(["", "## Top Series / Rooms", ""])
    for row in payload["top_series"][:20]:
        lines.append(f"- {row['value']}: {row['count']}")
    lines.extend(["", "## Strongest Approximate Listening Months", ""])
    for month, row in sorted(payload["effective_listening_monthly"].items(), key=lambda item: (-item[1]["events"], item[0]))[:24]:
        authors = ", ".join(item["value"] for item in row["top_authors"][:4])
        series = ", ".join(item["value"] for item in row["top_series"][:4])
        lines.append(f"- `{month}`: {row['events']} events; authors: {authors}; rooms: {series}")
    lines.extend(["", "## Query Shapes", ""])
    lines.append("- Primary Audible listening influence during a month: load `trace/audible_history_spectrum.json` then read `effective_listening_monthly[YYYY-MM]`.")
    lines.append("- Author listening wave: search `effective_listening_author_waves[]` by `value` and read its `wave`.")
    lines.append("- Series listening wave: search `effective_listening_series_waves[]` by `value` and read its `wave`.")
    lines.append("- Work listening wave: search `effective_listening_title_waves[]` by title and read source counts plus month wave.")
    lines.append("- Raw source-body audit: use `events`, `monthly`, `author_waves`, `series_waves`, and `title_waves`.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Audible history spectrum artifacts.")
    parser.add_argument("--field-dir", type=Path, default=Path("docs/field/urs"))
    parser.add_argument("--analysis-root", type=Path, default=ANALYSIS_ROOT)
    args = parser.parse_args()
    payload = build(args.analysis_root)
    write_json(args.field_dir / "trace" / "audible_history_spectrum.json", payload)
    write_markdown(args.field_dir / "output" / "audible_history_spectrum.md", payload)
    print(f"audible_events={len(payload['events'])}")
    print(f"effective_listening_events={len(payload['effective_listening_events'])}")
    print(f"purchase_approx_listen_rows={payload['capture_shape']['purchase_approx_listen_rows']}")
    print(f"unique_titles_or_asins={payload['capture_shape']['unique_titles_or_asins']}")
    print(args.field_dir / "output" / "audible_history_spectrum.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
