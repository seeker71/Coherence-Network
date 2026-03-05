#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# Coherence Network — Full Verification Suite
#
# Proves every machine + human interface improvement actually works.
# Run from the project root: ./verify_all_changes.sh
# ═══════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

passed=0
failed=0

section() { echo -e "\n${BLUE}${BOLD}═══ $1 ═══${NC}"; }
pass()    { passed=$((passed+1)); echo -e "  ${GREEN}PASS${NC}: $1"; }
fail()    { failed=$((failed+1)); echo -e "  ${RED}FAIL${NC}: $1 — $2"; }

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$PROJECT_ROOT/api"
WEB_DIR="$PROJECT_ROOT/web"
VENV_PYTHON="$API_DIR/.venv/bin/python"
VENV_PYTEST="$API_DIR/.venv/bin/pytest"

# ═══════════════════════════════════════════════════════════════
# PART 1: API Integration Tests (real HTTP requests)
# ═══════════════════════════════════════════════════════════════
section "PART 1: API Integration Tests (FastAPI + real HTTP)"

if [ ! -f "$VENV_PYTEST" ]; then
    echo "  ERROR: venv not found at $API_DIR/.venv — run: cd api && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    exit 1
fi

cd "$API_DIR"
echo "  Running pytest on test_interface_improvements.py..."
echo ""
if $VENV_PYTEST tests/test_interface_improvements.py -v --tb=short 2>&1; then
    pass "All API integration tests passed"
else
    fail "API integration tests" "see output above"
fi

# Also run the existing test suite to make sure nothing broke
echo ""
echo "  Running full existing test suite..."
echo ""
if $VENV_PYTEST tests/test_contributors.py tests/test_assets.py tests/test_contributions.py -v --tb=short 2>&1; then
    pass "Existing CRUD tests still pass with pagination changes"
else
    fail "Existing CRUD tests" "pagination changes broke something"
fi

# ═══════════════════════════════════════════════════════════════
# PART 2: Live API Server — security headers check
# ═══════════════════════════════════════════════════════════════
section "PART 2: Live API Response Headers"

# Start server in background
$VENV_PYTHON -m uvicorn app.main:app --port 9876 --log-level warning &
SERVER_PID=$!
sleep 2

cleanup() { kill $SERVER_PID 2>/dev/null || true; }
trap cleanup EXIT

if curl -sS -o /dev/null -w "%{http_code}" http://localhost:9876/api/health | grep -q "200"; then
    pass "API server started and /api/health returns 200"
else
    fail "API server" "could not reach /api/health"
fi

# Check actual headers
HEADERS=$(curl -sS -D - -o /dev/null http://localhost:9876/api/health 2>&1)

if echo "$HEADERS" | grep -qi "x-content-type-options: nosniff"; then
    pass "X-Content-Type-Options: nosniff present in response"
else
    fail "X-Content-Type-Options" "header missing from actual HTTP response"
fi

if echo "$HEADERS" | grep -qi "x-frame-options: DENY"; then
    pass "X-Frame-Options: DENY present in response"
else
    fail "X-Frame-Options" "header missing from actual HTTP response"
fi

if echo "$HEADERS" | grep -qi "referrer-policy"; then
    pass "Referrer-Policy present in response"
else
    fail "Referrer-Policy" "header missing from actual HTTP response"
fi

if echo "$HEADERS" | grep -qi "permissions-policy"; then
    pass "Permissions-Policy present in response"
else
    fail "Permissions-Policy" "header missing from actual HTTP response"
fi

if echo "$HEADERS" | grep -qi "x-request-id"; then
    pass "X-Request-ID present in response"
else
    fail "X-Request-ID" "header missing from actual HTTP response"
fi

# Check request ID propagation
PROP_HEADERS=$(curl -sS -D - -o /dev/null -H "X-Request-ID: my-trace-123" http://localhost:9876/api/health 2>&1)
if echo "$PROP_HEADERS" | grep -qi "x-request-id: my-trace-123"; then
    pass "X-Request-ID propagated correctly (sent my-trace-123, got it back)"
else
    fail "X-Request-ID propagation" "sent my-trace-123 but didn't get it back"
fi

# ═══════════════════════════════════════════════════════════════
# PART 3: Live API — Pagination Response
# ═══════════════════════════════════════════════════════════════
section "PART 3: Live API Pagination Responses"

# Create test data
curl -sS -X POST http://localhost:9876/api/contributors \
    -H "Content-Type: application/json" \
    -d '{"type":"HUMAN","name":"Alice","email":"alice@verify.com"}' > /dev/null

# Check the list endpoint returns paginated response
LIST_RESP=$(curl -sS http://localhost:9876/api/contributors?limit=10)

if echo "$LIST_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'items' in d" 2>/dev/null; then
    pass "GET /api/contributors returns 'items' field"
else
    fail "Pagination" "GET /api/contributors missing 'items' field. Got: $LIST_RESP"
fi

if echo "$LIST_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'total' in d" 2>/dev/null; then
    pass "GET /api/contributors returns 'total' field"
else
    fail "Pagination" "missing 'total' field"
fi

if echo "$LIST_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'limit' in d and 'offset' in d" 2>/dev/null; then
    pass "GET /api/contributors returns 'limit' and 'offset' fields"
else
    fail "Pagination" "missing limit/offset fields"
fi

if echo "$LIST_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); assert isinstance(d['items'], list)" 2>/dev/null; then
    pass "items field is a list (not a bare array at root)"
else
    fail "Pagination" "items is not a list"
fi

# ═══════════════════════════════════════════════════════════════
# PART 4: Live API — OpenAPI Schema
# ═══════════════════════════════════════════════════════════════
section "PART 4: OpenAPI Schema Validation"

SCHEMA=$(curl -sS http://localhost:9876/openapi.json)

if echo "$SCHEMA" | python3 -c "
import json,sys
s=json.load(sys.stdin)
tags=[t['name'] for t in s.get('tags',[])]
assert len(tags) >= 10, f'Only {len(tags)} tags'
" 2>/dev/null; then
    pass "OpenAPI schema has 10+ tag groups"
else
    fail "OpenAPI tags" "fewer than 10 tag groups"
fi

if echo "$SCHEMA" | python3 -c "
import json,sys
s=json.load(sys.stdin)
ed=s['components']['schemas']['ErrorDetail']['properties']
for f in ['type','title','status','detail']:
    assert f in ed, f'Missing {f}'
" 2>/dev/null; then
    pass "ErrorDetail schema has RFC 7807 fields (type, title, status, detail)"
else
    fail "ErrorDetail" "missing RFC 7807 fields in OpenAPI schema"
fi

kill $SERVER_PID 2>/dev/null || true

# ═══════════════════════════════════════════════════════════════
# PART 5: TypeScript Compilation
# ═══════════════════════════════════════════════════════════════
section "PART 5: Web TypeScript Compilation"

cd "$WEB_DIR"
if npx tsc --noEmit 2>&1; then
    pass "TypeScript compiles with zero errors (tsc --noEmit)"
else
    fail "TypeScript" "compilation errors found"
fi

# ═══════════════════════════════════════════════════════════════
# PART 6: Web File Structure
# ═══════════════════════════════════════════════════════════════
section "PART 6: Web File Structure Verification"

for f in app/error.tsx app/loading.tsx app/not-found.tsx; do
    if [ -f "$f" ]; then
        pass "$f exists"
    else
        fail "$f" "file does not exist"
    fi
done

# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}════════════════════════════════════════${NC}"
total=$((passed+failed))
if [ "$failed" -eq 0 ]; then
    echo -e "${GREEN}${BOLD}ALL $total CHECKS PASSED${NC}"
else
    echo -e "${RED}${BOLD}$failed/$total CHECKS FAILED${NC}"
fi
echo -e "${BOLD}════════════════════════════════════════${NC}"
exit $failed
