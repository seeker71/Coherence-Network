"""The public companion bundle is portable and has one maintained skill source."""
import importlib.util
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
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


def test_directory_listing_text_and_packaged_icons():
    """Public listing limits are stricter than successful draft import."""
    manifest = json.loads((PLUGIN / "plugin.json").read_text())
    interface = manifest["extensions"]["com.openai"]["interface"]
    for field, maximum in (("displayName", 30), ("shortDescription", 30),
                           ("longDescription", 4000), ("developerName", 80)):
        assert 0 < len(interface[field]) <= maximum, field
    prompts = interface["defaultPrompt"]
    assert len(prompts) <= 3
    assert len(set(prompts)) == len(prompts)
    assert all(0 < len(prompt) <= 128 for prompt in prompts)
    for field in ("logo", "composerIcon"):
        assert interface[field].startswith("./")
        icon = (PLUGIN / interface[field]).resolve()
        assert icon.is_relative_to(PLUGIN)
        data = icon.read_bytes()
        assert len(data) <= 5 * 1024 * 1024
        svg = ET.fromstring(data)
        _, _, width, height = map(float, svg.attrib["viewBox"].split())
        assert width == height and width >= 48
        assert data == (ROOT / "web/public/assets/logo.svg").read_bytes()


def test_distribution_drift_is_detected(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("companion_readmes", ROOT / "scripts/build_readmes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO_ROOT", str(tmp_path))
    source = tmp_path / "skills/coherence-network"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: example\n---\nCurrent skill\n")
    (tmp_path / "LICENSE").write_text("License\n")
    logo = tmp_path / "web/public/assets/logo.svg"
    logo.parent.mkdir(parents=True)
    logo.write_text('<svg viewBox="0 0 512 512"/>')
    target = tmp_path / "plugins/coherence-companion"
    target.mkdir(parents=True)
    (target / "plugin.json").write_text("{}")
    assert module.build_companion_plugin()
    assert module.build_companion_plugin(check=True)
    (target / "assets/logo.svg").write_text("stale image")
    assert not module.build_companion_plugin(check=True)
    assert module.build_companion_plugin()
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
