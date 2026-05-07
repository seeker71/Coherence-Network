#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path


ROOT = Path("/Users/ursmuff/CoherenceFieldAnalysis")


SERIES_RULES = [
    ("Frontiers Saga", ["Ryk Brown"], []),
    ("Spellmonger Universe", ["Terry Mancour"], []),
    ("Sword of Truth / Goodkind Universe", ["Terry Goodkind"], []),
    ("Kingkiller Chronicle", ["Patrick Rothfuss"], []),
    ("Daemon", ["Daniel Suarez"], ["Daemon", "Freedom (TM)"]),
    ("Ringworld", ["Larry Niven"], ["Ringworld"]),
    ("The Expanse", ["James S. A. Corey"], []),
    ("Viridian Gate Archives", ["James Hunter"], ["Viridian Gate"]),
    ("First Law World", ["Joe Abercrombie"], []),
    ("Peter F. Hamilton Systems Fiction", ["Peter F. Hamilton"], []),
    ("Arcane Ascension", ["Andrew Rowe"], ["Sufficiently Advanced Magic", "On The Shoulders of Titans", "The Torch That Ignites the Stars", "The Silence of Unworthy Gods"]),
    ("Weapons and Wielders", ["Andrew Rowe"], ["Six Sacred Swords", "Diamantine", "Soulbrand"]),
    ("War of Broken Mirrors", ["Andrew Rowe"], ["Forging Divinity", "Stealing Sorcery", "Defying Destiny"]),
    ("The Lost Edge", ["Andrew Rowe"], ["Edge of the Woods", "Edge of the Dream"]),
    ("King's Dark Tidings", ["Kel Kade"], ["Free the Darkness", "Kingdoms and Chaos", "Legends of Ahn", "Reign of Madness"]),
    ("Shroud of Prophecy", ["Kel Kade"], ["Fate of the Fallen", "Destiny of the Dead", "Dragons and Demons", "Mage of No Renown"]),
    ("Kingsbridge", ["Ken Follett"], ["The Pillars of the Earth", "World Without End", "A Column of Fire", "The Armor of Light"]),
    ("A Song of Ice and Fire", ["George R. R. Martin"], ["A Game of Thrones", "A Clash of Kings", "A Storm of Swords", "A Feast for Crows", "A Dance with Dragons"]),
    ("Sapiens / Human Systems", ["Yuval Noah Harari"], ["Sapiens", "Homo Deus", "21 Lessons"]),
    ("Radical Compassion / Acceptance", ["Tara Brach"], ["Radical Acceptance", "Radical Compassion"]),
    ("Power of Now / Presence", ["Eckhart Tolle"], ["The Power of Now", "A New Earth", "The Next Step in Human Evolution"]),
    ("Conversations with God", ["Neale Donald Walsch"], ["Conversations with God", "The God Solution"]),
]


@dataclass
class AudibleItem:
    title: str
    author: str
    source: str
    date: str | None
    asin: str | None
    url: str | None
    native_series: str | None = None
    inferred_series: str = "Standalone / Unclustered"
    inference: str = "none"


def clean(value: object) -> str:
    return str(value or "").strip()


def split_library_title(title: str, author: str) -> tuple[str, str]:
    if author:
        return title, author
    if " By " in title:
        possible_title, possible_author = title.rsplit(" By ", 1)
        return possible_title.strip(), possible_author.strip()
    return title, author


def infer_series(title: str, author: str, native_series: str | None) -> tuple[str, str]:
    if native_series:
        return native_series, "native-series-field"
    title_lower = title.lower()
    author_lower = author.lower()
    for series, authors, title_needles in SERIES_RULES:
        author_match = any(a.lower() == author_lower for a in authors)
        title_match = any(needle.lower() in title_lower for needle in title_needles)
        if title_needles:
            if author_match and title_match:
                return series, "author-and-title-rule"
        elif author_match:
            return series, "author-rule"
    return "Standalone / Unclustered", "none"


def load_items(root: Path) -> list[AudibleItem]:
    out: list[AudibleItem] = []
    base = root / "input" / "audible"
    for path in base.rglob("*.json"):
        if {"pages", "purchase-years"} & set(path.parts) or path.name.endswith("auth-state.json"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("Books") or data.get("books") or []
        for row in rows:
            title = clean(row.get("title") or row.get("Title"))
            author = clean(row.get("author") or row.get("Author") or row.get("Authors"))
            title, author = split_library_title(title, author)
            if not title:
                continue
            native_series = clean(row.get("series") or row.get("Series")) or None
            inferred_series, inference = infer_series(title, author, native_series)
            out.append(
                AudibleItem(
                    title=title,
                    author=author or "unknown",
                    source=clean(row.get("source")) or path.stem,
                    date=clean(row.get("listened_date") or row.get("purchased_date") or row.get("date_added")) or None,
                    asin=clean(row.get("asin") or row.get("ASIN")) or None,
                    url=clean(row.get("product_url") or row.get("url")) or None,
                    native_series=native_series,
                    inferred_series=inferred_series,
                    inference=inference,
                )
            )
    return out


def dedupe(items: list[AudibleItem]) -> list[AudibleItem]:
    by_key: dict[tuple[str, str], AudibleItem] = {}
    for item in items:
        key = (item.asin or "", re.sub(r"\W+", "", f"{item.author}:{item.title}".lower()))
        existing = by_key.get(key)
        if not existing:
            by_key[key] = item
            continue
        if existing.source == "audible-library" and item.source != "audible-library":
            by_key[key] = item
    return list(by_key.values())


def write_outputs(root: Path, items: list[AudibleItem], unique: list[AudibleItem]) -> None:
    out = root / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "audible_series_events.jsonl").write_text(
        "\n".join(json.dumps(asdict(item), ensure_ascii=False) for item in items) + "\n",
        encoding="utf-8",
    )
    by_series: dict[str, list[AudibleItem]] = defaultdict(list)
    for item in unique:
        by_series[item.inferred_series].append(item)

    series_summary = []
    for series, rows in sorted(by_series.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        authors = Counter(item.author for item in rows)
        sources = Counter(item.source for item in rows)
        series_summary.append(
            {
                "series": series,
                "unique_titles": len(rows),
                "authors": dict(authors.most_common()),
                "sources": dict(sources.most_common()),
                "titles": sorted({item.title for item in rows}),
                "inference_levels": dict(Counter(item.inference for item in rows)),
            }
        )
    summary = {
        "raw_audible_rows": len(items),
        "unique_audible_titles": len(unique),
        "series_count": len(series_summary),
        "series_clusters": series_summary,
    }
    (out / "audible_series_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Audible Series Clusters",
        "",
        f"Raw Audible rows: {len(items)}",
        f"Unique Audible titles: {len(unique)}",
        "",
        "Series labels are derived from Audible title/author evidence. `native-series-field` means Audible supplied it; `author-rule` and `author-and-title-rule` are explicit local inference rules.",
        "",
    ]
    for cluster in series_summary:
        if cluster["series"] == "Standalone / Unclustered":
            continue
        lines.extend(
            [
                f"## {cluster['series']}",
                "",
                f"- Unique titles: {cluster['unique_titles']}",
                f"- Authors: {', '.join(cluster['authors'])}",
                f"- Evidence: {cluster['inference_levels']}",
                "",
            ]
        )
        for title in cluster["titles"][:80]:
            lines.append(f"- {title}")
        lines.append("")
    standalone = next((c for c in series_summary if c["series"] == "Standalone / Unclustered"), None)
    if standalone:
        lines.extend(["## Standalone / Unclustered", "", f"- Unique titles: {standalone['unique_titles']}", ""])
        for title in standalone["titles"][:120]:
            lines.append(f"- {title}")
    (out / "audible_series_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    items = load_items(ROOT)
    unique = dedupe(items)
    write_outputs(ROOT, items, unique)
    print(f"raw_audible_rows={len(items)}")
    print(f"unique_audible_titles={len(unique)}")
    print(ROOT / "output" / "audible_series_report.md")


if __name__ == "__main__":
    main()
