from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import generate_visuals  # noqa: E402


def test_compose_manifest_prompt_applies_dynamic_profile() -> None:
    prompt = generate_visuals.compose_manifest_prompt(
        {"prompt": "a shared garden courtyard"},
        {
            "prompt_prefix": "high-quality documentary image",
            "prompt_suffix": "warm afternoon light",
            "negative_prompt": "text overlays, watermarks",
        },
    )

    assert prompt == (
        "high-quality documentary image a shared garden courtyard "
        "warm afternoon light Avoid: text overlays, watermarks"
    )


def test_manifest_output_dir_preserves_repo_relative_path(tmp_path: Path) -> None:
    dest = generate_visuals._destination_for_record(
        {"path": "web/public/visuals/generated/lc-space-0.jpg"},
        tmp_path,
    )

    assert dest == tmp_path / "web/public/visuals/generated/lc-space-0.jpg"


def test_manifest_url_profile_overrides_dimensions_model_and_seed() -> None:
    url = generate_visuals.manifest_pollinations_url(
        {
            "prompt": "living roof community home",
            "model": "sana",
            "seed": 7,
            "width": 512,
            "height": 512,
        },
        {
            "model": "flux",
            "seed_offset": 100,
            "width": 1024,
            "height": 768,
            "prompt_prefix": "quality sample",
        },
    )

    assert "quality%20sample%20living%20roof%20community%20home" in url
    assert "width=1024" in url
    assert "height=768" in url
    assert "model=flux" in url
    assert "seed=107" in url
