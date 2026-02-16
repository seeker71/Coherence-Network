# Deployment Checklist — Railway + GitHub Configuration

## Current Status

✅ Code deployed to Railway
✅ API is responding (health check passes)
✅ New endpoint exists (`/v1/contributions/github`)
❌ DATABASE_URL not configured → Internal Server Error
❌ GitHub secrets not configured → Workflow will skip tracking

## Issue 1: Railway DATABASE_URL

### Problem
The API is running but returns "Internal Server Error" when trying to create contributions because `DATABASE_URL` is not set.

### Solution: Add PostgreSQL to Railway

**Option A: Railway Dashboard (Recommended)**
1. Go to https://railway.app/
2. Navigate to your project: `Coherence-Network`
3. Click **"New"** → **"Database"** → **"PostgreSQL"**
4. Railway will:
   - Provision a PostgreSQL database
   - Automatically set `DATABASE_URL` env var
   - Auto-redeploy your API service
5. Wait 1-2 minutes for deployment

**Option B: Railway CLI**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Add PostgreSQL
railway add

# Select PostgreSQL from the list
```

### Verification After Adding Database
```bash
# Should return empty array (no 500 error)
curl https://coherence-network-production.up.railway.app/v1/contributors

# Should create a contribution (201 Created)
curl -X POST https://coherence-network-production.up.railway.app/v1/contributions/github \
  -H "Content-Type: application/json" \
  -d '{
    "contributor_email": "test@example.com",
    "repository": "seeker71/Coherence-Network",
    "commit_hash": "test123",
    "cost_amount": 100.00,
    "metadata": {"files_changed": 3, "lines_added": 50}
  }'
```

## Issue 2: GitHub Secrets

### Problem
GitHub Actions workflow needs these secrets:
- `COHERENCE_API_URL` → Not set
- `COHERENCE_API_KEY` → Not set

When secrets are missing, the workflow skips contribution tracking.

### Solution: Set GitHub Secrets

**Via GitHub Web UI:**
1. Go to https://github.com/seeker71/Coherence-Network
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add these secrets:

   **Secret 1:**
   - Name: `COHERENCE_API_URL`
   - Value: `https://coherence-network-production.up.railway.app`

   **Secret 2:**
   - Name: `COHERENCE_API_KEY`
   - Value: `dev-key-temp` (placeholder for now, auth not implemented yet)

**Via GitHub CLI (if available):**
```bash
gh secret set COHERENCE_API_URL --body "https://coherence-network-production.up.railway.app"
gh secret set COHERENCE_API_KEY --body "dev-key-temp"
```

### Verification After Setting Secrets
```bash
# Check secrets are set
gh secret list
# Should show: COHERENCE_API_URL and COHERENCE_API_KEY

# Test by creating a PR and merging (or push to main)
# Check GitHub Actions → Auto-Track Contributions
# Should see successful run with contribution logged
```

## Issue 3: CORS Configuration

### Problem
The CORS `ALLOWED_ORIGINS` env var may not be set on Railway.

### Solution: Set CORS Origins in Railway

**Railway Dashboard:**
1. Go to your Railway project
2. Select the API service
3. Go to **Variables** tab
4. Add:
   ```
   ALLOWED_ORIGINS=https://coherence-web-production.up.railway.app,http://localhost:3000
   ```
5. Railway will auto-redeploy

### Verification
```bash
# Test CORS
curl -I -H "Origin: https://coherence-web-production.up.railway.app" \
  https://coherence-network-production.up.railway.app/api/health \
  | grep -i "access-control-allow-origin"

# Should show:
# Access-Control-Allow-Origin: https://coherence-web-production.up.railway.app
```

## Complete Setup Script (After Manual Steps)

Once Railway PostgreSQL is added and GitHub secrets are set, run:

```bash
#!/bin/bash
set -e

echo "=== Verifying Coherence Network Deployment ==="

echo ""
echo "1. API Health Check..."
curl -fsS https://coherence-network-production.up.railway.app/api/health | jq .

echo ""
echo "2. Database Connection Check..."
curl -fsS https://coherence-network-production.up.railway.app/api/ready | jq .

echo ""
echo "3. Contributors Endpoint (should be empty array)..."
curl -fsS https://coherence-network-production.up.railway.app/v1/contributors | jq .

echo ""
echo "4. Assets Endpoint (should be empty array)..."
curl -fsS https://coherence-network-production.up.railway.app/v1/assets | jq .

echo ""
echo "5. Test Contribution Creation..."
RESPONSE=$(curl -s -X POST https://coherence-network-production.up.railway.app/v1/contributions/github \
  -H "Content-Type: application/json" \
  -d '{
    "contributor_email": "deploy-test@coherence.network",
    "repository": "seeker71/Coherence-Network",
    "commit_hash": "deploy-verification-001",
    "cost_amount": 100.00,
    "metadata": {
      "files_changed": 5,
      "lines_added": 150,
      "test": true
    }
  }')

echo "$RESPONSE" | jq .

if echo "$RESPONSE" | jq -e '.id' > /dev/null; then
  echo "✅ Contribution created successfully!"
else
  echo "❌ Failed to create contribution"
  exit 1
fi

echo ""
echo "6. Verify Contribution Was Saved..."
curl -fsS https://coherence-network-production.up.railway.app/v1/contributors | jq .

echo ""
echo "7. CORS Check..."
curl -I -H "Origin: https://coherence-web-production.up.railway.app" \
  https://coherence-network-production.up.railway.app/api/health 2>&1 \
  | grep -i "access-control-allow-origin"

echo ""
echo "8. Web Deployment Check..."
./scripts/verify_web_api_deploy.sh

echo ""
echo "=== All Checks Complete ==="
```

Save as `scripts/verify_full_deployment.sh` and run after setup.

## Quick Reference

### Railway Environment Variables Needed
```
DATABASE_URL=<auto-set when PostgreSQL added>
ALLOWED_ORIGINS=https://coherence-web-production.up.railway.app,http://localhost:3000
```

### GitHub Repository Secrets Needed
```
COHERENCE_API_URL=https://coherence-network-production.up.railway.app
COHERENCE_API_KEY=dev-key-temp
```

### Test Commands
```bash
# Health
curl https://coherence-network-production.up.railway.app/api/health

# Database connected
curl https://coherence-network-production.up.railway.app/v1/contributors

# Create contribution
curl -X POST https://coherence-network-production.up.railway.app/v1/contributions/github \
  -H "Content-Type: application/json" \
  -d '{"contributor_email":"test@example.com","repository":"test/repo","commit_hash":"abc","cost_amount":100,"metadata":{}}'
```

## Timeline

1. **Now**: Add PostgreSQL on Railway (5 min)
2. **Now**: Set GitHub secrets (2 min)
3. **Now**: Set ALLOWED_ORIGINS on Railway (1 min)
4. **Wait**: Railway redeploys (2-3 min)
5. **Then**: Run verification script
6. **Then**: Test by merging a real PR

Total: ~15 minutes including deployment time
