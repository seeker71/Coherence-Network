# Spec: Project Manager Load Backlog — Malformed Input Test Coverage

## Purpose

The `load_backlog()` function in `api/scripts/project_manager.py` parses a Markdown file to extract numbered work items. Without explicit test coverage for malformed input, the parser's defensive behavior against unnumbered lines, blank lines, comment lines, and other invalid formats is unverified. This spec formalizes the expected behavior when `load_backlog()` encounters mixed or malformed backlog content, ensuring the pipeline never silently ingests garbage items or crashes on unexpected input.

## Requirements

- [ ] `load_backlog()` returns only lines that match the pattern `\d+\.\s+(.+)` (numbered list items), in order.
- [ ] Lines without a numeric prefix (e.g., plain paragraphs, headers, blank lines, comment lines starting with `#`) are silently skipped — never raised as errors and never included in results.
- [ ] Lines that start with `#` (Markdown headers or comments) are excluded even if they contain a `1.` substring elsewhere in the line.
- [ ] `load_backlog()` returns `[]` (empty list) when the backlog file is missing, empty, or contains only non-matching lines.
- [ ] `load_backlog()` preserves the relative order of valid numbered items even when non-matching lines are interspersed.
- [ ] `load_backlog()` strips leading/trailing whitespace from each extracted item.
- [ ] The test `test_load_backlog_malformed_missing_number_prefix` in `api/tests/test_project_manager.py` encodes all of the above behaviors and passes under `pytest`.

## Research Inputs

- `2025-01-01` - [api/scripts/project_manager.py](../api/scripts/project_manager.py) - Contains `_parse_backlog_file()` and `load_backlog()` implementations; `re.match(r"^\d+\.\s+(.+)$", line)` is the parsing regex.
- `2025-01-01` - [api/tests/test_project_manager.py](../api/tests/test_project_manager.py) - Existing test file that already contains `test_load_backlog_malformed_missing_number_prefix` covering mixed-line input; this spec formalizes what that test proves.
- `2025-01-01` - [specs/005-project-manager-orchestrator.md](005-project-manager-orchestrator.md) - Parent spec defining the project manager contract and the role of `load_backlog()`.

## Task Card

```yaml
goal: Confirm and document the malformed-input contract for load_backlog(); ensure the test suite exercises all specified edge cases.
files_allowed:
  - api/tests/test_project_manager.py
  - api/scripts/project_manager.py
  - specs/040-project-manager-load-backlog-malformed-test.md
done_when:
  - cd api && pytest -v tests/test_project_manager.py::test_load_backlog_malformed_missing_number_prefix passes
  - cd api && pytest -v tests/test_project_manager.py::test_load_backlog_empty_file passes
  - cd api && pytest -v tests/test_project_manager.py::test_load_backlog_numbered_items passes
  - All 3 tests above pass in a single pytest run with no warnings about the backlog parser
commands:
  - cd api && pytest -v tests/test_project_manager.py -k "backlog"
constraints:
  - Do not modify tests to force passing — fix the implementation if tests fail
  - Changes scoped to listed files only
  - No new API endpoints, no schema migrations
```

## API Contract

N/A — no API contract changes in this spec. `load_backlog()` is an internal script function with no HTTP surface.

## Data Model

N/A — no model changes in this spec.

The backlog file format is plain Markdown with numbered list items:

```
# Optional header (skipped)
1. First work item
Unnumbered narrative line (skipped)
2. Second work item
  * bullet point (skipped)
3. Third work item
```

Parsed output: `["First work item", "Second work item", "Third work item"]`

## Files to Create/Modify

- `api/tests/test_project_manager.py` — primary location of the acceptance test; may need additional edge-case tests added.
- `api/scripts/project_manager.py` — `_parse_backlog_file()` function; fix only if current behavior diverges from spec.
- `specs/040-project-manager-load-backlog-malformed-test.md` — this spec file.

## Acceptance Tests

- `api/tests/test_project_manager.py::test_load_backlog_malformed_missing_number_prefix` — mixed numbered and unnumbered lines: asserts only numbered items are returned.
- `api/tests/test_project_manager.py::test_load_backlog_empty_file` — missing/empty file: asserts `[]`.
- `api/tests/test_project_manager.py::test_load_backlog_numbered_items` — well-formed backlog: asserts correct parse and ordering.

## Verification Scenarios

### Scenario 1: Well-formed backlog parses correctly

**Setup**: Create a temp file with three numbered items and no malformed lines.

```bash
python3 -c "
import tempfile, os, sys
sys.path.insert(0, 'api')
import api.scripts.project_manager as pm
with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False) as f:
    f.write('1. First item\n2. Second item\n3. Third item\n')
    path = f.name
pm.BACKLOG_FILE = path
result = pm.load_backlog()
assert result == ['First item', 'Second item', 'Third item'], result
print('PASS:', result)
os.unlink(path)
"
```

**Expected result**: `['First item', 'Second item', 'Third item']` — 3 items, correct order.

**Edge case**: Items with leading/trailing whitespace in the file must be stripped: `"  1. Item with spaces  "` → `"Item with spaces"`.

---

### Scenario 2: Malformed / mixed content — unnumbered lines skipped

**Setup**: Create a temp file mixing numbered items with plain paragraphs, headers, and blank lines.

```bash
python3 -c "
import tempfile, os, sys
sys.path.insert(0, 'api')
import api.scripts.project_manager as pm
content = '# Section header\n1. First item\nUnnumbered narrative line\n2. Second item\nAnother line without number\n\n3. Third item\n'
with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False) as f:
    f.write(content)
    path = f.name
pm.BACKLOG_FILE = path
result = pm.load_backlog()
assert result == ['First item', 'Second item', 'Third item'], result
print('PASS:', result)
os.unlink(path)
"
```

**Expected result**: `['First item', 'Second item', 'Third item']` — header, blank, and narrative lines silently dropped; order preserved.

**Edge case**: A line like `# 1. Looks numbered but is a header` must NOT be included (starts with `#`).

---

### Scenario 3: Empty / missing file returns empty list

**Setup**: Point `BACKLOG_FILE` at a path that does not exist.

```bash
python3 -c "
import sys
sys.path.insert(0, 'api')
import api.scripts.project_manager as pm
pm.BACKLOG_FILE = '/tmp/does_not_exist_xyz.md'
result = pm.load_backlog()
assert result == [], result
print('PASS (empty):', result)
"
```

**Expected result**: `[]` — no exception raised, no crash.

**Edge case**: File exists but is entirely blank — also returns `[]`.

---

### Scenario 4: pytest run — all backlog tests pass

**Setup**: Cloned repo with `api/` dependencies installed (`pip install -e api/`).

**Action**:
```bash
cd api && pytest -v tests/test_project_manager.py -k "backlog" --tb=short
```

**Expected result**:
```
tests/test_project_manager.py::test_load_backlog_empty_file PASSED
tests/test_project_manager.py::test_load_backlog_malformed_missing_number_prefix PASSED
tests/test_project_manager.py::test_load_backlog_numbered_items PASSED
3 passed
```

No failures, no errors, no skips.

**Edge case**: If `BACKLOG_FILE` module-level variable was mutated by a prior test and not restored, tests may interfere. Each test must set `pm.BACKLOG_FILE` in its own `tmp_path` fixture scope.

---

### Scenario 5: Full create-read cycle via project manager dry-run

**Setup**: A backlog file with 2 valid items and 1 malformed line exists at a temp path.

**Action**:
```bash
python3 -c "
import tempfile, os, sys
sys.path.insert(0, 'api')
import api.scripts.project_manager as pm
content = '1. First item\nUnnumbered line\n2. Second item\n'
with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False) as f:
    f.write(content)
    path = f.name
pm.BACKLOG_FILE = path
items = pm.load_backlog()
assert len(items) == 2, items
assert 'Unnumbered line' not in items
print('PASS: got', items)
os.unlink(path)
"
```

**Expected result**: Exit 0. `items` contains only `['First item', 'Second item']`. The string `'Unnumbered line'` does not appear in results.

**Edge case**: If the backlog file has zero valid items after skipping malformed lines, `load_backlog()` returns `[]` — does not crash or loop forever.

## Concurrency Behavior

- **Read operations**: `load_backlog()` reads the file once per call; safe for concurrent access — no shared mutable state beyond `BACKLOG_FILE` module variable (tests must isolate this).
- **Write operations**: N/A — `load_backlog()` is read-only.
- **Test isolation**: Tests that mutate `pm.BACKLOG_FILE` must restore the original value (or use `monkeypatch`) to prevent cross-test contamination.

## Out of Scope

- Meta-backlog interleaving behavior (`PIPELINE_META_BACKLOG` / `PIPELINE_META_RATIO`) — covered by separate tests.
- `refresh_backlog()` or `_run_acceptance_gate()` — separate concerns.
- Backlog file encoding issues (non-UTF-8 content) — out of scope for this spec; UTF-8 is assumed.

## Risks and Assumptions

- **Risk**: The `pm.BACKLOG_FILE` module-level variable is mutated by multiple tests without cleanup, causing test order-dependency. Mitigation: use `monkeypatch` or explicit save/restore in each test.
- **Assumption**: The current `_parse_backlog_file()` regex `r"^\d+\.\s+(.+)$"` is correct and should not be changed. This spec validates existing behavior — it does not propose new behavior.
- **Assumption**: Lines matching `r"^\d+\."` but starting with `#` (e.g., `# 1. header`) are correctly excluded by the `not line.startswith("#")` guard already present in `_parse_backlog_file()`.

## Known Gaps and Follow-up Tasks

- The test does not yet assert behavior for lines with unusual Unicode or embedded newlines — acceptable for MVP.
- No property-based (Hypothesis) tests exist for the parser — follow-up task if parser complexity grows.

## Failure / Retry Reflection

- **Failure mode**: Test mutates `pm.BACKLOG_FILE` and does not restore it → subsequent tests see wrong path → false positives or negatives.
- **Blind spot**: Module-level state is easy to overlook in test authoring.
- **Next action**: Add `monkeypatch.setattr(pm, "BACKLOG_FILE", str(p))` to all tests that need a custom path.

## Decision Gates

None — this spec formalizes existing behavior and adds test coverage; no architecture decisions required.

## Verification

```bash
cd api && pytest -v tests/test_project_manager.py -k "backlog" --tb=short
python3 scripts/validate_spec_quality.py --file specs/040-project-manager-load-backlog-malformed-test.md
```
