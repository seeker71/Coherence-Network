FROM python:3.11-slim

LABEL org.opencontainers.image.title="pulse"
LABEL org.opencontainers.image.description="Pulse Monitor — the witness that remembers the breath of Coherence Network"
LABEL org.opencontainers.image.source="https://github.com/seeker51/Coherence-Network"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PULSE_DB_PATH=/data/pulse.db

WORKDIR /app

# Dependencies first, for build caching.
COPY pyproject.toml README.md ./
RUN python -m pip install --upgrade pip \
 && python -m pip install \
    "fastapi>=0.110" \
    "uvicorn[standard]>=0.27" \
    "httpx>=0.27" \
    "apscheduler>=3.10" \
    "pydantic>=2.6"

COPY pulse_app ./pulse_app

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8100

HEALTHCHECK --interval=60s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; \
                   r=urllib.request.urlopen('http://127.0.0.1:8100/pulse/health',timeout=3); \
                   sys.exit(0 if r.status==200 else 1)" || exit 1

CMD ["uvicorn", "pulse_app.main:app", "--host", "0.0.0.0", "--port", "8100"]
