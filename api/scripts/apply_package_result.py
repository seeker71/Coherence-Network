#!/usr/bin/env python3
"""Apply AI-generated task package results back to the codebase.

Parses AI output containing file blocks delimited by:
    === FILE: path/to/file.py ===
    ```python
    {content}
    ```
    === END FILE ===

Usage:
    python scripts/apply_package_result.py --item 58 --input output_58.txt
    python scripts/apply_package_result.py --item 58 --input output_58.txt --dry-run
    python scripts/apply_package_result.py --item 58 --input output_58.txt --no-verify
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
API_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = API_DIR.parent
PACKAGES_DIR = API_DIR / "packages"
COMPLETION_FILE = PACKAGES_DIR / "completion.json"

# ---------------------------------------------------------------------------
# File block parser
# ---------------------------------------------------------------------------

# Match: === FILE: some/path.py ===
FILE_START_RE = re.compile(r"^=== FILE:\s*(.+?)\s*===$", re.MULTILINE)
# Match: === END FILE ===
FILE_END_RE = re.compile(r"^=== END FILE ===$", re.MULTILINE)
# Match code fence: ```lang or ```
FENCE_OPEN_RE = re.compile(r"^```\w*\s*$", re.MULTILINE)
FENCE_CLOSE_RE = re.compile(r"^```\s*$", re.MULTILINE)


def parse_file_blocks(text: str) -> list[tuple[str, str]]:
    """Parse AI output into (path, content) pairs.

    Supports format:
        === FILE: path ===
        ```lang
        {content}
        ```
        === END FILE ===

    FILE markers must be at the start of a line. Content inside code fences
    may contain nested fences (e.g. markdown docs with code examples).

    Returns list of (relative_path, file_content) tuples.
    """
    # Normalize line endings (CRLF → LF)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    blocks: list[tuple[str, str]] = []

    # Strategy: find all FILE_START markers and extract content between them and END FILE
    pos = 0
    while pos < len(text):
        start_match = FILE_START_RE.search(text, pos)
        if not start_match:
            break

        file_path = start_match.group(1).strip()
        # Strip (NEW) suffix if present
        file_path = re.sub(r"\s*\(NEW\)\s*$", "", file_path)

        search_from = start_match.end()

        # Find the === END FILE === marker
        end_match = FILE_END_RE.search(text, search_from)
        if not end_match:
            # No end marker — try to find the next FILE start as boundary
            next_start = FILE_START_RE.search(text, search_from)
            if next_start:
                raw_content = text[search_from:next_start.start()]
            else:
                raw_content = text[search_from:]
            pos = next_start.start() if next_start else len(text)
        else:
            raw_content = text[search_from:end_match.start()]
            pos = end_match.end()

        # Extract content from within code fences if present
        content = _extract_from_fences(raw_content)
        blocks.append((file_path, content))

    return blocks


def _extract_from_fences(raw: str) -> str:
    """Extract content from within the outermost ``` fences.

    Handles nested fences (e.g. markdown files containing code blocks)
    by stripping only the first opening and last closing fence.
    """
    lines = raw.strip().split("\n")
    if not lines:
        return ""

    # Strip the first line if it's an opening fence
    if lines[0].strip().startswith("```"):
        lines = lines[1:]

    # Strip the last line if it's a closing fence
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# File writer
# ---------------------------------------------------------------------------


def write_files(
    blocks: list[tuple[str, str]], dry_run: bool = False
) -> list[tuple[str, str]]:
    """Write parsed file blocks to disk.

    Returns list of (path, status) where status is 'written', 'created', or 'skipped'.
    """
    results = []
    for rel_path, content in blocks:
        abs_path = PROJECT_ROOT / rel_path
        existed = abs_path.is_file()

        if dry_run:
            action = "would update" if existed else "would create"
            print(f"  [DRY-RUN] {action}: {rel_path} ({len(content)} chars)")
            results.append((rel_path, "skipped"))
            continue

        # Create parent directories if needed
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        abs_path.write_text(content + "\n", encoding="utf-8")
        action = "updated" if existed else "created"
        print(f"  [{action.upper()}] {rel_path} ({len(content)} chars)")
        results.append((rel_path, action))

    return results


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def run_verification(item_num: int) -> tuple[bool, str]:
    """Run verification command for an item. Returns (passed, output).

    Security: shell=True is required for pipes/redirects/globs in verification
    commands. Commands come from TASK_REGISTRY (hardcoded, not user input).
    """
    # Import the registry to get verification command
    sys.path.insert(0, str(SCRIPT_DIR))
    from generate_task_package import TASK_REGISTRY

    task = TASK_REGISTRY.get(item_num)
    if not task:
        return False, f"Item {item_num} not in registry"

    cmd = task.verification
    print(f"\n  Running verification: {cmd}")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PROJECT_ROOT),
        )
        output = result.stdout + result.stderr
        passed = result.returncode == 0
        if passed:
            print("  PASSED")
        else:
            print(f"  FAILED (exit code {result.returncode})")
            if output.strip():
                # Show last 20 lines of output
                lines = output.strip().split("\n")
                for line in lines[-20:]:
                    print(f"    {line}")
        return passed, output
    except subprocess.TimeoutExpired:
        return False, "Verification timed out after 120s"
    except Exception as e:
        return False, f"Verification error: {e}"


# ---------------------------------------------------------------------------
# Completion tracking
# ---------------------------------------------------------------------------


def update_completion(item_num: int, status: str) -> None:
    """Update completion.json for an item."""
    data = {}
    if COMPLETION_FILE.is_file():
        try:
            data = json.loads(COMPLETION_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    key = str(item_num)
    if key not in data:
        data[key] = {}
    data[key]["status"] = status

    PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    COMPLETION_FILE.write_text(json.dumps(data, indent=2) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply AI-generated task package results to the codebase"
    )
    parser.add_argument(
        "--item", type=int, required=True,
        help="Item number this result is for",
    )
    parser.add_argument(
        "--input", type=str, required=True,
        dest="input_file",
        help="Path to the AI output file",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be written without writing",
    )
    parser.add_argument(
        "--no-verify", action="store_true",
        help="Skip verification step",
    )
    args = parser.parse_args()

    # Read input
    input_path = Path(args.input_file)
    if not input_path.is_file():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    text = input_path.read_text(encoding="utf-8", errors="replace")
    print(f"Read {len(text)} chars from {input_path}\n")

    # Parse file blocks
    blocks = parse_file_blocks(text)
    if not blocks:
        print("No file blocks found in input.")
        print("Expected format:")
        print("  === FILE: path/to/file.py ===")
        print("  ```python")
        print("  {content}")
        print("  ```")
        print("  === END FILE ===")
        sys.exit(1)

    print(f"Found {len(blocks)} file block(s):")
    for path, content in blocks:
        print(f"  - {path} ({len(content)} chars)")
    print()

    # Write files
    results = write_files(blocks, dry_run=args.dry_run)

    if args.dry_run:
        print("\nDry run complete — no files written.")
        return

    # Verify
    if not args.no_verify:
        passed, _ = run_verification(args.item)
        status = "completed" if passed else "failed"
    else:
        status = "applied"
        print("\nSkipped verification (--no-verify)")

    # Update completion tracking
    update_completion(args.item, status)
    print(f"\nItem {args.item} status: {status}")


if __name__ == "__main__":
    main()
