# Spec 080: Persistent Store Test Contributor Guard

## Goal
Prevent test contributors from polluting persistent contributor data.

## Requirements
- [x] Persistent stores reject contributor creation for test emails.
- [x] Persistent stores purge previously stored test contributors at load/startup.
- [x] Any contributions linked to purged test contributors are removed.
- [x] API returns `422` when persistent store rejects a test contributor.
- [x] Existing non-persistent test flows remain unaffected.

## Files To Modify (Allowed)
- `specs/080-persistent-store-test-contributor-guard.md`
- `api/app/services/contributor_hygiene.py`
- `api/app/adapters/graph_store.py`
- `api/app/adapters/postgres_store.py`
- `api/app/routers/contributors.py`
- `api/app/routers/contributions.py`
- `api/tests/test_contributor_hygiene.py`

## Validation
```bash
cd api && pytest -q tests/test_contributor_hygiene.py tests/test_contributors.py tests/test_contributions.py
```
