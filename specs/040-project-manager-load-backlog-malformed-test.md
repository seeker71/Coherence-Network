# Spec: Project Manager load_backlog — Malformed File (Missing Numbers) Test

**ID**: 040-project-manager-load-backlog-malformed-test
**Type**: test
**Status**: implemented
**Priority**: medium

---

## Summary

Ensure the project manager's `load_backlog` function is test-covered when the backlog file
contains lines that lack the required `\d+\. ` number prefix. The parser must skip
un-numbered lines, returning only valid numbered items with order preserved and no crash.

This spec covers the test implementation only — the parsing logic itself (`_parse_backlog_file`)
is already correct and is not modified.

---

## Goal

Add a focused regression test that protects against future regressions in `load_backlog`/
`_parse_backlog_file` when backlog files contain:

- Lines that begin with text (no leading number)
- Comment lines (`#`)
- Mixed numbered and unnumbered lines
- Edge cases: blank lines, number-only lines, numbers with no space

---

## Background

`_parse_backlog_file` (api/scripts/project_manager.py:193) uses the regex `^\d+\.\s+(.+)$`
to extract work items. Lines that don't match are silently skipped. This is the intended
behaviour per specs 005 and 006, but it lacked a dedicated regression test.

Without this test, a future change to the regex or the parse loop could silently break
backlog loading — items would disappear with no error, causing the pipeline to stall.

---

## Requirements

- [ ] A test named `test_load_backlog_malformed_missing_number_prefix` exists in
      `api/tests/test_project_manager.py`.
- [ ] The test writes a real file (via `tmp_path`) containing both numbered and
      unnumbered lines and calls `pm.load_backlog()` directly (no mocks, no HTTP).
- [ ] The test asserts the return value is exactly `["First item", "Second item"]` —
      unnumbered lines are absent and order is preserved.
- [ ] `pytest api/tests/test_project_manager.py -v` passes with this test included.

---

## API Contract

N/A — this feature is entirely a script-level unit test. No HTTP endpoints are added or
changed.

---

## Data Model

The backlog file format parsed by `_parse_backlog_file`:

| Line pattern               | Handling             |
|----------------------------|----------------------|
| `^\d+\.\s+(.+)$`           | Captured as work item |
| `^#.*`                     | Skipped (comment)    |
| Any other line             | Skipped (malformed)  |
| Empty / whitespace-only    | Skipped              |

Return type: `list[str]` — captured group 1 of each matching line, stripped.

---

## Files to Create / Modify

| File                                  | Change                                      |
|---------------------------------------|---------------------------------------------|
| `api/tests/test_project_manager.py`   | Add `test_load_backlog_malformed_missing_number_prefix` |

No other files are modified.

---

## Acceptance Tests

- [ ] Test `test_load_backlog_malformed_missing_number_prefix` is present in
      `api/tests/test_project_manager.py`.
- [ ] Given file content:
      ```
      1. First item
      Unnumbered line
      2. Second item
      Another line without number
      ```
      `pm.load_backlog()` returns `["First item", "Second item"]`.
- [ ] `pytest api/tests/test_project_manager.py -v` exits 0.
- [ ] No test in the file is modified to force passing (no mock bypass).

---

## Verification Scenarios

All scenarios are runnable against the repository as-is (no server required).

### Scenario 1 — Happy path: mixed numbered/unnumbered lines

**Setup**: backlog file with 2 numbered and 2 unnumbered lines.

```python
# tmp_path / "backlog.md"
"1. First item\n"
"Unnumbered line\n"
"2. Second item\n"
"Another line without number\n"
```

**Action**:
```bash
cd api && python3 -m pytest tests/test_project_manager.py::test_load_backlog_malformed_missing_number_prefix -v
```

**Expected result**:
```
PASSED tests/test_project_manager.py::test_load_backlog_malformed_missing_number_prefix
```
Return value is exactly `["First item", "Second item"]`; the two unnumbered lines are
absent from the list.

---

### Scenario 2 — All lines malformed (no numbered lines)

**Setup**: backlog file where every line lacks the `\d+. ` prefix.

```python
# tmp_path / "backlog.md"
"no number here\n"
"also no number\n"
"  still none  \n"
```

**Action**:
```python
p.write_text("no number here\nalso no number\n  still none  \n")
pm.BACKLOG_FILE = str(p)
items = pm.load_backlog()
assert items == []
```

**Expected result**: `items == []` — empty list, no crash, no exception.

---

### Scenario 3 — Comment lines are skipped (regression)

**Setup**: backlog file that mixes numbered items, comments, and unnumbered text.

```text
# This is a comment
1. Real task one
# another comment
Unnumbered prose
2. Real task two
```

**Action**:
```bash
cd api && python3 -c "
import sys; sys.path.insert(0,'.')
from scripts import project_manager as pm
import tempfile, os, pathlib
with tempfile.TemporaryDirectory() as d:
    p = pathlib.Path(d) / 'backlog.md'
    p.write_text('# This is a comment\n1. Real task one\n# another comment\nUnnumbered prose\n2. Real task two\n')
    pm.BACKLOG_FILE = str(p)
    print(pm.load_backlog())
"
```

**Expected result**: `['Real task one', 'Real task two']` — comments and prose lines
both excluded.

---

### Scenario 4 — Order preserved with non-sequential numbering

**Setup**: backlog file with out-of-order or non-sequential numbers.

```text
3. Task three first
1. Task one second
99. Task ninety-nine
Unnumbered line
```

**Action**:
```python
p.write_text("3. Task three first\n1. Task one second\n99. Task ninety-nine\nUnnumbered line\n")
pm.BACKLOG_FILE = str(p)
items = pm.load_backlog()
assert items == ["Task three first", "Task one second", "Task ninety-nine"]
```

**Expected result**: items returned in **file order** (not sorted by number).
`"Unnumbered line"` is absent. No crash.

---

### Scenario 5 — Full pytest suite passes (no regressions)

**Setup**: unmodified repository with test committed.

**Action**:
```bash
cd api && python3 -m pytest tests/test_project_manager.py -v --tb=short 2>&1 | tail -20
```

**Expected result**:
```
tests/test_project_manager.py::test_load_backlog_malformed_missing_number_prefix PASSED
...
== N passed in Xs ==
```

No test in the file should be `FAILED` or `ERROR`. Exit code `0`.

**Edge case — missing BACKLOG_FILE path**: if `pm.BACKLOG_FILE` points to a non-existent
path, `_parse_backlog_file` returns `[]` without raising — this is the existing behaviour
verified by `test_load_backlog_empty_file`.

---

## Out of Scope

- Modifying `_parse_backlog_file` or `load_backlog` behaviour (implementation is correct).
- Testing empty file or comment-only file (covered by `test_load_backlog_empty_and_malformed`
  if that test exists, or by Scenario 2 above).
- Meta-backlog (`PIPELINE_META_BACKLOG` env var) or `--backlog` flag (separate tests).
- Any API endpoint changes.

---

## Concurrency Behaviour

Read-only test using `tmp_path` (isolated per test run). Safe for parallel pytest workers.

---

## Failure and Retry Behaviour

| Failure mode                      | Expected behaviour                    |
|-----------------------------------|---------------------------------------|
| File does not exist               | Returns `[]`, no exception            |
| File unreadable (permissions)     | `OSError` propagates to caller        |
| All lines malformed               | Returns `[]`, no exception            |
| Regex engine error                | Not possible with fixed pattern       |

---

## Risks and Known Gaps

- **No auth gate**: N/A (no HTTP endpoint).
- **OS path portability**: `tmp_path` fixture is cross-platform (pytest handles Windows/Linux).
- **Follow-up**: Consider adding property-based tests (hypothesis) for the regex to catch
  future regex regressions automatically.

---

## Verification

```bash
# Run the specific test
cd api && python3 -m pytest tests/test_project_manager.py::test_load_backlog_malformed_missing_number_prefix -v

# Run the full test module
cd api && python3 -m pytest tests/test_project_manager.py -v --tb=short
```

Both commands must exit 0.

---

## See Also

- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — project manager orchestrator spec
- [006-overnight-backlog.md](006-overnight-backlog.md) — original backlog spec
- [041-project-manager-state-file-flag-test.md](041-project-manager-state-file-flag-test.md) — sibling test spec
- [042-project-manager-reset-clears-state-test.md](042-project-manager-reset-clears-state-test.md) — reset behaviour test
- `api/scripts/project_manager.py:193` — `_parse_backlog_file` implementation
- `api/tests/test_project_manager.py:38` — `test_load_backlog_malformed_missing_number_prefix`
