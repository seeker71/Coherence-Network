#!/usr/bin/env python3
"""
Check runtime idea mapping coverage threshold.

Ensures that critical ideas have runtime mappings to enable telemetry and cost/value tracking.
"""

import json
import sys
from pathlib import Path

# Minimum coverage threshold (ratio of mapped routes to critical ideas)
MIN_COVERAGE_THRESHOLD = 0.15  # 15% of ideas should have runtime mappings

# Critical ideas that MUST have runtime mappings
CRITICAL_IDEAS = {
    "portfolio-governance",
    "coherence-network-value-attribution",
    "coherence-network-agent-pipeline",
    "coherence-network-api-runtime",
    "oss-interface-alignment",
}


def main():
    # Read runtime idea map
    runtime_map_path = Path("config/runtime_idea_map.json")
    if not runtime_map_path.exists():
        print(f"❌ Error: {runtime_map_path} not found")
        sys.exit(1)

    with open(runtime_map_path) as f:
        runtime_map = json.load(f)

    prefix_map = runtime_map.get("prefix_map", {})

    # Get unique idea IDs with mappings
    mapped_ideas = set(prefix_map.values())

    # Read idea portfolio
    portfolio_path = Path("api/logs/idea_portfolio.json")
    if not portfolio_path.exists():
        print(f"❌ Error: {portfolio_path} not found")
        sys.exit(1)

    with open(portfolio_path) as f:
        portfolio = json.load(f)

    total_ideas = len(portfolio["ideas"])
    ideas_with_runtime = len(mapped_ideas)
    coverage_ratio = ideas_with_runtime / total_ideas if total_ideas > 0 else 0

    # Check critical ideas
    missing_critical = CRITICAL_IDEAS - mapped_ideas

    print("=== Runtime Idea Mapping Coverage ===")
    print(f"Total prefix mappings: {len(prefix_map)}")
    print(f"Total ideas in portfolio: {total_ideas}")
    print(f"Ideas with runtime mapping: {ideas_with_runtime}")
    print(f"Coverage ratio: {coverage_ratio:.2%}")
    print(f"Minimum threshold: {MIN_COVERAGE_THRESHOLD:.2%}")

    if missing_critical:
        print(f"\n❌ Missing critical idea mappings:")
        for idea_id in sorted(missing_critical):
            print(f"   - {idea_id}")
        sys.exit(1)

    if coverage_ratio < MIN_COVERAGE_THRESHOLD:
        print(f"\n❌ Coverage {coverage_ratio:.2%} below threshold {MIN_COVERAGE_THRESHOLD:.2%}")
        sys.exit(1)

    print(f"\n✅ All critical ideas mapped")
    print(f"✅ Coverage {coverage_ratio:.2%} meets threshold {MIN_COVERAGE_THRESHOLD:.2%}")
    print("\nMapped ideas:")
    for idea_id in sorted(mapped_ideas):
        count = sum(1 for v in prefix_map.values() if v == idea_id)
        print(f"   - {idea_id} ({count} prefixes)")


if __name__ == "__main__":
    main()
