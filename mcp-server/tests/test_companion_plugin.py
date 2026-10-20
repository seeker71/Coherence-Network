"""The public companion bundle is portable and has one maintained skill source."""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "coherence-companion"


def test_bundle_links_resolve_without_repository_files():
    for document in (PLUGIN / "skills").rglob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
            url = urlsplit(target)
            if url.scheme or not url.path:
                continue
            resolved = (document.parent / unquote(url.path)).resolve()
            assert resolved.is_relative_to(PLUGIN), (document, target)
            assert resolved.exists(), (document, target)


def test_bundle_has_one_skill_and_no_automatic_connections():
    manifest = json.loads((PLUGIN / "plugin.json").read_text())
    assert manifest["name"] == "coherence-companion"
    assert manifest["license"] == "Apache-2.0"
    assert sorted(p.relative_to(PLUGIN).as_posix() for p in PLUGIN.rglob("SKILL.md")) == [
        "skills/coherence-network/SKILL.md",
    ]
    assert not (PLUGIN / "hooks").exists()
    assert not (PLUGIN / "mcp.json").exists()
    assert not (PLUGIN / ".mcp.json").exists()
    assert (PLUGIN / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()


def test_distribution_drift_is_detected(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("companion_readmes", ROOT / "scripts/build_readmes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO_ROOT", str(tmp_path))
    source = tmp_path / "skills/coherence-network"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: example\n---\nCurrent skill\n")
    (tmp_path / "LICENSE").write_text("License\n")
    target = tmp_path / "plugins/coherence-companion"
    target.mkdir(parents=True)
    (target / "plugin.json").write_text("{}")
    assert module.build_companion_plugin()
    assert module.build_companion_plugin(check=True)
    (source / "SKILL.md").write_text("Changed source\n")
    assert not module.build_companion_plugin(check=True)
    assert module.build_companion_plugin()
    assert module.build_companion_plugin(check=True)
    (target / "skills/coherence-network/retired.md").write_text("Old generated guidance")
    assert not module.build_companion_plugin(check=True)
    script = tmp_path / "scripts/build_readmes.py"
    script.parent.mkdir()
    script.write_bytes((ROOT / "scripts/build_readmes.py").read_bytes())
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "STALE:" in result.stdout
