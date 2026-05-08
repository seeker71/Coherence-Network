"""Computed CC sensing for organism-scale influences.

This is a read-only allocation surface. It does not mint CC; it gives the
organism a compact way to sense which people, agents, works, practices, and
source bodies carried the most visible nutrition in the current trace.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import field_story_service


POLICY_ID = "organism-influence-cc:v1"
SCHEMA_VERSION = "organism-influence-cc/v1"
DEFAULT_POOL_WEIGHTS = {
    "stewardship_time": 0.18,
    "agent_time": 0.14,
    "significant_works": 0.34,
    "creators_and_channels": 0.24,
    "manual_practices": 0.10,
}


@dataclass
class InfluenceCandidate:
    influencer_id: str
    name: str
    kind: str
    pool_id: str
    ledger_recipient_id: str
    score: float = 0.0
    computed_cc: float = 0.0
    source_mix: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    trace_refs: set[str] = field(default_factory=set)
    reasons: list[str] = field(default_factory=list)

    def add(
        self,
        score: float,
        *,
        source: str,
        trace_ref: str,
        reason: str,
        source_amount: float = 1.0,
    ) -> None:
        self.score += max(0.0, score)
        self.source_mix[source] += source_amount
        self.trace_refs.add(trace_ref)
        if reason and reason not in self.reasons:
            self.reasons.append(reason)


def compute_organism_influence_cc(
    slug: str,
    *,
    limit: int = 40,
    cc_pool: float = 1000.0,
) -> dict[str, Any]:
    """Compute a compact CC distribution over top organism influencers."""

    limit = max(1, min(int(limit), 250))
    cc_pool = max(0.0, min(float(cc_pool), 1_000_000.0))
    story_dir = field_story_service._story_dir_for_slug(slug)  # noqa: SLF001

    source_crypto = _load_json(story_dir / "trace" / "source_crypto_trace.json")
    candidates: dict[str, InfluenceCandidate] = {}

    _add_stewardship_candidate(candidates, story_dir, source_crypto)
    _add_agent_time_candidates(candidates, field_story_service.REPO_ROOT)
    significant_author_scores = _add_significant_work_candidates(candidates, story_dir)
    author_slug_index = _add_author_candidates(candidates, story_dir, significant_author_scores)
    _add_manual_anchor_candidates(candidates, story_dir, author_slug_index)

    pools = _allocate_pool_cc(candidates, cc_pool)
    ranked = sorted(candidates.values(), key=lambda row: (-row.computed_cc, -row.score, row.name.lower()))
    top_rows = [_candidate_payload(idx + 1, row) for idx, row in enumerate(ranked[:limit])]

    return {
        "schema_version": SCHEMA_VERSION,
        "policy_id": POLICY_ID,
        "story_slug": slug,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_cc_pool": _round(cc_pool),
        "source_crypto_root": source_crypto.get("roots", {}).get("combined_trace_root", ""),
        "truth_boundary": (
            "Computed sensing allocation only; no CC is minted or paid here. "
            "Ledger-compatible recipient ids and trace refs let a later settlement breath "
            "write actual circulation rows with explicit consent and policy."
        ),
        "allocation_basis": {
            "pool_weights": DEFAULT_POOL_WEIGHTS,
            "stewardship_time": "Urs time is approximated from curated source rows, manual anchors, and project lineage.",
            "agent_time": "Agent time is approximated from model executor proof records and commands run.",
            "external_influences": "Works, creators, channels, and practices come from compact trace indexes and anchors.",
        },
        "pools": pools,
        "totals": {
            "total_cc_pool": _round(cc_pool),
            "distributed_cc": _round(sum(row.computed_cc for row in candidates.values())),
            "full_influencer_count": len(candidates),
            "returned_count": len(top_rows),
        },
        "top_influencers": top_rows,
        "dynamic_access": {
            "api": f"/api/field-stories/{slug}/organism-influence-cc",
            "mcp_tool": "get_organism_influence_cc",
            "cli": f"python3 scripts/organism_influence_cc.py --slug {slug}",
            "ledger_read": "/api/contributions/ledger/{ledger_recipient_id}",
            "source_crypto": f"/api/field-stories/{slug}/artifacts/trace-source-crypto",
        },
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _candidate(
    candidates: dict[str, InfluenceCandidate],
    *,
    influencer_id: str,
    name: str,
    kind: str,
    pool_id: str,
    ledger_recipient_id: str,
) -> InfluenceCandidate:
    existing = candidates.get(influencer_id)
    if existing:
        return existing
    row = InfluenceCandidate(
        influencer_id=influencer_id,
        name=name,
        kind=kind,
        pool_id=pool_id,
        ledger_recipient_id=ledger_recipient_id,
    )
    candidates[influencer_id] = row
    return row


def _add_stewardship_candidate(
    candidates: dict[str, InfluenceCandidate],
    story_dir: Path,
    source_crypto: dict[str, Any],
) -> None:
    anchors = _load_json(story_dir / "anchors" / "influence_anchors.json")
    lineage = _load_json(story_dir / "anchors" / "project_lineage_anchors.json")
    normalized = source_crypto.get("normalized_event_trace", {})
    manual_count = sum(len(rows) for key, rows in anchors.items() if isinstance(rows, list))
    attempt_count = len(lineage.get("official_attempts", [])) + len(lineage.get("prehistory", []))
    row_count = float(normalized.get("line_count") or 0)
    score = (row_count / 250.0) + (manual_count * 12.0) + (attempt_count * 32.0)
    row = _candidate(
        candidates,
        influencer_id="contributor:urs",
        name="Urs / TheSeeker71",
        kind="human_steward",
        pool_id="stewardship_time",
        ledger_recipient_id="contributor:urs",
    )
    row.add(
        score,
        source="curated-field-trace",
        source_amount=row_count,
        trace_ref="docs/field/urs/trace/source_crypto_trace.json",
        reason="Curated the source body, manual anchors, lineage, and organism direction into a queryable trace.",
    )


def _add_agent_time_candidates(candidates: dict[str, InfluenceCandidate], repo_root: Path) -> None:
    path = repo_root / "docs" / "system_audit" / "model_executor_runs.jsonl"
    aggregate: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    if path.exists():
        for record in _jsonl(path):
            model = str(record.get("model_used") or "codex").strip() or "codex"
            commands = record.get("commands_run") if isinstance(record.get("commands_run"), list) else []
            aggregate[model]["score"] += (
                (float(record.get("input_tokens") or 0) + float(record.get("output_tokens") or 0)) / 1000.0
                + float(record.get("attempts") or 1) * 2.0
                + len(commands) * 0.35
            )
            aggregate[model]["runs"] += 1
            aggregate[model]["commands"] += len(commands)
    if not aggregate:
        aggregate["codex"]["score"] = 1.0
    for model, stats in aggregate.items():
        row = _candidate(
            candidates,
            influencer_id=f"agent:{_slug(model)}",
            name=f"Codex agent time ({model})",
            kind="agent_time",
            pool_id="agent_time",
            ledger_recipient_id=f"agent:{_slug(model)}",
        )
        row.add(
            stats["score"],
            source="model-executor-proof",
            source_amount=stats.get("runs", 1),
            trace_ref="docs/system_audit/model_executor_runs.jsonl",
            reason="Agent execution proof records convert commands, attempts, and token pressure into a time proxy.",
        )


def _add_significant_work_candidates(
    candidates: dict[str, InfluenceCandidate],
    story_dir: Path,
) -> dict[str, float]:
    author_scores: dict[str, float] = defaultdict(float)
    for record in _jsonl(story_dir / "trace" / "significant_work_index.jsonl"):
        basis = record.get("impact_basis") if isinstance(record.get("impact_basis"), dict) else {}
        impact_score = float(record.get("impact_score") or 0)
        child_count = float(basis.get("unique_child_titles") or len(record.get("children", [])))
        audible_rows = float(basis.get("audible_event_rows") or 0)
        manual_boost = 16.0 if basis.get("manual_anchor") else 0.0
        score = impact_score + (child_count * 1.6) + (audible_rows * 0.2) + manual_boost
        title = str(record.get("title") or record.get("id") or "Untitled work")
        row = _candidate(
            candidates,
            influencer_id=str(record.get("id") or f"significant-work:{_slug(title)}"),
            name=title,
            kind="significant_work",
            pool_id="significant_works",
            ledger_recipient_id=f"work:{_slug(title)}",
        )
        row.add(
            score,
            source="significant-work-index",
            source_amount=impact_score,
            trace_ref="docs/field/urs/trace/significant_work_index.jsonl",
            reason="Significant work impact combines manual anchors, Audible/listening rows, child works, and concept links.",
        )
        for author in record.get("authors", []):
            author_scores[str(author)] += (impact_score * 0.75) + child_count
    return author_scores


def _add_author_candidates(
    candidates: dict[str, InfluenceCandidate],
    story_dir: Path,
    significant_author_scores: dict[str, float],
) -> dict[str, str]:
    slug_index: dict[str, str] = {}
    seen_authors: set[str] = set()
    for record in _jsonl(story_dir / "trace" / "author_index.jsonl"):
        name = str(record.get("name") or "").strip()
        if not name or name.lower() == "unknown":
            continue
        seen_authors.add(name)
        volume = record.get("volume") if isinstance(record.get("volume"), dict) else {}
        source_mix = record.get("source_mix") if isinstance(record.get("source_mix"), dict) else {}
        evidence = source_mix.get("evidence") if isinstance(source_mix.get("evidence"), dict) else {}
        score = (
            math.sqrt(float(volume.get("axis_energy") or 0)) * 2.0
            + math.log1p(float(volume.get("events") or record.get("events") or 0)) * 8.0
            + float(volume.get("known_duration_hours") or 0) * 2.0
            + len(evidence) * 5.0
            + significant_author_scores.get(name, 0.0)
        )
        row = _author_candidate(candidates, name)
        slug_index[_slug(name)] = row.influencer_id
        row.add(
            score,
            source="author-index",
            source_amount=float(record.get("events") or 0),
            trace_ref="docs/field/urs/trace/author_index.jsonl",
            reason="Creator/channel score uses event wave, duration, axis energy, source diversity, and significant-work resonance.",
        )
    for name, score in significant_author_scores.items():
        if name in seen_authors:
            continue
        row = _author_candidate(candidates, name)
        slug_index[_slug(name)] = row.influencer_id
        row.add(
            score,
            source="significant-work-author",
            source_amount=score,
            trace_ref="docs/field/urs/trace/significant_work_index.jsonl",
            reason="Author appears through significant works even when a direct listening author row is sparse.",
        )
    return slug_index


def _author_candidate(candidates: dict[str, InfluenceCandidate], name: str) -> InfluenceCandidate:
    return _candidate(
        candidates,
        influencer_id=f"creator:{_slug(name)}",
        name=name,
        kind="creator_or_channel",
        pool_id="creators_and_channels",
        ledger_recipient_id=f"creator:{name}",
    )


def _add_manual_anchor_candidates(
    candidates: dict[str, InfluenceCandidate],
    story_dir: Path,
    author_slug_index: dict[str, str],
) -> None:
    anchors = _load_json(story_dir / "anchors" / "influence_anchors.json")
    for group, rows in anchors.items():
        if not isinstance(rows, list):
            continue
        for item in rows:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            slug = _slug(name)
            influencer_id = author_slug_index.get(slug, f"presence:{slug}")
            row = candidates.get(influencer_id) or _candidate(
                candidates,
                influencer_id=influencer_id,
                name=name,
                kind="manual_practice_or_presence",
                pool_id="manual_practices",
                ledger_recipient_id=f"presence:{slug}",
            )
            evidence = item.get("evidence") if isinstance(item.get("evidence"), list) else []
            themes = item.get("themes") if isinstance(item.get("themes"), list) else []
            score = (len(evidence) * 7.0) + (len(themes) * 5.0) + (12.0 if item.get("first_evidence") else 0.0)
            row.add(
                score,
                source=f"manual-anchor:{group}",
                source_amount=1.0,
                trace_ref="docs/field/urs/anchors/influence_anchors.json",
                reason="User-supplied lived anchor adds influence when logs are partial or pre-digital.",
            )


def _allocate_pool_cc(candidates: dict[str, InfluenceCandidate], cc_pool: float) -> list[dict[str, Any]]:
    by_pool: dict[str, list[InfluenceCandidate]] = defaultdict(list)
    for row in candidates.values():
        if row.score > 0:
            by_pool[row.pool_id].append(row)

    pool_payloads: list[dict[str, Any]] = []
    for pool_id, weight in DEFAULT_POOL_WEIGHTS.items():
        rows = by_pool.get(pool_id, [])
        pool_cc = cc_pool * weight
        total_score = sum(row.score for row in rows) or 1.0
        for row in rows:
            row.computed_cc = pool_cc * (row.score / total_score)
        pool_payloads.append(
            {
                "pool_id": pool_id,
                "pool_cc": _round(pool_cc),
                "recipient_count": len(rows),
                "description": _pool_description(pool_id),
            }
        )
    return pool_payloads


def _candidate_payload(rank: int, row: InfluenceCandidate) -> dict[str, Any]:
    return {
        "rank": rank,
        "influencer_id": row.influencer_id,
        "name": row.name,
        "kind": row.kind,
        "pool_id": row.pool_id,
        "ledger_recipient_id": row.ledger_recipient_id,
        "computed_cc": _round(row.computed_cc),
        "score": _round(row.score),
        "source_mix": {key: _round(value) for key, value in sorted(row.source_mix.items())},
        "trace_refs": sorted(row.trace_refs),
        "reasons": row.reasons[:4],
    }


def _pool_description(pool_id: str) -> str:
    descriptions = {
        "stewardship_time": "Human source gathering, curation, direction, and lived integration.",
        "agent_time": "Agent execution effort derived from proof records.",
        "significant_works": "Books, series, and works that shaped concepts and field movement.",
        "creators_and_channels": "Authors, speakers, musicians, researchers, and channels.",
        "manual_practices": "Practices and lived presences named as formative even when logs are partial.",
    }
    return descriptions.get(pool_id, pool_id.replace("_", " "))


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _round(value: float) -> float:
    return round(float(value), 4)
