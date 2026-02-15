#!/usr/bin/env python3
"""Auto-create value-lineage links from spec and PR metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx

from extract_spec_metadata import extract_estimated_cost, extract_idea_id_from_content, extract_spec_id


def extract_spec_metadata(spec_path: str) -> dict[str, Any]:
    return {
        "spec_id": extract_spec_id(spec_path),
        "idea_id": extract_idea_id_from_content(spec_path),
        "estimated_cost": extract_estimated_cost(spec_path),
    }


def check_existing_lineage(spec_id: str) -> bool:
    lineage_path = Path("api/logs/value_lineage.json")
    if not lineage_path.exists():
        return False
    try:
        data = json.loads(lineage_path.read_text(encoding="utf-8"))
    except ValueError:
        return False
    links = data.get("links") if isinstance(data, dict) else []
    if not isinstance(links, list):
        return False
    return any(isinstance(link, dict) and link.get("spec_id") == spec_id for link in links)


def create_lineage_link(
    spec_id: str,
    idea_id: str,
    pr_number: int,
    pr_author: str,
    estimated_cost: float,
    api_url: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    link_data = {
        "idea_id": idea_id,
        "spec_id": spec_id,
        "implementation_refs": [f"PR#{pr_number}"],
        "contributors": {
            "idea": pr_author,
            "spec": pr_author,
            "implementation": pr_author,
            "review": "pending",
        },
        "estimated_cost": estimated_cost,
    }
    if dry_run:
        return {"status": "dry_run", "data": link_data}

    endpoint = f"{api_url.rstrip('/')}/api/value-lineage/links"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(endpoint, json=link_data)
        if response.status_code in {200, 201}:
            payload = response.json() if response.text else {}
            return {"status": "created", "data": payload}
        return {"status": "error", "error": f"HTTP {response.status_code}: {response.text}"}
    except (httpx.HTTPError, ValueError) as exc:
        return {"status": "error", "error": str(exc)}


def _render_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("\n=== Auto-Lineage Creation Report ===")
    print(f"Total specs: {summary['total_specs']}")
    print(f"Created: {summary['created']}")
    print(f"Dry-run generated: {summary['dry_run']}")
    print(f"Skipped (already exists): {summary['skipped']}")
    print(f"Needs idea_id: {summary['needs_idea_id']}")
    print(f"Errors: {summary['errors']}")
    missing = report["missing_idea_ids"]
    if missing:
        print("\nSpecs needing idea annotation:")
        for item in missing:
            print(f"- {item['spec_path']} -> add `**Idea**: `your-idea-id``")


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-create lineage from PR metadata")
    parser.add_argument("--specs", nargs="+", required=True, help="Modified spec files")
    parser.add_argument("--pr-number", type=int, required=True, help="PR number")
    parser.add_argument("--pr-author", required=True, help="PR author GitHub username")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--default-cost", type=float, default=2.0, help="Default estimated cost")
    parser.add_argument("--dry-run", action="store_true", help="Do not create links")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    missing_idea_ids: list[dict[str, str]] = []
    for spec_path in args.specs:
        metadata = extract_spec_metadata(spec_path)
        spec_id = metadata["spec_id"]
        idea_id = metadata["idea_id"]
        estimated_cost = float(metadata.get("estimated_cost") or args.default_cost)
        if check_existing_lineage(spec_id):
            results.append(
                {
                    "spec_path": spec_path,
                    "spec_id": spec_id,
                    "status": "skipped",
                    "reason": "Lineage already exists",
                }
            )
            continue
        if not idea_id:
            missing_idea_ids.append({"spec_path": spec_path, "spec_id": spec_id})
            results.append(
                {
                    "spec_path": spec_path,
                    "spec_id": spec_id,
                    "status": "needs_idea_id",
                    "reason": "Could not extract idea_id from spec content",
                }
            )
            continue
        create_result = create_lineage_link(
            spec_id=spec_id,
            idea_id=idea_id,
            pr_number=args.pr_number,
            pr_author=args.pr_author,
            estimated_cost=estimated_cost,
            api_url=args.api_url,
            dry_run=args.dry_run,
        )
        results.append(
            {
                "spec_path": spec_path,
                "spec_id": spec_id,
                "idea_id": idea_id,
                "status": create_result["status"],
                "result": create_result,
            }
        )

    summary = {
        "total_specs": len(args.specs),
        "created": sum(1 for item in results if item["status"] == "created"),
        "dry_run": sum(1 for item in results if item["status"] == "dry_run"),
        "skipped": sum(1 for item in results if item["status"] == "skipped"),
        "needs_idea_id": len(missing_idea_ids),
        "errors": sum(1 for item in results if item["status"] == "error"),
    }
    report = {"summary": summary, "results": results, "missing_idea_ids": missing_idea_ids}

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _render_report(report)
    return 0 if summary["needs_idea_id"] == 0 and summary["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
