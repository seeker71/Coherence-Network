# Real-World Examples

## Example 1: Record Your Initial Contribution

**Scenario**: You spent 16 hours over 2 days building the Coherence Network MVP.

**Step 1**: Calculate total cost

```bash
# Human labor
HOURS=16
RATE=150
LABOR_COST=$(echo "$HOURS * $RATE" | bc)  # $2400

# Cursor Pro subscription (2 days prorated)
CURSOR_COST=1.33

# Mac M4 Ultra compute
COMPUTE_COST=11.86

# Total
TOTAL=$(echo "$LABOR_COST + $CURSOR_COST + $COMPUTE_COST" | bc)  # $2413.19
```

**Step 2**: Assess coherence

```json
{
  "code_quality_score": 0.85,
  "architecture_alignment": 1.0,
  "value_add_score": 1.0,
  "test_coverage": 0.3,
  "documentation_score": 0.7
}
```

**Step 3**: Record contribution

```bash
curl -X POST https://api.coherence-network.io/v1/contributions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "contributor_id": "your-uuid",
    "asset_id": "coherence-network-uuid",
    "event_type": "PROJECT_INCEPTION",
    "cost_amount": 2413.19,
    "resonance": {
      "code_quality_score": 0.85,
      "architecture_alignment": 1.0,
      "value_add_score": 1.0,
      "test_coverage": 0.3,
      "documentation_score": 0.7
    },
    "metadata": {
      "hours_worked": 16,
      "tools_used": ["Cursor Pro+", "OpenRouter Free", "Claude Code"],
      "description": "Initial MVP architecture and implementation"
    }
  }'
```

**Expected Response**:
```json
{
  "event_id": "uuid",
  "coherence_score": 0.92,
  "coherence_multiplier": 1.42,
  "weighted_cost": 3426.73,
  "recorded_at": "2026-02-13T10:00:00Z"
}
```

## Example 2: Distribute $10,000

**Scenario**: Asset generates $10,000 in value. Distribute to contributors.

```bash
curl -X POST https://api.coherence-network.io/v1/distributions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY_ADMIN" \
  -d '{
    "asset_id": "coherence-network-uuid",
    "value_amount": 10000.00,
    "distribution_method": "COHERENCE_WEIGHTED"
  }'
```

**Response**:
```json
{
  "distribution_id": "uuid",
  "total_distributed": 10000.00,
  "payouts": [
    {
      "contributor_name": "seeker71",
      "payout_amount": 9622.18,
      "direct_cost": 2413.19,
      "coherence_multiplier": 1.42
    },
    {
      "contributor_name": "Urs Muff",
      "payout_amount": 377.82,
      "direct_cost": 100.00,
      "coherence_multiplier": 1.14
    }
  ]
}
```

## Example 3: Register as Node Operator

**Scenario**: You have a $5/month VPS with spare capacity.

```bash
curl -X POST https://api.coherence-network.io/v1/nodes \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "operator_id": "your-contributor-uuid",
    "node_type": "API",
    "endpoint": "https://your-node.example.com",
    "specs": {
      "cpu_cores": 1,
      "ram_gb": 1,
      "storage_gb": 25
    },
    "pricing": {
      "api_request": 0.00002,
      "storage_gb_month": 0.005
    },
    "health_check_url": "https://your-node.example.com/health"
  }'
```

**Response**:
```json
{
  "node_id": "uuid",
  "status": "ACTIVE",
  "api_key": "node-api-key",
  "pricing_rank": {
    "percentile": 15,
    "message": "You're 15th cheapest out of 100 nodes!"
  }
}
```

**Revenue Projection**:
- At 10% utilization: $5/month (covers costs)
- At 50% utilization: $25/month (5x profit!)
- At 90% utilization: $45/month (9x profit!)
