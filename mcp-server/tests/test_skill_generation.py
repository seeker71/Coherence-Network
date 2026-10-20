"""Generated skill discovery must retain YAML and explicit installation boundaries."""
import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("build_readmes", ROOT / "scripts/build_readmes.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_skill_frontmatter_remains_discoverable_and_roundtrips():
    template = (ROOT / "skills/coherence-network/SKILL.template.md").read_text()
    result = builder.expand(template, "SKILL.template.md")
    assert result.startswith("---\n")
    metadata = yaml.safe_load(result.split("---", 2)[1])
    assert metadata["name"] == "coherence-network"
    assert metadata["description"]
    assert result == (ROOT / "skills/coherence-network/SKILL.md").read_text()


def test_generation_only_writes_repository_outputs(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    skill = repo / "skills/coherence-network"
    skill.mkdir(parents=True)
    (skill / "SKILL.template.md").write_text("---\nname: example\ndescription: Example\n---\nBody\n")
    installed = tmp_path / "home/.openclaw/workspace/skills/coherence-network/SKILL.md"
    installed.parent.mkdir(parents=True)
    installed.write_text("installed version")
    monkeypatch.setattr(builder, "REPO_ROOT", str(repo))
    monkeypatch.setattr(builder, "TEMPLATES", ["skills/coherence-network/SKILL.template.md"])
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert builder.build()
    assert (skill / "SKILL.md").exists()
    assert installed.read_text() == "installed version"
