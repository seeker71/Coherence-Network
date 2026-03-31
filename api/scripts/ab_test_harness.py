#!/usr/bin/env python3
"""A/B prompt variant test harness.

Generates the full prompt for each variant+feature combo so agents can
run identical test conditions. Results go to api/logs/ab_test_results.json.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

_api_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_api_dir))

from app.services.agent_routing.prompt_templates_loader import (
    _config_path,
    reset_prompt_templates_cache,
)


FEATURES = [
    ("rate-limit-middleware", "Add per-IP rate limiting middleware that returns 429 after 100 req/min"),
    ("api-versioning-header", "Add X-API-Version response header to all endpoints returning the current API version"),
    ("idea-export-csv", "Add GET /api/ideas/export/csv that returns the idea portfolio as a downloadable CSV"),
    ("contributor-leaderboard", "Add GET /api/contributors/leaderboard returning top 10 contributors by contribution count"),
    ("spec-dependency-graph", "Add GET /api/specs/dependencies returning a JSON adjacency list of spec cross-references"),
    ("task-timeout-watchdog", "Add a background watchdog that marks agent tasks as failed after 15 minutes of no heartbeat"),
    ("audit-log-append", "Add POST /api/audit/log that appends an immutable audit entry with timestamp, actor, and action"),
    ("coherence-score-history", "Add GET /api/ideas/{id}/coherence-history returning the last 30 coherence score snapshots"),
    ("webhook-notification", "Add POST /api/webhooks/register and fire HTTP POST on idea state transitions"),
    ("batch-idea-create", "Add POST /api/ideas/batch that creates up to 20 ideas in a single request with atomic rollback"),
    ("api-metrics-prometheus", "Add GET /api/metrics/prometheus returning request counts and latencies in Prometheus exposition format"),
    ("spec-template-lint", "Add GET /api/specs/{id}/lint that runs validate_spec_quality and returns structured JSON errors"),
]


def render_prompt_a(feature_id: str, feature_desc: str, spec_filename: str) -> str:
    reset_prompt_templates_cache()
    os.environ["PROMPT_VARIANT"] = "a"
    path = _config_path("a")
    data = json.loads(path.read_text())
    template = data["direction_templates"]["spec"]
    direction = template.format(item=feature_id, iteration=1, last_output="")
    role_common = data["role_wrapper"]["common"]
    role_spec = data["role_wrapper"]["by_task_type"]["spec"]

    return f"""Role agent: spec-agent.
Task type: spec.
{chr(10).join(role_common)}
{chr(10).join(role_spec)}
Direction: {direction}

FEATURE CONTEXT: {feature_desc}
SPEC FILENAME: specs/{spec_filename}"""


def render_prompt_b(feature_id: str, feature_desc: str, spec_filename: str) -> str:
    reset_prompt_templates_cache()
    os.environ["PROMPT_VARIANT"] = "b"
    path = _config_path("b")
    data = json.loads(path.read_text())
    template = data["direction_templates"]["spec"]
    direction = template.format(item=feature_id, iteration=1, last_output="")
    role_common = data["role_wrapper"]["common"]
    role_spec = data["role_wrapper"]["by_task_type"]["spec"]

    return f"""Role agent: spec-agent.
Task type: spec.
{chr(10).join(role_common)}
{chr(10).join(role_spec)}
Direction: {direction}

FEATURE CONTEXT: {feature_desc}
SPEC FILENAME: specs/{spec_filename}"""


def main():
    """Print rendered prompts for a specific variant+index."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["a", "b"], required=True)
    parser.add_argument("--index", type=int, required=True)
    args = parser.parse_args()

    feat_id, feat_desc = FEATURES[args.index]
    spec_file = f"test-ab-{args.variant}-{feat_id}.md"

    if args.variant == "a":
        print(render_prompt_a(feat_id, feat_desc, spec_file))
    else:
        print(render_prompt_b(feat_id, feat_desc, spec_file))


if __name__ == "__main__":
    main()
