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
echo "3. Contributors Endpoint (should be empty array or have data)..."
curl -fsS https://coherence-network-production.up.railway.app/v1/contributors | jq .

echo ""
echo "4. Assets Endpoint (should be empty array or have data)..."
curl -fsS https://coherence-network-production.up.railway.app/v1/assets | jq .

echo ""
echo "5. Test Contribution Creation..."
RESPONSE=$(curl -s -X POST https://coherence-network-production.up.railway.app/v1/contributions/github \
  -H "Content-Type: application/json" \
  -d '{
    "contributor_email": "deploy-test@coherence.network",
    "repository": "seeker71/Coherence-Network",
    "commit_hash": "deploy-verification-'"$(date +%s)"'",
    "cost_amount": 100.00,
    "metadata": {
      "files_changed": 5,
      "lines_added": 150,
      "test": true
    }
  }')

echo "$RESPONSE" | jq .

if echo "$RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
  echo "✅ Contribution created successfully!"
  CONTRIB_ID=$(echo "$RESPONSE" | jq -r '.id')
  echo "Contribution ID: $CONTRIB_ID"
else
  echo "❌ Failed to create contribution"
  echo "Response: $RESPONSE"
  exit 1
fi

echo ""
echo "6. Verify Contribution Was Saved..."
CONTRIBUTORS=$(curl -fsS https://coherence-network-production.up.railway.app/v1/contributors)
echo "$CONTRIBUTORS" | jq .
CONTRIB_COUNT=$(echo "$CONTRIBUTORS" | jq 'length')
echo "Total contributors in database: $CONTRIB_COUNT"

echo ""
echo "7. CORS Check..."
CORS_HEADER=$(curl -sI -H "Origin: https://coherence-web-production.up.railway.app" \
  https://coherence-network-production.up.railway.app/api/health 2>&1 \
  | grep -i "access-control-allow-origin" || echo "CORS header not found")
echo "$CORS_HEADER"

if [[ "$CORS_HEADER" == *"coherence-web-production.up.railway.app"* ]] || [[ "$CORS_HEADER" == *"*"* ]]; then
  echo "✅ CORS configured correctly"
else
  echo "⚠️  CORS may need configuration"
fi

echo ""
echo "8. Web + API Deployment Check..."
if [[ -f "./scripts/verify_web_api_deploy.sh" ]]; then
  ./scripts/verify_web_api_deploy.sh || echo "⚠️  Some deployment checks failed"
else
  echo "⚠️  verify_web_api_deploy.sh not found, skipping"
fi

echo ""
echo "=== Deployment Verification Summary ==="
echo "✅ API is responding"
echo "✅ Database is connected"
if [[ "$CONTRIB_COUNT" -gt 0 ]]; then
  echo "✅ Contributions are being persisted"
else
  echo "⚠️  No contributions in database yet"
fi

echo ""
echo "Next steps:"
echo "1. Merge a PR to test the GitHub Actions workflow"
echo "2. Check GitHub Actions → Auto-Track Contributions"
echo "3. Verify contribution appears in database"
echo ""
