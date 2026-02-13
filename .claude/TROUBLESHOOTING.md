# Troubleshooting

## Database Connection Issues

### PostgreSQL Connection Failed

**Symptoms**: `asyncpg.exceptions.CannotConnectNowError`

**Causes**:
1. Wrong connection string
2. Database not running
3. Firewall blocking port 5432
4. SSL required but not configured

**Solutions**:
```bash
# Test connection
psql $DATABASE_URL

# Check if database is running
sudo systemctl status postgresql

# Allow connections in pg_hba.conf
sudo nano /etc/postgresql/14/main/pg_hba.conf
# Add: host all all 0.0.0.0/0 md5

# Restart
sudo systemctl restart postgresql
```

### Neo4j Authentication Error

**Symptoms**: `neo4j.exceptions.AuthError`

**Solution**:
```bash
# Reset password
docker exec neo4j cypher-shell -u neo4j -p old-password
ALTER USER neo4j SET PASSWORD 'new-password';
```

## API Errors

### 401 Unauthorized

**Cause**: Invalid or missing API key

**Solution**:
```bash
# Check API key format
echo $API_KEY  # Should be 32-char hex

# Regenerate if needed
API_KEY=$(openssl rand -hex 16)
```

### 400 Validation Error

**Cause**: Invalid request body

**Solution**: Check Pydantic model requirements

```python
# Example fix
{
  "cost_amount": 100.00,  # Must be Decimal, not string
  "coherence_score": 0.85  # Must be 0.0-1.0
}
```

## Distribution Errors

### Cycle Detected

**Symptoms**: Distribution fails with "circular dependency"

**Cause**: Asset depends on itself (A → B → A)

**Solution**: Check contribution graph
```cypher
MATCH path = (a:Asset)-[:CONTRIBUTED_TO*]->(a)
RETURN path
```

### Payout Sum Mismatch

**Symptoms**: Sum of payouts ≠ distribution amount

**Cause**: Floating point rounding (using float instead of Decimal)

**Solution**: Always use Decimal
```python
# Wrong
cost = 100.50  # float

# Right
from decimal import Decimal
cost = Decimal("100.50")
```

## Performance Issues

### Slow Distribution

**Symptoms**: Distribution takes >30 seconds

**Causes**:
1. Deep graph (>10 levels)
2. Many contributors (>1000)
3. Missing indexes

**Solutions**:
```sql
-- Add indexes
CREATE INDEX IF NOT EXISTS idx_events_asset ON contribution_events_ledger(asset_id);

-- Limit depth
POST /v1/distributions
{"max_depth": 5}  # Limit to 5 levels
```

### Database Connection Pool Exhausted

**Symptoms**: `asyncpg.exceptions.TooManyConnectionsError`

**Solution**: Increase pool size
```python
# config.py
DB_POOL_MIN_SIZE = 10
DB_POOL_MAX_SIZE = 50  # Increase from 20
```
