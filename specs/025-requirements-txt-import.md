# Spec: requirements.txt Import (extend spec 022)

## Purpose

Per docs/STATUS.md: extend import stack to accept requirements.txt (PyPI). Users can upload requirements.txt for Python projects and get coherence risk analysis. Same API shape as package-lock.json import.

## Requirements

- [x] POST /api/import/stack accepts requirements.txt in addition to package-lock.json
- [x] Detect format by filename: .json -> lockfile, .txt -> requirements
- [x] Parse requirements.txt: name==version, name>=x, name (PEP 508)
- [x] Look up packages in GraphStore with ecosystem="pypi"
- [x] Return same ImportStackResponse shape (packages, risk_summary)
- [x] Real parsing (no mocks)


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Per docs/STATUS.
files_allowed:
  - api/app/services/import_stack_service.py
  - api/app/routers/import_stack.py
done_when:
  - POST /api/import/stack accepts requirements.txt in addition to package-lock.json
  - Detect format by filename: .json -> lockfile, .txt -> requirements
  - Parse requirements.txt: name==version, name>=x, name (PEP 508)
  - Look up packages in GraphStore with ecosystem="pypi"
  - Return same ImportStackResponse shape (packages, risk_summary)
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

Same as spec 022. Request: multipart file. Response: ImportStackResponse.

Accept: package-lock.json (npm) or requirements.txt (PyPI).


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Files to Create/Modify

- `api/app/services/import_stack_service.py` — add parse_requirements(), enrich_pypi, process_requirements
- `api/app/routers/import_stack.py` — accept .txt; route to requirements parser

## Acceptance Tests

- POST with requirements.txt returns 200 with packages and risk_summary
- PyPI packages in GraphStore get coherence; others get "unknown"
- requirements.txt with `requests==2.28.0` parses correctly

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Render error**: Show fallback error boundary with retry action.
- **API failure**: Display user-friendly error message; retry fetch on user action or after 5s.
- **Network offline**: Show offline indicator; queue actions for replay on reconnect.
- **Asset load failure**: Retry asset load up to 3 times; show placeholder on permanent failure.
- **Timeout**: API calls timeout after 10s; show loading skeleton until resolved or failed.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add end-to-end browser tests for critical paths.


## Out of Scope

- Pipfile, poetry.lock (future)
- Resolving version specs (use pinned version when ==, else "unknown" version)
