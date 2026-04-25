# Cursor Workflows

## Generate New API Endpoint

**Prompt**:
```
Create a new FastAPI endpoint for listing all distributions with pagination.

Requirements:
- Route: GET /v1/distributions
- Query params: page (int), page_size (int, max 100), status filter
- Response: list of distributions with pagination metadata
- Include contributor names in results
- Add to api/routes/distributions.py
- Use async/await
- Validate with Pydantic
- Add error handling
```

**Files Created**:
- `api/routes/distributions.py` (updated)
- `models/distribution.py` (updated)

## Add Database Migration

**Prompt**:
```
Create an Alembic migration to add a 'reputation_score' column to contributors table.

Requirements:
- Column: reputation_score INTEGER DEFAULT 0
- Index on reputation_score for leaderboard queries
- Include upgrade and downgrade functions
- Follow existing migration pattern
```

**Command**:
```bash
cursor chat "Create Alembic migration for reputation_score column"
alembic revision --autogenerate -m "add_reputation_score"
alembic upgrade head
```

## Implement Distribution Method

**Prompt**:
```
Add a new distribution method 'TIME_WEIGHTED' that gives more weight to recent contributions.

Requirements:
- In services/distribution_engine.py
- Add TimeWeightedDistribution class
- Weight formula: cost × (0.5 + coherence) × (1 + days_ago / 365)
- Use exponential decay for very old contributions
- Add tests in tests/test_distribution.py
```
