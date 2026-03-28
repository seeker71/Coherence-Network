# Spec: Project Manager load_backlog — Malformed File (Missing Numbers) Test

## Summary

Ensure `load_backlog()` / `_parse_backlog_file()` in `api/scripts/project_manager.py` is
covered by explicit test cases for backlog files that contain lines **without** the required
`\d+\.\s+` prefix. The implementation already skips such lines; this spec defines the test
coverage contract that guards against regressions.

---

## Purpose

`_parse_backlog_file` applies `re.match(r"^\d+\.\s+(.+)$", line)` to each line. Lines that
do not match are silently skipped. This is the correct behavior; however, without a targeted
test, a future refactor could accidentally include malformed lines or crash on them. This spec
closes that coverage gap.

---

## Requirements

- [ ] A test exists that feeds `load_backlog()` a file containing **both** valid numbered lines
      and lines that lack the `\d+\.\s+` prefix (unnumbered prose, empty lines, comment lines
      starting with `#`, lines with partial prefixes like `1` or `1.item`).
- [ ] The test asserts that `load_backlog()` returns **only** the text of valid numbered lines,
      in their original order.
- [ ] No mocks are used; the test relies on real `tempfile`-based I/O and the real
      `load_backlog()` entry point (which calls `_parse_backlog_file` internally).
- [ ] A second test covers the **all-malformed** edge case: a file where every line is
      malformed must return an empty list — not crash, not raise, not return garbage.
- [ ] A third test covers **comment lines** (lines starting with `#`): they must be excluded
      even when they start with a digit-dot pattern embedded elsewhere in the text.
- [ ] All tests in `api/tests/test_project_manager.py` continue to pass with `pytest -x -v`.

---

## Research Inputs

- Implementation: `api/scripts/project_manager.py`, functions `_parse_backlog_file` (line 193)
  and `load_backlog` (line 207).
- Related specs: [005-project-manager-pipeline.md](005-project-manager-pipeline.md),
  [041-project-manager-state-file-flag-test.md](041-project-manager-state-file-flag-test.md),
  [042-project-manager-reset-clears-state-test.md](042-project-manager-reset-clears-state-test.md).

---

## Task Card

```yaml
goal: >
  Add test coverage for load_backlog() when the backlog file contains lines that lack
  the required number prefix. Lines without the prefix must be skipped; valid numbered
  lines must be returned in order; all-malformed file must return [].
files_allowed:
  - api/tests/test_project_manager.py
done_when:
  - test_load_backlog_mixed_numbered_and_unnumbered passes
  - test_load_backlog_all_malformed_returns_empty passes
  - test_load_backlog_comment_lines_excluded passes (if not already present)
  - python3 -m pytest api/tests/test_project_manager.py -x -v exits 0
commands:
  - python3 -m pytest api/tests/test_project_manager.py -x -v
constraints:
  - changes scoped to api/tests/test_project_manager.py only
  - do not modify _parse_backlog_file or load_backlog behavior
  - no schema migrations
```

---

## API Contract

N/A — this is a pure script / file-I/O behavior test. No HTTP endpoints are introduced or
changed.

---

## Data Model

Backlog file format (unchanged):

```
\d+\.\s+<item-text>   → included; item-text = everything after the number-dot-space prefix
<anything else>        → ignored / skipped silently
#<anything>            → comment; excluded even if it contains a digit-dot pattern
```

Example malformed lines that must be excluded:

| Line content                   | Reason excluded                        |
|--------------------------------|----------------------------------------|
| `(empty)`                      | No digit prefix                        |
| `Unnumbered prose`             | No digit prefix                        |
| `# 1. Looks numbered`          | Starts with `#` — comment              |
| `1.No space after dot`         | Regex requires `\s+` after dot         |
| `1item`                        | No dot separator                       |

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `api/tests/test_project_manager.py` | Add three targeted tests (see Acceptance Tests) |

---

## Acceptance Tests

### 1. Mixed numbered and unnumbered lines

```python
def test_load_backlog_mixed_malformed(tmp_path):
    p = tmp_path / "backlog.md"
    p.write_text(
        "1. First item\n"
        "Unnumbered line\n"
        "2. Second item\n"
        "Another line without number\n"
        "   \n"
        "3. Third item\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["First item", "Second item", "Third item"]
```

### 2. All-malformed file returns empty list (not a crash)

```python
def test_load_backlog_all_malformed_returns_empty(tmp_path):
    p = tmp_path / "backlog_malformed.md"
    p.write_text(
        "No numbers here\n"
        "Still no numbers\n"
        "1.MissingSpace\n"
        "item without prefix\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == []
```

### 3. Comment lines (starting with `#`) excluded

```python
def test_load_backlog_comments_excluded(tmp_path):
    p = tmp_path / "backlog_comments.md"
    p.write_text(
        "# 1. This looks numbered but is a comment\n"
        "1. Real item\n"
        "# another comment\n"
        "2. Another real item\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["Real item", "Another real item"]
```

All three tests must be present in `api/tests/test_project_manager.py` and pass with:

```bash
python3 -m pytest api/tests/test_project_manager.py -x -v
```

---

## Verification Scenarios

The reviewer will run these against the test suite after implementation.

---

### Scenario 1 — Mixed numbered and unnumbered lines

**Setup**: Temporary backlog file containing:
```
1. First item
Unnumbered line
2. Second item
Another line without number

3. Third item
```

**Action**:
```bash
python3 -m pytest api/tests/test_project_manager.py::test_load_backlog_numbered_items -v
# (or the equivalent named test for mixed content)
```

**Expected result**: Test passes; `load_backlog()` returns exactly
`["First item", "Second item", "Third item"]` — three items, no unnumbered content.

**Edge case**: If the file contained ONLY unnumbered lines, return value must be `[]` and no
exception must be raised.

---

### Scenario 2 — All-malformed file returns empty list

**Setup**: Temporary backlog file containing only lines without valid `\d+\.\s+` prefix:
```
No numbers here
Still no numbers
1.MissingSpace
item without prefix
```

**Action**:
```bash
python3 -m pytest api/tests/test_project_manager.py::test_load_backlog_all_malformed_returns_empty -v
```

**Expected result**: Test passes; `load_backlog()` returns `[]`; no `ValueError`, `IndexError`,
or `AttributeError` raised.

**Edge case**: `1.MissingSpace` (no whitespace after dot) must NOT be parsed as a valid item —
the regex `r"^\d+\.\s+(.+)$"` requires one or more whitespace characters.

---

### Scenario 3 — Comment lines (starting with `#`) excluded

**Setup**: Temporary backlog file:
```
# 1. This looks numbered but is a comment
1. Real item
# another comment
2. Another real item
```

**Action**:
```bash
python3 -m pytest api/tests/test_project_manager.py::test_load_backlog_comments_excluded -v
```

**Expected result**: `load_backlog()` returns `["Real item", "Another real item"]`; the comment
line `# 1. This looks numbered but is a comment` is excluded.

**Edge case**: A comment that does not contain any digit prefix (e.g. `# plain comment`) must
also be excluded.

---

### Scenario 4 — Full test suite still passes

**Setup**: All existing tests in `test_project_manager.py` intact; new tests added.

**Action**:
```bash
python3 -m pytest api/tests/test_project_manager.py -x -v
```

**Expected result**: All tests pass, exit code 0, no `FAILED` or `ERROR` lines in output.

**Edge case**: If `pm.BACKLOG_FILE` is not reset between tests, later tests may use a stale
path from a previous `tmp_path`. Each test must set `pm.BACKLOG_FILE` at the start of the test.

---

### Scenario 5 — Order preservation in mixed file

**Setup**: Backlog file:
```
2. Second item
Noise line
1. First item
3. Third item
More noise
```

**Action**:
```bash
python3 -m pytest api/tests/test_project_manager.py -k "malformed or mixed or numbered" -v
```

**Expected result**: Items returned in file order: `["Second item", "First item", "Third item"]`
(order follows line order, not numeric value of prefix digit).

**Edge case**: Numeric ordering is NOT enforced — items are returned in file-line order. A test
must not assume sorted output.

---

## Out of Scope

- Changing `_parse_backlog_file` or `load_backlog` behavior (the implementation is already
  correct; this spec adds test coverage only).
- Testing an empty file (covered by existing `test_load_backlog_empty_file`).
- Meta-backlog interleaving logic (`PIPELINE_META_BACKLOG` env var) — covered separately.
- The `--backlog` CLI flag — covered by spec 041.

---

## Concurrency Behavior

- **Read operations**: `_parse_backlog_file` is read-only; safe for concurrent access.
- **Write operations**: `pm.BACKLOG_FILE` is a module-level variable; tests must set it per test
  and not run these particular tests in parallel to avoid races.
- **Recommendation**: Use `pytest-xdist` only with `-n auto` after confirming state isolation.

---

## Failure and Retry Behavior

- **Missing file**: `_parse_backlog_file` returns `[]` when path is absent — no retry needed.
- **Unreadable file**: `open()` will raise `PermissionError`; caller should handle via
  standard exception propagation (log + abort run).
- **Corrupt UTF-8**: `open(..., encoding="utf-8")` will raise `UnicodeDecodeError`; treat as
  unrecoverable for that file.

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `pm.BACKLOG_FILE` not reset between tests causes cross-test contamination | Medium | Each test sets `pm.BACKLOG_FILE` at start; use `tmp_path` fixture |
| `test_load_backlog_numbered_items` already covers mixed content — duplicate test | Low | Verify the test covers all edge cases listed here; add dedicated tests for all-malformed and comment-only scenarios |
| Future regex change breaks malformed-skip behavior | Low | These tests lock in the contract; they will fail loudly on regression |

---

## Known Gaps and Follow-up Tasks

- [ ] Validate behavior when `BACKLOG_FILE` points to a binary file (not a text file) — not
  covered here, low priority.
- [ ] Property-based test with `hypothesis` generating random line content — optional hardening.
- [ ] Confirm `test_load_backlog_numbered_items` (already present) covers the mixed-content
  case; if so, a dedicated `test_load_backlog_mixed_malformed` can reference it as a
  duplicate and focus on the all-malformed and comment scenarios only.

---

## See Also

- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — project manager orchestrator and backlog format
- [006-overnight-backlog.md](006-overnight-backlog.md) — backlog item 21
- [041-project-manager-state-file-flag-test.md](041-project-manager-state-file-flag-test.md) — `--state-file` flag test
- [042-project-manager-reset-clears-state-test.md](042-project-manager-reset-clears-state-test.md) — `--reset` flag test

---

## Verification

```bash
python3 -m pytest api/tests/test_project_manager.py -x -v
```

Exit code must be `0`. All tests — pre-existing and newly added — must pass.
