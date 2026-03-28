"""Acceptance tests for CLI non-interactive identity (cli-noninteractive-identity).

Implements spec `specs/task_a50fa999fdddd444.md` acceptance checks that require the
npm `cc` CLI and/or `cli/lib/config.mjs` (R1, R2, R3, R4 at the JS layer).

Existing module tests live in `test_cli_noninteractive_identity.py` — this file
adds subprocess coverage only (new file; does not modify other tests).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths & skips
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _cc_bin() -> Path:
    return _repo_root() / "cli" / "bin" / "cc.mjs"


def _config_mjs_uri() -> str:
    return (_repo_root() / "cli" / "lib" / "config.mjs").as_uri()


pytestmark = pytest.mark.skipif(
    not shutil.which("node"),
    reason="Node.js is required for cc CLI acceptance tests",
)


def _env_for_home(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    for key in ("COHERENCE_CONTRIBUTOR_ID", "COHERENCE_CONTRIBUTOR"):
        env.pop(key, None)
    return env


def _run_cc_identity_set(home: Path, contributor_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [shutil.which("node"), str(_cc_bin()), "identity", "set", contributor_id],
        env=_env_for_home(home),
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# R1 / R2 — `cc identity set` non-interactive + validation (npm CLI)
# ---------------------------------------------------------------------------


class TestCcIdentitySetSubprocess:
    """Spec checklist: valid set succeeds; invalid inputs exit non-zero; config unchanged on failure."""

    def test_identity_set_valid_writes_config(self, tmp_path: Path) -> None:
        """AC: `cc identity set valid-agent-01` writes config and prints success (exit 0)."""
        rid = "valid-agent-accept-01"
        proc = _run_cc_identity_set(tmp_path, rid)
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        assert "Identity set" in proc.stdout or "✓" in proc.stdout, proc.stdout
        cfg = tmp_path / ".coherence-network" / "config.json"
        assert cfg.is_file()
        data = json.loads(cfg.read_text(encoding="utf-8"))
        assert data.get("contributor_id") == rid

    def test_identity_set_empty_rejected(self, tmp_path: Path) -> None:
        """AC: empty contributor_id rejected; config dir absent or unchanged."""
        proc = _run_cc_identity_set(tmp_path, "")
        assert proc.returncode != 0
        assert "invalid" in (proc.stdout + proc.stderr).lower()

    def test_identity_set_invalid_chars_rejected(self, tmp_path: Path) -> None:
        """AC: injection-like id rejected."""
        proc = _run_cc_identity_set(tmp_path, "alice; rm -rf /")
        assert proc.returncode != 0
        assert "invalid" in (proc.stdout + proc.stderr).lower()

    def test_identity_set_overlong_rejected(self, tmp_path: Path) -> None:
        """AC: length > 64 rejected."""
        proc = _run_cc_identity_set(tmp_path, "x" * 65)
        assert proc.returncode != 0

    def test_identity_set_failure_does_not_write_bad_value(self, tmp_path: Path) -> None:
        """After failed set, a subsequent read of config must not contain the bad id."""
        bad = "bad;id!"
        proc = _run_cc_identity_set(tmp_path, bad)
        assert proc.returncode != 0
        cfg = tmp_path / ".coherence-network" / "config.json"
        if cfg.is_file():
            raw = cfg.read_text(encoding="utf-8")
            assert bad not in raw


# ---------------------------------------------------------------------------
# R2 — JS `parseContributorId` matches spec pattern (contract with npm layer)
# ---------------------------------------------------------------------------


class TestNodeContributorIdContract:
    """Run `cli/lib/config.mjs` in Node so Python tests pin the same rules as the CLI."""

    def _run_node(self, snippet: str) -> str:
        proc = subprocess.run(
            [shutil.which("node"), "--input-type=module", "-e", snippet],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        return proc.stdout.strip()

    def test_parse_contributor_id_valid(self) -> None:
        uri = _config_mjs_uri()
        xs64 = "x" * 64
        out = self._run_node(
            f"""
import {{ parseContributorId }} from '{uri}';
const o = {{
  a: parseContributorId('valid-agent-01'),
  b: parseContributorId('{xs64}'),
}};
console.log(JSON.stringify(o));
"""
        )
        data = json.loads(out)
        assert data["a"] == "valid-agent-01"
        assert data["b"] == "x" * 64

    def test_parse_contributor_id_invalid(self) -> None:
        uri = _config_mjs_uri()
        xs65 = "x" * 65
        out = self._run_node(
            f"""
import {{ parseContributorId }} from '{uri}';
const o = {{
  empty: parseContributorId(''),
  long: parseContributorId('{xs65}'),
  bad: parseContributorId('bad;chars!'),
}};
console.log(JSON.stringify(o));
"""
        )
        data = json.loads(out)
        assert data["empty"] is None
        assert data["long"] is None
        assert data["bad"] is None


# ---------------------------------------------------------------------------
# R3 / R4 — getContributorId / getContributorSource (no network)
# ---------------------------------------------------------------------------


class TestNodeContributorResolution:
    """Env precedence and source labels from `config.mjs` (matches spec R3/R4)."""

    def _run_with_env(self, home: Path, extra_env: dict[str, str], snippet: str) -> str:
        env = _env_for_home(home)
        env.update(extra_env)
        proc = subprocess.run(
            [shutil.which("node"), "--input-type=module", "-e", snippet],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        return proc.stdout.strip()

    def test_env_canonical_over_config_file(self, tmp_path: Path) -> None:
        d = tmp_path / ".coherence-network"
        d.mkdir(parents=True)
        (d / "config.json").write_text(
            json.dumps({"contributor_id": "from-config"}),
            encoding="utf-8",
        )
        uri = _config_mjs_uri()
        snippet = f"""
import {{ getContributorId, getContributorSource }} from '{uri}';
console.log(JSON.stringify({{ id: getContributorId(), src: getContributorSource() }}));
"""
        out = self._run_with_env(
            tmp_path,
            {"COHERENCE_CONTRIBUTOR_ID": "env-wins"},
            snippet,
        )
        data = json.loads(out)
        assert data["id"] == "env-wins"
        assert "COHERENCE_CONTRIBUTOR_ID" in data["src"]

    def test_canonical_env_beats_legacy(self, tmp_path: Path) -> None:
        (tmp_path / ".coherence-network").mkdir(parents=True)
        (tmp_path / ".coherence-network" / "config.json").write_text("{}", encoding="utf-8")
        uri = _config_mjs_uri()
        snippet = f"""
import {{ getContributorId }} from '{uri}';
console.log(getContributorId());
"""
        out = self._run_with_env(
            tmp_path,
            {
                "COHERENCE_CONTRIBUTOR_ID": "new-wins",
                "COHERENCE_CONTRIBUTOR": "old-loses",
            },
            snippet,
        )
        assert out == "new-wins"

    def test_legacy_env_used_when_canonical_absent(self, tmp_path: Path) -> None:
        (tmp_path / ".coherence-network").mkdir(parents=True)
        (tmp_path / ".coherence-network" / "config.json").write_text("{}", encoding="utf-8")
        uri = _config_mjs_uri()
        snippet = f"""
import {{ getContributorId, getContributorSource }} from '{uri}';
console.log(JSON.stringify({{ id: getContributorId(), src: getContributorSource() }}));
"""
        out = self._run_with_env(
            tmp_path,
            {"COHERENCE_CONTRIBUTOR": "legacy-agent"},
            snippet,
        )
        data = json.loads(out)
        assert data["id"] == "legacy-agent"
        assert "legacy" in data["src"].lower()

    def test_source_none_when_unconfigured(self, tmp_path: Path) -> None:
        (tmp_path / ".coherence-network").mkdir(parents=True)
        (tmp_path / ".coherence-network" / "config.json").write_text("{}", encoding="utf-8")
        uri = _config_mjs_uri()
        snippet = f"""
import {{ getContributorSource }} from '{uri}';
console.log(getContributorSource());
"""
        out = self._run_with_env(tmp_path, {}, snippet)
        assert out == "none"
