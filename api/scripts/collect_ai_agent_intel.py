#!/usr/bin/env python3
"""Collect biweekly AI-agent intelligence from primary-source URLs.

This script fetches a curated source set and emits a normalized digest with
publication dates, retrieval evidence, and implementation relevance scores.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class SourceSpec:
    id: str
    url: str
    title_hint: str
    published_at: str
    source_type: str
    category: str
    tags: tuple[str, ...]
    why_it_matters: str
    severity: str = "info"


SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        id="ms_agent_framework_rc",
        url="https://devblogs.microsoft.com/foundry/introducing-microsoft-agent-framework-the-open-source-engine-for-agentic-ai-apps/",
        title_hint="Microsoft Agent Framework RC",
        published_at="2026-02-19T00:00:00Z",
        source_type="official_blog",
        category="framework",
        tags=("framework", "agent-orchestration", "open-source"),
        why_it_matters="Signals convergence toward unified enterprise agent runtime patterns.",
    ),
    SourceSpec(
        id="openai_bedrock_stateful_runtime",
        url="https://openai.com/index/introducing-stateful-runtime-for-agents-in-amazon-bedrock/",
        title_hint="Stateful Runtime for Agents in Amazon Bedrock",
        published_at="2026-02-27T00:00:00Z",
        source_type="official_blog",
        category="platform",
        tags=("stateful-runtime", "agent-platform", "production"),
        why_it_matters="Confirms mainstream support for persistent, stateful agent execution.",
    ),
    SourceSpec(
        id="openai_figma_integration",
        url="https://openai.com/index/figma-openai/",
        title_hint="Figma and OpenAI",
        published_at="2026-02-26T00:00:00Z",
        source_type="official_blog",
        category="coding_agent",
        tags=("mcp", "coding-agent", "tool-integration"),
        why_it_matters="Demonstrates production MCP-style integration between design and code workflows.",
    ),
    SourceSpec(
        id="github_copilot_cli_ga",
        url="https://github.blog/changelog/2026-02-25-github-copilot-cli-is-now-generally-available/",
        title_hint="GitHub Copilot CLI GA",
        published_at="2026-02-25T00:00:00Z",
        source_type="official_changelog",
        category="coding_agent",
        tags=("copilot", "cli", "coding-agent"),
        why_it_matters="CLI-native coding agent workflows are now default production paths, not beta experiments.",
    ),
    SourceSpec(
        id="github_enterprise_ai_controls_ga",
        url="https://github.blog/changelog/2026-02-26-enterprise-ai-controls-and-agent-control-plane-are-now-generally-available/",
        title_hint="Enterprise AI Controls GA",
        published_at="2026-02-26T00:00:00Z",
        source_type="official_changelog",
        category="governance",
        tags=("governance", "agent-control-plane", "enterprise"),
        why_it_matters="Agent systems are moving from pure capability to controlled governance and policy enforcement.",
    ),
    SourceSpec(
        id="github_copilot_metrics_ga",
        url="https://github.blog/changelog/2026-02-27-metrics-for-github-copilot-is-now-generally-available/",
        title_hint="Metrics for GitHub Copilot GA",
        published_at="2026-02-27T00:00:00Z",
        source_type="official_changelog",
        category="observability",
        tags=("metrics", "copilot", "observability"),
        why_it_matters="Usage-quality observability is now expected for coding-agent deployments.",
    ),
    SourceSpec(
        id="figma_claude_code_integration",
        url="https://www.figma.com/blog/introducing-claude-code-integration/",
        title_hint="Figma Claude Code Integration",
        published_at="2026-02-26T00:00:00Z",
        source_type="official_blog",
        category="coding_agent",
        tags=("claude-code", "design-to-code", "integration"),
        why_it_matters="Cross-tool agent handoff quality is becoming a core productivity differentiator.",
    ),
    SourceSpec(
        id="checkpoint_mcp_vulnerability",
        url="https://research.checkpoint.com/2026/from-prompt-to-pwn-analyzing-vulnerabilities-in-mcp-powered-ai-agent/",
        title_hint="Prompt to Pwn MCP Vulnerability Analysis",
        published_at="2026-02-24T00:00:00Z",
        source_type="security_research",
        category="security",
        tags=("security", "mcp", "agent-risk"),
        why_it_matters="Agent toolchain attack surfaces are active and require explicit mitigation loops.",
        severity="high",
    ),
    SourceSpec(
        id="nvd_cve_2026_27794",
        url="https://nvd.nist.gov/vuln/detail/CVE-2026-27794",
        title_hint="CVE-2026-27794",
        published_at="2026-02-26T00:00:00Z",
        source_type="official_advisory",
        category="security",
        tags=("security", "langgraph", "dependency"),
        why_it_matters="High-severity dependency vulnerabilities in agent frameworks now require continuous tracking.",
        severity="high",
    ),
    SourceSpec(
        id="arxiv_codified_context",
        url="https://arxiv.org/abs/2602.16786",
        title_hint="Codified Context",
        published_at="2026-02-24T00:00:00Z",
        source_type="research_paper",
        category="research",
        tags=("spec-driven", "large-codebase", "coding-agent"),
        why_it_matters="Provides evidence that explicit contextual specification improves large-repo coding outcomes.",
    ),
    SourceSpec(
        id="arxiv_pancake",
        url="https://arxiv.org/abs/2602.18012",
        title_hint="Pancake",
        published_at="2026-02-25T00:00:00Z",
        source_type="research_paper",
        category="research",
        tags=("agent-memory", "planning", "multi-agent"),
        why_it_matters="Shows memory/credit assignment advances that can lower retry waste in long-horizon workflows.",
    ),
)


_CATEGORY_WEIGHT: dict[str, float] = {
    "coding_agent": 1.0,
    "framework": 0.95,
    "security": 0.95,
    "platform": 0.92,
    "observability": 0.9,
    "research": 0.9,
    "governance": 0.88,
}


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    return title[:220]


def _fetch_source(client: httpx.Client, source: SourceSpec, timeout_seconds: float) -> dict[str, Any]:
    try:
        response = client.get(source.url, follow_redirects=True, timeout=timeout_seconds)
        body = response.text[:40000]
        title = _extract_title(body)
        status_ok = 200 <= int(response.status_code) < 400
        return {
            "fetch_ok": status_ok,
            "http_status": response.status_code,
            "final_url": str(response.url),
            "title": title or source.title_hint,
            "content_bytes": len(response.content),
            "error": "" if status_ok else f"http_status_{response.status_code}",
        }
    except Exception as exc:  # pragma: no cover - network behavior
        return {
            "fetch_ok": False,
            "http_status": 0,
            "final_url": source.url,
            "title": source.title_hint,
            "content_bytes": 0,
            "error": str(exc)[:240],
        }


def _relevance_score(*, category: str, days_old: float, window_days: int, severity: str) -> float:
    recency = max(0.0, 1.0 - (days_old / max(float(window_days), 1.0)))
    category_weight = _CATEGORY_WEIGHT.get(category, 0.8)
    severity_weight = 1.0 if severity in {"high", "critical"} else 0.85
    score = 100.0 * ((0.55 * recency) + (0.35 * category_weight) + (0.10 * severity_weight))
    return round(max(0.0, min(score, 100.0)), 2)


def _build_digest(window_days: int, timeout_seconds: float) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []

    with httpx.Client(headers={"User-Agent": "coherence-network-intel-collector/1.0"}) as client:
        for source in SOURCES:
            published = _parse_iso(source.published_at)
            days_old = max(0.0, (now - published).total_seconds() / 86400.0)
            fetched = _fetch_source(client, source, timeout_seconds)
            score = _relevance_score(
                category=source.category,
                days_old=days_old,
                window_days=window_days,
                severity=source.severity,
            )
            row = {
                "id": source.id,
                "url": source.url,
                "final_url": fetched["final_url"],
                "title": fetched["title"],
                "title_hint": source.title_hint,
                "source_type": source.source_type,
                "category": source.category,
                "tags": list(source.tags),
                "published_at": source.published_at,
                "days_old": round(days_old, 2),
                "severity": source.severity,
                "relevance_score": score,
                "why_it_matters": source.why_it_matters,
                "fetch_ok": fetched["fetch_ok"],
                "http_status": fetched["http_status"],
                "content_bytes": fetched["content_bytes"],
                "error": fetched["error"],
                "retrieved_at": now.isoformat().replace("+00:00", "Z"),
            }
            rows.append(row)

    rows.sort(key=lambda item: float(item.get("relevance_score") or 0.0), reverse=True)
    fetch_ok_count = len([row for row in rows if row.get("fetch_ok") is True])
    avg_score = round(sum(float(row.get("relevance_score") or 0.0) for row in rows) / max(len(rows), 1), 2)

    return {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "window_days": int(window_days),
        "source_count": len(rows),
        "fetch_ok_count": fetch_ok_count,
        "avg_relevance_score": avg_score,
        "sources": rows,
    }


def _build_security_watch(digest: dict[str, Any]) -> dict[str, Any]:
    sources = digest.get("sources") if isinstance(digest.get("sources"), list) else []
    high_rows = [
        {
            "id": str(row.get("id") or ""),
            "title": str(row.get("title") or ""),
            "url": str(row.get("url") or ""),
            "published_at": str(row.get("published_at") or ""),
            "severity": str(row.get("severity") or ""),
            "http_status": int(row.get("http_status") or 0),
        }
        for row in sources
        if isinstance(row, dict)
        and str(row.get("category") or "") == "security"
        and str(row.get("severity") or "") in {"high", "critical"}
    ]

    critical_rows = [row for row in high_rows if str(row.get("severity") or "") == "critical"]
    high_only_rows = [row for row in high_rows if str(row.get("severity") or "") == "high"]

    return {
        "generated_at": str(digest.get("generated_at") or ""),
        "source_digest_file": "",
        "open_high_severity": high_only_rows,
        "open_critical_severity": critical_rows,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _latest_alias_path(path: Path, suffix: str) -> Path:
    if path.name.endswith(".json"):
        return path.with_name(suffix)
    return path.parent / suffix


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect biweekly AI-agent intelligence.")
    parser.add_argument("--window-days", type=int, default=14)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--output", required=True, help="Output digest JSON path")
    parser.add_argument(
        "--security-output",
        default="",
        help="Optional security watch JSON path. Defaults next to --output.",
    )
    args = parser.parse_args()

    window_days = max(1, int(args.window_days))
    timeout_seconds = max(2.0, float(args.timeout_seconds))
    output_path = Path(args.output).resolve()

    digest = _build_digest(window_days=window_days, timeout_seconds=timeout_seconds)
    _write_json(output_path, digest)

    security_payload = _build_security_watch(digest)
    security_payload["source_digest_file"] = str(output_path)
    security_output = Path(args.security_output).resolve() if str(args.security_output).strip() else output_path.with_name(
        "ai_agent_security_watch_" + output_path.name.replace("ai_agent_biweekly_sources_", "")
    )
    _write_json(security_output, security_payload)

    digest_latest = _latest_alias_path(output_path, "ai_agent_biweekly_sources_latest.json")
    security_latest = _latest_alias_path(security_output, "ai_agent_security_watch_latest.json")
    _write_json(digest_latest, digest)
    _write_json(security_latest, security_payload)

    print(
        json.dumps(
            {
                "output": str(output_path),
                "security_output": str(security_output),
                "latest_digest": str(digest_latest),
                "latest_security": str(security_latest),
                "source_count": digest.get("source_count"),
                "fetch_ok_count": digest.get("fetch_ok_count"),
                "avg_relevance_score": digest.get("avg_relevance_score"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
