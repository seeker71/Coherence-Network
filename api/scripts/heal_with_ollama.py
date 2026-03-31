#!/usr/bin/env python3
"""Auto-fix failing task packages using a local Ollama model.

When apply_package_result.py verification fails, this script:
1. Reads the error output + relevant source files
2. Sends a repair prompt to Ollama (local, free, unlimited)
3. Parses the response for === FILE: === blocks
4. Applies the fix and re-verifies
5. Repeats up to --max-retries times

Usage:
    python scripts/heal_with_ollama.py --item 56 --error "TypeError: str | None..."
    python scripts/heal_with_ollama.py --item 56 --error-file /tmp/error.txt
    python scripts/heal_with_ollama.py --item 56 --error-file /tmp/error.txt --model codellama

Requires: Ollama running locally (ollama serve)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Ensure we can import sibling scripts
SCRIPT_DIR = Path(__file__).resolve().parent
API_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = API_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from apply_package_result import parse_file_blocks, write_files
from generate_task_package import TASK_REGISTRY, _read_file_safe, _resolve_dynamic_files

# ---------------------------------------------------------------------------
# Ollama client
# ---------------------------------------------------------------------------

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3-coder:30b")


def _detect_model(model: str) -> str:
    """If the requested model isn't available, pick the best local alternative."""
    import httpx

    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if r.status_code != 200:
            return model
        available = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return model

    if model in available:
        return model

    # Prefer coding models, then anything available
    preferences = ["qwen3-coder:30b", "qwen3-coder", "glm-4.7-flash:latest"]
    for pref in preferences:
        if pref in available:
            print(f"  Model {model} not found, using {pref}")
            return pref

    if available:
        fallback = available[0]
        print(f"  Model {model} not found, using {fallback}")
        return fallback

    return model


def ollama_generate(prompt: str, model: str, timeout: int = 300) -> str:
    """Call Ollama OpenAI-compatible endpoint and return the response text."""
    import httpx

    model = _detect_model(model)

    # Use OpenAI-compatible /v1/chat/completions (works across Ollama versions)
    url = f"{OLLAMA_URL}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 8192,
        "stream": False,
    }

    print(f"  Calling Ollama ({model})...")
    start = time.time()

    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            elapsed = time.time() - start
            choices = data.get("choices", [])
            response = choices[0]["message"]["content"] if choices else ""
            print(f"  Ollama responded in {elapsed:.1f}s ({len(response)} chars)")
            return response
    except Exception as e:
        print(f"  Ollama error: {e}")
        print(f"  Is Ollama running? Try: ollama serve")
        print(f"  Available models: ollama list")
        return ""


# ---------------------------------------------------------------------------
# Build repair prompt
# ---------------------------------------------------------------------------


def build_repair_prompt(item_num: int, error_text: str) -> str:
    """Build a focused repair prompt with error + affected files."""
    task = TASK_REGISTRY.get(item_num)
    if not task:
        return ""

    task = _resolve_dynamic_files(task)

    lines = []
    lines.append("# Fix Request\n")
    lines.append(f"Task: Item {item_num} — {task.title}\n")
    lines.append("## Error\n")
    lines.append("The following error occurred after applying changes:\n")
    lines.append("```")
    # Trim error to last 80 lines to stay within context
    error_lines = error_text.strip().split("\n")
    if len(error_lines) > 80:
        error_lines = error_lines[-80:]
    lines.append("\n".join(error_lines))
    lines.append("```\n")

    lines.append("## Project Constraints\n")
    lines.append("- Python 3.9 (no `str | None` in Pydantic models, use `Optional[str]`)")
    lines.append("- `from __future__ import annotations` helps for function signatures but NOT Pydantic fields")
    lines.append("- FastAPI + Pydantic v2")
    lines.append("- Do NOT modify test files — fix the implementation\n")

    lines.append("## Current Source Files\n")

    # Include output files (the ones that were modified)
    files_to_include = list(task.output_files)
    # Also include input files that might be relevant
    for f in task.input_files:
        if f not in files_to_include:
            files_to_include.append(f)

    for rel_path in files_to_include:
        # Strip (NEW) suffix
        clean_path = rel_path.replace(" (NEW)", "")
        content = _read_file_safe(clean_path)
        if content is None:
            continue

        ext = Path(clean_path).suffix
        lang_map = {".py": "python", ".md": "markdown", ".sh": "bash",
                    ".toml": "toml", ".json": "json"}
        lang = lang_map.get(ext, "")

        lines.append(f"### {clean_path}\n")
        lines.append(f"```{lang}")
        # Trim very large files
        content_lines = content.split("\n")
        if len(content_lines) > 300:
            lines.append("\n".join(content_lines[:300]))
            lines.append(f"\n# ... truncated ({len(content_lines)} total lines)")
        else:
            lines.append(content.rstrip())
        lines.append("```\n")

    lines.append("## Instructions\n")
    lines.append("Fix the error above. Output ONLY the files that need changes.")
    lines.append("Use this exact format for each file:\n")
    lines.append("```")
    lines.append("=== FILE: path/to/file.py ===")
    lines.append("```python")
    lines.append("{complete fixed file}")
    lines.append("```")
    lines.append("=== END FILE ===")
    lines.append("```\n")
    lines.append("Output the COMPLETE file content, not diffs.")
    lines.append("Only output files that need changes to fix the error.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def run_verification(item_num: int) -> tuple[bool, str]:
    """Run verification for an item. Returns (passed, output)."""
    task = TASK_REGISTRY.get(item_num)
    if not task:
        return False, f"Item {item_num} not in registry"

    cmd = task.verification
    print(f"  Verifying: {cmd}")

    try:
        result = subprocess.run(
            cmd,
            shell=True,  # Required for pipes/globs; commands from trusted TASK_REGISTRY
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PROJECT_ROOT),
        )
        output = result.stdout + result.stderr
        passed = result.returncode == 0
        return passed, output
    except subprocess.TimeoutExpired:
        return False, "Verification timed out after 120s"
    except Exception as e:
        return False, f"Verification error: {e}"


# ---------------------------------------------------------------------------
# Main heal loop
# ---------------------------------------------------------------------------


def heal(item_num: int, error_text: str, model: str, max_retries: int, dry_run: bool) -> bool:
    """Attempt to heal a failing item. Returns True if fixed."""

    for attempt in range(1, max_retries + 1):
        print(f"\n--- Heal attempt {attempt}/{max_retries} for item {item_num} ---\n")

        prompt = build_repair_prompt(item_num, error_text)
        if not prompt:
            print(f"  Could not build repair prompt for item {item_num}")
            return False

        # Call Ollama
        response = ollama_generate(prompt, model=model)
        if not response:
            print("  No response from Ollama. Retrying...")
            continue

        # Parse file blocks from response
        blocks = parse_file_blocks(response)
        if not blocks:
            print("  No file blocks found in Ollama response. Retrying...")
            # Save the raw response for debugging
            debug_path = API_DIR / "packages" / f"heal_{item_num}_attempt{attempt}.txt"
            debug_path.write_text(response, encoding="utf-8")
            print(f"  Raw response saved to {debug_path}")
            continue

        print(f"  Found {len(blocks)} file(s) to fix:")
        for path, content in blocks:
            print(f"    - {path} ({len(content)} chars)")

        if dry_run:
            print("  [DRY-RUN] Would write files")
            return False

        # Apply fixes
        write_files(blocks, dry_run=False)

        # Re-verify
        passed, output = run_verification(item_num)
        if passed:
            print(f"\n  HEALED on attempt {attempt}!")
            return True

        # Verification still failing — feed error back for next attempt
        print(f"  Still failing after attempt {attempt}")
        error_text = output
        # Show last few lines
        for line in output.strip().split("\n")[-10:]:
            print(f"    {line}")

    print(f"\n  Failed to heal item {item_num} after {max_retries} attempts")
    return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-fix failing task packages using local Ollama model"
    )
    parser.add_argument(
        "--item", type=int, required=True,
        help="Item number to heal",
    )
    error_group = parser.add_mutually_exclusive_group(required=True)
    error_group.add_argument(
        "--error", type=str,
        help="Error text (inline)",
    )
    error_group.add_argument(
        "--error-file", type=str,
        help="Path to file containing error output",
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL,
        help=f"Ollama model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--max-retries", type=int, default=3,
        help="Max heal attempts (default: 3)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be done without writing",
    )
    args = parser.parse_args()

    if args.error_file:
        error_path = Path(args.error_file)
        if not error_path.is_file():
            print(f"Error file not found: {error_path}")
            sys.exit(1)
        error_text = error_path.read_text(encoding="utf-8", errors="replace")
    else:
        error_text = args.error

    success = heal(
        item_num=args.item,
        error_text=error_text,
        model=args.model,
        max_retries=args.max_retries,
        dry_run=args.dry_run,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
