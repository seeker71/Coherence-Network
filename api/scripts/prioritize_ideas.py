#!/usr/bin/env python3
"""Rank ideas by free-energy score."""

from __future__ import annotations

import argparse
import json

from app.services.idea_service import list_ideas


def main() -> None:
    parser = argparse.ArgumentParser(description="Prioritize ideas by free-energy score.")
    parser.add_argument("--only-unvalidated", action="store_true", help="Show only ideas not yet validated.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON.")
    args = parser.parse_args()

    portfolio = list_ideas(only_unvalidated=args.only_unvalidated)
    if args.json:
        print(portfolio.model_dump_json(indent=2))
        return

    print("Idea priorities:")
    for idx, idea in enumerate(portfolio.ideas, start=1):
        status = idea.manifestation_status.value if hasattr(idea.manifestation_status, "value") else str(idea.manifestation_status)
        print(
            f"{idx}. {idea.id} | score={idea.free_energy_score:.4f} "
            f"| gap={idea.value_gap:.2f} | status={status}"
        )
    print("")
    print(
        f"Summary: total={portfolio.summary.total_ideas} "
        f"unvalidated={portfolio.summary.unvalidated_ideas} "
        f"value_gap={portfolio.summary.total_value_gap:.2f}"
    )


if __name__ == "__main__":
    main()
