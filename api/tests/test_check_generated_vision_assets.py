from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_generated_vision_assets


def test_translated_concept_uses_frontmatter_id_for_story_assets(monkeypatch, tmp_path: Path):
    concept_dir = tmp_path / "concepts"
    generated_dir = tmp_path / "generated"
    concept_dir.mkdir()
    generated_dir.mkdir()

    concept_path = concept_dir / "lc-nourishing.de.md"
    concept_path.write_text(
        """---
id: lc-nourishing
lang: de
---

# Nährend

![Erstes Bild](visuals:some prompt)
![Zweites Bild](visuals:another prompt)
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(check_generated_vision_assets, "CONCEPT_DIR", concept_dir)
    monkeypatch.setattr(check_generated_vision_assets, "GENERATED_DIR", generated_dir)

    requirements = check_generated_vision_assets.concept_story_requirements()

    assert [asset.name for _label, asset, _source in requirements] == [
        "lc-nourishing-story-0.jpg",
        "lc-nourishing-story-1.jpg",
    ]
