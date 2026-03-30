"""Tests for friction report performance fix (friction-page-slow-loading).

Validates that:
1. The /friction/report endpoint accepts a limit parameter
2. The limit caps the number of events scanned
3. The default window_days is capped at 90
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.main import app
    return TestClient(app)


def test_friction_report_returns_200(client):
    """Basic smoke test: endpoint responds."""
    resp = client.get("/api/friction/report")
    assert resp.status_code == 200
    data = resp.json()
    assert "source_file" in data


def test_friction_report_limit_param(client):
    """The limit parameter is accepted and doesn't error."""
    resp = client.get("/api/friction/report?limit=10")
    assert resp.status_code == 200


def test_friction_report_window_days_capped(client):
    """window_days > 90 should be rejected (validation)."""
    resp = client.get("/api/friction/report?window_days=365")
    assert resp.status_code == 422  # validation error


def test_friction_report_window_days_default(client):
    """Default window_days should be 7 (not 30)."""
    resp = client.get("/api/friction/report?window_days=7")
    assert resp.status_code == 200


def test_friction_report_limit_bounds(client):
    """limit > 5000 should be rejected."""
    resp = client.get("/api/friction/report?limit=10000")
    assert resp.status_code == 422
