# Spec 040: Project Manager load_backlog — Malformed File (Missing Number Prefix) Test

## Summary

Ensure `load_backlog()` in `api/scripts/project_manager.py` is covered by a targeted test for the malformed-input path: a backlog file that contains a mix of numbered lines (`N. <text>`) and lines that lack the required `\d+\.\s+` prefix. The function must skip unnumbered lines without crashing and return only the valid numbered items in original order.

---

## Purpose

Add (or verify existence of) a pytest test that exercises `_parse_backlog_file` / `load_backlog` with a deliberately malformed backlog file containing both valid numbered items and invalid unnumbered lines. The implementation already handles this correctly; this spec exists solely to lock the behaviour with a regression test and prevent silent regressions in a future refactor.

---

## Background

The project manager reads one or more backlog files (product backlog and optional meta-backlog) and iterates through the resulting list. Each line is matched against `^\d+\.\s+(.+)$`. Lines that do not match (headers, blank lines, narrative text, comments) are silently ignored. Without an explicit test for this path, a future refactor could accidentally include or crash on such lines without any failing CI signal.

Related specs:
- `005-backlog.md` — product backlog format
- `005-project-manager-orchestrator.md` — orchestration loop
- `006-overnight-backlog.md` — extended backlog items
- `041-project-manager-state-file-flag-test.md` — sibling test spec
- `042-project-manager-reset-clears-state-test.md` — sibling test spec

---

## Requirements

| # | Requirement |
|---|-------------|
| R1 | A test named `test_load_backlog_malformed_missing_number_prefix` exists in `api/tests/test_project_manager.py`. |
| R2 | The test creates a real temporary file (via `tmp_path`) with both numbered and unnumbered lines. |
| R3 | The test calls `pm.load_backlog()` (or `pm._parse_backlog_file(path)`) using the real file — no mocks. |
| R4 | The test asserts that only items from numbered lines are returned, in original order. |
| R5 | Unnumbered lines (no leading `\d+. `) are silently discarded — not included, not raising an exception. |
| R6 | `pytest api/tests/test_project_manager.py -x -v` passes with exit code 0. |
| R7 | No production code in `project_manager.py` is modified; only the test file is touched. |

---

## Files to Create / Modify

| File | Action | Notes |
|------|--------|-------|
| `api/tests/test_project_manager.py` | Add or verify test | `test_load_backlog_malformed_missing_number_prefix` |

All other files are **out of scope**.

---

## Data Model

No schema changes.  The backlog file format is already defined:

```
<N>. <item text>        ← valid: captured as item
<text without number>   ← invalid: silently skipped
# <comment>            ← comment: silently skipped
                        ← blank line: silently skipped
```

Items are returned as `list[str]` — the captured group from `^\d+\.\s+(.+)$`, stripped of surrounding whitespace.

---

## Acceptance Criteria

- [ ] `test_load_backlog_malformed_missing_number_prefix` exists in `api/tests/test_project_manager.py`.
- [ ] Test uses a real temporary file (not an in-memory mock).
- [ ] Test asserts `items == ["First item", "Second item"]` (or equivalent numbered content) when file contains:
  ```
  1. First item
  Unnumbered line
  2. Second item
  Another line without number
  ```
- [ ] `python3 -m pytest api/tests/test_project_manager.py -x -v` exits with code 0.
- [ ] No changes to `api/scripts/project_manager.py`.

---

## Verification Scenarios

All scenarios are runnable against a local checkout with `python3 -m pytest`.

### Scenario 1 — Happy path: mixed numbered and unnumbered lines

**Setup:** Temporary file `backlog.md` with content:
```
1. First item
Unnumbered line
2. Second item
Another line without number
```
`pm.BACKLOG_FILE` is pointed at this file.

**Action:**
```bash
python3 -m pytest api/tests/test_project_manager.py::test_load_backlog_malformed_missing_number_prefix -v
```

**Expected result:**
- Exit code `0`
- Test output shows `PASSED`
- Internally: `load_backlog()` returns `["First item", "Second item"]` — exactly two items, in order

**Edge:** Unnumbered lines are absent from the returned list; no `IndexError`, `ValueError`, or `AttributeError` is raised.

---

### Scenario 2 — All lines are unnumbered (degenerate malformed file)

**Setup:** Temporary file containing only unnumbered lines:
```
Just a header
Some prose
More text without numbers
```

**Action:**
```python
# within a pytest test or Python REPL
import api.scripts.project_manager as pm
pm.BACKLOG_FILE = "<path_to_above_file>"
items = pm.load_backlog()
assert items == []
```

**Expected result:** `items` is an empty list `[]`; no exception.

**Edge:** This exercises the "all malformed, nothing returned" path — distinct from the empty-file case.

---

### Scenario 3 — Order preservation across gaps

**Setup:** Temporary file:
```
3. Third item first
Bad header
1. First item second
# comment line
2. Second item third
```

**Action:**
```bash
python3 -m pytest api/tests/test_project_manager.py -k "malformed" -v
```

**Expected result:** `load_backlog()` returns items in file-order: `["Third item first", "First item second", "Second item third"]`.

**Important:** Items are returned in *file order*, not sorted by the leading number. Spec 005 defines them as ordered by position.

---

### Scenario 4 — Comment lines are excluded alongside unnumbered lines

**Setup:** Temporary file:
```
1. Valid item one
# This is a comment
2. Valid item two
Not a numbered line
```

**Action:**
```bash
python3 -m pytest api/tests/test_project_manager.py -x -v
```

**Expected result:** `["Valid item one", "Valid item two"]` — comment line and unnumbered line both excluded.

**Edge:** A comment that begins with `# 3. item` is also excluded because the regex match is performed *after* the `startswith("#")` guard in `_parse_backlog_file`.

---

### Scenario 5 — Regression: existing tests continue to pass

**Setup:** Unmodified `api/tests/test_project_manager.py` with all existing tests.

**Action:**
```bash
python3 -m pytest api/tests/test_project_manager.py -v
```

**Expected result:** All previously passing tests still pass; exit code `0`; no regressions introduced by adding the new test.

---

## API Contract

N/A — this feature tests a script-level function, not an HTTP endpoint.

---

## CLI Commands Verified

| Command | Expected outcome |
|---------|-----------------|
| `python3 -m pytest api/tests/test_project_manager.py -x -v` | All tests pass, exit 0 |
| `python3 -m pytest api/tests/test_project_manager.py::test_load_backlog_malformed_missing_number_prefix -v` | Single test passes, exit 0 |

---

## Out of Scope

- Changing `_parse_backlog_file` or `load_backlog` implementation.
- Testing empty files (already covered by `test_load_backlog_empty_file`).
- Testing the meta-backlog interleaving logic.
- Modifying any other test files.
- Any API endpoints or web pages.

---

## Concurrency Behaviour

`_parse_backlog_file` is a pure read-only function — safe for concurrent calls with no locking required.

---

## Failure and Retry Behaviour

No runtime failure modes; this is a test-only spec. If the test file is missing, `pytest` exits non-zero and CI blocks the merge.

---

## Risks and Known Gaps

| Risk | Mitigation |
|------|-----------|
| Test already exists | Check before creating to avoid duplicate; update if semantics differ |
| `_parse_backlog_file` signature changes | Test calls `load_backlog()` which wraps it; coupling is one level removed |
| `BACKLOG_FILE` module-level variable mutation in tests | Each test fixture sets `pm.BACKLOG_FILE` locally; teardown or fixture cleanup may be needed to avoid cross-test contamination |

---

## Verification Command (CI)

```bash
python3 -m pytest api/tests/test_project_manager.py -x -v
```

Exit code must be `0`. Any failure is a CI blocker.
