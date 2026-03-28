# Spec 040: Project Manager — `load_backlog` Malformed / Mixed-Line Test

## Summary

The overnight pipeline and local automation rely on `api/scripts/project_manager.py` to read work items from Markdown backlog files (default `specs/005-backlog.md`, override via `--backlog`). Real files often contain section headers, notes, or pasted lines **without** the required `N. ` prefix. The parser (`_parse_backlog_file`) must **skip** those lines, **never crash**, and return **only** the text of valid numbered items **in file order**.

This spec defines the **behavioral contract** and **automated verification** for that path: a **pytest** test that exercises a temporary backlog file with **mixed valid numbered lines and malformed/unnumbered lines**, asserting the exact list returned by `load_backlog()`. It does **not** require HTTP API or web changes.

## Purpose

- Lock in regression coverage so future edits to parsing cannot silently ingest junk lines or reorder items.
- Give reviewers a **runnable** contract (pytest + optional CLI smoke) they can execute against a checkout without production.

## Requirements

- [ ] **R1 — Mixed file parsing:** Given a UTF-8 backlog file containing lines matching `^\d+\.\s+(.+)$` interleaved with lines that do **not** match (e.g. section titles, `unnumbered line`, `1) wrong format`), `load_backlog()` returns **only** the captured item text from numbered lines, **in source order** (no duplicates from malformed lines).
- [ ] **R2 — No crash:** Parsing must not raise for missing file, empty file, or mixed content; empty/missing file yields `[]` (existing behavior).
- [ ] **R3 — No mocks for backlog content:** The test uses `tmp_path` (or equivalent) to write a **real** file, sets `project_manager.BACKLOG_FILE` to that path, clears `PIPELINE_META_BACKLOG` / `PIPELINE_META_RATIO` for the test process so `load_backlog()` returns **only** the product backlog (no meta interleave), then calls `load_backlog()` and asserts.
- [ ] **R4 — Documented regex:** Valid line pattern is `^\d+\.\s+(.+)$` after `strip()`; lines starting with `#` after strip are still subject to the same regex (a line `# 1. foo` does not match `^\d+\.` at start).
- [ ] **R5 — CI command:** `python3 -m pytest api/tests/test_project_manager.py -x -v` passes on a clean branch.

## Research Inputs

- `2024-` — Repo `api/scripts/project_manager.py` — `_parse_backlog_file`, `load_backlog` (authoritative implementation).
- `2024-` — `specs/005-backlog.md` / `specs/006-overnight-backlog.md` — backlog file format and pipeline context.
- `2024-` — `specs/005-project-manager-pipeline.md` — project manager orchestration and dry-run behavior.

## Task Card

```yaml
goal: Prove with pytest that load_backlog parses only numbered lines and skips malformed lines without crashing.
files_allowed:
  - api/tests/test_project_manager.py
done_when:
  - Pytest test covers a backlog file with numbered + unnumbered lines; asserts exact ordered list.
  - python3 -m pytest api/tests/test_project_manager.py -x -v exits 0.
commands:
  - python3 -m pytest api/tests/test_project_manager.py -x -v
constraints:
  - Do not change production parsing behavior unless a bug is proven; this spec is primarily test coverage.
  - No REST API or schema migrations in scope.
```

## API Changes

**N/A — no REST API changes.**  
Script / CLI surface (unchanged; documented for verification):

| Surface | Purpose |
|--------|---------|
| `python api/scripts/project_manager.py --dry-run [--backlog PATH]` | Loads backlog via `load_backlog()` after `--backlog` sets `BACKLOG_FILE`; prints `DRY-RUN: backlog index=...` and item preview when applicable. |
| `load_backlog()` | Module-level function returning `list[str]` of item titles from numbered lines only. |

**Endpoints:** None required for this feature.

**Web pages:** None.

## Data Model

**Backlog file (text, UTF-8):**

- Each **work item** is one line: `^\d+\.\s+(.+)$` (after stripping leading/trailing whitespace on the line).
- **Non-matching** lines are ignored (not errors).
- **No database** or Pydantic models for backlog lines; the in-memory model is `list[str]` of item titles.

**Environment (optional interleave, out of scope for the core malformed test unless explicitly tested):**

- `PIPELINE_META_BACKLOG` — path to meta backlog file.
- `PIPELINE_META_RATIO` — float; when > 0 and meta file set, `load_backlog()` interleaves product + meta items.

## Files to Create/Modify

- `api/tests/test_project_manager.py` — test that asserts mixed numbered + unnumbered backlog content (e.g. `test_load_backlog_numbered_items` or equivalent).

## Acceptance Tests

- `api/tests/test_project_manager.py::test_load_backlog_numbered_items` (or same behavior under a more explicit name) — file content includes at least:
  - `1. First item`
  - `Unnumbered line`
  - `2. Second item`
  - `Another line without number`
  - `3. Third item`
  - Expected: `["First item", "Second item", "Third item"]`.
- `api/tests/test_project_manager.py::test_load_backlog_empty_file` — empty file → `[]`.
- Full module: `python3 -m pytest api/tests/test_project_manager.py -x -v` passes.

## Verification Scenarios

These scenarios are the **contract** for reviewers and CI. Any failure means the work is incomplete.

### Scenario 1 — Mixed malformed lines (unit test, primary)

- **Setup:** Checkout with `api/` on `PYTHONPATH`; no production DB required. Create `tmp_path / "backlog.md"` with:
  ```
  1. First item
  unnumbered line
  2. Second item
  Another line without number
  3. Third item
  ```
  In the test, set `pm.BACKLOG_FILE` to that path; unset meta interleave (`monkeypatch.delenv("PIPELINE_META_BACKLOG", raising=False)`, `monkeypatch.setenv("PIPELINE_META_RATIO", "0")` or equivalent).
- **Action:** `python3 -m pytest api/tests/test_project_manager.py::test_load_backlog_numbered_items -v`
- **Expected result:** Test **passed**; `load_backlog()` returns exactly `["First item", "Second item", "Third item"]`.
- **Edge:** Line `10. Tenth` still matches (multi-digit index); line `1.` with empty title: regex requires `.+` so `1.` alone may not match — document as **ignored**; optional follow-up test if product wants empty titles rejected.

### Scenario 2 — Empty file (read path)

- **Setup:** `tmp_path / "empty.md"` exists, zero bytes.
- **Action:** Run `test_load_backlog_empty_file` — `pm.BACKLOG_FILE` points to empty file.
- **Expected:** `load_backlog()` returns `[]`, no exception.
- **Edge:** Missing file path → `[]` (per `_parse_backlog_file`).

### Scenario 3 — CLI dry-run uses backlog length (smoke)

- **Setup:** Write a temp backlog with two valid numbered lines and one junk line; run from repo root (`api/` parent).
- **Action:**  
  `python api/scripts/project_manager.py --dry-run --reset --backlog /absolute/path/to/backlog.md`  
  (use `--state-file` under `tmp_path` to avoid touching default logs if desired.)
- **Expected:** Process exit code **0**; stdout contains `DRY-RUN: backlog index=` and log line indicates backlog count **2** (only valid items).
- **Edge:** If `--backlog` points to nonexistent file, backlog length **0**; still exit 0 for dry-run.

### Scenario 4 — Wrong numbering style (error handling)

- **Setup:** File contains `1) First item` (parenthesis, not dot-space) and `1. Valid item`.
- **Action:** Parse via `load_backlog()` after pointing `BACKLOG_FILE` at file.
- **Expected:** Only `Valid item` appears in the list; `1) First item` is **skipped** (not split errors).
- **Edge:** Ensures reviewers do not assume “any line with numbers” is accepted.

### Scenario 5 — Full test module regression

- **Setup:** Clean venv with dev deps.
- **Action:** `python3 -m pytest api/tests/test_project_manager.py -x -v`
- **Expected:** All tests pass; no `ImportError` for `scripts.project_manager`.
- **Edge:** Duplicate numbered lines both included if they match regex (duplicate titles allowed).

## Verification (manual / CI)

```bash
cd /path/to/repo
python3 -m pytest api/tests/test_project_manager.py -x -v
```

## Out of Scope

- Changing `_parse_backlog_file` or `load_backlog` behavior (unless a bug is demonstrated by a failing test).
- Meta-backlog interleaving tests (spec 028) — separate coverage unless explicitly added to `files_allowed`.
- REST auth, rate limits, or Neo4j.

## Risks and Assumptions

- **Assumption:** Tests run with `api/` as cwd or `sys.path` including `api` so `from scripts import project_manager` works (matches existing `test_project_manager.py`).
- **Risk:** Global `BACKLOG_FILE` mutation in tests can leak order if tests run in parallel; pytest default is usually fine; use `tmp_path` isolation.
- **Assumption:** UTF-8 encoding for backlog files; unusual encodings are out of scope.

## Known Gaps and Follow-up Tasks

- Optional explicit test for `1) ` style lines if product wants to support them.
- Optional test with `PIPELINE_META_*` set to ensure malformed meta file does not break product-only expectations.

## See also

- [005-project-manager-pipeline.md](005-project-manager-pipeline.md)
- [006-overnight-backlog.md](006-overnight-backlog.md)

## Decision Gates

None.

## Concurrency Behavior

N/A for backlog file read in tests (single-threaded pytest). Production PM is single-process per state file.

## Failure and Retry Behavior

N/A for this spec (parser returns partial list; no retry). PM pipeline retry logic is covered in spec 005.
