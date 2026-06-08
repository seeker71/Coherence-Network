# Coherence Network — Setup Instructions

## Prerequisites

- Python 3.13 recommended for compatibility API/tooling; 3.9+ minimum supported
- Node.js 20+
- Docker (optional for local Neo4j/Postgres)

## Compatibility API Setup

```bash
cd api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -e ".[dev]"
```

## Run Compatibility API

```bash
cd api
uvicorn app.main:app --reload --port 8000
```

Open compatibility API docs at `http://localhost:8000/docs`.

For native kernel/front-door route work, start from
[`kernels/SOURCE_LANGUAGE_KERNEL_ROUTER_ARCHITECTURE.md`](../kernels/SOURCE_LANGUAGE_KERNEL_ROUTER_ARCHITECTURE.md)
and [`kernels/SOURCE_LANGUAGE_KERNEL_ROUTER_TRACKING.md`](../kernels/SOURCE_LANGUAGE_KERNEL_ROUTER_TRACKING.md).
New high-traffic handlers should be BML/domain grammar first; the local API
process is the bridge/upstream for routes not yet promoted.

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

## Deployment baseline

Use the managed-hosting baseline from `docs/DEPLOY.md`:
- API on Hostinger VPS at `https://api.coherencycoin.com`
- Web on Hostinger VPS at `https://coherencycoin.com`
- PostgreSQL as the internal Docker Compose service on the VPS
- Neo4j on AuraDB Free

For credential carriers and native-kernel DB probes, read
[`PRODUCTION-SUBSTRATE.md`](PRODUCTION-SUBSTRATE.md).

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
