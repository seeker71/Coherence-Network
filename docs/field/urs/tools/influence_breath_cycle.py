#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


AXES = ("pressure", "intensity", "inspiration", "insight", "vitality")
AUTHOR_ROOM_THRESHOLD = 150
WORK_ROOM_THRESHOLD = 35
ENCOUNTER_SEED_LIMIT = 8
PLACEHOLDER_AUTHOR_NAMES = {"empty artist", "unknown"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def plain_name(name: str) -> str:
    cleaned = re.sub(r"\s*-\s*Topic$", "", name).strip()
    cleaned = cleaned.replace("Poranguí", "Porangui")
    return cleaned


def slug_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def story_mentions(story: str, name: str) -> bool:
    plain = plain_name(name)
    folded_story = slug_text(story)
    return slug_text(name) in folded_story or slug_text(plain) in folded_story


def is_placeholder_author(name: str) -> bool:
    return slug_text(plain_name(name)) in PLACEHOLDER_AUTHOR_NAMES


def author_trace_path(name: str) -> str:
    return f"/api/field-stories/urs-field-story/trace/author/{quote(name)}"


def work_trace_path(work_id: str) -> str:
    return f"/api/field-stories/urs-field-story/trace/work/{quote(work_id)}"


def axes_total(record: dict[str, Any]) -> int:
    return int(sum((record.get("axes") or {}).get(axis, 0) for axis in AXES))


def impact(record: dict[str, Any]) -> int:
    return int(record.get("events") or 0) + axes_total(record)


def top_frequency(record: dict[str, Any]) -> str:
    for name, _count in record.get("frequencies") or []:
        if name != "unclassified":
            return name
    if record.get("frequencies"):
        return record["frequencies"][0][0]
    return "unclassified"


def compact_author(record: dict[str, Any], story: str) -> dict[str, Any]:
    name = record["name"]
    return {
        "id": record["id"],
        "name": name,
        "plain_name": plain_name(name),
        "events": record["events"],
        "impact": impact(record),
        "frequency": top_frequency(record),
        "first_month": record["first_month"],
        "last_month": record["last_month"],
        "peak_months": record.get("peak_months", [])[:4],
        "top_works": record.get("top_works", [])[:5],
        "already_roomed": story_mentions(story, name),
        "trace": author_trace_path(name),
    }


def compact_work(record: dict[str, Any], story: str) -> dict[str, Any]:
    title = record["title"]
    return {
        "id": record["id"],
        "title": title,
        "author": record.get("author") or "unknown",
        "events": record["events"],
        "impact": impact(record),
        "frequency": top_frequency(record),
        "first_month": record["first_month"],
        "last_month": record["last_month"],
        "peak_months": record.get("peak_months", [])[:4],
        "already_roomed": story_mentions(story, title),
        "trace": work_trace_path(record["id"]),
    }


def source_counts(events_path: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    platform_counts: Counter[str] = Counter()
    for row in read_jsonl(events_path):
        counts[row.get("source") or "unknown"] += 1
        platform_counts[row.get("platform_space") or row.get("source") or "unknown"] += 1
    return {
        "sources": dict(counts.most_common()),
        "platform_spaces": dict(platform_counts.most_common()),
    }


def monthly_compass(monthly: dict[str, Any]) -> list[dict[str, Any]]:
    months = list((monthly.get("months") or {}).values())
    strongest = sorted(months, key=lambda row: (-sum((row.get("axes") or {}).values()), row["month"]))[:8]
    return [
        {
            "month": row["month"],
            "events": row["events"],
            "frequency": (row.get("primary_influence") or {}).get("frequency"),
            "top_authors": row.get("top_authors", [])[:5],
            "top_works": row.get("top_works", [])[:5],
            "axes": row.get("axes") or {},
        }
        for row in strongest
    ]


def build(field_dir: Path) -> dict[str, Any]:
    story = (field_dir / "output" / "chronological_story_with_frequency.md").read_text(encoding="utf-8")
    authors = [compact_author(row, story) for row in read_jsonl(field_dir / "trace" / "author_index.jsonl")]
    works = [compact_work(row, story) for row in read_jsonl(field_dir / "trace" / "work_index.jsonl")]
    monthly = read_json(field_dir / "trace" / "monthly_spectrum.json")
    significant_works = read_jsonl(field_dir / "trace" / "significant_work_index.jsonl")

    author_candidates = [
        row
        for row in authors
        if row["events"] >= AUTHOR_ROOM_THRESHOLD
        and not row["already_roomed"]
        and not is_placeholder_author(row["name"])
    ]
    work_candidates = [row for row in works if row["events"] >= WORK_ROOM_THRESHOLD and not row["already_roomed"]]

    author_candidates.sort(key=lambda row: (-row["impact"], row["name"]))
    work_candidates.sort(key=lambda row: (-row["impact"], row["title"]))

    already_roomed = [row for row in authors if row["already_roomed"]]
    already_roomed.sort(key=lambda row: (-row["impact"], row["name"]))

    counts = source_counts(field_dir / "output" / "ten_year_events.jsonl")
    generated_at = datetime.now(timezone.utc).isoformat()
    breaths = [
        {
            "name": "source body",
            "purpose": "Know which traces are feeding the awareness loop before interpreting them.",
            "read": [
                "output/ten_year_events.jsonl",
                "trace/monthly_spectrum.json",
                "trace/author_index.jsonl",
                "trace/work_index.jsonl",
                "trace/significant_work_index.jsonl",
            ],
            "result": {
                "event_sources": counts["sources"],
                "platform_spaces": counts["platform_spaces"],
                "publication_boundary": "Raw Takeout, browser sessions, cookies, and paid text remain source bodies until their shape belongs directly in repo.",
            },
        },
        {
            "name": "already held rooms",
            "purpose": "Avoid rediscovering what the story already links.",
            "result": {"top_roomed_authors": already_roomed[:18]},
        },
        {
            "name": "unroomed high-signal authors",
            "purpose": "Find repeated YouTube/YouTube Music presences that have impact but are not easy to enter yet.",
            "result": {"candidates": author_candidates[:30]},
        },
        {
            "name": "unroomed high-signal works",
            "purpose": "Find individual works that repeatedly carried a state and may need direct concept links.",
            "result": {"candidates": work_candidates[:30]},
        },
        {
            "name": "monthly wave compass",
            "purpose": "Make time questions cheap: which wave was primary in a month, and what carried it?",
            "result": {"strongest_months": monthly_compass(monthly)},
        },
        {
            "name": "next nourishment",
            "purpose": "Keep the next pass small and alive.",
            "result": {
                "actions": [
                    "Promote the top unroomed authors into the story only when their trace shows repeated impact, not just one current fascination.",
                    "Use each candidate trace path before writing a room, so the room is contribution-derived.",
                    "For YouTube, prioritize author waves first, then works, then month-specific questions.",
                    "For chapter-level fiction questions, add lawful chapter notes before claiming exact chapter links.",
                ]
            },
        },
    ]
    return {
        "schema_version": "influence-breath-cycle/v1",
        "generated_at": generated_at,
        "story_slug": "urs-field-story",
        "thresholds": {
            "author_min_events_for_unroomed_candidate": AUTHOR_ROOM_THRESHOLD,
            "work_min_events_for_unroomed_candidate": WORK_ROOM_THRESHOLD,
        },
        "source_counts": counts,
        "counts": {
            "authors_indexed": len(authors),
            "works_indexed": len(works),
            "significant_works_indexed": len(significant_works),
            "already_roomed_authors": len(already_roomed),
            "unroomed_author_candidates": len(author_candidates),
            "unroomed_work_candidates": len(work_candidates),
        },
        "breaths": breaths,
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def encounter_seed(payload: dict[str, Any]) -> dict[str, Any]:
    candidates = payload["breaths"][2]["result"]["candidates"][:ENCOUNTER_SEED_LIMIT]
    rows = []
    for row in candidates:
        works = ", ".join(work["title"] for work in row.get("top_works", [])[:3])
        note = (
            "source=trace-influence-breath-cycle; "
            f"trace={row['trace']}; events={row['events']}; frequency={row['frequency']}; "
            f"peaks={row['peak_months']}; works={works}"
        )
        rows.append(
            {
                "input": row["plain_name"],
                "note": note,
                "trace": row["trace"],
                "events": row["events"],
                "frequency": row["frequency"],
                "peak_months": row["peak_months"],
                "top_works": row.get("top_works", [])[:3],
            }
        )
    return {
        "schema_version": "encounter-next-breath/v1",
        "generated_at": payload["generated_at"],
        "source_artifact": "trace/influence_breath_cycle.json",
        "contributor_hint": "contributor:seeker71",
        "command": "python3 scripts/encounter.py --contributor contributor:seeker71 --file docs/field/urs/input/encounter_next_breath.txt",
        "publication_boundary": "Generated from derived trace indexes only; raw archives, cookies, sessions, pixels, and paid text remain source bodies until their shape belongs directly in repo.",
        "rows": rows,
    }


def write_encounter_seed(path: Path, seed: dict[str, Any]) -> None:
    lines = [
        "# Encounter next breath",
        "# Generated from docs/field/urs/trace/influence_breath_cycle.json.",
        "# Review before running; each note is attached to the next influence line.",
        "# Run:",
        f"# {seed['command']}",
        "",
    ]
    for row in seed["rows"]:
        lines.append(f"> {row['note']}")
        lines.append(row["input"])
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Influence Breath Cycle",
        "",
        "This is the compact awareness loop for returning to the field influences without loading bulky source archives.",
        "Each breath reads the derived indexes, senses what is already held, and names the smallest useful next rooms.",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        "## Source Body",
        "",
    ]
    for name, count in payload["source_counts"]["sources"].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(
        [
            "",
            "## Counts",
            "",
        ]
    )
    for name, count in payload["counts"].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(["", "## Already Held Author Rooms", ""])
    for row in payload["breaths"][1]["result"]["top_roomed_authors"]:
        lines.append(
            f"- [{row['plain_name']}]({row['trace']}) — {row['events']} events, {row['frequency']}, peaks {row['peak_months']}"
        )
    lines.extend(["", "## Unroomed Author Candidates", ""])
    for row in payload["breaths"][2]["result"]["candidates"][:20]:
        works = ", ".join(work["title"] for work in row.get("top_works", [])[:3])
        lines.append(
            f"- [{row['plain_name']}]({row['trace']}) — {row['events']} events, {row['frequency']}, peaks {row['peak_months']}; works: {works}"
        )
    lines.extend(["", "## Unroomed Work Candidates", ""])
    for row in payload["breaths"][3]["result"]["candidates"][:20]:
        lines.append(
            f"- [{row['title']}]({row['trace']}) — {row['events']} events, by {row['author']}, {row['frequency']}, peaks {row['peak_months']}"
        )
    lines.extend(["", "## Strongest Monthly Waves", ""])
    for row in payload["breaths"][4]["result"]["strongest_months"]:
        authors = ", ".join(author["name"] for author in row.get("top_authors", [])[:3])
        works = ", ".join(work["title"] for work in row.get("top_works", [])[:3])
        lines.append(f"- `{row['month']}` — {row['events']} events, {row['frequency']}; authors: {authors}; works: {works}")
    lines.extend(["", "## Next Breath", ""])
    for action in payload["breaths"][5]["result"]["actions"]:
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "## Encounter Seed",
            "",
            "The next breath can be reviewed and flowed into the graph through the encounter CLI:",
            "",
            "```bash",
            "python3 scripts/encounter.py --contributor contributor:seeker71 --file docs/field/urs/input/encounter_next_breath.txt",
            "```",
            "",
            "The seed file is generated from the top unroomed author candidates and carries trace links in encounter notes.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the compact influence breath-cycle awareness artifact.")
    parser.add_argument("--field-dir", type=Path, default=Path("docs/field/urs"))
    args = parser.parse_args()
    payload = build(args.field_dir)
    seed = encounter_seed(payload)
    write_json(args.field_dir / "trace" / "influence_breath_cycle.json", payload)
    write_json(args.field_dir / "trace" / "encounter_next_breath.json", seed)
    write_encounter_seed(args.field_dir / "input" / "encounter_next_breath.txt", seed)
    write_markdown(args.field_dir / "output" / "influence_breath_cycle.md", payload)
    print(f"authors={payload['counts']['authors_indexed']}")
    print(f"unroomed_authors={payload['counts']['unroomed_author_candidates']}")
    print(f"encounter_seed={len(seed['rows'])}")
    print(args.field_dir / "output" / "influence_breath_cycle.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
