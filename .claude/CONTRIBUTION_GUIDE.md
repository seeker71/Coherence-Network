# Contribution Guide

## What Counts as a Contribution?

**Everything that adds value**:
- Writing code
- Fixing bugs
- Writing documentation
- Designing features
- Code reviews
- Testing
- DevOps/deployment
- Community support

## How to Record a Contribution

### Step 1: Calculate Cost

**Human Labor**:
```
Hours worked × Hourly rate = Labor cost
Example: 2 hours × $150/hr = $300
```

**Tool Usage** (LLM API calls):
```
Input tokens × Input rate + Output tokens × Output rate = Tool cost
Example: 1000 × $0.000003 + 500 × $0.000015 = $0.0105
```

**Compute** (local machine):
```
Hours × Power (kW) × Electricity rate + (Hardware cost / Lifetime hours) × Hours
Example: 2 × 0.14 × $0.15 + ($7199 / 10000) × 2 = $0.042 + $1.44 = $1.48
```

**Total Cost**: Labor + Tools + Compute

### Step 2: Assess Coherence

Run automated assessment or self-assess:

**Code Quality** (0.0 to 1.0):
- 0 lint errors: 1.0
- 1-5 errors: 0.8
- 6-10 errors: 0.6
- 10+ errors: 0.4

**Architecture Alignment** (0.0 to 1.0):
- Perfect alignment with CCN principles: 1.0
- Good alignment: 0.8
- Some alignment: 0.6
- Poor alignment: 0.4

**Value Add** (0.0 to 1.0):
- Novel contribution: 1.0
- Incremental improvement: 0.8
- Minor change: 0.6
- Duplicate work: 0.3

**Test Coverage** (0.0 to 1.0):
- >90%: 1.0
- 75-90%: 0.8
- 50-75%: 0.6
- <50%: 0.4

**Documentation** (0.0 to 1.0):
- All functions documented: 1.0
- >75% documented: 0.8
- 50-75%: 0.6
- <50%: 0.4

### Step 3: Record via API

```bash
curl -X POST https://api.your-domain.com/v1/contributions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "contributor_id": "your-contributor-id",
    "asset_id": "asset-id",
    "event_type": "MANUAL_LABOR",
    "cost_amount": 301.48,
    "resonance": {
      "code_quality_score": 0.85,
      "architecture_alignment": 1.0,
      "value_add_score": 0.9,
      "test_coverage": 0.8,
      "documentation_score": 0.7
    },
    "metadata": {
      "hours_worked": 2,
      "files_changed": ["api/routes/distributions.py"],
      "lines_added": 150,
      "description": "Implemented value distribution API endpoint"
    }
  }'
```

## GitHub Integration

### Automatic Tracking

When you push commits, the webhook automatically:
1. Captures commit metadata
2. Estimates cost (files changed × $10 base)
3. Calculates basic coherence
4. Records contribution event

**No manual action needed!**

### Manual Override

If automatic estimate is wrong:

```bash
# Get the auto-created contribution
curl https://api.your-domain.com/v1/contributions?commit_hash=abc123 \
  -H "X-API-Key: $API_KEY"

# Update with correct values
curl -X PATCH https://api.your-domain.com/v1/contributions/event-id \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "cost_amount": 150.00,
    "resonance": {
      "code_quality_score": 0.95
    }
  }'
```

## Code Patterns

### Always Use Decimal for Money

**Wrong**:
```python
cost = 100.50  # float - rounding errors!
```

**Right**:
```python
from decimal import Decimal
cost = Decimal("100.50")  # exact precision
```

### Always Use Async/Await

**Wrong**:
```python
def get_contributor(id):
    return db.query(Contributor).get(id)
```

**Right**:
```python
async def get_contributor(id: UUID) -> Contributor:
    return await db.query(Contributor).get(id)
```

### Always Validate with Pydantic

**Wrong**:
```python
data = request.json()
contributor = Contributor(**data)
```

**Right**:
```python
from pydantic import BaseModel

class ContributorCreate(BaseModel):
    name: str
    email: EmailStr
    wallet_address: str

contributor = ContributorCreate(**request.json())
```

### Always Record to Both DBs

**Wrong**:
```python
await postgres.insert(contribution)
# Forgot Neo4j!
```

**Right**:
```python
async with transaction_manager.begin():
    await postgres.insert(contribution)
    await neo4j.create_edge(contribution)
```

## Testing Contributions

### Test Distribution Calculation

```python
# Create test data
alice = create_contributor(name="Alice")
asset = create_asset(name="test-asset")

# Record contributions
record_contribution(alice, asset, cost=Decimal("100"), coherence=Decimal("0.9"))

# Distribute value
payouts = await distribute_value(asset.id, Decimal("1000"))

# Verify
assert payouts[alice.id] == Decimal("1000")  # 100% of contributions
```

### Test Coherence Scores

```python
# High coherence
resonance = ResonanceMetrics(
    code_quality_score=Decimal("0.95"),
    architecture_alignment=Decimal("1.0"),
    value_add_score=Decimal("1.0"),
    test_coverage=Decimal("0.9"),
    documentation_score=Decimal("0.85")
)

coherence = calculate_coherence(resonance)
assert coherence >= Decimal("0.9")  # Should be high
```

## Common Tasks

### Add a New Contributor

```bash
curl -X POST https://api.your-domain.com/v1/contributors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY_ADMIN" \
  -d '{
    "type": "HUMAN",
    "name": "Jane Developer",
    "email": "jane@example.com",
    "wallet_address": "0x..."
  }'
```

### Record Tool Execution

```bash
curl -X POST https://api.your-domain.com/v1/contributions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "contributor_id": "system-claude-id",
    "asset_id": "asset-id",
    "event_type": "TOOL_EXECUTION",
    "cost_amount": 0.15,
    "tool_profile_id": "claude-sonnet-4-profile-id",
    "triggered_by_contributor_id": "your-id",
    "metadata": {
      "model": "claude-sonnet-4-20250514",
      "tokens_input": 1000,
      "tokens_output": 500
    }
  }'
```

### Run a Distribution

```bash
curl -X POST https://api.your-domain.com/v1/distributions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY_ADMIN" \
  -d '{
    "asset_id": "asset-id",
    "value_amount": 10000.00,
    "distribution_method": "COHERENCE_WEIGHTED",
    "notes": "Q1 2026 revenue distribution"
  }'
```

### Check Your Earnings

```bash
curl https://api.your-domain.com/v1/contributors/your-id/payouts \
  -H "X-API-Key: $API_KEY" \
  | jq '.total_earned'
```

## Best Practices

1. **Record immediately**: Don't wait - record contributions as they happen
2. **Be honest**: Accurate cost tracking ensures fair distributions
3. **Document well**: High documentation score → higher coherence → more earnings
4. **Write tests**: Test coverage directly impacts coherence score
5. **Follow conventions**: Architecture alignment is heavily weighted
6. **Review others**: Code review is also a contribution!
