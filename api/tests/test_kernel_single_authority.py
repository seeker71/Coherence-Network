from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[2]


def test_kernel_authority_is_only_the_form_submodule() -> None:
    result = subprocess.run(
        ["python3", "scripts/verify_kernel_single_authority.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_retired_python_form_api_points_to_native_door() -> None:
    response = TestClient(app).post(
        "/api/substrate/form", json={"expression": "(add 1 2)", "mode": "run"}
    )
    assert response.status_code == 410
    assert "native form-cli" in response.json()["detail"]
