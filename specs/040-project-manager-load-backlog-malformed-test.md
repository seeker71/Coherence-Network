# Spec: Project Manager load_backlog — Malformed File (Missing Numbers) Test

**Spec ID**: 040
**Status**: Approved
**Type**: test

---

## Summary

Ensure the project manager's `load_backlog` behavior is tested when the backlog file contains lines that lack the required number prefix (`N. `). Parsing must skip such lines and return only valid numbered items, with no crash or inclusion of malformed content.

The implementation (`_parse_backlog_file`) already handles this correctly via the regex `^\d+\.\s+(.+)$`. This spec adds explicit test coverage for the malformed-input case so that future refactors cannot silently regress the behavior.

---

## Goal

Add a focused pytest test: given a backlog file with a mixture of valid numbered lines (`1. Item`) and malformed unnumbered lines (`Some header`, `## Section`, `- bullet`), `load_backlog()` returns **only** the parsed items from numbered lines, in order, with zero crashes and zero inclusion of malformed lines.

---

## Requirements

- [ ] A test exists in `api/tests/test_project_manager.py` named `test_load_backlog_malformed_mixed_lines` (or equivalent).
- [ ] The test writes a real temporary backlog file containing **both** numbered lines and lines missing the `\d+\.\s+` prefix.
- [ ] The test asserts that `load_backlog()` returns only the parsed items from numbered lines, preserving order.
- [ ] The test does **not** rely on mocks; it uses real file I/O (`tmp_path`) and the real `load_backlog()` function.
- [ ] `pytest api/tests/test_project_manager.py -x -v` passes with exit code 0.

---

## Background

The `_parse_backlog_file` function (line 193, `api/scripts/project_manager.py`) applies:

```python
m = re.match(r"^\d+\.\s+(.+)$", line)
if m and not line.startswith("#"):
    items.append(m.group(1).strip())
```

Lines without a leading digit-dot-space prefix are silently skipped. This is correct behavior; the test must prove it.

---

## API Contract

N/A — script/file behavior only. No HTTP endpoints involved.

---

## Data Model

Backlog file format:
- Lines matching `^\d+\.\s+(.+)$` are included (the captured group is the item text).
- All other lines are skipped (headers, comments `#`, bullets `-`, blank lines, etc.).

---

## Files to Create/Modify

| File | Change |
|------|--------|
| `api/tests/test_project_manager.py` | Add `test_load_backlog_malformed_mixed_lines` test function |

---

## Acceptance Tests

- [ ] Test function exists and is named `test_load_backlog_malformed_mixed_lines` (or clearer equivalent).
- [ ] Test input file content includes at least one numbered item, at least two unnumbered lines, and another numbered item.
- [ ] Assertion: `load_backlog()` returns only the texts from numbered lines, in file order.
- [ ] No mock patching of `open`, `re`, or `os`; uses real file I/O with `tmp_path`.
- [ ] `python3 -m pytest api/tests/test_project_manager.py -x -v` passes with exit code 0.

---

## Verification Scenarios

### Scenario 1 — Happy path with malformed mixed content

**Setup**: Create a temporary file `backlog.md` with the following content:

```
1. First item
Unnumbered line
2. Second item
Another line without number
```

Set `pm.BACKLOG_FILE` to point to this file.

**Action**:
```python
items = pm.load_backlog()
```

**Expected result**: `items == ["First item", "Second item"]` — exactly two items, in order. The two unnumbered lines produce no entries.

**Edge case**: If `load_backlog()` returns 4 items (including malformed lines), the regex guard is broken.

---

### Scenario 2 — All lines malformed (no numbered items)

**Setup**: Create a temporary file with only unnumbered lines:

```
This is a header
- bullet point
## Section title
No numbers here
```

Set `pm.BACKLOG_FILE` to this path.

**Action**:
```python
items = pm.load_backlog()
```

**Expected result**: `items == []` — empty list, no crash.

**Edge case**: Function must not raise `AttributeError` or `TypeError` on lines that don't match the regex.

---

### Scenario 3 — Numbered items only (no malformed lines; regression guard)

**Setup**: Create a file with only valid numbered items:

```
1. Alpha
2. Beta
3. Gamma
```

**Action**:
```python
items = pm.load_backlog()
```

**Expected result**: `items == ["Alpha", "Beta", "Gamma"]` — all three present in order.

**Edge case**: Renumbered items (e.g., `10. Ten`) are also parsed; single-digit and multi-digit numbers both match `^\d+\.\s+`.

---

### Scenario 4 — Comment lines (lines starting with `#`) are excluded

**Setup**: Create a file mixing numbered items with comment lines:

```
# This is a comment
1. Real item
# Another comment
2. Second real item
```

**Action**:
```python
items = pm.load_backlog()
```

**Expected result**: `items == ["Real item", "Second real item"]` — comment lines are excluded even though they might otherwise look like section markers.

**Edge case**: A line like `1. # item` — the regex matches because `#` is inside the text portion, not at line start, so it IS included as `"# item"`. This is expected behavior per the current guard logic.

---

### Scenario 5 — Run pytest directly to confirm test passes

**Setup**: Working directory is repo root; `api/tests/test_project_manager.py` contains the malformed test.

**Action**:
```bash
python3 -m pytest api/tests/test_project_manager.py::test_load_backlog_malformed_mixed_lines -v
```

**Expected result**:
```
PASSED api/tests/test_project_manager.py::test_load_backlog_malformed_mixed_lines
1 passed in <Xs>
```

**Edge case**: Running the full suite (`python3 -m pytest api/tests/test_project_manager.py -x -v`) must also pass — the new test must not interfere with existing state-file tests via `pm.BACKLOG_FILE` side-effects (each test sets `pm.BACKLOG_FILE` via its own `tmp_path`).

---

## Out of Scope

- Changing `_parse_backlog_file` or `load_backlog` implementation (implementation is already correct).
- Testing empty file or comment-only file exhaustively (basic empty-file case covered by `test_load_backlog_empty_file`).
- Meta-backlog interleaving (`PIPELINE_META_BACKLOG` env var) — covered by other tests.
- HTTP endpoints, Pydantic models, or schema migrations.

---

## Concurrency Behavior

- **Read operations**: `_parse_backlog_file` is stateless and safe for concurrent access; no locking required.
- **Write operations**: Test uses isolated `tmp_path` per test function; no shared state between test runs.

---

## Failure and Retry Behavior

- **Test failure**: If `load_backlog()` returns malformed lines, the assertion will fail with a clear diff.
- **No retries**: Tests are deterministic; no network or timing dependencies.

---

## Risks and Known Gaps

- **Side-effects between tests**: `pm.BACKLOG_FILE` is module-level state. Each test that uses `tmp_path` must explicitly set `pm.BACKLOG_FILE` before calling `load_backlog()`. Failing to do so can cause cross-test interference.
- **Follow-up**: Add a pytest fixture to reset `pm.BACKLOG_FILE` to a safe default after each test (`yield`-based fixture) if test suite grows large.

---

## Verification

```bash
python3 -m pytest api/tests/test_project_manager.py -x -v
```

Expected: all tests pass, including `test_load_backlog_malformed_mixed_lines`.

---

## See Also

- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — project manager orchestrator spec
- [006-overnight-backlog.md](006-overnight-backlog.md) — backlog item format spec
- [041-project-manager-state-file-flag-test.md](041-project-manager-state-file-flag-test.md) — adjacent test spec
