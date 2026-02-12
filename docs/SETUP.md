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

Use `.venv/bin/pytest` if `pytest` is not on PATH. Scripts in `api/scripts/` should use `.venv/bin/python` for consistency.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` when running scripts | Run from `api/` directory; use `api/.venv/bin/python scripts/foo.py` |
| `pytest: command not found` | Use `api/.venv/bin/pytest` or `python -m pytest` |
| API won't start (port in use) | Use `--port 8001` or kill process on 8000 |
| Import errors in tests | Ensure `cd api` first; venv has `pip install -e ".[dev]"` |

## Web (Placeholder)

Web app will be added in a follow-up spec. Structure: Next.js 16 + shadcn/ui.

## Environment

Copy `api/.env.example` to `api/.env` and fill in keys. For Telegram alerts and webhook, see [API-KEYS-SETUP.md](API-KEYS-SETUP.md) §6. Test with: `cd api && pip install python-dotenv && python scripts/test_telegram.py`

## Production Deploy

See [DEPLOY.md](DEPLOY.md) for deploy checklist, health probes, and env vars.

## Cursor

Open this repo in Cursor. Rules in `.cursor/rules/` apply. Use Cursor as the primary manual development interface.
