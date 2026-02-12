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

## API Contract

Same as spec 022. Request: multipart file. Response: ImportStackResponse.

Accept: package-lock.json (npm) or requirements.txt (PyPI).

## Files to Create/Modify

- `api/app/services/import_stack_service.py` — add parse_requirements(), enrich_pypi, process_requirements
- `api/app/routers/import_stack.py` — accept .txt; route to requirements parser

## Acceptance Tests

- POST with requirements.txt returns 200 with packages and risk_summary
- PyPI packages in GraphStore get coherence; others get "unknown"
- requirements.txt with `requests==2.28.0` parses correctly

## Out of Scope

- Pipfile, poetry.lock (future)
- Resolving version specs (use pinned version when ==, else "unknown" version)
