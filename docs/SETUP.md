# Coherence Network — Setup Instructions

## Prerequisites

- Python 3.9+
- Node.js 20+ (for web, when added)
- Docker (optional, for Neo4j/Postgres)

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

Visit http://localhost:8000/docs for OpenAPI UI.

## Run Tests

```bash
cd api
pytest -v
```

Use `.venv/bin/pytest` if `pytest` is not on PATH.

## Scripts and venv

For all `api/scripts/*` invocations, use the venv Python explicitly so scripts run reliably from any working directory:

- **From repo root:** `api/.venv/bin/python api/scripts/script_name.py`
- **From `api/`:** `.venv/bin/python scripts/script_name.py`
- **Windows (from repo root):** `api\.venv\Scripts\python.exe api\scripts\script_name.py`
- **Windows (from `api\`):** `.venv\Scripts\python.exe scripts\script_name.py`

Same pattern for pytest: `api/.venv/bin/pytest` or `.venv/bin/pytest` when in `api/`.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` or import errors when running scripts | Run from `api/` or use full venv path: `api/.venv/bin/python api/scripts/foo.py` (see **Scripts and venv** above). Ensure `pip install -e ".[dev]"` was run in that venv. |
| `pytest: command not found` | Use `api/.venv/bin/pytest` or, from `api/`, `.venv/bin/pytest`; or `api/.venv/bin/python -m pytest`. |
| API won't start (port in use) | Use a different port: `uvicorn app.main:app --reload --port 8001`. Or find and kill the process using port 8000. |
| Venv activation vs path | You can either activate the venv (`source .venv/bin/activate` in `api/`) and then run `python`/`pytest`, or skip activation and always use the full path (`api/.venv/bin/python`, `api/.venv/bin/pytest`) so the correct interpreter is used from any directory. |
| Import errors in tests | Run from `api/`; use `api/.venv/bin/pytest` or ensure venv is activated and has `pip install -e ".[dev]"`. |

## Web (Placeholder)

Web app: Next.js 15 + shadcn/ui (see spec 012).

## Environment

Copy `api/.env.example` to `api/.env` and fill in keys. For Telegram alerts and webhook, see [API-KEYS-SETUP.md](API-KEYS-SETUP.md) §6. Test with: `cd api && pip install python-dotenv && python scripts/test_telegram.py`

## Production Deploy

See [DEPLOY.md](DEPLOY.md) for deploy checklist, health probes, and env vars.

## Cursor

Open this repo in Cursor. Rules in `.cursor/rules/` apply. Use Cursor as the primary manual development interface.
