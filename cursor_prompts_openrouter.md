# Cursor Prompts for OpenRouter/Free
## Optimized for Google Gemini Flash & Free Models

These prompts are designed to work reliably with free/cheap models like:
- `google/gemini-flash-1.5`
- `meta-llama/llama-3.1-8b-instruct:free`
- `microsoft/phi-3-mini-128k-instruct:free`

---

## PROMPT 1: Generate FastAPI Application Structure

**Use this prompt in Cursor to generate the core API:**

```
Create a production-ready FastAPI application for Coherence Network with this exact structure:

coherence-network/
├── api/
│   ├── __init__.py
│   ├── main.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── contributors.py
│   │   └── contributions.py
│   └── middleware/
│       ├── __init__.py
│       └── auth.py
├── models/
│   ├── __init__.py
│   ├── contributor.py
│   └── contribution.py
├── config.py
├── requirements.txt
├── Dockerfile
└── .dockerignore

Requirements:
1. api/main.py: FastAPI app with CORS, health endpoint at /health
2. routes/health.py: Simple health check returning {"status": "healthy"}
3. routes/contributors.py: POST /v1/contributors (create), GET /v1/contributors/{id} (read)
4. routes/contributions.py: POST /v1/contributions (record contribution)
5. middleware/auth.py: API key authentication via X-API-Key header
6. models/contributor.py: Pydantic model with id, name, email, type (HUMAN/SYSTEM)
7. models/contribution.py: Pydantic model with id, contributor_id, cost_amount, timestamp
8. config.py: Environment variables using pydantic-settings
9. requirements.txt: fastapi, uvicorn[standard], pydantic-settings, python-dotenv
10. Dockerfile: Python 3.12 slim, expose port 8000, run uvicorn

Use async/await for all endpoints. Add type hints. Include docstrings.
Make it production-ready with proper error handling.

DO NOT use any database yet - just return mock data for now.
We'll add PostgreSQL and Neo4j in the next step.

Generate all files now.
```

**Expected Output**: Complete FastAPI application skeleton (no database)

---

## PROMPT 2: Add Database Integration

**After PROMPT 1 succeeds, use this:**

```
Add PostgreSQL and Neo4j database integration to the existing FastAPI app.

Add these new files:
├── database/
│   ├── __init__.py
│   ├── postgres.py    # PostgreSQL connection with asyncpg
│   ├── neo4j.py       # Neo4j connection with neo4j driver
│   └── models.py      # SQLAlchemy models
├── alembic/
│   ├── env.py
│   └── versions/
└── alembic.ini

Requirements:
1. database/postgres.py:
   - Async connection pool using asyncpg
   - Tables: contributors, contribution_events_ledger
   - Function: async def get_connection()

2. database/neo4j.py:
   - Async Neo4j driver connection
   - Functions: create_contributor_node(), create_contribution_edge()

3. database/models.py:
   - SQLAlchemy models matching Pydantic models
   - Use NUMERIC(20,8) for money fields
   - Add created_at timestamps

4. Update routes/contributors.py:
   - Actually store in PostgreSQL
   - Create node in Neo4j
   - Return saved data

5. Update routes/contributions.py:
   - Store in PostgreSQL ledger
   - Create edge in Neo4j
   - Return event_id

6. Update requirements.txt:
   - Add: asyncpg, neo4j, sqlalchemy[asyncio], alembic

7. Update config.py:
   - Add DATABASE_URL, NEO4J_URI, NEO4J_PASSWORD

DO NOT add complex distribution logic yet.
Just basic CRUD with dual database writes.

Generate the database integration code now.
```

**Expected Output**: Database layer added to existing app

---

## PROMPT 3: Add Value Distribution Engine

**After PROMPT 2 succeeds:**

```
Add the value distribution engine to calculate and distribute payouts.

Add these files:
├── services/
│   ├── __init__.py
│   └── distribution_engine.py
├── api/routes/
│   └── distributions.py

Requirements:
1. services/distribution_engine.py:
   - Class: DistributionEngine
   - Method: async def distribute_value(asset_id, value_amount) -> dict
   - Algorithm:
     a. Get all contributions to asset from Neo4j
     b. Calculate weighted costs: cost × (0.5 + coherence_score)
     c. Sum total weighted cost
     d. Calculate payout per contributor: (weighted_cost / total) × value_amount
     e. Return dict {contributor_id: payout_amount}
   - Use Decimal for all money calculations
   - Handle empty contributions (return empty dict)

2. api/routes/distributions.py:
   - POST /v1/distributions
   - Request body: {asset_id, value_amount}
   - Call distribution_engine.distribute_value()
   - Store results in value_distributions table
   - Return distribution_id and payouts breakdown

3. Add to database/models.py:
   - Table: value_distributions (id, asset_id, value_amount, created_at)
   - Table: contributor_payouts (id, distribution_id, contributor_id, payout_amount)

4. Update requirements.txt:
   - No new dependencies needed

Simple and focused implementation.
No recursion or complex graph traversal yet - just one level.
Use straightforward algorithm.

Generate the distribution engine code now.
```

**Expected Output**: Working distribution engine

---

## PROMPT 4: Add GitHub Webhook Integration

**After PROMPT 3 succeeds:**

```
Add GitHub webhook integration to automatically track git commits as contributions.

Add these files:
├── api/routes/
│   └── webhooks.py
├── services/
│   └── github_handler.py

Requirements:
1. api/routes/webhooks.py:
   - POST /webhooks/github
   - Verify HMAC signature using GITHUB_WEBHOOK_SECRET
   - Extract push events
   - Call github_handler.process_push()
   - Return 200 OK

2. services/github_handler.py:
   - Function: process_push(payload)
   - For each commit in payload:
     a. Extract: author email, commit hash, files changed
     b. Estimate cost: len(files_changed) × 10 (base $10 per file)
     c. Calculate basic coherence: 0.5 baseline
     d. Find contributor by email (or create if not exists)
     e. Record contribution event
   - Return number of contributions created

3. Update config.py:
   - Add GITHUB_WEBHOOK_SECRET

4. Add function to verify HMAC:
   - Use hmac.compare_digest()
   - SHA256 signature

5. Handle errors gracefully:
   - Unknown contributor → create with email
   - Invalid signature → return 403
   - Malformed payload → return 400

Keep it simple - just basic commit tracking.
Don't add complex coherence calculation yet.

Generate the GitHub webhook integration code now.
```

**Expected Output**: GitHub integration working

---

## PROMPT 5: Add Node Operator System

**After PROMPT 4 succeeds:**

```
Add node operator system for distributed hosting marketplace.

Add these files:
├── api/routes/
│   └── nodes.py
├── services/
│   └── load_balancer.py
├── database/models.py (update)

Requirements:
1. database/models.py additions:
   - Table: nodes
     Fields: id, operator_id, node_type, endpoint, 
             pricing (JSONB), status, uptime_percentage, created_at

2. api/routes/nodes.py:
   - POST /v1/nodes - Register new node
     Request: {operator_id, node_type, endpoint, pricing}
     Response: {node_id, api_key, status}
   
   - GET /v1/nodes - List all nodes
     Query: ?node_type=API&status=ACTIVE&sort=price
     Response: [{node_id, operator_name, pricing, uptime, status}]
   
   - GET /v1/nodes/{node_id}/stats - Node statistics
     Response: {requests_24h, earnings_today, uptime_24h}

3. services/load_balancer.py:
   - Function: select_cheapest_node(node_type) -> Node
   - Algorithm:
     a. Filter: status=ACTIVE, uptime>99%
     b. Sort by pricing[node_type] ascending
     c. Return first (cheapest)
   - Function: route_request(request_type, payload) -> response
     a. Get cheapest node
     b. Forward request
     c. Record usage for billing

4. Add node health checking:
   - Background task: ping nodes every 60 seconds
   - Mark offline if 3 consecutive failures

Simple marketplace implementation.
No complex billing yet - just tracking.

Generate the node operator system code now.
```

**Expected Output**: Node marketplace functional

---

## PROMPT 6: Add Frontend Landing Page

**After PROMPT 5 succeeds:**

```
Create a simple landing page for coherencycoin.com.

Create these files:
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js

Requirements:
1. index.html:
   - Hero section: "Coherence Network - Fair Value Distribution for Contributors"
   - Features section: 3 cards (Track Contributions, Quality Scoring, Auto Distribution)
   - Stats section: Total Contributors, Total Distributed, Active Nodes
   - CTA: "Get Started" button linking to API docs
   - Footer with GitHub link

2. style.css:
   - Modern, clean design
   - Dark theme (background: #0a0a0a, text: #e0e0e0)
   - Accent color: #00d4ff (cyan/blue)
   - Responsive (mobile-first)
   - Smooth animations

3. app.js:
   - Fetch stats from API (GET /v1/stats)
   - Update numbers in stats section
   - Add smooth scroll to sections
   - Animate numbers counting up

4. Add new API endpoint:
   - GET /v1/stats
   - Return: {total_contributors, total_distributed, active_nodes}

No frameworks - pure HTML/CSS/JS.
Keep it simple and fast.
Single page application.

Generate the landing page code now.
```

**Expected Output**: Beautiful landing page

---

## USAGE INSTRUCTIONS

### How to Use These Prompts in Cursor

1. **Open Cursor** in your Coherence-Network repo
2. **Select OpenRouter model**: 
   - Cmd+Shift+P → "Select Model"
   - Choose: `google/gemini-flash-1.5` or similar free model
3. **Open Cursor Chat**: Cmd+L
4. **Copy Prompt 1** exactly as written
5. **Paste and Send**
6. **Wait for generation** (30-60 seconds)
7. **Review code** - Cursor will create files
8. **Accept changes**: Click checkmark or Cmd+Enter
9. **Repeat with Prompt 2-6** in sequence

### Why These Prompts Work Well

✅ **Specific structure** - Free models need exact file paths  
✅ **Simple requirements** - One feature at a time  
✅ **No ambiguity** - Clear algorithm steps  
✅ **Incremental** - Builds on previous work  
✅ **Production-ready** - Includes error handling  

### Troubleshooting

**If Cursor generates incomplete code**:
- Add to prompt: "Generate COMPLETE code with no placeholders or TODOs"

**If code has errors**:
- Paste error into Cursor chat: "Fix this error: [paste error]"

**If model refuses (safety)**:
- Rephrase as: "Create a code generation system for tracking work contributions"

---

## VERIFICATION AFTER EACH PROMPT

### After Prompt 1:
```bash
cd coherence-network
python -m pip install -r requirements.txt
uvicorn api.main:app --reload
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

### After Prompt 2:
```bash
# Set environment variables first
export DATABASE_URL="your-supabase-url"
export NEO4J_URI="your-neo4j-uri"
export NEO4J_PASSWORD="your-password"

# Test contributor creation
curl -X POST http://localhost:8000/v1/contributors \
  -H "Content-Type: application/json" \
  -d '{"type":"HUMAN","name":"Test","email":"test@example.com"}'
# Should return contributor with ID
```

### After Prompt 3:
```bash
# Test distribution
curl -X POST http://localhost:8000/v1/distributions \
  -H "Content-Type: application/json" \
  -d '{"asset_id":"uuid","value_amount":1000.00}'
# Should return distribution breakdown
```

### After Prompt 4:
```bash
# Test webhook (manual)
curl -X POST http://localhost:8000/webhooks/github \
  -H "X-GitHub-Event: push" \
  -H "Content-Type: application/json" \
  -d '{"commits":[{"author":{"email":"test@example.com"},"added":["test.py"]}]}'
```

### After Prompt 5:
```bash
# Test node registration
curl -X POST http://localhost:8000/v1/nodes \
  -H "Content-Type: application/json" \
  -d '{"operator_id":"uuid","node_type":"API","endpoint":"https://node.example.com","pricing":{"api_request":0.00002}}'
```

### After Prompt 6:
```bash
# Open in browser
open frontend/index.html
# Or serve:
python -m http.server 8080 --directory frontend
open http://localhost:8080
```

---

## EXPECTED TIMELINE

| Prompt | Time | Total |
|--------|------|-------|
| 1. FastAPI Structure | 5 min | 5 min |
| 2. Database Integration | 10 min | 15 min |
| 3. Distribution Engine | 7 min | 22 min |
| 4. GitHub Webhooks | 5 min | 27 min |
| 5. Node Operators | 8 min | 35 min |
| 6. Landing Page | 5 min | 40 min |

**Total**: ~40 minutes of active work

---

## COST ANALYSIS

**Using OpenRouter Free Tier**:
- `google/gemini-flash-1.5`: $0.00/request (free tier)
- `meta-llama/llama-3.1-8b-instruct:free`: $0.00/request
- Estimated tokens: 50K input + 30K output per prompt
- **Total cost: $0.00** ✅

**Alternative (if free tier exhausted)**:
- `google/gemini-flash-1.5` (paid): ~$0.02 per prompt
- All 6 prompts: **~$0.12 total**

Still cheaper than a coffee! ☕

---

## NEXT STEPS AFTER ALL PROMPTS

Once all 6 prompts are complete:

1. **Test locally**: Run verification scripts above
2. **Deploy to managed hosting (Railway)**: Use `deploy_master.sh`
3. **Configure GitHub webhook**: Point to your API
4. **Record your contribution**: Track this development work!
5. **Invite first contributors**: Share the API docs

**Congratulations!** You have a working Coherence Network! 🎉
