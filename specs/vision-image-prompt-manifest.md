---
idea_id: living-collective-vision
status: done
source:
  - file: docs/visuals/prompts.json
    symbols: [vision image prompt records]
  - file: docs/visuals/regeneration_profiles.json
    symbols: [dynamic prompt profiles]
  - file: scripts/generate_visuals.py
    symbols: [generate_from_manifest(), compose_manifest_prompt()]
requirements:
  - "Every current Living Collective vision image has a persistent prompt record."
  - "Prompt validation fails when an image lacks a prompt record or has an empty prompt."
  - "Regeneration can target one stable image path or deterministic prompt batch."
  - "Regeneration can write review candidates under a separate output directory before production assets are replaced."
done_when:
  - "Prompt manifest covers all current vision images."
  - "Asset validation includes prompt-record coverage."
  - "Manifest regeneration dry-run can target one stable image path."
test: "python3 scripts/check_generated_vision_assets.py --allow-untracked"
constraints:
  - "Do not replace image assets in this change."
  - "Preserve all existing filenames and image references."
---

# Spec: Vision Image Prompt Manifest

## Purpose

Living Collective vision images must be regenerable from source-controlled prompts, not recovered from generated image metadata. This prevents the image files from becoming the only durable prompt source and lets future image-quality upgrades happen through reviewable prompt edits, stable filenames, and deterministic batches.

## Requirements

- [ ] **R1**: Add a repository-owned prompt manifest that records every current `web/public/visuals/generated/*.jpg` and `docs/visuals/*.png` image with stable path, prompt text, source collection, model settings when known, and mirror paths when applicable.
- [ ] **R2**: Add or update validation so current vision images fail checks when they have no prompt manifest record or when the prompt is empty.
- [ ] **R3**: Add a manifest-driven regeneration path that can target one image by stable repo path or record id without reading prompt data from the existing image artifact.
- [ ] **R4**: Add deterministic batch planning so the prompt manifest can be split into non-overlapping regeneration batches for parallel review or future swarm execution.

## Files to Create/Modify

- `docs/visuals/prompts.json` — persistent prompt records for current vision images.
- `docs/visuals/regeneration_profiles.json` — dynamic prompt overlays for quality/sample regeneration.
- `scripts/export_vision_image_prompts.py` — migration/audit exporter for prompt records.
- `scripts/check_generated_vision_assets.py` — asset and prompt-record validation.
- `scripts/generate_visuals.py` — manifest-driven regeneration mode.
- `scripts/plan_vision_image_regeneration.py` — deterministic batch planner.
- `specs/vision-image-prompt-manifest.md` — this spec.

## Acceptance Tests

- `python3 scripts/export_vision_image_prompts.py` exports prompt records for all current vision images.
- `python3 scripts/check_generated_vision_assets.py --allow-untracked` passes and reports prompt-record validation.
- `python3 scripts/generate_visuals.py --from-manifest --only-path web/public/visuals/generated/lc-space-0.jpg --dry-run --force` targets one stable image from the manifest.
- `python3 scripts/generate_visuals.py --from-manifest --only-path web/public/visuals/generated/lc-space-0.jpg --profile fast-sample-v1 --out-dir output/vision-quality/candidates --dry-run --force` targets one stable candidate path with a dynamic profile.
- `python3 scripts/plan_vision_image_regeneration.py --batch-size 50 --out-dir output/vision-quality/batches` writes deterministic batch files.

## Verification

```bash
python3 scripts/export_vision_image_prompts.py
python3 scripts/check_generated_vision_assets.py --allow-untracked
python3 scripts/generate_visuals.py --from-manifest --only-path web/public/visuals/generated/lc-space-0.jpg --dry-run --force
python3 scripts/generate_visuals.py --from-manifest --only-path web/public/visuals/generated/lc-space-0.jpg --profile fast-sample-v1 --out-dir output/vision-quality/candidates --dry-run --force
python3 scripts/plan_vision_image_regeneration.py --batch-size 50 --out-dir output/vision-quality/batches
python3 -m py_compile scripts/export_vision_image_prompts.py scripts/plan_vision_image_regeneration.py scripts/generate_visuals.py scripts/check_generated_vision_assets.py
```

## Out of Scope

- Replacing production image assets.
- Choosing a new paid image model or API provider.
- Changing web pages that consume the existing image filenames.
- Adding runtime image generation to the public application.

## Risks and Assumptions

- Risk: The initial prompt manifest is migrated from embedded image metadata. Mitigation: after migration, the manifest becomes authoritative and image metadata is treated as non-authoritative.
- Risk: Mirrored `docs/visuals` and `web/public/visuals` files can drift. Mitigation: prompt records include mirror paths so validation and future regeneration can preserve both locations.
- Assumption: Existing filenames are the stable public contract for current web pages and should not be renamed during prompt persistence work.

## Known Gaps and Follow-up Tasks

- Follow-up: connect the reviewed candidate-output workflow to Codex app image generation or a configured image API provider when a repository-owned binary replacement policy is chosen.
- Follow-up: decide whether future generated image binaries should be committed, uploaded, or produced by a release-time artifact pipeline.
