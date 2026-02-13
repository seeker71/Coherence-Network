# Coherence Network — Setup Instructions

## Prerequisites

- Python 3.9+
- Node.js 20+
- Docker (optional for local Neo4j/Postgres)

## API Setup

```bash
cd api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
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

Useful commands:

```bash
cd api && .venv/bin/python scripts/project_manager.py --dry-run
cd api && .venv/bin/python scripts/check_pipeline.py --json
cd api && ./scripts/run_overnight_pipeline.sh
```

## Environment

Copy `api/.env.example` to `api/.env` and fill required keys.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `pytest: command not found` | Use `.venv/bin/pytest` or `python -m pytest` in the venv |
| Import/module errors | Ensure `pip install -e ".[dev]"` ran in active venv |
| Port 8000 in use | Start API on another port (`--port 8001`) |

## Deployment

See [DEPLOY.md](DEPLOY.md) and [RUNBOOK.md](RUNBOOK.md).
