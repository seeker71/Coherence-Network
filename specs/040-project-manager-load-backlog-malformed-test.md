# Spec 040: Project Manager `load_backlog` — Malformed File (Missing Number Prefix) Test

## Summary

This spec defines the test coverage requirement for `load_backlog()` in
`api/scripts/project_manager.py` when the backlog file contains a mixture of
properly-numbered lines and lines that lack the required `\d+\. ` prefix. The
implementation already skips malformed lines; this spec formalises the test
that **proves** that behaviour under all relevant edge cases, so regressions
are caught immediately by pytest in CI.

---

## Goal

Guarantee that `load_backlog()` (and its inner helper `_parse_backlog_file()`)
is covered by at least one targeted test that:

1. Feeds a real temporary file (no mocks) containing both valid and malformed
   lines into `load_backlog()`.
2. Asserts that only items from lines matching `^\d+\.\s+(.+)$` are returned.
3. Asserts that the returned order matches the physical line order of the
   numbered items (order-preserving).
4. Asserts that malformed lines — including lines that start with text, blank
   lines, Markdown headings, comment lines, and lines that begin with a number
   but lack a dot-space separator — are silently skipped (no exception raised).

---

## Background

`_parse_backlog_file(path)` in `api/scripts/project_manager.py` iterates every
line, strips whitespace, and runs:

```python
m = re.match(r"^\d+\.\s+(.+)$", line)
if m and not line.startswith("#"):
    items.append(m.group(1).strip())
```

Lines that do not match are ignored. This is the correct and intended
behaviour. What was missing (prior to spec 040) was an explicit test whose
*only* purpose is to assert that malformed lines are silently dropped and do
not corrupt the output list.

---

## Requirements

- [ ] A test named `test_load_backlog_malformed_missing_number_prefix` exists
  in `api/tests/test_project_manager.py`.
- [ ] The test creates a `tmp_path`-scoped real file (no mock, no patch).
- [ ] The file contains at least two valid numbered lines and at least two
  lines that lack the `\d+\. ` prefix.
- [ ] The test calls `pm.load_backlog()` after setting `pm.BACKLOG_FILE` to the
  temp file path.
- [ ] The assertion is exact: only the text portions of the numbered lines are
  returned, in source order.
- [ ] `pytest api/tests/test_project_manager.py -x -v` exits 0.
- [ ] No modifications to `_parse_backlog_file` or `load_backlog` are made; the
  spec is test-only.

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `api/tests/test_project_manager.py` | Add (or confirm presence of) `test_load_backlog_malformed_missing_number_prefix` |

No other files are modified.

---

## Data Model

No database schema changes. The backlog file format is plain text:

```
^\d+\.\s+(.+)$   → valid item — captured group 1 is the task description
^#.*              → comment — skipped (starts with #)
.*                → everything else — silently skipped
```

Empty lines and blank-only lines are also skipped by the `strip()` + regex
pair.

---

## API Contract

N/A — this feature is a test-only change for a CLI script, not an HTTP endpoint.

---

## Acceptance Criteria

| # | Criterion | Done-when |
|---|-----------|-----------|
| 1 | Test exists in `api/tests/test_project_manager.py` | `grep test_load_backlog_malformed_missing_number_prefix` succeeds |
| 2 | Test uses real file I/O | No `mock`, `patch`, or `MagicMock` in the test body |
| 3 | Malformed lines silently skipped | `items == ["First item", "Second item"]` for the canonical input |
| 4 | Order preserved | Numbered lines appear in the same order as in the file |
| 5 | pytest passes | `pytest api/tests/test_project_manager.py -x -v` exits 0 |

---

## Verification Scenarios

### Scenario 1 — Canonical Malformed File (Happy Path)

**Setup:** A temp file with two numbered items interleaved with two unnumbered
lines.

```
1. First item
Unnumbered line
2. Second item
Another line without number
```

**Action (in pytest):**

```python
pm.BACKLOG_FILE = str(p)
items = pm.load_backlog()
assert items == ["First item", "Second item"]
```

**Expected result:** `["First item", "Second item"]` — exactly two items, order
preserved, no crash.

**Edge case:** If the file contained *only* unnumbered lines, `load_backlog()`
must return `[]` (empty list), not raise an exception.

---

### Scenario 2 — All Lines Malformed (Edge: Nothing to Parse)

**Setup:** A temp file whose every line lacks a digit prefix.

```
This is a heading
Another prose line
- bullet point
```

**Action:**

```python
p = tmp_path / "all_malformed.md"
p.write_text("This is a heading\nAnother prose line\n- bullet point\n")
pm.BACKLOG_FILE = str(p)
items = pm.load_backlog()
assert items == []
```

**Expected result:** `[]` — empty list, no exception.

**Edge case:** No crash even if the file is entirely whitespace (`"   \n   \n"`).

---

### Scenario 3 — Comment Lines Are Also Skipped

**Setup:** A file mixing valid items, unnumbered prose, and comment lines.

```
# This is a comment
1. Valid task one
Prose without number
# Another comment
2. Valid task two
```

**Action:**

```python
p = tmp_path / "with_comments.md"
p.write_text(
    "# This is a comment\n"
    "1. Valid task one\n"
    "Prose without number\n"
    "# Another comment\n"
    "2. Valid task two\n"
)
pm.BACKLOG_FILE = str(p)
items = pm.load_backlog()
assert items == ["Valid task one", "Valid task two"]
```

**Expected result:** `["Valid task one", "Valid task two"]`.

**Edge case:** A line like `#1. Not a task` starts with `#` so it is treated as
a comment and excluded even though it matches the number pattern.

---

### Scenario 4 — Number Present But Missing Dot-Space Separator

**Setup:** Lines that look numbered but use an invalid separator.

```
1) No dot separator
2- Dash separator
3 No separator at all
4. Valid item
```

**Action:**

```python
p = tmp_path / "bad_separator.md"
p.write_text(
    "1) No dot separator\n"
    "2- Dash separator\n"
    "3 No separator at all\n"
    "4. Valid item\n"
)
pm.BACKLOG_FILE = str(p)
items = pm.load_backlog()
assert items == ["Valid item"]
```

**Expected result:** `["Valid item"]` — only the line with `\d+\. ` matches.

**Edge case:** `10. Double-digit number` must also be parsed correctly.

---

### Scenario 5 — Order Preservation With Gaps in Numbering

**Setup:** A file where numbers are non-sequential and interspersed with prose.

```
prose header
3. Third (in file position 2)
more prose
1. First (in file position 4)
99. Ninety-ninth (in file position 6)
```

**Action:**

```python
p = tmp_path / "gaps.md"
p.write_text(
    "prose header\n"
    "3. Third (in file position 2)\n"
    "more prose\n"
    "1. First (in file position 4)\n"
    "99. Ninety-ninth (in file position 6)\n"
)
pm.BACKLOG_FILE = str(p)
items = pm.load_backlog()
assert items == [
    "Third (in file position 2)",
    "First (in file position 4)",
    "Ninety-ninth (in file position 6)",
]
```

**Expected result:** Items appear in **file line order**, not numeric-label
order.

**Edge case:** The function does not sort or deduplicate; the numeric label is
irrelevant to ordering.

---

## CLI Commands (Verification)

```bash
# Run the targeted test in isolation
python3 -m pytest api/tests/test_project_manager.py \
  -k "malformed" -v

# Run the full test module (must all pass)
python3 -m pytest api/tests/test_project_manager.py -x -v
```

Expected exit code: `0`.

---

## Out of Scope

- Changing `_parse_backlog_file` or `load_backlog` implementation (the parsing
  logic is already correct).
- Testing empty file or comment-only file beyond what is covered by
  `test_load_backlog_empty_file` and the edge cases above.
- Meta-backlog interleaving (PIPELINE_META_BACKLOG env var) — covered by spec
  028.
- Concurrent access or file-locking concerns.
- Web UI or API endpoint changes.

---

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| `pm.BACKLOG_FILE` is a module-level global; one test mutating it may affect others | Each test uses `tmp_path` and sets `pm.BACKLOG_FILE` at the start; pytest isolation is sufficient |
| Regex `^\d+\.\s+(.+)$` may behave differently on Windows (`\r\n` endings) | `line.strip()` normalises line endings before matching |
| Future refactor renames `_parse_backlog_file` | Test calls `load_backlog()` (the public API), not the private helper directly |

---

## Known Gaps and Follow-up Tasks

- **Gap:** The test does not cover Unicode content in backlog items (e.g. CJK
  characters, emoji). If needed, add a follow-up test.
- **Follow-up:** Consider adding a pytest fixture that resets `pm.BACKLOG_FILE`
  after each test to avoid global-state leakage between tests in the module.
- **Follow-up:** Property-based testing (Hypothesis) could generate arbitrary
  malformed lines and verify no exception is ever raised.

---

## Concurrency Behaviour

- **Read operations:** `_parse_backlog_file` opens the file in read-only mode;
  safe for concurrent access with no locking required.
- **Write operations:** N/A for this spec (tests do not write to the real
  backlog file).

---

## Failure and Retry Behaviour

- **Missing file:** `_parse_backlog_file` returns `[]` if the path does not
  exist (`os.path.isfile(path)` check).
- **Permission error:** Not handled; caller receives an `OSError`. No retry
  logic needed for a local test environment.

---

## See Also

- [005-project-manager-orchestrator.md](005-project-manager-orchestrator.md) —
  project manager orchestrator
- [006-overnight-backlog.md](006-overnight-backlog.md) — backlog item 21
- [041-project-manager-state-file-flag-test.md](041-project-manager-state-file-flag-test.md) —
  companion test spec for state-file flag
- [042-project-manager-reset-clears-state-test.md](042-project-manager-reset-clears-state-test.md) —
  companion test spec for reset behaviour

---

## Decision Gates

None required. The implementation is already correct; this spec only adds test
coverage.

---

## Verification Command

```bash
python3 -m pytest api/tests/test_project_manager.py -x -v
```
