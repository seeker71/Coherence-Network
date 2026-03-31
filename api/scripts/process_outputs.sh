#!/usr/bin/env bash
# Process AI output files and apply them to the codebase.
#
# Workflow:
#   1. Paste AI output into api/packages/output_58.txt (number = item number)
#   2. Run: ./scripts/process_outputs.sh
#   3. Script applies each file, runs verification, auto-commits if passing
#   4. On verification failure: auto-heals with local Ollama model (free)
#
# Options:
#   --watch       Re-check every 10s for new files (Ctrl-C to stop)
#   --no-commit   Apply and verify but don't git commit
#   --no-heal     Skip Ollama auto-heal on failure
#   --dry-run     Parse and show what would be written, don't write
#   --model NAME  Ollama model for healing (default: $OLLAMA_MODEL or qwen2.5-coder:14b)
#
# Zero Claude Code tokens used. Pure bash + python + local Ollama.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$API_DIR")"
PACKAGES_DIR="$API_DIR/packages"
PYTHON="${API_DIR}/.venv/bin/python"

WATCH=false
NO_COMMIT=false
NO_HEAL=false
DRY_RUN=false
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3-coder:30b}"
HEAL_RETRIES=3

for arg in "$@"; do
    case "$arg" in
        --watch)     WATCH=true ;;
        --no-commit) NO_COMMIT=true ;;
        --no-heal)   NO_HEAL=true ;;
        --dry-run)   DRY_RUN=true; NO_COMMIT=true ;;
        --model=*)   OLLAMA_MODEL="${arg#--model=}" ;;
        -h|--help)
            echo "Usage: $0 [--watch] [--no-commit] [--no-heal] [--dry-run] [--model=NAME]"
            echo ""
            echo "Drop AI output files as api/packages/output_N.txt then run this script."
            echo ""
            echo "  --watch         Poll every 10s for new output files"
            echo "  --no-commit     Apply + verify but skip git commit"
            echo "  --no-heal       Skip auto-heal with Ollama on verification failure"
            echo "  --dry-run       Show what would be written without writing"
            echo "  --model=NAME    Ollama model for healing (default: $OLLAMA_MODEL)"
            echo ""
            echo "Pipeline: apply → verify → [heal with Ollama x3] → commit"
            exit 0
            ;;
    esac
done

if [ ! -x "$PYTHON" ]; then
    echo "Error: Python not found at $PYTHON"
    echo "Run: cd api && python -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    exit 1
fi

process_one() {
    local output_file="$1"
    local basename
    basename="$(basename "$output_file")"

    # Extract item number from filename: output_58.txt -> 58
    local item_num
    item_num="$(echo "$basename" | sed -n 's/^output_\([0-9]*\)\.txt$/\1/p')"
    if [ -z "$item_num" ]; then
        echo "  SKIP: $basename (filename must be output_N.txt)"
        return 1
    fi

    echo ""
    echo "======================================"
    echo "  Processing item $item_num from $basename"
    echo "======================================"

    # Build apply args — always --no-verify first, we verify separately to capture output
    local apply_args="--item $item_num --input $output_file --no-verify"
    if [ "$DRY_RUN" = true ]; then
        apply_args="--item $item_num --input $output_file --dry-run"
    fi

    # Apply files
    if ! "$PYTHON" "$SCRIPT_DIR/apply_package_result.py" $apply_args; then
        echo "  FAILED: Could not parse/apply item $item_num"
        mv "$output_file" "${output_file%.txt}.failed"
        return 1
    fi

    if [ "$DRY_RUN" = true ]; then
        return 0
    fi

    # Run verification
    echo ""
    echo "  Running verification for item $item_num..."
    local error_file="$PACKAGES_DIR/error_${item_num}.txt"

    # Get the verification command from the registry
    local verify_cmd
    verify_cmd=$("$PYTHON" -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR')
from generate_task_package import TASK_REGISTRY
t = TASK_REGISTRY.get($item_num)
print(t.verification if t else '')
")

    if [ -z "$verify_cmd" ]; then
        echo "  No verification command for item $item_num, skipping verify"
    else
        echo "  Verify: $verify_cmd"
        local verify_ok=false
        if (cd "$PROJECT_ROOT" && eval "$verify_cmd") > "$error_file" 2>&1; then
            verify_ok=true
            echo "  PASSED"
            rm -f "$error_file"
        else
            echo "  FAILED — verification error:"
            tail -20 "$error_file" | sed 's/^/    /'

            # Auto-heal with Ollama if enabled
            if [ "$NO_HEAL" = false ]; then
                echo ""
                echo "  Attempting auto-heal with Ollama ($OLLAMA_MODEL)..."
                if "$PYTHON" "$SCRIPT_DIR/heal_with_ollama.py" \
                    --item "$item_num" \
                    --error-file "$error_file" \
                    --model "$OLLAMA_MODEL" \
                    --max-retries "$HEAL_RETRIES"; then
                    verify_ok=true
                    echo "  HEALED successfully"
                    rm -f "$error_file"
                else
                    echo "  Auto-heal failed after $HEAL_RETRIES attempts"
                    echo "  Error saved: $error_file"
                    echo "  Manual fix needed. To retry healing:"
                    echo "    python scripts/heal_with_ollama.py --item $item_num --error-file $error_file"
                fi
            fi
        fi

        if [ "$verify_ok" = false ]; then
            mv "$output_file" "${output_file%.txt}.failed"
            return 1
        fi
    fi

    # Auto-commit if enabled
    if [ "$NO_COMMIT" = false ]; then
        echo ""
        echo "  Committing item $item_num..."
        cd "$PROJECT_ROOT"
        git add -A
        git commit -m "[task-package] Apply item $item_num" 2>/dev/null || true
        cd "$API_DIR"
    fi

    # Mark as done
    mv "$output_file" "${output_file%.txt}.done"
    echo "  DONE: $basename -> $(basename "${output_file%.txt}.done")"
}

process_all() {
    local found=0
    for f in "$PACKAGES_DIR"/output_*.txt; do
        [ -f "$f" ] || continue
        found=$((found + 1))
        process_one "$f" || true
    done

    if [ "$found" -eq 0 ]; then
        return 1  # nothing to process
    fi
    return 0
}

cd "$API_DIR"

if [ "$WATCH" = true ]; then
    echo "Watching $PACKAGES_DIR for output_*.txt files... (Ctrl-C to stop)"
    echo "Pipeline: apply → verify → heal (Ollama $OLLAMA_MODEL) → commit"
    echo "Drop files like: output_58.txt, output_59.txt, etc."
    echo ""
    while true; do
        if process_all; then
            echo ""
            echo "--- Waiting for more files ---"
        fi
        sleep 10
    done
else
    if ! process_all; then
        echo "No output_*.txt files found in $PACKAGES_DIR"
        echo ""
        echo "Workflow:"
        echo "  1. Paste AI output into api/packages/output_58.txt"
        echo "  2. Run: ./scripts/process_outputs.sh"
        echo ""
        echo "Pipeline: apply → verify → heal (Ollama) → commit"
        echo "Or use --watch to poll continuously."
    fi
fi
