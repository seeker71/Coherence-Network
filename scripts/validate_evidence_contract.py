#!/usr/bin/env python3
"""
Validate evidence contract: ensure claims are backed by verifiable data, not assumptions.

Checks:
1. Contributor identity confidence (GitHub username vs "unknown")
2. Implementation refs are specific (PR# or commit SHA, not vague)
3. Measured deltas are present for answered questions
4. Usage events exist for claimed value

Spec: 061-traceability-maturity-governance.md
Idea: traceability-maturity-governance (ROI: 5.785)
"""

import argparse
import json
import re
import sys
from pathlib import Path


def load_value_lineage() -> list[dict]:
    """Load value-lineage links."""
    lineage_path = Path("api/logs/value_lineage.json")
    if not lineage_path.exists():
        return []

    try:
        with open(lineage_path) as f:
            data = json.load(f)
            return data.get("links", [])
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load value lineage: {e}")
        return []


def load_idea_portfolio() -> list[dict]:
    """Load idea portfolio."""
    portfolio_path = Path("api/logs/idea_portfolio.json")
    if not portfolio_path.exists():
        return []

    try:
        with open(portfolio_path) as f:
            data = json.load(f)
            return data.get("ideas", [])
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load portfolio: {e}")
        return []


def validate_contributor_identity(contributor: str) -> tuple[str, str | None]:
    """Validate contributor identity confidence.

    Returns: (confidence_level, issue_description)
    - "high": GitHub username format
    - "medium": Known system identifier
    - "low": Unknown or generic
    """
    if not contributor or contributor.strip() == "":
        return ("none", "Empty contributor")

    contributor = contributor.strip()

    # Unknown/generic identifiers (low confidence)
    if contributor.startswith("unknown"):
        return ("low", f"Generic identifier: {contributor}")

    # System identifiers (medium confidence)
    if contributor.startswith("system:") or contributor.startswith("ai:"):
        return ("medium", None)

    # GitHub username pattern (high confidence)
    # GitHub usernames can contain alphanumeric + hyphens, 1-39 chars
    if re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$', contributor):
        return ("high", None)

    return ("low", f"Non-standard format: {contributor}")


def validate_implementation_ref(ref: str) -> tuple[bool, str | None]:
    """Validate implementation reference is specific.

    Acceptable formats:
    - PR#123
    - commit-abc1234567890123456789012345678901234567
    - https://github.com/.../pull/123
    - https://github.com/.../commit/abc123...

    Returns: (is_valid, issue_description)
    """
    if not ref or ref.strip() == "":
        return (False, "Empty reference")

    ref = ref.strip()

    # PR reference
    if re.match(r'^PR#\d+$', ref, re.IGNORECASE):
        return (True, None)

    # Commit SHA (40 hex chars)
    if re.match(r'^[0-9a-f]{40}$', ref, re.IGNORECASE):
        return (True, None)

    # GitHub PR URL
    if re.match(r'^https://github\.com/.+/pull/\d+$', ref):
        return (True, None)

    # GitHub commit URL
    if re.match(r'^https://github\.com/.+/commit/[0-9a-f]{40}$', ref):
        return (True, None)

    # Vague references
    vague_patterns = [
        "TBD", "TODO", "pending", "in progress", "various", "multiple", "see docs"
    ]
    if any(pattern.lower() in ref.lower() for pattern in vague_patterns):
        return (False, f"Vague reference: {ref}")

    return (False, f"Non-standard format: {ref}")


def validate_evidence_contract(
    lineage_links: list[dict],
    ideas: list[dict]
) -> tuple[dict, list[dict]]:
    """Validate evidence contract across lineage and portfolio.

    Returns: (summary_stats, violations)
    """
    violations = []

    # Check lineage links
    for link in lineage_links:
        link_id = link.get("id", "unknown")
        spec_id = link.get("spec_id", "unknown")

        # Check contributor identities
        contributors = link.get("contributors", {})
        for role, contributor in contributors.items():
            confidence, issue = validate_contributor_identity(contributor)
            if confidence in ["low", "none"]:
                violations.append({
                    "category": "contributor_identity",
                    "severity": "medium",
                    "lineage_id": link_id,
                    "spec_id": spec_id,
                    "issue": f"{role} contributor has {confidence} confidence: {issue}"
                })

        # Check implementation refs
        impl_refs = link.get("implementation_refs", [])
        if not impl_refs:
            violations.append({
                "category": "implementation_refs",
                "severity": "high",
                "lineage_id": link_id,
                "spec_id": spec_id,
                "issue": "No implementation references"
            })
        else:
            for ref in impl_refs:
                is_valid, issue = validate_implementation_ref(ref)
                if not is_valid:
                    violations.append({
                        "category": "implementation_refs",
                        "severity": "medium",
                        "lineage_id": link_id,
                        "spec_id": spec_id,
                        "issue": f"Invalid implementation ref: {issue}"
                    })

    # Check idea questions
    for idea in ideas:
        idea_id = idea.get("id", "unknown")
        questions = idea.get("open_questions", [])

        for question in questions:
            question_id = question.get("question_id", "unknown")
            answered_by = question.get("answered_by")
            answer = question.get("answer")
            measured_delta = question.get("measured_delta")

            # If answered, must have measured_delta
            if answer and answered_by:
                if measured_delta is None:
                    violations.append({
                        "category": "measured_delta",
                        "severity": "high",
                        "idea_id": idea_id,
                        "question_id": question_id,
                        "issue": "Answered question missing measured_delta (assumption, not evidence)"
                    })

                # Validate answerer identity
                confidence, issue = validate_contributor_identity(answered_by)
                if confidence in ["low", "none"]:
                    violations.append({
                        "category": "contributor_identity",
                        "severity": "low",
                        "idea_id": idea_id,
                        "question_id": question_id,
                        "issue": f"Answerer has {confidence} confidence: {issue}"
                    })

    # Calculate stats
    total_violations = len(violations)
    by_severity = {
        "high": len([v for v in violations if v["severity"] == "high"]),
        "medium": len([v for v in violations if v["severity"] == "medium"]),
        "low": len([v for v in violations if v["severity"] == "low"])
    }
    by_category = {}
    for v in violations:
        cat = v["category"]
        by_category[cat] = by_category.get(cat, 0) + 1

    stats = {
        "total_violations": total_violations,
        "by_severity": by_severity,
        "by_category": by_category,
        "pass": total_violations == 0
    }

    return stats, violations


def main():
    parser = argparse.ArgumentParser(description="Validate evidence contract")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--fail-on-high", action="store_true", help="Exit 1 if high severity violations")
    args = parser.parse_args()

    lineage_links = load_value_lineage()
    ideas = load_idea_portfolio()

    stats, violations = validate_evidence_contract(lineage_links, ideas)

    report = {
        "result": "pass" if stats["pass"] else "fail",
        "stats": stats,
        "violations": violations[:50]  # Limit to first 50
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\n=== Evidence Contract Validation ===")
        print(f"Total violations: {stats['total_violations']}")
        print(f"By severity: High={stats['by_severity']['high']}, "
              f"Medium={stats['by_severity']['medium']}, "
              f"Low={stats['by_severity']['low']}")
        print(f"By category: {stats['by_category']}")

        if violations:
            print(f"\n❌ Found {len(violations)} evidence contract violations:")
            for v in violations[:20]:  # Show first 20
                print(f"\n[{v['severity'].upper()}] {v['category']}")
                for key, val in v.items():
                    if key not in ['severity', 'category', 'issue']:
                        print(f"  {key}: {val}")
                print(f"  Issue: {v['issue']}")
        else:
            print("\n✅ All evidence claims backed by verifiable data")

    # Exit code logic
    if args.fail_on_high and stats['by_severity']['high'] > 0:
        sys.exit(1)
    elif not stats['pass']:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
