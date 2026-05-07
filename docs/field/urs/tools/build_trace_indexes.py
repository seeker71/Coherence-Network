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

SIGNIFICANT_WORK_RULES: dict[str, dict[str, Any]] = {
    "Spellmonger": {
        "canonical_title": "Spellmonger Universe",
        "authors": ["Terry Mancour"],
        "series_aliases": ["Spellmonger", "Spellmonger Universe"],
        "concepts": {
            "lc-network": ["mageland as living network", "village-to-duchy coordination", "distributed mutual defense"],
            "lc-field-sensing": ["wizardly sensing", "reading pressure in the local field", "timing before force"],
            "lc-instruments": ["magic as tool system", "trained practice before power"],
            "lc-coherence-over-control": ["institution-building without brittle centralization"],
        },
        "chapter_probe_terms": {
            "lc-network": ["Sevendor", "mageland", "vassal", "duchy", "supply", "alliance", "market"],
            "lc-field-sensing": ["scrying", "ward", "thaumaturgy", "pressure", "omen", "timing"],
            "lc-instruments": ["spell", "stone", "craft", "apprentice", "adept", "training"],
            "lc-coherence-over-control": ["council", "charter", "law", "oath", "defense", "responsibility"],
        },
    },
    "Daemon": {
        "canonical_title": "Daemon",
        "authors": ["Daniel Suarez"],
        "series_aliases": ["Daemon"],
        "concepts": {
            "lc-agent-memory": ["software agency persists beyond one operator", "instructions become runtime"],
            "lc-network": ["distributed coordination", "network power", "resilient cells"],
            "lc-open-design": ["systems that can be inspected and remixed"],
            "lc-economy": ["new incentives inside automated infrastructure"],
        },
        "chapter_probe_terms": {
            "lc-agent-memory": ["daemon", "process", "agent", "instruction", "persistence"],
            "lc-network": ["darknet", "node", "cell", "network", "coordination"],
            "lc-open-design": ["source", "protocol", "interface", "permission"],
            "lc-economy": ["currency", "reputation", "market", "incentive"],
        },
    },
    "Ringworld": {
        "canonical_title": "Ringworld",
        "authors": ["Larry Niven"],
        "series_aliases": ["Ringworld"],
        "concepts": {
            "lc-space": ["world-scale habitat", "room for civilizations to unfold"],
            "lc-open-design": ["megastructure as inspectable design problem"],
            "lc-field-edge": ["edge of known world", "meeting unknown design constraints"],
            "lc-discovery": ["exploration as humility before scale"],
        },
        "chapter_probe_terms": {
            "lc-space": ["ringworld", "arc", "habitat", "surface", "sun"],
            "lc-open-design": ["engineer", "structure", "stability", "design", "repair"],
            "lc-field-edge": ["rim", "unknown", "edge", "crash", "risk"],
            "lc-discovery": ["explore", "map", "artifact", "mystery"],
        },
    },
    "The Expanse": {
        "canonical_title": "The Expanse",
        "authors": ["James S. A. Corey"],
        "series_aliases": ["The Expanse"],
        "concepts": {
            "lc-network": ["interdependent nodes under distance and delay"],
            "lc-boundaries-as-loving-truth": ["factions need boundaries before peace"],
            "lc-circulation": ["water, air, ships, and trust as circulation systems"],
            "lc-coherence-over-control": ["survival through alignment, not domination"],
        },
        "chapter_probe_terms": {
            "lc-network": ["belt", "mars", "earth", "ship", "station", "relay"],
            "lc-boundaries-as-loving-truth": ["truce", "border", "faction", "opa", "truth"],
            "lc-circulation": ["air", "water", "supply", "drive", "transit"],
            "lc-coherence-over-control": ["crew", "consensus", "command", "trust", "war"],
        },
    },
    "Kingkiller Chronicle": {
        "canonical_title": "Kingkiller Chronicle",
        "authors": ["Patrick Rothfuss"],
        "series_aliases": ["Kingkiller Chronicle"],
        "concepts": {
            "lc-transmission": ["story as carrier wave", "teaching through song and naming"],
            "lc-instruments": ["music and craft as precise instruments"],
            "lc-beauty": ["beauty as signal, not decoration"],
            "lc-sensing": ["listening for names beneath ordinary language"],
        },
        "chapter_probe_terms": {
            "lc-transmission": ["story", "song", "name", "telling", "lesson"],
            "lc-instruments": ["lute", "music", "craft", "practice", "arcanum"],
            "lc-beauty": ["beauty", "silence", "song", "moon"],
            "lc-sensing": ["name", "wind", "listen", "sleeping mind"],
        },
    },
    "Sword of Truth": {
        "canonical_title": "Sword of Truth / Goodkind Universe",
        "authors": ["Terry Goodkind"],
        "series_aliases": ["Sword of Truth", "Sword of Truth / Goodkind Universe"],
        "concepts": {
            "lc-boundaries-as-loving-truth": ["truth spoken as boundary"],
            "lc-freedom-as-recognition": ["freedom requires seeing what is real"],
            "lc-presence-over-protection": ["protection becomes harmful when it hides truth"],
            "lc-coherence-over-control": ["moral choice over coercive power"],
        },
        "chapter_probe_terms": {
            "lc-boundaries-as-loving-truth": ["truth", "confessor", "boundary", "choice"],
            "lc-freedom-as-recognition": ["freedom", "rule", "recognize", "will"],
            "lc-presence-over-protection": ["protect", "fear", "love", "honesty"],
            "lc-coherence-over-control": ["power", "control", "responsibility", "law"],
        },
    },
    "The First Law Trilogy": {
        "canonical_title": "First Law World",
        "authors": ["Joe Abercrombie"],
        "series_aliases": ["The First Law Trilogy", "First Law World"],
        "concepts": {
            "lc-trauma-as-identity-anchor": ["old wounds steering identity"],
            "lc-old-signal-echo": ["repeating old power patterns"],
            "lc-coherence-over-control": ["control without coherence decays into violence"],
            "lc-boundaries-as-loving-truth": ["truth without romanticizing shadow"],
        },
        "chapter_probe_terms": {
            "lc-trauma-as-identity-anchor": ["scar", "pain", "past", "fear", "identity"],
            "lc-old-signal-echo": ["revenge", "habit", "old", "return"],
            "lc-coherence-over-control": ["power", "king", "war", "control"],
            "lc-boundaries-as-loving-truth": ["truth", "mercy", "line", "choice"],
        },
    },
    "Peter F. Hamilton Systems Fiction": {
        "canonical_title": "Peter F. Hamilton Systems Fiction",
        "authors": ["Peter F. Hamilton"],
        "series_aliases": ["Most series", "Peter F. Hamilton Systems Fiction"],
        "concepts": {
            "lc-network": ["large-scale civilization as living network"],
            "lc-economy": ["post-scarcity and resource circulation"],
            "lc-phase-transitions": ["civilization crossing thresholds"],
            "lc-circulation": ["transport, attention, and abundance flows"],
        },
        "chapter_probe_terms": {
            "lc-network": ["commonwealth", "void", "network", "planet", "connection"],
            "lc-economy": ["scarcity", "abundance", "wealth", "resource"],
            "lc-phase-transitions": ["evolution", "threshold", "salvation", "transcend"],
            "lc-circulation": ["wormhole", "transit", "flow", "supply"],
        },
    },
    "Frontiers Saga": {
        "canonical_title": "Frontiers Saga",
        "authors": ["Ryk Brown"],
        "series_aliases": ["Frontiers Saga"],
        "concepts": {
            "lc-network": ["fleet and worlds as distributed organism"],
            "lc-circulation": ["movement of people, ships, resources, and repair"],
            "lc-boundaries-as-loving-truth": ["defense lines under pressure"],
            "lc-field-edge": ["frontier pressure as teacher"],
        },
        "chapter_probe_terms": {
            "lc-network": ["fleet", "alliance", "world", "command", "node"],
            "lc-circulation": ["ship", "supply", "repair", "jump", "route"],
            "lc-boundaries-as-loving-truth": ["defense", "line", "enemy", "protect"],
            "lc-field-edge": ["frontier", "unknown", "risk", "edge"],
        },
    },
    "The Viridian Gate Archives": {
        "canonical_title": "The Viridian Gate Archives",
        "authors": ["James Hunter"],
        "series_aliases": ["The Viridian Gate Archives", "Viridian Gate Online"],
        "concepts": {
            "lc-play": ["game systems as practice space"],
            "lc-identity-dissolution": ["identity moving through simulated worlds"],
            "lc-network": ["guilds, roles, and worlds as coordination layer"],
            "lc-open-design": ["rulesets as inspectable reality engines"],
        },
        "chapter_probe_terms": {
            "lc-play": ["game", "quest", "level", "skill", "class"],
            "lc-identity-dissolution": ["avatar", "body", "world", "identity"],
            "lc-network": ["guild", "party", "alliance", "city"],
            "lc-open-design": ["system", "rules", "interface", "mechanic"],
        },
    },
    "Momo": {
        "canonical_title": "Momo",
        "authors": ["Michael Ende"],
        "series_aliases": ["Momo"],
        "concepts": {
            "lc-rhythm": ["time restored to human rhythm"],
            "lc-presence-over-protection": ["attention as protection against extraction"],
            "lc-rest": ["non-productive time as life"],
            "lc-sensing": ["listening as transformative intelligence"],
        },
        "chapter_probe_terms": {
            "lc-rhythm": ["time", "hour", "rhythm", "slow"],
            "lc-presence-over-protection": ["listen", "attention", "friend", "gray"],
            "lc-rest": ["pause", "silence", "play", "nothing"],
            "lc-sensing": ["listen", "hear", "child", "heart"],
        },
    },
    "Die unendliche Geschichte": {
        "canonical_title": "Die unendliche Geschichte",
        "authors": ["Michael Ende"],
        "series_aliases": ["Die unendliche Geschichte", "The Neverending Story"],
        "concepts": {
            "lc-transmission": ["story changes the world reading it"],
            "lc-identity-dissolution": ["self remade by imagination"],
            "lc-discovery": ["world-renewal through inner travel"],
            "lc-inner-travel": ["journey inward as real terrain"],
        },
        "chapter_probe_terms": {
            "lc-transmission": ["story", "book", "name", "voice"],
            "lc-identity-dissolution": ["wish", "memory", "self", "identity"],
            "lc-discovery": ["fantastica", "journey", "world", "renew"],
            "lc-inner-travel": ["inside", "path", "desire", "return"],
        },
    },
}


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


def normalize_series(value: str) -> str:
    lowered = value.strip().lower()
    for key, rule in SIGNIFICANT_WORK_RULES.items():
        aliases = [key, rule["canonical_title"], *(rule.get("series_aliases") or [])]
        if any(lowered == alias.lower() for alias in aliases):
            return key
    return value.strip()


def concise_children(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_title: dict[str, dict[str, Any]] = {}
    for row in rows:
        title = row.get("title") or row.get("series") or "unknown"
        entry = by_title.setdefault(
            title,
            {
                "title": title,
                "author": row.get("author") or "unknown",
                "sources": set(),
                "dates": set(),
                "asins": set(),
                "urls": set(),
            },
        )
        for field, target in (("source", "sources"), ("date", "dates"), ("asin", "asins"), ("url", "urls")):
            if row.get(field):
                entry[target].add(row[field])
    children: list[dict[str, Any]] = []
    for entry in sorted(by_title.values(), key=lambda item: item["title"]):
        children.append(
            {
                "title": entry["title"],
                "author": entry["author"],
                "sources": sorted(entry["sources"]),
                "dates": sorted(entry["dates"]),
                "asins": sorted(entry["asins"]),
                "urls": sorted(entry["urls"])[:2],
            }
        )
    return children


def significant_work_record(series_key: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    rule = SIGNIFICANT_WORK_RULES.get(series_key, {})
    title = rule.get("canonical_title") or series_key
    authors = rule.get("authors") or sorted({row.get("author") or "unknown" for row in rows})
    manual_rows = [row for row in rows if str(row.get("evidence", "")).startswith("manual")]
    audible_rows = [row for row in rows if row.get("evidence") == "audible-series-event"]
    children = concise_children(audible_rows)
    unique_title_count = len(children) if children else max(1, len({row.get("title") for row in rows if row.get("title")}))
    impact_score = min(100, 35 + 20 * bool(manual_rows) + min(35, unique_title_count * 2) + min(10, len(rows) // 6))
    themes = Counter(theme for row in manual_rows for theme in (row.get("themes") or []))
    concepts = rule.get("concepts") or {}
    concept_links = [
        {
            "concept_id": concept_id,
            "resonance": motifs,
            "chapter_probe_terms": (rule.get("chapter_probe_terms") or {}).get(concept_id, []),
            "source_status": "motif-level-derived-link",
        }
        for concept_id, motifs in sorted(concepts.items())
    ]
    return {
        "id": stable_id("significant-work", title),
        "record_type": "significant-work",
        "title": title,
        "authors": authors,
        "aliases": sorted(set([series_key, title, *(rule.get("series_aliases") or [])])),
        "impact_score": impact_score,
        "impact_basis": {
            "manual_anchor": bool(manual_rows),
            "audible_event_rows": len(audible_rows),
            "unique_child_titles": unique_title_count,
            "manual_themes": top_counter(themes, 12),
        },
        "concept_links": concept_links,
        "children": children,
        "deep_discovery": {
            "current_depth": "title-and-motif-level",
            "chapter_precision": "not-yet-evidence-backed",
            "can_answer_now": "which works and motifs most likely relate to a concept",
            "needs_for_exact_chapters": [
                "table of contents, chapter notes, or legally available chapter text",
                "one note per chapter with book title, chapter number/name, and 1-5 sentence summary",
                "optional listener timestamp notes from Audible or manual recollection",
            ],
            "efficient_workflow": [
                "resolve concept with concept_work_map.json",
                "open only the linked significant-work record from significant_work_index.jsonl",
                "use chapter_probe_terms for that concept against chapter notes/text",
                "append exact hits to chapter_links with evidence source and confidence",
            ],
            "chapter_link_schema": {
                "book": "title",
                "chapter": "number-or-name",
                "concept_id": "lc-*",
                "evidence": "short note, not copyrighted chapter text",
                "confidence": "low|medium|high",
            },
            "chapter_links": [],
        },
    }


def build_significant_work_indexes(field_dir: Path, generated_at: str) -> dict[str, Any]:
    rows = load_manual_significant_work_rows(field_dir) + load_audible_series_rows(field_dir)
    by_series: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        series = normalize_series(row.get("series") or row.get("title") or "")
        if not series:
            continue
        if series in SIGNIFICANT_WORK_RULES or row.get("evidence", "").startswith("manual"):
            by_series[series].append(row)
    records = [
        significant_work_record(series, rows)
        for series, rows in sorted(by_series.items(), key=lambda item: item[0].lower())
        if series in SIGNIFICANT_WORK_RULES
    ]
    concept_map: dict[str, Any] = {
        "schema_version": "field-trace-index/v1",
        "generated_at": generated_at,
        "concepts": {},
    }
    for record in records:
        for link in record["concept_links"]:
            concept = concept_map["concepts"].setdefault(
                link["concept_id"],
                {
                    "concept_id": link["concept_id"],
                    "related_significant_works": [],
                    "query_hint": "Use related work id with selector=significant-work, then run chapter probes only against chapter notes/text.",
                },
            )
            concept["related_significant_works"].append(
                {
                    "id": record["id"],
                    "title": record["title"],
                    "impact_score": record["impact_score"],
                    "resonance": link["resonance"],
                    "chapter_probe_terms": link["chapter_probe_terms"],
                }
            )
    for concept in concept_map["concepts"].values():
        concept["related_significant_works"].sort(key=lambda item: (-item["impact_score"], item["title"]))
    return {
        "significant_works": records,
        "concept_work_map": concept_map,
    }


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


def field_dir_for_source(source_path: Path) -> Path:
    return source_path.parent.parent


def load_manual_significant_work_rows(field_dir: Path) -> list[dict[str, Any]]:
    path = field_dir / "anchors" / "manual_reading_anchors.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for item in data.get("early_childhood_reading", []):
        rows.append(
            {
                "title": item.get("title") or "",
                "author": item.get("author") or "unknown",
                "series": item.get("title") or "",
                "themes": item.get("themes") or [],
                "evidence": "manual-childhood-reading-anchor",
            }
        )
    for item in data.get("later_series", []):
        rows.append(
            {
                "title": item.get("series") or "",
                "author": item.get("author") or "unknown",
                "series": item.get("series") or "",
                "themes": item.get("themes") or [],
                "evidence": "manual-later-series-anchor",
            }
        )
    return [row for row in rows if row["series"]]


def load_audible_series_rows(field_dir: Path) -> list[dict[str, Any]]:
    path = field_dir / "output" / "audible_series_events.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            series = row.get("inferred_series") or row.get("native_series") or "Standalone / Unclustered"
            if series == "Standalone / Unclustered":
                series = row.get("title") or series
            rows.append(
                {
                    "title": row.get("title") or "",
                    "author": row.get("author") or "unknown",
                    "series": series,
                    "date": row.get("date"),
                    "asin": row.get("asin"),
                    "url": row.get("url"),
                    "source": row.get("source"),
                    "inference": row.get("inference"),
                    "evidence": "audible-series-event",
                }
            )
    return [row for row in rows if row["title"]]


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
            "significant_work_discovery": "Search significant_work_index.jsonl by id, title, or alias, then use concept links and chapter probes.",
            "concept_to_work_discovery": "Load concept_work_map.json -> concepts[lc-*] for related significant works.",
        },
        "privacy_boundary": "Indexes are derived counts and links. Raw Google Takeout, Audible exports, browser sessions, cookies, and extracted service files remain out of repo.",
    }

    significant = build_significant_work_indexes(field_dir_for_source(source_path), monthly["generated_at"])
    manifest["significant_work_count"] = len(significant["significant_works"])
    manifest["concept_work_count"] = len(significant["concept_work_map"]["concepts"])

    return {
        "manifest": manifest,
        "monthly": monthly,
        "authors": author_records,
        "works": work_records,
        "significant_works": significant["significant_works"],
        "concept_work_map": significant["concept_work_map"],
    }


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
    write_jsonl(args.output_dir / "significant_work_index.jsonl", indexes["significant_works"])
    write_json(args.output_dir / "concept_work_map.json", indexes["concept_work_map"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
