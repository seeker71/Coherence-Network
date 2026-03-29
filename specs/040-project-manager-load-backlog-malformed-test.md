# Spec 040 — Project Manager `load_backlog` Malformed Input Test

**Idea ID:** `040-project-manager-load-backlog-malformed-test`  
**Status:** Approved for implementation  
**Primary surface:** CLI / library — `api/scripts/project_manager.py` (no HTTP API in this spec)

## Summary

The overnight and interactive pipelines rely on `load_backlog()` to read numbered work items from a markdown backlog file. Real files often contain prose, section headers, or partially edited lines that do **not** match the required `N. ` prefix. This spec locks in **automated pytest coverage** proving that mixed valid and malformed lines are handled deterministically: valid numbered lines become backlog entries in file order; malformed lines are skipped; the process never raises and never silently corrupts the item list.

This protects operators from subtle pipeline stalls (crashes) or wrong item ordering when hand-editing `specs/006-overnight-backlog.md` or a worktree-local backlog copy.

## Requirements

- [ ] **R1 — Mixed file:** A test uses a temporary backlog file containing at least two numbered lines (`^\d+\.\s+`) and at least two lines that do not match that pattern (headers, prose, blank-looking lines without numbers).
- [ ] **R2 — Assertions:** The test asserts `load_backlog()` returns **only** the text after the number prefix for each matching line, in **file order** (not sorted by the numeric prefix).
- [ ] **R3 — No mocks:** The test exercises the real `_parse_backlog_file` path through `load_backlog()` with real file I/O and `pm.BACKLOG_FILE` pointed at the temp file (same pattern as existing tests in `test_project_manager.py`).
- [ ] **R4 — Environment isolation:** Tests clear or override `PIPELINE_META_BACKLOG` / `PIPELINE_META_RATIO` when needed so meta-backlog interleaving does not affect the product-only assertion (default `load_backlog()` behavior with those unset is product-only).
- [ ] **R5 — Regression suite:** `pytest api/tests/test_project_manager.py` remains green.

## API Changes

**None.** No new FastAPI routes, request bodies, or response models.

### CLI / script contract (behavior under test)

| Mechanism | Location | Notes |
|-----------|----------|--------|
| `load_backlog()` | `api/scripts/project_manager.py` | Reads `BACKLOG_FILE`, optionally interleaves meta backlog when env vars set |
| `_parse_backlog_file(path)` | same | Per-line regex `^\d+\.\s+(.+)$`; strips line; skips lines starting with `#` after strip (see implementation) |
| Verification command | shell | `cd api && python3 -m pytest api/tests/test_project_manager.py -v` |

There is **no** `GET /api/...` endpoint for backlog parsing in this spec. Reviewers validate via pytest in CI and locally.

## Data Model

**No database or Pydantic model changes.**

### Backlog file format (normative for tests)

- **Included:** Lines that match `^\d+\.\s+(.+)$` after `strip()`, and that are not treated as comments by the parser (implementation uses `not line.startswith("#")` in conjunction with the regex match).
- **Excluded:** Lines without the numbered prefix; lines that are comment-only in the parser’s logic; empty lines (no match).
- **Order:** Items appear in the order lines appear in the file, not sorted by the integer prefix.

## Files to Create or Modify

| File | Action |
|------|--------|
| `api/tests/test_project_manager.py` | Holds `test_load_backlog_malformed_missing_number_prefix` (and related cases if split). |

**Out of scope for this spec:** Changing `_parse_backlog_file` or `load_backlog` implementation (behavior is already correct; this spec is **test contract** only). Additional coverage for `PIPELINE_META_*` interleaving is optional and not required here.

## Acceptance Criteria

1. `test_load_backlog_malformed_missing_number_prefix` exists and fails if `load_backlog()` ever returns malformed lines or wrong order for the mixed-input fixture described in Verification Scenarios.
2. `python3 -m pytest api/tests/test_project_manager.py::test_load_backlog_malformed_missing_number_prefix -v` exits `0`.
3. Full file: `python3 -m pytest api/tests/test_project_manager.py -v` exits `0`.

## Verification

### Automated commands (required)

```bash
cd api
python3 -m pytest api/tests/test_project_manager.py::test_load_backlog_malformed_missing_number_prefix -v
python3 -m pytest api/tests/test_project_manager.py -v
```

Paths are relative to repo root; when `cd api`, use:

```bash
cd api && python3 -m pytest tests/test_project_manager.py -v
```

### Verification Scenarios

#### Scenario 1 — Happy path: mixed numbered and unnumbered lines

- **Setup:** `tmp_path / "backlog.md"` with exact content:
  ```
  1. First item
  Unnumbered line
  2. Second item
  Another line without number
  ```
  `pm.BACKLOG_FILE` set to that path; `PIPELINE_META_BACKLOG` unset or empty and `PIPELINE_META_RATIO` `0` so only the product file is parsed.
- **Action:** `cd api && python3 -m pytest tests/test_project_manager.py::test_load_backlog_malformed_missing_number_prefix -v`
- **Expected:** Exit code `0`; test `PASSED`; `load_backlog()` returns `["First item", "Second item"]` (two strings, that order).
- **Edge:** If an implementation incorrectly included `"Unnumbered line"`, the test fails (proves filtering).

#### Scenario 2 — Error handling: all lines unnumbered

- **Setup:** Temporary file containing only non-matching lines (no `\d+\.\s+` prefix).
- **Action:** Same module test or a dedicated test that sets `BACKLOG_FILE` and calls `load_backlog()`.
- **Expected:** Returns `[]`; **no** exception (`ValueError`, `IndexError`, etc.).
- **Edge:** Distinguishes “empty parse result” from “missing file” (missing file also yields `[]` via `_parse_backlog_file`; document that both are empty-list outcomes for the parser).

#### Scenario 3 — Order preservation (not numeric sort)

- **Setup:** File with lines `3. Third first`, then garbage, then `1. First second`, then `2. Second third`.
- **Action:** Parse with `load_backlog()`.
- **Expected:** `["Third first", "First second", "Second third"]` — **file order**, not `[1,2,3]` sorting.
- **Edge:** Proves pipeline items follow editor order, which matters for dependency intent in manual backlog edits.

#### Scenario 4 — Comments and malformed lines together

- **Setup:**
  ```
  1. Valid item one
  # This is a comment
  2. Valid item two
  Not a numbered line
  ```
- **Action:** `load_backlog()`.
- **Expected:** `["Valid item one", "Valid item two"]`.
- **Edge:** A line like `# 3. fake item` is excluded because comment handling interacts with line content (align with implementation in `project_manager.py`).

#### Scenario 5 — Full module regression

- **Setup:** Clean checkout; optional `python3 -m pytest tests/test_project_manager.py -v` in CI.
- **Action:** Run entire `test_project_manager.py`.
- **Expected:** All tests pass; exit code `0`.
- **Edge:** Catches accidental changes to globals (`BACKLOG_FILE`, env) shared across tests.

## Risks and Assumptions

- **Assumption:** `BACKLOG_FILE` and `STATE_FILE` are overridden per test via `pm.BACKLOG_FILE` assignments; tests run in a single process sequentially (pytest default for this module) so global mutation is acceptable as in existing tests.
- **Assumption:** Meta-backlog interleaving (`PIPELINE_META_BACKLOG`, `PIPELINE_META_RATIO`) is not enabled in CI for this test; if CI sets these env vars globally, tests must `monkeypatch` or `del os.environ` for the duration of the test.
- **Risk:** Over-broad regex changes to `_parse_backlog_file` could make tests pass while breaking real backlog files — reviewers should treat **spec 006** backlog samples as additional manual smoke when changing parsing.

## Known Gaps and Follow-up Tasks

- Optional: Explicit pytest for meta-interleaving **plus** malformed lines in the product file (not required for 040 closure).
- Optional: Property-based test (hypothesis) for random prefixes — deferred cost/benefit.
- No production deploy requirement: test-only spec; deployment verification is N/A unless paired with a release that touches `project_manager.py`.

## Task Card

```yaml
goal: Lock in pytest coverage for load_backlog() when the backlog file mixes valid numbered lines with malformed unnumbered lines.
files_allowed:
  - api/tests/test_project_manager.py
done_when:
  - test_load_backlog_malformed_missing_number_prefix passes with mixed content fixture.
  - pytest api/tests/test_project_manager.py exits 0.
commands:
  - cd api && python3 -m pytest tests/test_project_manager.py::test_load_backlog_malformed_missing_number_prefix -v
  - cd api && python3 -m pytest tests/test_project_manager.py -v
constraints:
  - Implementation of _parse_backlog_file unchanged unless a separate spec/issue says otherwise.
  - No mock of load_backlog; use tmp_path files.
```

## Research Inputs

- `api/scripts/project_manager.py` — `_parse_backlog_file`, `load_backlog`
- `api/tests/test_project_manager.py` — existing `test_load_backlog_*` patterns
- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — orchestration context
- [006-overnight-backlog.md](006-overnight-backlog.md) — backlog content source

## See also

- [005-project-manager-pipeline.md](005-project-manager-pipeline.md)
- [006-overnight-backlog.md](006-overnight-backlog.md)
