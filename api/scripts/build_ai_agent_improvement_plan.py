#!/usr/bin/env python3
"""Build a scored 10-point project improvement plan from intelligence evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _load_model_runs(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _recent_failure_rate(rows: list[dict[str, Any]], sample_size: int = 40) -> float:
    if not rows:
        return 0.0
    sample = rows[-sample_size:]
    failures = sum(1 for row in sample if str(row.get("pass_fail") or "").strip().lower() == "fail")
    return round(failures / float(len(sample)), 4)


def _source_score_map(digest: dict[str, Any]) -> dict[str, float]:
    sources = digest.get("sources") if isinstance(digest.get("sources"), list) else []
    score_by_tag: dict[str, list[float]] = {}
    for row in sources:
        if not isinstance(row, dict):
            continue
        score = float(row.get("relevance_score") or 0.0)
        tags = row.get("tags") if isinstance(row.get("tags"), list) else []
        for tag in tags:
            key = str(tag).strip().lower()
            if key:
                score_by_tag.setdefault(key, []).append(score)
        category = str(row.get("category") or "").strip().lower()
        if category:
            score_by_tag.setdefault(category, []).append(score)

    averaged: dict[str, float] = {}
    for key, values in score_by_tag.items():
        averaged[key] = round(sum(values) / max(len(values), 1), 2)
    return averaged


def _match_evidence_score(tags: list[str], score_map: dict[str, float]) -> float:
    matches = [score_map.get(tag.lower(), 0.0) for tag in tags]
    if not matches:
        return 40.0
    return round(sum(matches) / max(len(matches), 1), 2)


def _base_plan_items() -> list[dict[str, Any]]:
    return [
        {
            "id": "P1",
            "title": "Automate n8n advisory ingestion into security watch",
            "tags": ["security", "automation-workflow", "n8n", "ghsa"],
            "impact": 5,
            "effort": 2,
            "files": ["api/scripts/collect_ai_agent_intel.py", "api/scripts/monitor_pipeline.py"],
            "done_when": [
                "Collector imports recent high/critical n8n GitHub advisories into digest output",
                "Security watch artifact includes n8n GHSA IDs and monitor surfaces the top advisory",
            ],
        },
        {
            "id": "P2",
            "title": "Pilot CrewAI async step-callback integration",
            "tags": ["framework", "agent-orchestration", "crewai"],
            "impact": 4,
            "effort": 3,
            "files": ["specs/006-overnight-backlog.md", "docs/AGENT-DEBUGGING.md"],
            "done_when": [
                "Backlog includes an explicit CrewAI async callback pilot task with validation gates",
                "Runbook/debug docs include callback latency/error telemetry checkpoints",
            ],
        },
        {
            "id": "P3",
            "title": "Run LangGraphJS Overwrite/tool-lifecycle compatibility spike",
            "tags": ["framework", "langgraph", "state-schema", "observability"],
            "impact": 4,
            "effort": 3,
            "files": ["specs/006-overnight-backlog.md", "specs/110-langgraph-stateschema-adoption.md"],
            "done_when": [
                "Backlog includes a scoped implementation task for Overwrite semantics and tools stream events",
                "Spec 110 cross-links the new validation approach and deterministic diagnostics target",
            ],
        },
        {
            "id": "P4",
            "title": "Add stale-intelligence monitor guard",
            "tags": ["observability", "governance"],
            "impact": 4,
            "effort": 2,
            "files": ["api/scripts/monitor_pipeline.py"],
            "done_when": [
                "Monitor adds ai_agent_intelligence_stale condition for outdated digest",
                "Condition appears in monitor_issues output",
            ],
        },
        {
            "id": "P5",
            "title": "Track open high-severity agent advisories",
            "tags": ["security", "agent-risk"],
            "impact": 5,
            "effort": 2,
            "files": ["api/scripts/monitor_pipeline.py"],
            "done_when": [
                "Monitor adds ai_agent_security_advisory_open condition when high/critical advisories exist",
                "Issue severity reflects advisory criticality",
            ],
        },
        {
            "id": "P6",
            "title": "Automate biweekly intelligence collection",
            "tags": ["framework", "coding-agent", "research"],
            "impact": 4,
            "effort": 3,
            "files": ["api/scripts/collect_ai_agent_intel.py"],
            "done_when": [
                "Digest captures source URLs, dates, fetch status, and relevance scores",
                "Security watch artifact is generated from digest",
            ],
        },
        {
            "id": "P7",
            "title": "Generate scored 10-point execution plan",
            "tags": ["governance", "observability"],
            "impact": 4,
            "effort": 2,
            "files": ["api/scripts/build_ai_agent_improvement_plan.py"],
            "done_when": [
                "Plan output includes ranked items with rio_score",
                "Each item includes measurable done_when checks",
            ],
        },
        {
            "id": "P8",
            "title": "Expand spec template for evidence-first execution",
            "tags": ["spec-driven", "governance"],
            "impact": 4,
            "effort": 2,
            "files": ["specs/TEMPLATE.md"],
            "done_when": [
                "Template includes research links, task card, and retry reflection sections",
                "Quality gate still passes",
            ],
        },
        {
            "id": "P9",
            "title": "Publish biweekly ecosystem synthesis report",
            "tags": ["research", "framework", "coding-agent"],
            "impact": 3,
            "effort": 2,
            "files": ["docs/system_audit/ai_agent_biweekly_summary_2026-02-28.md"],
            "done_when": [
                "Report documents dated developments and implications",
                "Sources are primary and linked",
            ],
        },
        {
            "id": "P10",
            "title": "Attach commit evidence for all executed checks",
            "tags": ["governance", "observability"],
            "impact": 4,
            "effort": 2,
            "files": ["docs/system_audit/commit_evidence_2026-02-28_ai-agent-intel-feedback-loop.json"],
            "done_when": [
                "Evidence artifact validates with validate_commit_evidence.py",
                "Evidence lists executed commands and outputs",
            ],
        },
    ]


def _score_items(items: list[dict[str, Any]], score_map: dict[str, float], failure_rate: float) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    failure_multiplier = 1.0 + min(max(failure_rate, 0.0), 0.5)
    for item in items:
        tags = [str(tag) for tag in item.get("tags", [])]
        evidence_score = _match_evidence_score(tags, score_map)
        impact = float(item.get("impact") or 1)
        effort = max(1.0, float(item.get("effort") or 1))
        confidence = max(0.3, min(1.0, evidence_score / 100.0))
        rio_score = round((impact * confidence * failure_multiplier) / effort, 4)
        row = dict(item)
        row["evidence_score"] = evidence_score
        row["failure_multiplier"] = round(failure_multiplier, 4)
        row["rio_score"] = rio_score
        scored.append(row)
    scored.sort(key=lambda item: float(item.get("rio_score") or 0.0), reverse=True)
    for index, item in enumerate(scored, start=1):
        item["priority_rank"] = index
    return scored


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a scored 10-point improvement plan.")
    parser.add_argument("--intel", required=True, help="Path to intelligence digest JSON")
    parser.add_argument("--output", required=True, help="Output plan JSON path")
    parser.add_argument(
        "--executor-runs",
        default="../docs/system_audit/model_executor_runs.jsonl",
        help="Path to model executor runs jsonl for failure-rate context",
    )
    args = parser.parse_args()

    intel_path = Path(args.intel).resolve()
    output_path = Path(args.output).resolve()
    runs_path = Path(args.executor_runs).resolve()

    digest = _load_json(intel_path)
    runs = _load_model_runs(runs_path)
    failure_rate = _recent_failure_rate(runs)

    score_map = _source_score_map(digest)
    plan_items = _score_items(_base_plan_items(), score_map, failure_rate)

    payload = {
        "generated_at": digest.get("generated_at"),
        "source_digest": str(intel_path),
        "executor_runs_source": str(runs_path),
        "recent_failure_rate": failure_rate,
        "item_count": len(plan_items),
        "plan": plan_items,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "item_count": len(plan_items),
                "top_item": plan_items[0]["id"] if plan_items else "",
                "recent_failure_rate": failure_rate,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
