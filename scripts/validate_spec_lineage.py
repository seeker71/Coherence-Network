#!/usr/bin/env python3
"""
Validate that spec changes have corresponding value-lineage links.

Ensures every modified spec has:
1. A value-lineage link entry
2. Complete contributor attribution (idea, spec, implementation, review)
3. Traceable connection to an idea

This enforces traceability-maturity-governance for autonomous evolution.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def get_changed_specs(base_sha: str, head_sha: str) -> list[str]:
    """Get list of modified spec files between two commits."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_sha}...{head_sha}", "specs/"],
            capture_output=True,
            text=True,
            check=True,
        )
        specs = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        return [s for s in specs if s.endswith(".md")]
    except subprocess.CalledProcessError as e:
        print(f"Error getting changed specs: {e}")
        return []


def extract_spec_id(spec_path: str) -> str:
    """Extract spec ID from path (e.g., 'specs/049-foo.md' -> '049-foo')."""
    return Path(spec_path).stem


def load_value_lineage() -> list[dict]:
    """Load value-lineage links from storage."""
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


def validate_lineage_completeness(link: dict) -> tuple[bool, list[str]]:
    """Validate that a lineage link has all required fields."""
    errors = []

    # Required fields
    if not link.get("idea_id"):
        errors.append("Missing idea_id")
    if not link.get("spec_id"):
        errors.append("Missing spec_id")

    # Contributor attribution
    contributors = link.get("contributors", {})
    required_roles = ["idea", "spec", "implementation", "review"]
    for role in required_roles:
        if not contributors.get(role):
            errors.append(f"Missing contributor for role: {role}")

    # Implementation references
    impl_refs = link.get("implementation_refs", [])
    if not impl_refs:
        errors.append("Missing implementation_refs (at least one PR/commit reference required)")

    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(description="Validate spec lineage for PR")
    parser.add_argument("--base", required=True, help="Base commit SHA")
    parser.add_argument("--head", required=True, help="Head commit SHA")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    # Get changed specs
    changed_specs = get_changed_specs(args.base, args.head)

    if not changed_specs:
        report = {
            "result": "pass",
            "reason": "No spec files modified",
            "changed_specs": [],
            "missing_lineage": [],
            "incomplete_lineage": []
        }
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("✅ No spec files modified - lineage validation skipped")
        sys.exit(0)

    # Load value-lineage links
    lineage_links = load_value_lineage()
    lineage_by_spec = {link["spec_id"]: link for link in lineage_links if link.get("spec_id")}

    # Validate each changed spec
    missing_lineage = []
    incomplete_lineage = []

    for spec_path in changed_specs:
        spec_id = extract_spec_id(spec_path)

        if spec_id not in lineage_by_spec:
            missing_lineage.append({
                "spec_path": spec_path,
                "spec_id": spec_id,
                "error": "No value-lineage link found"
            })
            continue

        link = lineage_by_spec[spec_id]
        is_complete, errors = validate_lineage_completeness(link)

        if not is_complete:
            incomplete_lineage.append({
                "spec_path": spec_path,
                "spec_id": spec_id,
                "lineage_id": link.get("id"),
                "errors": errors
            })

    # Generate report
    all_valid = len(missing_lineage) == 0 and len(incomplete_lineage) == 0

    report = {
        "result": "pass" if all_valid else "fail",
        "reason": "All spec changes have complete lineage" if all_valid else "Spec changes missing or incomplete lineage",
        "changed_specs": changed_specs,
        "missing_lineage": missing_lineage,
        "incomplete_lineage": incomplete_lineage,
        "stats": {
            "total_specs_changed": len(changed_specs),
            "specs_with_lineage": len(changed_specs) - len(missing_lineage),
            "specs_missing_lineage": len(missing_lineage),
            "specs_incomplete_lineage": len(incomplete_lineage)
        }
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\n=== Spec Lineage Validation ===")
        print(f"Changed specs: {len(changed_specs)}")
        for spec in changed_specs:
            print(f"  - {spec}")

        if missing_lineage:
            print(f"\n❌ Missing lineage ({len(missing_lineage)} specs):")
            for item in missing_lineage:
                print(f"  - {item['spec_path']} (spec_id: {item['spec_id']})")

        if incomplete_lineage:
            print(f"\n❌ Incomplete lineage ({len(incomplete_lineage)} specs):")
            for item in incomplete_lineage:
                print(f"  - {item['spec_path']} (spec_id: {item['spec_id']})")
                for error in item['errors']:
                    print(f"    • {error}")

        if all_valid:
            print("\n✅ All spec changes have complete lineage")
        else:
            print("\n" + "=" * 70)
            print("REQUIRED ACTION:")
            print("Create value-lineage links for modified specs:")
            print("  POST /api/value-lineage/links")
            print("  {")
            print('    "idea_id": "<idea-id>",')
            print('    "spec_id": "<spec-id>",')
            print('    "implementation_refs": ["PR#123", "commit-sha"],')
            print('    "contributors": {')
            print('      "idea": "<github-username>",')
            print('      "spec": "<github-username>",')
            print('      "implementation": "<github-username>",')
            print('      "review": "<github-username>"')
            print('    },')
            print('    "estimated_cost": <hours>')
            print("  }")

    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
