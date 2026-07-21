from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "validate_spec_quality.py"


def _run(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--file", str(path), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_spec_concerns_are_observed_without_veto_by_default(tmp_path: Path) -> None:
    spec = tmp_path / "small-honest-offer.md"
    spec.write_text("## Purpose\nA bounded offer.\n", encoding="utf-8")

    result = _run(spec)

    assert result.returncode == 0
    assert "OBSERVED: spec quality concerns" in result.stdout
    assert "ACK: concerns witnessed" in result.stdout


def test_strict_failure_requires_explicit_opt_in(tmp_path: Path) -> None:
    spec = tmp_path / "small-honest-offer.md"
    spec.write_text("## Purpose\nA bounded offer.\n", encoding="utf-8")

    result = _run(spec, "--strict")

    assert result.returncode == 1
    assert "OBSERVED: spec quality concerns" in result.stdout
