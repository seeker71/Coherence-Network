#!/usr/bin/env python3
"""Pre-generate all Pollinations images and save as static assets.

Fetches concepts from the DB (via API), generates deterministic
Pollinations URLs for BOTH gallery visuals and inline story visuals,
downloads each image, and saves to web/public/visuals/generated/.

Naming convention:
  Gallery visuals:  {concept-id}-{index}.jpg
  Story visuals:    {concept-id}-story-{index}.jpg

After running, the concept page serves local files — zero runtime
dependency on Pollinations.

Usage:
    python scripts/generate_visuals.py                              # production
    python scripts/generate_visuals.py --api-url http://localhost:8000
    python scripts/generate_visuals.py --dry-run
    python scripts/generate_visuals.py --force                      # re-download all
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

from kb_common import (
    OUTPUT_DIR, DEFAULT_API,
    concept_seed, SEED_STRIDE, STORY_SEED_STRIDE,
    pollinations_url, api_get, download_image,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_MANIFEST = REPO_ROOT / "docs" / "visuals" / "prompts.json"
PROMPT_PROFILES = REPO_ROOT / "docs" / "visuals" / "regeneration_profiles.json"


def fetch_concepts(api_url: str) -> list[dict]:
    """Fetch all living-collective concepts."""
    url = f"{api_url}/api/concepts/domain/living-collective?limit=200"
    data = api_get(url)
    return data.get("items", [])


def extract_story_visuals(story_content: str) -> list[dict]:
    """Extract inline visuals from story_content markdown."""
    visuals = []
    for m in re.finditer(r"!\[([^\]]*)\]\(visuals:([^)]+)\)", story_content):
        visuals.append({"caption": m.group(1).strip(), "prompt": m.group(2).strip()})
    return visuals


def _load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_prompt_profile(profiles_path: Path, profile_id: str | None) -> dict[str, Any]:
    """Load an optional dynamic prompt profile.

    Prompt records stay stable and editable in docs/visuals/prompts.json. A
    profile adds reviewable generation-time guidance without rewriting every
    record, which lets future quality upgrades run as deterministic batches.
    """
    if not profile_id:
        return {}

    profiles = _load_json_file(profiles_path)
    records = profiles.get("profiles")
    if not isinstance(records, list):
        raise ValueError(f"profiles file has no profiles list: {profiles_path}")

    for record in records:
        if isinstance(record, dict) and record.get("id") == profile_id:
            return record
    raise ValueError(f"unknown prompt profile: {profile_id}")


def compose_manifest_prompt(record: dict[str, Any], profile: dict[str, Any] | None = None) -> str:
    prompt = str(record.get("prompt") or "").strip()
    if not profile:
        return prompt

    parts = [
        str(profile.get("prompt_prefix") or "").strip(),
        prompt,
        str(profile.get("prompt_suffix") or "").strip(),
    ]
    negative = str(profile.get("negative_prompt") or "").strip()
    if negative:
        parts.append(f"Avoid: {negative}")
    return " ".join(part for part in parts if part)


def _profile_int(profile: dict[str, Any], key: str, fallback: int) -> int:
    value = profile.get(key)
    if value in (None, ""):
        return fallback
    return int(value)


def manifest_pollinations_url(record: dict[str, Any], profile: dict[str, Any] | None = None) -> str:
    """Build a Pollinations URL from a persistent prompt manifest record."""
    profile = profile or {}
    prompt = compose_manifest_prompt(record, profile)
    encoded = urllib.parse.quote(prompt)
    width = _profile_int(profile, "width", int(record.get("width") or 1024))
    height = _profile_int(profile, "height", int(record.get("height") or 576))
    seed = int(record.get("seed") or 42) + _profile_int(profile, "seed_offset", 0)
    model = urllib.parse.quote(str(profile.get("model") or record.get("model") or "flux"))
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={width}&height={height}&model={model}&nologo=true&seed={seed}"
    )


def _load_manifest_records(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = _load_json_file(manifest_path)
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ValueError(f"Manifest has no records list: {manifest_path}")
    return [record for record in records if isinstance(record, dict)]


def _load_batch_records(batch_file: Path) -> list[dict[str, Any]]:
    batch = _load_json_file(batch_file)
    records = batch.get("records")
    if not isinstance(records, list):
        raise ValueError(f"Batch has no records list: {batch_file}")
    return [record for record in records if isinstance(record, dict)]


def _select_manifest_records(
    records: list[dict[str, Any]],
    only_path: str | None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for record in records:
        path = str(record.get("path") or "")
        mirrors = [str(p) for p in record.get("mirror_paths") or []]
        if only_path and only_path not in [path, *mirrors, record.get("id")]:
            continue
        selected.append(record)
    return selected


def _destination_for_record(record: dict[str, Any], output_dir: Path | None) -> Path:
    rel_path = Path(str(record.get("path") or ""))
    if output_dir is None:
        return REPO_ROOT / rel_path
    base = output_dir if output_dir.is_absolute() else REPO_ROOT / output_dir
    return base / rel_path


def generate_from_manifest(
    manifest_path: Path,
    only_path: str | None,
    dry_run: bool,
    force: bool,
    *,
    batch_file: Path | None = None,
    output_dir: Path | None = None,
    profile: dict[str, Any] | None = None,
) -> int:
    """Generate images from committed prompt records.

    This path is the durable regeneration contract: edit the manifest prompt,
    then regenerate by stable repo path without reading metadata from the old
    image artifact.
    """
    try:
        records = _load_batch_records(batch_file) if batch_file else _load_manifest_records(manifest_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    selected = _select_manifest_records(records, only_path)

    if only_path and not selected:
        print(f"No manifest record matched: {only_path}", file=sys.stderr)
        return 1

    total = len(selected)
    downloaded = 0
    skipped = 0
    failed = 0

    for record in selected:
        prompt = compose_manifest_prompt(record, profile)
        rel_path = str(record.get("path") or "")
        if not prompt or not rel_path:
            failed += 1
            print(f"  SKIP invalid record: {record.get('id')}", file=sys.stderr)
            continue

        dest = _destination_for_record(record, output_dir)
        mirror_paths = [] if output_dir else [REPO_ROOT / str(path) for path in record.get("mirror_paths") or []]
        if dest.exists() and not force:
            skipped += 1
            for mirror in mirror_paths:
                if not mirror.exists():
                    mirror.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, mirror)
            continue

        url = manifest_pollinations_url(record, profile)
        if dry_run:
            print(f"  [DRY RUN] {dest.relative_to(REPO_ROOT)}: {prompt[:100]}...")
            downloaded += 1
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"  {rel_path}...", end=" ", flush=True)
        if download_image(url, dest):
            for mirror in mirror_paths:
                mirror.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, mirror)
            size_kb = dest.stat().st_size // 1024
            print(f"OK ({size_kb}KB)")
            downloaded += 1
        else:
            print("FAILED")
            failed += 1
        time.sleep(1)

    print(f"\nDone: {downloaded} generated, {skipped} already exist, {failed} failed (of {total} total)")
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description="Pre-generate Pollinations images as static assets")
    parser.add_argument("--api-url", default=DEFAULT_API)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    parser.add_argument(
        "--from-manifest",
        action="store_true",
        help="Generate from docs/visuals/prompts.json instead of API concept data.",
    )
    parser.add_argument("--manifest", type=Path, default=PROMPT_MANIFEST)
    parser.add_argument("--profiles", type=Path, default=PROMPT_PROFILES)
    parser.add_argument(
        "--profile",
        help="Dynamic prompt profile id from docs/visuals/regeneration_profiles.json.",
    )
    parser.add_argument(
        "--batch-file",
        type=Path,
        help="Manifest batch file from scripts/plan_vision_image_regeneration.py.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help=(
            "Write regenerated candidates under this directory while preserving "
            "repo-relative paths. When omitted, production asset paths are used."
        ),
    )
    parser.add_argument(
        "--only-path",
        help="When using --from-manifest, regenerate one repo path or record id.",
    )
    args = parser.parse_args()

    if args.from_manifest:
        try:
            profile = load_prompt_profile(args.profiles, args.profile)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return generate_from_manifest(
            args.manifest,
            args.only_path,
            args.dry_run,
            args.force,
            batch_file=args.batch_file,
            output_dir=args.out_dir,
            profile=profile,
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    concepts = fetch_concepts(args.api_url)
    print(f"Total concepts: {len(concepts)}")

    total = 0
    downloaded = 0
    skipped = 0
    failed = 0

    for c in concepts:
        cid = c["id"]
        base_seed = concept_seed(cid)

        # ── Gallery visuals (from `visuals` property) ──
        gallery_visuals = c.get("visuals", [])
        for i, v in enumerate(gallery_visuals):
            prompt = v.get("prompt", "")
            if not prompt:
                continue
            total += 1
            seed = base_seed + i * SEED_STRIDE
            filename = f"{cid}-{i}.jpg"
            dest = OUTPUT_DIR / filename

            if dest.exists() and not args.force:
                skipped += 1
                continue

            url = pollinations_url(prompt, seed)
            if args.dry_run:
                print(f"  [DRY RUN] {filename}: {prompt[:60]}...")
                downloaded += 1
                continue

            print(f"  {filename}...", end=" ", flush=True)
            if download_image(url, dest):
                size_kb = dest.stat().st_size // 1024
                print(f"OK ({size_kb}KB)")
                downloaded += 1
            else:
                print("FAILED")
                failed += 1
            time.sleep(1)

        # ── Story visuals (from `story_content` inline ![](visuals:...) ) ──
        story_content = c.get("story_content", "")
        if story_content:
            story_visuals = extract_story_visuals(story_content)
            for i, v in enumerate(story_visuals):
                prompt = v.get("prompt", "")
                if not prompt:
                    continue
                total += 1
                seed = base_seed + i * STORY_SEED_STRIDE
                filename = f"{cid}-story-{i}.jpg"
                dest = OUTPUT_DIR / filename

                if dest.exists() and not args.force:
                    skipped += 1
                    continue

                url = pollinations_url(prompt, seed)
                if args.dry_run:
                    print(f"  [DRY RUN] {filename}: {prompt[:60]}...")
                    downloaded += 1
                    continue

                print(f"  {filename}...", end=" ", flush=True)
                if download_image(url, dest):
                    size_kb = dest.stat().st_size // 1024
                    print(f"OK ({size_kb}KB)")
                    downloaded += 1
                else:
                    print("FAILED")
                    failed += 1
                time.sleep(1)

    print(f"\nDone: {downloaded} downloaded, {skipped} already exist, {failed} failed (of {total} total)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
