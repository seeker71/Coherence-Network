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

## Web (Placeholder)

Web app will be added in a follow-up spec. Structure: Next.js 16 + shadcn/ui.

## Environment

Copy `api/.env.example` to `api/.env` and fill in keys. For Telegram alerts and webhook, see [API-KEYS-SETUP.md](API-KEYS-SETUP.md) §6. Test with: `cd api && pip install python-dotenv && python scripts/test_telegram.py`

## Cursor

Open this repo in Cursor. Rules in `.cursor/rules/` apply. Use Cursor as the primary manual development interface.
