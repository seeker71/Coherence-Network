"""A cold native build returns one path even when the Form gate emits diagnostics."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def test_cold_build_path_excludes_gate_diagnostics(tmp_path):
    root = Path(__file__).resolve().parents[2]
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(root / "scripts/ensure_form_cli_native.sh", scripts)
    kernel = tmp_path / "form"
    (kernel / "gate").mkdir(parents=True)
    (kernel / "runtime").mkdir()
    (kernel / "gate/form-cli-build-run.bml").touch()
    (kernel / "runtime/fkwu-uni.c").touch()
    stub = kernel / "fkwu"
    stub.write_text(
        "#!" + sys.executable + "\n"
        "import json, pathlib, sys\n"
        "request = json.load(sys.stdin)\n"
        "if request.get('source_id'):\n"
        "    print('0123456789abcdef')\n"
        "    print('0')\n"
        "else:\n"
        "    target = pathlib.Path(request['out'])\n"
        "    target.write_text('#!/bin/sh\\nexit 0\\n')\n"
        "    target.chmod(0o755)\n"
        "    pathlib.Path(str(target) + '.source.id').write_text('0123456789abcdef\\n')\n"
        "    print('building native carrier')\n"
        "    print('0')\n"
    )
    stub.chmod(0o755)
    command = ["bash", str(scripts / "ensure_form_cli_native.sh"), "--print-path"]
    built = subprocess.run(command, capture_output=True, text=True, check=True)
    path = built.stdout.strip()
    assert len(built.stdout.splitlines()) == 1
    assert Path(path).is_file() and os.access(path, os.X_OK)
    assert "building native carrier" in built.stderr
    selected = json.loads((tmp_path / ".cache/form-cli-native/selected.json").read_text())
    assert selected["native_path"] == path
    cached = subprocess.run(command, capture_output=True, text=True, check=True)
    assert cached.stdout == built.stdout
    assert "building native carrier" not in cached.stderr
