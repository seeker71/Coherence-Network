# Coherence Network — Setup Instructions

## Prerequisites

- Python 3.13 recommended (latest stable); 3.9+ minimum supported
- Node.js 20+
- Docker (optional for local Neo4j/Postgres)

## API Setup

```bash
cd api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -e ".[dev]"
```

## Run API

```bash
cd api
uvicorn app.main:app --reload --port 8000
```

Open API docs at `http://localhost:8000/docs`.

## Run Tests

```bash
cd api
pytest -v
pytest -v --ignore=tests/holdout
```

If needed, use `.venv/bin/pytest`.

## Run Web

```bash
cd web
npm install
npm run dev
```


## Run Pipeline Scripts

Use the venv Python explicitly for script reliability:

- From repo root: `api/.venv/bin/python api/scripts/<script>.py`
- From `api/`: `.venv/bin/python scripts/<script>.py`

## Environment

Copy `api/.env.example` to `api/.env` and fill required keys.

## Worktree Task Start (Required)

When starting a new task in a worktree, run:

```bash
./scripts/setup_worktree_context.sh
```

This setup step:
- copies `api/.env` from the main repository root to the worktree if missing
- copies `web/.env.local` from the source repo when present, otherwise seeds from `web/.env.example`
- does not overwrite existing worktree env files

Optional explicit source root:

```bash
WORKTREE_ENV_SOURCE=/path/to/main/repo ./scripts/setup_worktree_context.sh
```

## Local CI/CD Context Validation (GitHub-parity)

Before pushing changes, run:

```bash
./scripts/run_local_ci_context.sh
```

This mirrors `.github/workflows/test.yml` order in local context:
1. commit evidence validation
2. spec quality validation
3. workflow reference validation
4. API test suite (`pytest -v`) with CI-like env sanitization
5. web build (`npm ci && npm run build`)

Make targets:

```bash
make worktree-setup
make local-ci-context
```

## Deployment baseline

Use the managed-hosting baseline from `docs/DEPLOY.md`:
- API on Railway
- Web on Railway
- PostgreSQL on Neon/Supabase
- Neo4j on AuraDB Free

## Post-deploy smoke tests

```bash
curl https://<api-domain>/api/health
curl https://<api-domain>/api/ready
curl https://<api-domain>/api/version
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `pytest: command not found` | Use `.venv/bin/pytest` or `python -m pytest` in the venv |
| `ModuleNotFoundError` / import error when running scripts | Use explicit venv path and ensure `pip install -e ".[dev]"` ran in the active venv |
| Port 8000 in use | Start API on another port (`--port 8001`) |
