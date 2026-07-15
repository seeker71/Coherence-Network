"""Contract for the canonical coherence-kernel consumer boundary."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
KERNEL_URL = "https://github.com/seeker71/coherence-kernel.git"
APP_RECIPES = {
    "endpoint_gathering_head_value.fk",
    "endpoint_gathering_visible.fk",
    "endpoint_household_advance.fk",
    "endpoint_ical_allday.fk",
    "endpoint_ical_field.fk",
    "endpoint_member_active.fk",
    "endpoint_place_distance.fk",
    "endpoint_placeholder_name.fk",
    "endpoint_reaction_resonance.fk",
    "endpoint_request_progress.fk",
}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _run_script(path: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, path, *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _blueprint_source_bytes() -> dict[Path, bytes]:
    paths = (
        REPO_ROOT / "form" / "form-stdlib" / "blueprint-registry.json",
        REPO_ROOT / "form" / "form-kernel-go" / "bp_table.go",
        REPO_ROOT / "form" / "form-kernel-rust" / "src" / "bp_table.rs",
        REPO_ROOT / "form" / "form-kernel-ts" / "src" / "bp_table.ts",
    )
    return {path: path.read_bytes() for path in paths}


def test_form_is_pinned_path_preserving_kernel_submodule() -> None:
    """The gitlink and populated checkout identify the same exact snapshot."""
    mode, gitlink, _stage, path = _git("ls-files", "--stage", "form").split()

    assert mode == "160000"
    assert path == "form"
    assert _git("-C", "form", "rev-parse", "HEAD") == gitlink
    assert _git("-C", "form", "status", "--short", "--untracked-files=no") == ""
    assert _git("config", "-f", ".gitmodules", "submodule.form.url") == KERNEL_URL
    assert (
        _git("config", "-f", ".gitmodules", "submodule.form.branch")
        == "form-submodule"
    )

    # The split branch keeps the historic consumer paths (no form/form level).
    assert (REPO_ROOT / "form" / "validate.sh").is_file()
    assert (REPO_ROOT / "form" / "form-stdlib" / "core.fk").is_file()
    assert (
        REPO_ROOT
        / "form"
        / "form-stdlib"
        / "tests"
        / "form-asm-fam-tanh-band.fk"
    ).is_file()
    astro = (
        REPO_ROOT
        / "form"
        / "form-kernel-ts"
        / "seedbank"
        / "python-adapter"
        / "examples"
        / "endpoint_astro_aspect_demo"
    )
    assert astro.with_suffix(".fk").is_file()
    assert astro.with_suffix(".py").is_file()
    assert not any((REPO_ROOT / "form").rglob("form-gen.fk"))
    assert not (REPO_ROOT / "form" / "form" / "form-stdlib").exists()


def test_kernel_regeneration_is_owned_by_submodule() -> None:
    """Every carrier that authors committed kernel artifacts lives upstream."""
    regen_scripts = {
        "regen_fkwu_bootstrap.sh",
        "regen_t_flat.sh",
        "regen_form_cli_bootstrap.sh",
        "regen_standard_lane_binaries.sh",
    }

    for name in regen_scripts:
        canonical = REPO_ROOT / "form" / "scripts" / name
        assert canonical.is_file()
        assert canonical.stat().st_mode & 0o111
        assert not (REPO_ROOT / "scripts" / name).exists()


def test_legacy_form_tree_is_preserved_before_gitlink_initialization(
    tmp_path: Path,
) -> None:
    """Ignored output from the tree-to-gitlink cut is moved, never deleted."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Coherence Test"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@coherencycoin.com"], cwd=repo, check=True
    )
    seed = repo / "seed"
    seed.write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "update-index", "--add", "--cacheinfo", "160000", commit, "form"],
        cwd=repo,
        check=True,
    )
    legacy = repo / "form" / "form-kernel-rust" / "target"
    legacy.mkdir(parents=True)
    (legacy / "kernel-cache").write_text("local artifact\n", encoding="utf-8")

    result = _run_script(
        "scripts/prepare_form_submodule.py", "--repo-root", str(repo)
    )
    backups = list((repo / ".cache").glob("form-pre-submodule-*"))

    assert result.returncode == 0, result.stderr
    assert len(backups) == 1
    backup = backups[0]
    assert not (repo / "form").exists()
    assert (backup / "form-kernel-rust" / "target" / "kernel-cache").read_text(
        encoding="utf-8"
    ) == "local artifact\n"


def test_network_endpoint_recipes_are_owned_by_the_api() -> None:
    """Application recipes remain outside the independently versioned gitlink."""
    tracked = set(_git("ls-files", "api/app/form_recipes").splitlines())

    assert {Path(path).name for path in tracked} == APP_RECIPES
    for name in APP_RECIPES:
        assert (REPO_ROOT / "api" / "app" / "form_recipes" / name).is_file()
        assert not (
            REPO_ROOT
            / "form"
            / "form-kernel-ts"
            / "seedbank"
            / "python-adapter"
            / "examples"
            / name
        ).exists()


def test_form_cli_installer_hydrates_the_kernel_submodule() -> None:
    """A first install and an update both populate the pinned Form checkout."""
    installer = (REPO_ROOT / "install" / "form-cli-install.sh").read_text(
        encoding="utf-8"
    )

    assert 'git clone --depth 1 --recurse-submodules "$REPO_URL" "$DEST"' in installer
    assert 'git -C "$DEST" submodule sync --recursive' in installer
    assert 'git -C "$DEST" submodule update --init --recursive' in installer
    assert 'prepare_form_submodule.py" --repo-root "$DEST" --verify-clean' in installer
    assert "form has material changes" in installer


def test_runner_update_and_deploy_carriers_hydrate_the_kernel_submodule() -> None:
    """Legacy update/deploy carriers cannot leave workers on the previous pin."""
    runner = (REPO_ROOT / "api" / "scripts" / "local_runner.py").read_text(
        encoding="utf-8"
    )

    safe_update = (
        '"update": "git pull origin main && git submodule sync --recursive '
        '&& git submodule update --force --init --recursive"'
    )
    assert safe_update in runner
    assert runner.count("_initialize_worktree_submodules(") >= 6
    assert runner.count("python3 scripts/prepare_form_submodule.py --repo-root .") >= 4

    cli_deploy = (REPO_ROOT / "cli" / "lib" / "commands" / "deploy.mjs").read_text(
        encoding="utf-8"
    )
    assert cli_deploy.count(
        "python3 scripts/prepare_form_submodule.py --repo-root . && "
        "git submodule sync --recursive && "
        "git submodule update --force --init --recursive"
    ) >= 2


def test_consumer_blueprint_mutation_commands_refuse_the_kernel_gitlink() -> None:
    """Consumer tooling cannot rewrite files owned by coherence-kernel."""
    before = _blueprint_source_bytes()
    commands = (
        ("scripts/gen_bp_table.py",),
        ("scripts/scan_form_blueprints.py", "--emit-registry"),
        ("scripts/scan_form_blueprints.py", "register", "CONSUMER-WRITE-PROBE"),
        ("scripts/scan_form_blueprints.py", "unregister", "CONSUMER-WRITE-PROBE"),
    )

    for command in commands:
        result = _run_script(*command)
        assert result.returncode == 2, (command, result.stdout, result.stderr)
        assert "form is the pinned coherence-kernel submodule" in result.stderr
        assert _blueprint_source_bytes() == before


def test_consumer_blueprint_read_only_scans_still_run() -> None:
    """Default reporting and the drift check retain their existing behavior."""
    before = _blueprint_source_bytes()

    report = _run_script("scripts/scan_form_blueprints.py")
    assert report.returncode == 0, report.stderr
    assert "Form Blueprint scan" in report.stdout
    assert "refusing to" not in report.stderr

    check = _run_script("scripts/scan_form_blueprints.py", "--check")
    assert check.returncode in {0, 1}, check.stderr
    assert "refusing to" not in check.stderr
    assert _blueprint_source_bytes() == before
