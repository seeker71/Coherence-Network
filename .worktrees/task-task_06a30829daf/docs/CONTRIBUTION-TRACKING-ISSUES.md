# Contribution Tracking Issues — 2026-02-14

## Summary

The Auto-Track Contributions workflow is configured but **not working** due to schema mismatches and lack of database persistence.

## Issues

### 1. ❌ No Database Persistence

**Current State:**
```python
# api/app/main.py
app.state.graph_store = InMemoryGraphStore()  # No persist_path parameter
```

**Problem:**
- All data stored in memory only
- Lost on every Railway container restart
- No PostgreSQL or Neo4j integration yet

**Evidence:**
```bash
$ curl https://coherence-network-production.up.railway.app/v1/contributors
[]  # Empty - all data lost on restart

$ curl https://coherence-network-production.up.railway.app/v1/assets
[]  # Empty - all data lost on restart
```

### 2. ❌ Workflow Schema Mismatch

**What the workflow sends:**
```json
{
  "contributor_email": "user@example.com",  ❌
  "event_type": "GIT_COMMIT",                ❌
  "cost_amount": 123,
  "metadata": {...}
}
```

**What the API expects** (from `app/models/contribution.py`):
```json
{
  "contributor_id": "uuid",  ✅ Required
  "asset_id": "uuid",        ✅ Required
  "cost_amount": 123,
  "metadata": {...}
}
```

**Result:** Workflow would fail with `422 Unprocessable Entity`

### 3. ❌ No Contributors or Assets Exist

Even with correct schema, POST to `/v1/contributions` would fail:

```python
# api/app/routers/contributions.py
@router.post("/contributions", ...)
async def create_contribution(...):
    if not store.get_contributor(contribution.contributor_id):
        raise HTTPException(status_code=404, detail="Contributor not found")  # ❌

    if not store.get_asset(contribution.asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")  # ❌
```

Database is empty, so both checks fail.

### 4. ⚠️ No API Key Validation

The workflow sends `X-API-Key` header but the API doesn't validate it (no auth middleware).

## Fix Options

### Option A: Quick Fix - JSON Persistence (Minimal Changes)

Enable JSON file persistence for InMemoryGraphStore:

```python
# api/app/main.py
persist_path = os.getenv("GRAPH_STORE_PATH", "/tmp/graph_store.json")
app.state.graph_store = InMemoryGraphStore(persist_path=persist_path)

# Save on shutdown
@app.on_event("shutdown")
def save_data():
    app.state.graph_store.save()
```

**Pros:**
- Quick to implement
- No database setup needed
- Works on Railway with persistent disk

**Cons:**
- Single file - no concurrent writes
- Not suitable for production scale
- Manual save/load required

### Option B: Add Helper Endpoint for GitHub Webhooks (Recommended)

Create a new endpoint that accepts email and auto-creates contributor/asset:

```python
# New endpoint: POST /v1/contributions/github
@router.post("/contributions/github")
async def track_github_contribution(
    contributor_email: str,
    repository: str,
    commit_hash: str,
    cost_amount: Decimal,
    metadata: dict,
    store: GraphStore = Depends(get_store)
):
    # Find or create contributor by email
    contributor = store.find_contributor_by_email(contributor_email)
    if not contributor:
        contributor = store.create_contributor(Contributor(
            name=contributor_email.split('@')[0],
            email=contributor_email
        ))

    # Find or create asset for this repository
    asset = store.find_asset_by_name(repository)
    if not asset:
        asset = store.create_asset(Asset(
            name=repository,
            asset_type="REPOSITORY"
        ))

    # Create contribution
    coherence = calculate_coherence_from_metadata(metadata)
    return store.create_contribution(
        contributor_id=contributor.id,
        asset_id=asset.id,
        cost_amount=cost_amount,
        coherence_score=coherence,
        metadata=metadata
    )
```

Update workflow to use this endpoint.

**Pros:**
- Matches workflow data structure
- Auto-creates entities as needed
- Clean separation of concerns

**Cons:**
- Still needs persistence (Option A or C)
- Requires adding email index to store

### Option C: Real Database Integration (Production-Ready)

Implement PostgreSQL or Neo4j adapter:

1. Create `PostgresGraphStore` or `Neo4jGraphStore`
2. Configure DATABASE_URL on Railway
3. Add migrations for schema
4. Update main.py to use real store

**Pros:**
- Production-ready
- True persistence
- Concurrent access
- Query capabilities

**Cons:**
- More work to implement
- Requires database provisioning
- More complex deployment

## Recommended Approach

**Phase 1 (Immediate):**
1. Add JSON persistence (Option A) to stop losing data on restart
2. Create `/v1/contributions/github` endpoint (Option B)
3. Update workflow to use new endpoint
4. Verify end-to-end tracking works

**Phase 2 (Next):**
1. Implement PostgreSQL adapter (Option C)
2. Migrate from JSON to real database
3. Add proper authentication
4. Add monitoring/metrics

## Verification Steps

After fixes, verify:

```bash
# 1. Check persistence survives restart
curl https://api.../v1/contributors
# Should return data after restart

# 2. Test contribution creation
curl -X POST https://api.../v1/contributions/github \
  -H "Content-Type: application/json" \
  -d '{
    "contributor_email": "test@example.com",
    "repository": "seeker71/Coherence-Network",
    "commit_hash": "abc123",
    "cost_amount": 100.00,
    "metadata": {...}
  }'

# 3. Verify stored
curl https://api.../v1/contributors
curl https://api.../v1/contributions
```

## Files to Modify

**Option A + B (Recommended Quick Fix):**
- `api/app/main.py` — Add persist_path
- `api/app/adapters/graph_store.py` — Add find_by_email methods
- `api/app/routers/contributions.py` — Add `/github` endpoint
- `.github/workflows/auto_track_contributions.yml` — Update endpoint URL
- `api/.env.example` — Add GRAPH_STORE_PATH

**Option C (Future):**
- `api/app/adapters/postgres_store.py` — New file
- `api/alembic/` — Database migrations
- Railway: Provision PostgreSQL addon

## Current Status

- ❌ Contributions are NOT being tracked
- ❌ Database is empty on Railway
- ❌ Workflow would fail if secrets were configured
- ⚠️ No monitoring of tracking status

## Next Steps

1. Decide on fix approach (recommend Phase 1)
2. Implement persistence + helper endpoint
3. Test locally
4. Deploy to Railway
5. Verify end-to-end tracking
6. Add monitoring/alerts
