from __future__ import annotations

import re
import subprocess
from pathlib import Path
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]

# The four transmuted-endpoint recipes the live API loads at request time
# (api/app/routers/utils.py → serve_via_kernel). They are the deployable
# artifact the prod kernel reads; if they are missing from the image,
# load_recipe raises FileNotFoundError and the endpoints silently degrade to
# python-fallback (correct values, but NOT kernel-served). These tests are the
# regression guard against an image that drops the recipes.
_ENDPOINT_RECIPES = (
    "endpoint_coherence_weight_demo.fk",
    "endpoint_nodeid_distance_demo.fk",
    "endpoint_nodeid_compatibility_demo.fk",
    "endpoint_weighted_average_demo.fk",
    "endpoint_simpson_diversity_demo.fk",
    "endpoint_idea_score_demo.fk",
    "endpoint_marginal_cc_return_demo.fk",
    "endpoint_breath_balance_demo.fk",
)
_RECIPE_DIR_REL = "form/form-kernel-ts/seedbank/python-adapter/examples"


def _dependency_name(value: str) -> str:
    match = re.match(r"([A-Za-z0-9_.-]+)", value.strip())
    assert match is not None
    return match.group(1).lower().replace("_", "-")


def test_api_kernel_builder_rust_toolchain_supports_locked_edition2024_crates() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile.api").read_text(encoding="utf-8")
    lockfile = (REPO_ROOT / "form" / "form-kernel-rust" / "Cargo.lock").read_text(
        encoding="utf-8"
    )

    assert 'name = "idna_adapter"' in lockfile
    assert 'version = "1.2.2"' in lockfile

    match = re.search(
        r"^FROM rust:(?P<major>\d+)\.(?P<minor>\d+)-slim-bookworm AS kernel-builder$",
        dockerfile,
        re.MULTILINE,
    )
    assert match is not None

    toolchain = (int(match.group("major")), int(match.group("minor")))
    assert toolchain >= (1, 86)


def test_api_docker_requirements_cover_pyproject_runtime_dependencies() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "api" / "pyproject.toml").read_text(encoding="utf-8"))
    project_dependencies = {
        _dependency_name(value)
        for value in pyproject["project"]["dependencies"]
    }
    docker_requirements = {
        _dependency_name(line)
        for line in (REPO_ROOT / "api" / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert sorted(project_dependencies - docker_requirements) == []


def test_transmuted_endpoint_recipes_are_git_tracked() -> None:
    """The four endpoint .fk live on disk AND are tracked by git.

    They are gitignored as a class (`*.fk`) but un-ignored individually via
    `!` negations in examples/.gitignore. If a future change drops a negation,
    the recipe falls out of version control, never reaches the image, and the
    endpoint degrades to python-fallback. Asserting tracked-ness catches that
    even in a CI env with no kernel to actually run them.
    """
    recipe_dir = REPO_ROOT / _RECIPE_DIR_REL
    tracked = set(
        subprocess.run(
            ["git", "ls-files", _RECIPE_DIR_REL],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
    )
    for name in _ENDPOINT_RECIPES:
        on_disk = recipe_dir / name
        assert on_disk.is_file(), f"recipe missing on disk: {name}"
        rel = f"{_RECIPE_DIR_REL}/{name}"
        assert rel in tracked, (
            f"recipe not git-tracked: {rel} — it must be committed so the "
            "deploy image carries it and the endpoint serves kernel-side"
        )


def test_dockerfile_copies_endpoint_recipes_to_recipe_dir() -> None:
    """Dockerfile.api copies the four recipes and points FORM_RECIPE_DIR there.

    The bridge resolves bare recipe names against FORM_RECIPE_DIR (when set).
    This asserts (a) every endpoint .fk is COPY'd into the image, and (b) the
    COPY destination matches the FORM_RECIPE_DIR env exactly — so load_recipe
    resolves on disk in the container and the kernel actually serves.
    """
    dockerfile = (REPO_ROOT / "Dockerfile.api").read_text(encoding="utf-8")

    env_match = re.search(r"FORM_RECIPE_DIR=(\S+)", dockerfile)
    assert env_match is not None, "Dockerfile.api must set FORM_RECIPE_DIR"
    recipe_dir = env_match.group(1).rstrip("/")
    assert recipe_dir == f"/app/{_RECIPE_DIR_REL}", recipe_dir

    # Every endpoint recipe is named as a COPY source.
    for name in _ENDPOINT_RECIPES:
        assert f"{_RECIPE_DIR_REL}/{name}" in dockerfile, (
            f"Dockerfile.api must COPY {name} into the image"
        )

    # The COPY destination directory matches FORM_RECIPE_DIR (image path).
    assert f"./{_RECIPE_DIR_REL}/" in dockerfile, (
        "Dockerfile.api COPY destination must be the recipe dir under /app"
    )
