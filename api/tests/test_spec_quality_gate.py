from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts" / "validate_spec_quality.py"


def test_spec_quality_gate_passes_for_complete_spec(tmp_path: Path) -> None:
    spec = tmp_path / "100-sample-spec.md"
    spec.write_text(
        """
# Spec: Sample

## Purpose

This spec prevents ambiguity by defining exact requirements, tests, and validation commands before implementation begins.

## Requirements

- [ ] `GET /api/sample` returns 200 with deterministic JSON payload.
- [ ] Request validation rejects invalid IDs with 422.
- [ ] Runtime usage is tracked to idea lineage for this endpoint.

## API Contract (if applicable)

### `GET /api/sample`

Returns 200 with `{ "ok": true }`.

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `api/app/routers/sample.py` - API route.
- `api/tests/test_sample.py` - acceptance tests.

## Acceptance Tests

- `api/tests/test_sample.py::test_get_sample_200`
- `api/tests/test_sample.py::test_get_sample_422`

## Verification

```bash
cd api && pytest -q tests/test_sample.py
```

## Out of Scope

- UI changes.

## Risks and Assumptions

- Risk: upstream API latency; mitigation via timeout guard.
- Assumption: sample payload schema remains stable.

## Known Gaps and Follow-up Tasks

- None at spec time.
""".strip(),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(_script_path()), "--file", str(spec)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_spec_quality_gate_fails_when_required_sections_missing(tmp_path: Path) -> None:
    spec = tmp_path / "101-incomplete-spec.md"
    spec.write_text(
        """
# Spec: Incomplete

## Purpose

Short purpose only.

## Requirements

- [ ] Requirement 1
- [ ] Requirement 2
- [ ] Requirement 3
""".strip(),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(_script_path()), "--file", str(spec)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "missing required section: verification" in combined
    assert "missing required section: gaps" in combined


def test_spec_quality_gate_fails_on_template_placeholders(tmp_path: Path) -> None:
    spec = tmp_path / "102-placeholder-spec.md"
    spec.write_text(
        """
# Spec: [Feature Name]

## Purpose

[1-2 sentences: WHY this exists]

## Requirements

- [ ] Requirement 1
- [ ] Requirement 2
- [ ] Requirement 3

## Files to Create/Modify

- `api/app/routers/example.py` - route

## Acceptance Tests

- `api/tests/test_example.py::test_ok`

## Verification

pytest -q

## Out of Scope

- TBD

## Risks and Assumptions

- TBD

## Known Gaps and Follow-up Tasks

- None at spec time.
""".strip(),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(_script_path()), "--file", str(spec)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "contains unresolved template placeholder" in (result.stdout + result.stderr)
