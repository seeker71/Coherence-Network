# API Reference

Base URL: `https://api.coherence-network.io`

Authentication: API key in `X-API-Key` header

## Contributors API

### Create Contributor

**POST** `/v1/contributors`

Creates a new contributor (human or system).

**Request**:
```json
{
  "type": "HUMAN",
  "name": "Jane Developer",
  "email": "jane@example.com",
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
}
```

**Response**:
```json
{
  "id": "uuid",
  "type": "HUMAN",
  "name": "Jane Developer",
  "email": "jane@example.com",
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
  "total_cost_contributed": 0.0,
  "total_value_earned": 0.0,
  "created_at": "2026-02-13T10:00:00Z"
}
```

**Example**:
```bash
curl -X POST https://api.coherence-network.io/v1/contributors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"type":"HUMAN","name":"Jane","email":"jane@example.com","wallet_address":"0x..."}'
```

### Get Contributor

**GET** `/v1/contributors/{contributor_id}`

**Response**:
```json
{
  "id": "uuid",
  "name": "Jane Developer",
  "type": "HUMAN",
  "total_cost_contributed": 2413.19,
  "total_value_earned": 9622.18,
  "contribution_count": 150,
  "coherence_average": 0.92
}
```

### List Contributor Payouts

**GET** `/v1/contributors/{contributor_id}/payouts`

**Query Parameters**:
- `status`: `PENDING|COMPLETED|FAILED`
- `from_date`: ISO 8601 date
- `to_date`: ISO 8601 date

**Response**:
```json
{
  "payouts": [
    {
      "payout_id": "uuid",
      "amount": 9622.18,
      "distribution_id": "uuid",
      "status": "COMPLETED",
      "transaction_hash": "0x...",
      "created_at": "2026-02-13T10:00:00Z"
    }
  ],
  "total": 9622.18,
  "count": 1
}
```

## Assets API

### Create Asset

**POST** `/v1/assets`

**Request**:
```json
{
  "type": "CODE",
  "name": "Coherence-Network",
  "version": "1.0.0",
  "content_hash": "sha256:abc123...",
  "storage_uri": "github.com/seeker71/Coherence-Network"
}
```

**Response**:
```json
{
  "id": "uuid",
  "type": "CODE",
  "name": "Coherence-Network",
  "version": "1.0.0",
  "creation_cost_total": 0.0,
  "total_value_generated": 0.0,
  "contributor_count": 0,
  "status": "ACTIVE",
  "created_at": "2026-02-13T10:00:00Z"
}
```

### Get Asset Lineage

**GET** `/v1/assets/{asset_id}/lineage`

Returns complete contribution graph.

**Response**:
```json
{
  "asset_id": "uuid",
  "contributors": [
    {
      "contributor_id": "uuid",
      "name": "seeker71",
      "direct_cost": 2413.19,
      "coherence_score": 0.92,
      "depth": 0
    }
  ],
  "total_cost": 2413.19,
  "max_depth": 1
}
```

## Contributions API

### Record Contribution

**POST** `/v1/contributions`

**Request**:
```json
{
  "contributor_id": "uuid",
  "asset_id": "uuid",
  "event_type": "MANUAL_LABOR",
  "cost_amount": 150.00,
  "resonance": {
    "code_quality_score": 0.85,
    "architecture_alignment": 0.90,
    "value_add_score": 0.80,
    "test_coverage": 0.75,
    "documentation_score": 0.70
  },
  "metadata": {
    "hours_worked": 1,
    "description": "Implemented distribution API"
  }
}
```

**Response**:
```json
{
  "event_id": "uuid",
  "coherence_score": 0.82,
  "coherence_multiplier": 1.32,
  "weighted_cost": 198.00,
  "recorded_at": "2026-02-13T10:00:00Z"
}
```

### List Asset Contributions

**GET** `/v1/assets/{asset_id}/contributions`

**Response**:
```json
{
  "contributions": [
    {
      "event_id": "uuid",
      "contributor_name": "seeker71",
      "event_type": "PROJECT_INCEPTION",
      "cost_amount": 2413.19,
      "coherence_score": 0.92,
      "timestamp": "2026-02-11T10:00:00Z"
    }
  ],
  "total_cost": 2413.19,
  "count": 1
}
```

## Distributions API

### Trigger Distribution

**POST** `/v1/distributions`

**Request**:
```json
{
  "asset_id": "uuid",
  "value_amount": 10000.00,
  "distribution_method": "COHERENCE_WEIGHTED",
  "max_depth": -1,
  "notes": "Q1 2026 revenue"
}
```

**Response**:
```json
{
  "distribution_id": "uuid",
  "asset_id": "uuid",
  "total_distributed": 10000.00,
  "contributor_count": 2,
  "payouts": [
    {
      "contributor_id": "uuid",
      "contributor_name": "seeker71",
      "payout_amount": 9622.18,
      "payout_share": 0.9622,
      "direct_cost": 2413.19,
      "coherence_multiplier": 1.20
    },
    {
      "contributor_id": "uuid",
      "contributor_name": "Urs Muff",
      "payout_amount": 377.82,
      "payout_share": 0.0378,
      "direct_cost": 100.00,
      "coherence_multiplier": 1.14
    }
  ],
  "created_at": "2026-02-13T10:00:00Z"
}
```

### Get Distribution

**GET** `/v1/distributions/{distribution_id}`

Returns complete distribution details including audit trail.

## Nodes API

### Register Node

**POST** `/v1/nodes`

**Request**:
```json
{
  "operator_id": "uuid",
  "node_type": "API",
  "endpoint": "https://node.example.com",
  "specs": {
    "cpu_cores": 4,
    "ram_gb": 8,
    "storage_gb": 100
  },
  "pricing": {
    "api_request": 0.00002,
    "storage_gb_month": 0.005,
    "compute_hour": 0.008
  }
}
```

**Response**:
```json
{
  "node_id": "uuid",
  "status": "ACTIVE",
  "api_key": "generated-api-key",
  "created_at": "2026-02-13T10:00:00Z"
}
```

### List Nodes

**GET** `/v1/nodes`

**Query Parameters**:
- `node_type`: `API|STORAGE|COMPUTE`
- `status`: `ACTIVE|OFFLINE`
- `sort_by`: `price|uptime`

**Response**:
```json
{
  "nodes": [
    {
      "node_id": "uuid",
      "operator_name": "seeker71",
      "node_type": "API",
      "pricing": {"api_request": 0.00002},
      "uptime_percentage": 99.95,
      "status": "ACTIVE"
    }
  ]
}
```

## Webhooks

### GitHub Webhook

**POST** `/webhooks/github`

Receives GitHub push events.

**Headers**:
- `X-GitHub-Event`: `push`
- `X-Hub-Signature-256`: HMAC signature

**Request** (from GitHub):
```json
{
  "repository": {"full_name": "seeker71/Coherence-Network"},
  "commits": [
    {
      "id": "abc123",
      "author": {"name": "seeker71", "email": "..."},
      "message": "Add distribution API",
      "added": ["api/routes/distributions.py"],
      "modified": ["README.md"]
    }
  ]
}
```

**Response**:
```json
{
  "status": "processed",
  "contributions_created": 1,
  "event_ids": ["uuid"]
}
```

## Error Responses

### 400 Bad Request
```json
{
  "error": "validation_error",
  "message": "cost_amount must be positive",
  "field": "cost_amount"
}
```

### 401 Unauthorized
```json
{
  "error": "unauthorized",
  "message": "Invalid API key"
}
```

### 404 Not Found
```json
{
  "error": "not_found",
  "message": "Contributor not found",
  "resource_id": "uuid"
}
```

### 500 Internal Server Error
```json
{
  "error": "internal_error",
  "message": "Database connection failed",
  "request_id": "uuid"
}
```
