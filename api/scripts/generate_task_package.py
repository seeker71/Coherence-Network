#!/usr/bin/env python3
"""Generate self-contained task packages for multi-tool AI workflow.

Each package is a paste-ready markdown file containing:
- Task description + acceptance criteria
- Full source file contents (not just paths)
- Project conventions subset
- Output format instructions

Usage:
    python scripts/generate_task_package.py --item 58
    python scripts/generate_task_package.py --item 58 59 60
    python scripts/generate_task_package.py --daily-plan
    python scripts/generate_task_package.py --all
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
API_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = API_DIR.parent
PACKAGES_DIR = API_DIR / "packages"
COMPLETION_FILE = PACKAGES_DIR / "completion.json"

# ---------------------------------------------------------------------------
# Project conventions (subset of CLAUDE.md relevant to task packages)
# ---------------------------------------------------------------------------
CONVENTIONS = """\
## Project Conventions (from CLAUDE.md)

- API: REST `/api/{resource}/{id}`
- All responses: Pydantic models
- Neo4j labels: `Project`, `Contributor`, `Organization`
- Coherence scores: 0.0–1.0
- Dates: ISO 8601 UTC
- File size limits: Pydantic models ~50 lines, route handlers ~80 lines,
  service files ~150 lines, React components ~100 lines
- Do NOT modify test files when implementing — fix implementation, not tests
- Implement exactly what the spec says — no simplification, no scope creep
- Only modify files listed in the task — stay in scope
"""


# ---------------------------------------------------------------------------
# Task registry: items 56–74
# ---------------------------------------------------------------------------
@dataclass
class TaskItem:
    """A backlog item with metadata for package generation."""

    item: int
    title: str
    description: str
    task_type: str  # Code, Docs, Script, Config
    priority: str  # HIGH, MED, LOW
    tool: str  # chatgpt, gemini, grok, claude_code
    input_files: list[str] = field(default_factory=list)
    output_files: list[str] = field(default_factory=list)
    blocked_by: list[int] = field(default_factory=list)
    verification: str = "cd api && python -m pytest tests/ -v -k 'not holdout'"
    skip: bool = False
    notes: str = ""


TASK_REGISTRY: dict[int, TaskItem] = {
    56: TaskItem(
        item=56,
        title="Implement spec 029 — GitHub API integration",
        description=(
            "Implement GitHub API client, Contributor/Organization nodes, "
            "and index_github.py per spec 029-github-api-integration.md.\n\n"
            "Acceptance criteria:\n"
            "- GitHub API client with rate-limit handling\n"
            "- Contributor and Organization Neo4j node creation\n"
            "- index_github.py script to index repos\n"
            "- Integration with existing graph store"
        ),
        task_type="Code",
        priority="HIGH",
        tool="claude_code",
        input_files=[
            "api/app/adapters/graph_store.py",
            "api/app/services/coherence_service.py",
            "api/app/services/indexer_service.py",
            "api/app/models/project.py",
            "specs/029-github-api-integration.md",
            "api/scripts/index_npm.py",
        ],
        output_files=[
            "api/app/services/github_client.py (NEW)",
            "api/app/adapters/graph_store.py",
            "api/scripts/index_github.py (NEW)",
            "api/app/services/coherence_service.py",
        ],
    ),
    57: TaskItem(
        item=57,
        title="Wire contributor metrics into coherence API",
        description=(
            "Add Contributor and Organization to GraphStore; wire "
            "contributor_diversity, activity_cadence into the coherence API "
            "per spec 029.\n\n"
            "Acceptance criteria:\n"
            "- GraphStore has methods for Contributor/Org CRUD\n"
            "- coherence_service computes contributor_diversity\n"
            "- coherence_service computes activity_cadence\n"
            "- GET /api/projects/{id} returns enriched coherence scores"
        ),
        task_type="Code",
        priority="HIGH",
        tool="grok",
        input_files=[
            "api/app/adapters/graph_store.py",
            "api/app/services/coherence_service.py",
            "api/app/routers/projects.py",
            "specs/029-github-api-integration.md",
        ],
        output_files=[
            "api/app/adapters/graph_store.py",
            "api/app/services/coherence_service.py",
        ],
        blocked_by=[56],
    ),
    58: TaskItem(
        item=58,
        title="Expand spec 008 — deps.dev API contract section",
        description=(
            "Expand specs/008-sprint-1-graph-foundation.md: add a deps.dev "
            "API contract section documenting endpoints, request/response "
            "shapes, rate limits, and error handling."
        ),
        task_type="Docs",
        priority="LOW",
        tool="chatgpt",
        input_files=["specs/008-sprint-1-graph-foundation.md"],
        output_files=["specs/008-sprint-1-graph-foundation.md"],
        verification="cat specs/008-sprint-1-graph-foundation.md | head -5",
    ),
    59: TaskItem(
        item=59,
        title="Update OSS concept mapping with examples",
        description=(
            "Update docs/concepts/OSS-CONCEPT-MAPPING.md with concrete "
            "node/edge examples. Show real Project, Contributor, Organization "
            "nodes and DEPENDS_ON, CONTRIBUTED_BY edges with sample data."
        ),
        task_type="Docs",
        priority="LOW",
        tool="chatgpt",
        input_files=["docs/concepts/OSS-CONCEPT-MAPPING.md"],
        output_files=["docs/concepts/OSS-CONCEPT-MAPPING.md"],
        verification="cat docs/concepts/OSS-CONCEPT-MAPPING.md | head -5",
    ),
    60: TaskItem(
        item=60,
        title="Add coherence algorithm sketch doc",
        description=(
            "Add docs/concepts/COHERENCE-ALGORITHM-SKETCH.md from the "
            "formula in PLAN.md. Document the scoring formula, weights, "
            "input signals, and edge cases."
        ),
        task_type="Docs",
        priority="LOW",
        tool="chatgpt",
        input_files=[
            "api/app/services/coherence_service.py",
            "docs/PLAN.md",
            "docs/concepts/COHERENCE-ALGORITHM-SKETCH.md",
        ],
        output_files=["docs/concepts/COHERENCE-ALGORITHM-SKETCH.md"],
        verification="cat docs/concepts/COHERENCE-ALGORITHM-SKETCH.md | head -5",
    ),
    61: TaskItem(
        item=61,
        title="Cross-link all specs with See Also",
        description=(
            "Review all specs/*.md files and add 'See also' sections "
            "where relevant, linking related specs to each other. "
            "Every spec should reference at least one related spec."
        ),
        task_type="Docs",
        priority="MED",
        tool="gemini",
        input_files=[],  # Populated dynamically — all specs
        output_files=[],  # Same — all specs
        verification="grep -l 'See also' specs/*.md | wc -l",
        notes="Input/output files populated dynamically with all specs/*.md",
    ),
    62: TaskItem(
        item=62,
        title="Add acceptance criteria checklist to spec template",
        description=(
            "Add an acceptance criteria checklist section to "
            "specs/TEMPLATE.md with example checkboxes and guidance."
        ),
        task_type="Docs",
        priority="LOW",
        tool="chatgpt",
        input_files=["specs/TEMPLATE.md"],
        output_files=["specs/TEMPLATE.md"],
        verification="cat specs/TEMPLATE.md | head -5",
    ),
    63: TaskItem(
        item=63,
        title="SKIP — already implemented",
        description="Item 63 (run_backlog_item.py) already exists.",
        task_type="SKIP",
        priority="LOW",
        tool="",
        skip=True,
    ),
    64: TaskItem(
        item=64,
        title="Run ruff and fix auto-fixable issues",
        description=(
            "Run ruff on api/ and fix all auto-fixable lint issues. "
            "Report which files were changed and what categories of "
            "fixes were applied."
        ),
        task_type="Script",
        priority="LOW",
        tool="chatgpt",
        input_files=["api/pyproject.toml"],
        output_files=[],
        verification="cd api && python -m ruff check .",
        notes="This is a command task — output should be the ruff fix commands and results",
    ),
    65: TaskItem(
        item=65,
        title="Expand CHANGELOG.md",
        description=(
            "Expand CHANGELOG.md with proper Keep a Changelog structure. "
            "Add entries for all completed phases (1-5) based on the "
            "backlog items in specs/006-overnight-backlog.md."
        ),
        task_type="Docs",
        priority="LOW",
        tool="chatgpt",
        input_files=[
            "CHANGELOG.md",
            "specs/006-overnight-backlog.md",
        ],
        output_files=["CHANGELOG.md"],
        verification="cat CHANGELOG.md | head -5",
    ),
    66: TaskItem(
        item=66,
        title="Expand Makefile with standard targets",
        description=(
            "Expand the Makefile with targets: test, run, lint, setup, "
            "format, clean. Each target should have a help comment."
        ),
        task_type="Config",
        priority="LOW",
        tool="chatgpt",
        input_files=["Makefile"],
        output_files=["Makefile"],
        verification="make -n test 2>/dev/null || echo 'make dry-run done'",
    ),
    67: TaskItem(
        item=67,
        title="Verify .env.example documents all env vars",
        description=(
            "Grep all Python files for os.environ / os.getenv references, "
            "compare with .env.example, and update .env.example to document "
            "all required and optional env vars with comments."
        ),
        task_type="Docs",
        priority="LOW",
        tool="chatgpt",
        input_files=["api/.env.example"],
        output_files=["api/.env.example"],
        verification="cat api/.env.example | head -5",
        notes="Include grep results for os.environ in the package",
    ),
    68: TaskItem(
        item=68,
        title="Add log rotation to agent runner",
        description=(
            "Review agent_runner.py and add RotatingFileHandler to ensure "
            "logs don't grow unbounded. Use 10MB max size, 5 backups."
        ),
        task_type="Code",
        priority="MED",
        tool="chatgpt",
        input_files=["api/scripts/agent_runner.py"],
        output_files=["api/scripts/agent_runner.py"],
    ),
    69: TaskItem(
        item=69,
        title="Add log cleanup to cleanup_temp.py",
        description=(
            "Extend cleanup_temp.py to also clean up old task logs "
            "(keep last 7 days). Add a --dry-run flag to preview."
        ),
        task_type="Script",
        priority="MED",
        tool="chatgpt",
        input_files=["api/scripts/cleanup_temp.py"],
        output_files=["api/scripts/cleanup_temp.py"],
    ),
    70: TaskItem(
        item=70,
        title="Document max backlog size in RUNBOOK.md",
        description=(
            "Document max backlog size and performance implications "
            "in docs/RUNBOOK.md. Add a section about project_manager "
            "operational limits and tuning."
        ),
        task_type="Docs",
        priority="LOW",
        tool="chatgpt",
        input_files=[
            "docs/RUNBOOK.md",
            "api/scripts/project_manager.py",
        ],
        output_files=["docs/RUNBOOK.md"],
        verification="cat docs/RUNBOOK.md | head -5",
    ),
    71: TaskItem(
        item=71,
        title="Verify shebangs and executable bits on scripts",
        description=(
            "Check all files in api/scripts/*.py and *.sh. Ensure each "
            "has a proper shebang line (#!/usr/bin/env python3 or "
            "#!/usr/bin/env bash) and report which need chmod +x."
        ),
        task_type="Script",
        priority="LOW",
        tool="chatgpt",
        input_files=[],  # Populated dynamically — all scripts
        output_files=[],
        verification="head -1 api/scripts/*.py api/scripts/*.sh",
        notes="Input files populated dynamically with all api/scripts/*",
    ),
    72: TaskItem(
        item=72,
        title="Expand smoke test script",
        description=(
            "Expand scripts/smoke_test.sh to: curl /health, "
            "curl /api/agent/pipeline-status, create a minimal task, "
            "verify it appears in the task list."
        ),
        task_type="Script",
        priority="MED",
        tool="chatgpt",
        input_files=["api/scripts/smoke_test.sh"],
        output_files=["api/scripts/smoke_test.sh"],
        verification="bash -n api/scripts/smoke_test.sh",
    ),
    73: TaskItem(
        item=73,
        title="Consolidate project_manager and overnight_orchestrator",
        description=(
            "Find and consolidate duplicate logic between project_manager.py "
            "(814 lines) and overnight_orchestrator.py (123 lines). "
            "Extract shared logic into a new backlog_service.py module."
        ),
        task_type="Code",
        priority="MED",
        tool="grok",
        input_files=[
            "api/scripts/project_manager.py",
            "api/scripts/overnight_orchestrator.py",
        ],
        output_files=[
            "api/app/services/backlog_service.py (NEW)",
            "api/scripts/project_manager.py",
            "api/scripts/overnight_orchestrator.py",
        ],
    ),
    74: TaskItem(
        item=74,
        title="Expand debugging and routing docs",
        description=(
            "Expand docs/AGENT-DEBUGGING.md and docs/MODEL-ROUTING.md "
            "with learnings from recent pipeline work. Add troubleshooting "
            "sections, common failure modes, and model selection guidance."
        ),
        task_type="Docs",
        priority="MED",
        tool="gemini",
        input_files=[
            "docs/AGENT-DEBUGGING.md",
            "docs/MODEL-ROUTING.md",
        ],
        output_files=[
            "docs/AGENT-DEBUGGING.md",
            "docs/MODEL-ROUTING.md",
        ],
        verification="cat docs/AGENT-DEBUGGING.md | head -5",
    ),
}


# ---------------------------------------------------------------------------
# Tool routing metadata
# ---------------------------------------------------------------------------
TOOL_INFO = {
    "chatgpt": {
        "name": "ChatGPT / Codex",
        "context": "Standard",
        "best_for": "Small docs, scripts, config",
    },
    "gemini": {
        "name": "Gemini Advanced",
        "context": "1M tokens",
        "best_for": "Large-context docs (many files needed)",
    },
    "grok": {
        "name": "Grok SuperGrok",
        "context": "2M tokens",
        "best_for": "Complex code needing big context",
    },
    "claude_code": {
        "name": "Claude Code",
        "context": "200K",
        "best_for": "Hard interactive tasks",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_path(rel_path: str) -> Path:
    """Resolve a project-relative path to absolute."""
    return PROJECT_ROOT / rel_path


def _read_file_safe(rel_path: str) -> Optional[str]:
    """Read a file, returning None if it doesn't exist."""
    p = _resolve_path(rel_path)
    if p.is_file():
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"# Error reading {rel_path}: {e}"
    return None


def _get_all_spec_files() -> list[str]:
    """List all spec files (for item 61)."""
    specs_dir = PROJECT_ROOT / "specs"
    if not specs_dir.is_dir():
        return []
    return sorted(
        [f"specs/{f.name}" for f in specs_dir.glob("*.md")],
    )


def _get_all_script_files() -> list[str]:
    """List all script files (for item 71)."""
    scripts_dir = API_DIR / "scripts"
    if not scripts_dir.is_dir():
        return []
    py = sorted([f"api/scripts/{f.name}" for f in scripts_dir.glob("*.py")])
    sh = sorted([f"api/scripts/{f.name}" for f in scripts_dir.glob("*.sh")])
    return py + sh


def _resolve_dynamic_files(item: TaskItem) -> TaskItem:
    """Fill in dynamically-populated file lists."""
    if item.item == 61:
        specs = _get_all_spec_files()
        item.input_files = specs
        item.output_files = specs
    elif item.item == 71:
        scripts = _get_all_script_files()
        item.input_files = scripts
    return item


def _load_completion() -> dict:
    """Load completion tracking state."""
    if COMPLETION_FILE.is_file():
        try:
            return json.loads(COMPLETION_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_completion(data: dict) -> None:
    """Save completion tracking state."""
    PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    COMPLETION_FILE.write_text(json.dumps(data, indent=2) + "\n")


def _init_completion() -> dict:
    """Initialize completion.json from registry."""
    data = {}
    for num, task in sorted(TASK_REGISTRY.items()):
        if task.skip:
            data[str(num)] = {"status": "skip", "tool": ""}
            continue
        status = "pending"
        if task.blocked_by:
            status = "blocked"
        data[str(num)] = {
            "status": status,
            "tool": task.tool,
        }
        if task.blocked_by:
            data[str(num)]["blocked_by"] = task.blocked_by
    return data


# ---------------------------------------------------------------------------
# Package generation
# ---------------------------------------------------------------------------


def generate_package(item_num: int) -> str:
    """Generate a self-contained markdown package for one backlog item."""
    if item_num not in TASK_REGISTRY:
        return f"# Error: Item {item_num} not in registry (valid: 56–74)\n"

    task = TASK_REGISTRY[item_num]
    task = _resolve_dynamic_files(task)

    if task.skip:
        return f"# Item {item_num}: SKIP — {task.title}\n"

    tool_info = TOOL_INFO.get(task.tool, {})
    tool_name = tool_info.get("name", task.tool)

    lines = []
    lines.append(f"# Task Package: Item {item_num} — {task.title}\n")
    lines.append(f"**Type:** {task.task_type} | **Priority:** {task.priority} "
                 f"| **Tool:** {tool_name}\n")

    if task.blocked_by:
        lines.append(f"**Blocked by:** items {task.blocked_by} "
                     "(complete those first)\n")

    # --- TASK section ---
    lines.append("## TASK\n")
    lines.append(task.description + "\n")

    if task.output_files:
        lines.append("### Files to produce\n")
        for f in task.output_files:
            lines.append(f"- `{f}`")
        lines.append("")

    if task.notes:
        lines.append(f"### Notes\n\n{task.notes}\n")

    # --- CONVENTIONS section ---
    lines.append(CONVENTIONS)

    # --- SOURCE FILES section ---
    lines.append("## SOURCE FILES (current contents)\n")

    included_count = 0
    for rel_path in task.input_files:
        content = _read_file_safe(rel_path)
        if content is None:
            lines.append(f"### {rel_path}\n")
            lines.append("*File does not exist yet — will be created.*\n")
            continue

        included_count += 1
        # Determine language for syntax highlighting
        ext = Path(rel_path).suffix
        lang_map = {".py": "python", ".md": "markdown", ".sh": "bash",
                    ".toml": "toml", ".json": "json", ".yaml": "yaml",
                    ".yml": "yaml", ".tsx": "typescript", ".ts": "typescript",
                    ".js": "javascript"}
        lang = lang_map.get(ext, "")

        lines.append(f"### {rel_path}\n")
        lines.append(f"```{lang}")
        lines.append(content.rstrip())
        lines.append("```\n")

    if included_count == 0 and not task.input_files:
        lines.append("*No source files needed — this is a standalone task.*\n")

    # --- OUTPUT FORMAT section ---
    lines.append("## WHAT TO PRODUCE\n")
    lines.append("For each file you modify or create, output in this exact format:\n")
    lines.append("```")
    lines.append("=== FILE: path/to/file.py ===")
    lines.append("```python")
    lines.append("{complete file content}")
    lines.append("```")
    lines.append("=== END FILE ===")
    lines.append("```\n")
    lines.append("**Important:**")
    lines.append("- Output the COMPLETE file, not just diffs")
    lines.append("- Use the exact file paths shown above")
    lines.append("- Include ALL original content plus your changes")
    lines.append("- Do not add explanations between file blocks\n")

    # --- VERIFY section ---
    lines.append("## VERIFY (run after applying)\n")
    lines.append("```bash")
    lines.append(task.verification)
    lines.append("```\n")

    return "\n".join(lines)


def write_package(item_num: int) -> Path:
    """Generate and write a package file. Returns the output path."""
    PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    content = generate_package(item_num)
    out_path = PACKAGES_DIR / f"item_{item_num}.md"
    out_path.write_text(content, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Daily plan generation
# ---------------------------------------------------------------------------

DAY_1_SCHEDULE = [
    {"time": "Morning", "tool": "chatgpt", "items": [58, 59, 60, 62, 65, 66],
     "desc": "Quick docs/config (6 packages, ~15 min each)"},
    {"time": "Afternoon", "tool": "chatgpt", "items": [64, 67, 71],
     "desc": "Scripts/lint (3 packages)"},
    {"time": "Afternoon", "tool": "gemini", "items": [61],
     "desc": "Cross-link all specs (needs all spec files)"},
    {"time": "Evening", "tool": "claude_code", "items": [56],
     "desc": "GitHub API integration (interactive, hardest task)"},
]

DAY_2_SCHEDULE = [
    {"time": "Morning", "tool": "chatgpt", "items": [68, 69, 70, 72],
     "desc": "Log rotation, cleanup, smoke test"},
    {"time": "Afternoon", "tool": "grok", "items": [57],
     "desc": "Wire contributor metrics (depends on 56)"},
    {"time": "Afternoon", "tool": "grok", "items": [73],
     "desc": "Consolidate PM + orchestrator (large files)"},
    {"time": "Evening", "tool": "gemini", "items": [74],
     "desc": "Expand debugging/routing docs"},
]


def generate_daily_plan() -> str:
    """Generate a daily routing plan as markdown."""
    lines = []
    lines.append(f"# Daily Task Routing Plan — {date.today().isoformat()}\n")
    lines.append("## Tool Capacity\n")
    lines.append("| Tool | Daily Capacity | Context | Best For |")
    lines.append("|------|---------------|---------|----------|")
    for key, info in TOOL_INFO.items():
        lines.append(f"| {info['name']} | — | {info['context']} | {info['best_for']} |")
    lines.append("")

    # Completion state
    completion = _load_completion()

    def _format_schedule(day_name: str, schedule: list) -> None:
        lines.append(f"## {day_name}\n")
        lines.append("| Time | Tool | Items | Description | Status |")
        lines.append("|------|------|-------|-------------|--------|")
        for slot in schedule:
            tool_name = TOOL_INFO.get(slot["tool"], {}).get("name", slot["tool"])
            items_str = ", ".join(str(i) for i in slot["items"])
            statuses = [completion.get(str(i), {}).get("status", "pending")
                        for i in slot["items"]]
            if all(s == "completed" for s in statuses):
                status = "DONE"
            elif any(s == "completed" for s in statuses):
                status = "PARTIAL"
            elif any(s == "blocked" for s in statuses):
                status = "BLOCKED"
            else:
                status = "pending"
            lines.append(
                f"| {slot['time']} | {tool_name} | {items_str} "
                f"| {slot['desc']} | {status} |"
            )
        lines.append("")

    _format_schedule("Day 1 (12 items)", DAY_1_SCHEDULE)
    _format_schedule("Day 2 (7 items)", DAY_2_SCHEDULE)

    # Workflow instructions
    lines.append("## Workflow\n")
    lines.append("1. Open the package file: `api/packages/item_{N}.md`")
    lines.append("2. Copy the entire contents")
    lines.append("3. Paste into the designated tool")
    lines.append("4. Copy the AI's response into a file, e.g. `output_58.txt`")
    lines.append("5. Apply: `python scripts/apply_package_result.py --item 58 "
                 "--input output_58.txt`")
    lines.append("6. Verify: run the verification command shown in the package")
    lines.append("7. Commit if passing\n")

    # Summary
    total = sum(1 for t in TASK_REGISTRY.values() if not t.skip)
    done = sum(1 for v in completion.values() if v.get("status") == "completed")
    lines.append(f"## Progress: {done}/{total} items completed\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate self-contained task packages for multi-tool AI workflow"
    )
    parser.add_argument(
        "--item", type=int, nargs="+",
        help="Item number(s) to generate (56–74)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Generate packages for all non-skip items",
    )
    parser.add_argument(
        "--daily-plan", action="store_true",
        help="Generate all packages + daily routing plan",
    )
    parser.add_argument(
        "--init-completion", action="store_true",
        help="Initialize completion.json from registry",
    )
    args = parser.parse_args()

    if not any([args.item, args.all, args.daily_plan, args.init_completion]):
        parser.print_help()
        sys.exit(1)

    # Ensure completion.json exists
    if args.init_completion or not COMPLETION_FILE.is_file():
        data = _init_completion()
        _save_completion(data)
        print(f"Initialized {COMPLETION_FILE}")
        if args.init_completion and not any([args.item, args.all, args.daily_plan]):
            return

    items_to_generate: list[int] = []

    if args.daily_plan or args.all:
        items_to_generate = [
            num for num, task in sorted(TASK_REGISTRY.items()) if not task.skip
        ]
    elif args.item:
        items_to_generate = args.item

    # Generate packages
    for num in items_to_generate:
        path = write_package(num)
        task = TASK_REGISTRY.get(num)
        status = "SKIP" if (task and task.skip) else "OK"
        print(f"  [{status}] {path.name}")

    # Generate daily plan
    if args.daily_plan:
        plan_content = generate_daily_plan()
        plan_path = PACKAGES_DIR / "daily_plan.md"
        plan_path.write_text(plan_content, encoding="utf-8")
        print(f"  [PLAN] {plan_path.name}")

    print(f"\nPackages written to {PACKAGES_DIR}/")


if __name__ == "__main__":
    main()
