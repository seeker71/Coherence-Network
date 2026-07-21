from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
RECEIVER = ROOT / "scripts" / "mesh_command_receiver.sh"


def _identity(home: Path, **extra: str) -> str:
    env = os.environ.copy()
    env.update({"HOME": str(home), "MR_ROOT": str(ROOT), **extra})
    result = subprocess.run(
        ["bash", str(RECEIVER), "--identity"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.strip()


def test_receiver_uses_canonical_local_node_id(tmp_path: Path) -> None:
    config = tmp_path / ".coherence-network"
    config.mkdir()
    (config / "node_id").write_text("8160aa905ac5881e\n", encoding="utf-8")
    assert _identity(tmp_path) == "8160aa905ac5881e"


def test_receiver_environment_identity_has_priority(tmp_path: Path) -> None:
    config = tmp_path / ".coherence-network"
    config.mkdir()
    (config / "node_id").write_text("from-file\n", encoding="utf-8")
    assert _identity(tmp_path, MR_NODE_ID="from-env") == "from-env"


def test_receiver_legacy_identity_is_last_fallback(tmp_path: Path) -> None:
    assert _identity(tmp_path) == "sema-macos"


def test_receiver_retries_transient_inbox_failure(tmp_path: Path) -> None:
    config = tmp_path / ".coherence-network"
    config.mkdir()
    counter = tmp_path / "curl-count"
    fake_curl = tmp_path / "curl"
    fake_curl.write_text(
        "#!/bin/bash\n"
        f"n=$(cat {counter!s} 2>/dev/null || echo 0)\n"
        "n=$((n + 1))\n"
        f"echo $n > {counter!s}\n"
        "if [ $n -lt 3 ]; then exit 28; fi\n"
        "printf '{\"messages\":[],\"count\":0}'\n",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    log = tmp_path / "receiver.log"
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path),
            "MR_ROOT": str(ROOT),
            "MR_CURL": str(fake_curl),
            "MR_LOG": str(log),
            "MR_RETRY_SLEEP": "0",
            "MR_POLL_RETRIES": "4",
        }
    )

    result = subprocess.run(
        ["bash", str(RECEIVER), "--once"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert counter.read_text(encoding="utf-8").strip() == "3"
    assert "no response from bus" not in log.read_text(encoding="utf-8")
