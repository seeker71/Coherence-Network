from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
import tomllib

from app import server


REPO_ROOT = Path(__file__).resolve().parents[2]

_APP_RECIPE_DIR_REL = "api/app/form_recipes"
_APP_ENDPOINT_RECIPES = (
    "endpoint_gathering_head_value.fk",
    "endpoint_gathering_visible.fk",
    "endpoint_household_advance.fk",
    "endpoint_ical_allday.fk",
    "endpoint_ical_field.fk",
    "endpoint_member_active.fk",
    "endpoint_membership_lookup_status.fk",
    "endpoint_place_distance.fk",
    "endpoint_placeholder_name.fk",
    "endpoint_reaction_resonance.fk",
    "endpoint_request_progress.fk",
    "endpoint_vedic_chat.fk",
    "endpoint_vedic_chart.fk",
)


def _dependency_name(value: str) -> str:
    match = re.match(r"([A-Za-z0-9_.-]+)", value.strip())
    assert match is not None
    return match.group(1).lower().replace("_", "-")


def test_api_kernel_builder_compiles_only_the_pinned_fkwu_runtime() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile.api").read_text(encoding="utf-8")

    assert "COPY form/ /build/form/" in dockerfile
    assert "cc -O2 -o fkwu runtime/fkwu-uni.c" in dockerfile
    assert "COPY --from=kernel-builder /build/form/fkwu /app/form/fkwu" in dockerfile
    assert "gate/form-cli-build-run.bml" in dockerfile
    # the image keeps the pinned source home whole (#4117): the kernel root is /app/form, with
    # form/form-stdlib, runtime/ and control/ beside each other as in the checkout's form/
    assert "COPY form/runtime /app/form/runtime" in dockerfile
    assert "COPY --from=kernel-builder /build/form/form/form-stdlib/ /app/form/form/form-stdlib/" in dockerfile
    assert "COPY --from=kernel-builder /build/form-cli.source.id /app/form/form-cli.source.id" in dockerfile
    assert "cargo build" not in dockerfile
    assert "form-kernel-rust" not in dockerfile


def test_kernel_toolchain_is_an_immutable_shared_image_without_apt_drift() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile.api").read_text(encoding="utf-8")
    fkwu_source = (REPO_ROOT / "form" / "runtime" / "fkwu-uni.c").read_text(
        encoding="utf-8"
    )
    builder = dockerfile.split(" AS kernel-builder\n", 1)[1].split(
        "# Stage 2 — Python runtime", 1
    )[0]

    image_pin = re.search(
        r"^FROM (docker\.io/library/gcc:12\.5\.0-bookworm@sha256:[0-9a-f]{64}) "
        r"AS kernel-builder$",
        dockerfile,
        re.MULTILINE,
    )
    assert image_pin is not None
    assert "apt-get" not in builder
    assert "command -v cc >/dev/null" in builder
    assert "command -v openssl >/dev/null" in builder
    assert builder.count("SOURCE_DATE_EPOCH=0") == 1
    assert "__DATE__" not in fkwu_source
    assert "__TIME__" not in fkwu_source


def test_staged_form_runner_executes_with_the_flattened_image_stdlib(tmp_path) -> None:
    # the image's layout: the source home is the root (/app), its stdlib /app/form/form-stdlib and
    # the runtime source beside form/ at /app/runtime — fkwu_run.sh reads it as <source root>/../runtime
    root = tmp_path / "image"
    scripts = root / "scripts"
    runtime = root / "runtime"
    stdlib = root / "form" / "form-stdlib"
    scripts.mkdir(parents=True)
    runtime.mkdir(parents=True)
    stdlib.mkdir(parents=True)
    runner = scripts / "fkwu_run.sh"
    shutil.copy2(REPO_ROOT / "scripts" / "fkwu_run.sh", runner)
    (runtime / "fkwu-uni.c").write_text("bootstrap", encoding="utf-8")
    (runtime / "fkwu-optable.h").write_text("bootstrap", encoding="utf-8")
    (stdlib / "core.fk").write_text("flat-core-marker\n", encoding="utf-8")
    offered = root / "offered.fk"
    offered.write_text("offered-recipe-marker\n", encoding="utf-8")
    fkwu = root / "form" / "fkwu"
    # fkwu_run.sh folds the stdlib core and the offered recipes into one program file and
    # hands the kernel that single path
    fkwu.write_text(
        "#!/usr/bin/env bash\n"
        "grep -q flat-core-marker \"$1\" || exit 4\n"
        "grep -q offered-recipe-marker \"$1\" || exit 5\n"
        "printf '42\\n'\n",
        encoding="utf-8",
    )
    fkwu.chmod(fkwu.stat().st_mode | 0o111)

    result = subprocess.run(
        ["bash", str(runner), "--src", str(offered)],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "TMPDIR": str(tmp_path)},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "42"


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


def test_api_runtime_installs_the_sqlalchemy_psycopg3_driver() -> None:
    requirements = (REPO_ROOT / "api" / "requirements.txt").read_text(
        encoding="utf-8"
    )
    pyproject = tomllib.loads(
        (REPO_ROOT / "api" / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert "psycopg[binary]>=" in requirements
    assert any(
        dependency.startswith("psycopg[binary]>=")
        for dependency in pyproject["project"]["dependencies"]
    )


def test_api_server_reads_internal_proxy_trust_from_file_backed_config(monkeypatch) -> None:
    dockerfile = (REPO_ROOT / "Dockerfile.api").read_text(encoding="utf-8")
    config = json.loads((REPO_ROOT / "api" / "config" / "api.json").read_text())
    captured = {}

    monkeypatch.setattr(
        server,
        "get_list",
        lambda *args: config["server"]["forwarded_allow_ips"],
    )
    monkeypatch.setattr(
        server.uvicorn,
        "run",
        lambda app, **values: captured.update(app=app, **values),
    )
    server.main()

    assert config["server"]["forwarded_allow_ips"] == ["127.0.0.1", "172.16.0.0/12"]
    assert captured == {
        "app": "app.main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "ws": "websockets-sansio",
        "proxy_headers": True,
        "forwarded_allow_ips": ["127.0.0.1", "172.16.0.0/12"],
    }
    assert 'CMD ["python", "-m", "app.server"]' in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert "http://127.0.0.1:8000/api/ping" in dockerfile
    assert "HEALTHCHECK --interval=30s --timeout=5s" in dockerfile
    assert "FORWARDED_ALLOW_IPS" not in dockerfile
    assert "--forwarded-allow-ips=*" not in dockerfile


def test_release_runs_no_substrate_maintenance_and_form_owns_changed_source_work() -> None:
    # since #4088 the release script carries no ingest or RAG heal of its own (the shell gate that
    # re-ingested on every rollout is retired); a changed source is maintained on request by the
    # Form owner, which runs the projection and the heal inside the serving container as explicit steps
    deploy = (REPO_ROOT / "deploy" / "hostinger" / "auto-deploy.sh").read_text(
        encoding="utf-8"
    )
    owner = (
        REPO_ROOT / "api" / "app" / "form_recipes" / "source_maintenance.bml"
    ).read_text(encoding="utf-8")

    assert "run_substrate_ingest" not in deploy
    assert "coh_substrate.py bootstrap" not in deploy
    assert "form_cli_rag.py heal" not in deploy
    assert "--cpus" not in deploy
    assert "--memory" not in deploy
    assert "source_maintenance.bml" in deploy
    assert '"scripts/coh_substrate.py","ingest-paths"' in owner
    assert '"scripts/form_cli_rag.py","heal"' in owner


def test_eager_startup_cache_warm_is_disabled_by_file_configuration() -> None:
    config = json.loads((REPO_ROOT / "api" / "config" / "api.json").read_text())

    assert config["server"]["startup_cache_warm_enabled"] is False


def test_native_form_shell_carriers_are_file_backed_configuration() -> None:
    config = json.loads((REPO_ROOT / "api" / "config" / "api.json").read_text())

    assert config["form_runtime"] == {
        "_doc": "Host carrier paths used to enter local Form source execution.",
        "posix_bash_path": "/bin/bash",
        "windows_bash_path": r"C:\Program Files\Git\bin\bash.exe",
    }


def test_api_runtime_carries_the_process_inspector_used_by_dialogue_reaping() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile.api").read_text(encoding="utf-8")

    assert re.search(r"^\s+procps \\$", dockerfile, re.MULTILINE) is not None


def test_app_endpoint_recipes_are_git_tracked() -> None:
    """Network-owned live recipes remain versioned with their API callers."""
    recipe_dir = REPO_ROOT / _APP_RECIPE_DIR_REL
    tracked = set(
        subprocess.run(
            ["git", "ls-files", _APP_RECIPE_DIR_REL],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
    )

    for name in _APP_ENDPOINT_RECIPES:
        rel = f"{_APP_RECIPE_DIR_REL}/{name}"
        assert (recipe_dir / name).is_file(), f"app recipe missing on disk: {name}"
        assert rel in tracked, f"app recipe not git-tracked: {rel}"


def test_dockerfile_copies_app_endpoint_recipes_with_api_tree() -> None:
    """The API-owned recipes enter the image through the package-tree copy."""
    dockerfile = (REPO_ROOT / "Dockerfile.api").read_text(encoding="utf-8")

    assert re.search(r"^COPY api/ \./$", dockerfile, re.MULTILINE) is not None
    for name in _APP_ENDPOINT_RECIPES:
        assert (REPO_ROOT / _APP_RECIPE_DIR_REL / name).is_file()


def test_kernel_bridge_runs_fkwu_from_the_image_kernel_root(tmp_path, monkeypatch) -> None:
    # the image keeps the pinned source home whole: /app/form/form/form-stdlib, /app/form/runtime; the
    # module lives at /app/app/services, so "four parents up" is `/` there, not the repo root. The bridge
    # must still find the kernel root to run fkwu from — on 2026-10-20 it ran from `/` and the API died at import
    from app.services import form_kernel_bridge as bridge

    image = tmp_path / "app"
    (image / "form" / "form" / "form-stdlib").mkdir(parents=True)
    (image / "form" / "runtime").mkdir(parents=True)
    monkeypatch.setattr(bridge, "_IMAGE_ROOT", image)
    monkeypatch.setattr(bridge, "_REPO_ROOT", tmp_path / "nowhere")
    assert bridge._form_source_parent() == image / "form"

    flat = tmp_path / "flat"
    (flat / "form" / "form-stdlib").mkdir(parents=True)
    monkeypatch.setattr(bridge, "_IMAGE_ROOT", flat)
    assert bridge._form_source_parent() == flat

    checkout = tmp_path / "checkout"
    (checkout / "form" / "form" / "form-stdlib").mkdir(parents=True)
    monkeypatch.setattr(bridge, "_IMAGE_ROOT", tmp_path / "no-image")
    monkeypatch.setattr(bridge, "_REPO_ROOT", checkout)
    assert bridge._form_source_parent() == checkout / "form"
