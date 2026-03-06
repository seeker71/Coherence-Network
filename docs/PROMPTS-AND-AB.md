# Prompts and A/B Testing — Current State and Config

## Prompt/direction data in config (no data in code)

**All prompt and direction text** is loaded from **`api/config/prompt_templates.json`** (or `PROMPT_TEMPLATES_CONFIG_PATH`). No prompt strings live in code.

| Config section | Used by |
|----------------|--------|
| **direction_templates** | spec, impl, impl_iteration, test, review — `project_manager.build_direction()` via `prompt_templates_loader.build_direction()`. |
| **role_wrapper** | common + by_task_type (spec, review) — `agent_service_executor._with_agent_roles()` via `prompt_templates_loader.build_direction_with_roles()`. |
| **unblock_direction** | flow unblock by blocking_stage (spec, process, implementation, validation) — `inventory/flow_helpers._build_unblock_direction()` via `get_unblock_direction()`. |
| **idea_progress_direction**, **spec_progress_direction** | ROI progress tasks — `inventory_service._build_idea_progress_direction()` / `_build_spec_progress_direction()` via loader. |
| **cli_flow_directions** | impl, review, heal for CLI flow matrix — `run_cli_task_flow_matrix` `_impl_direction` / `_review_direction` / `_heal_direction` via `get_cli_flow_direction()`. |

Loader: **`api/app/services/agent_routing/prompt_templates_loader.py`** (`build_direction`, `build_direction_with_roles`, `get_unblock_direction`, `get_idea_progress_direction`, `get_spec_progress_direction`, `get_cli_flow_direction`).

---

## A/B testing: where config lives and what’s implemented

### Config files

| Config | Purpose |
|--------|--------|
| **`api/config/orchestrator_policy.json`** | Executor A/B candidate priority, **prompt variant names** per task type, and A/B tuning (challenger %, regression cooldown, etc.). |
| **`api/config/model_routing.json`** | Model selection (strong/fast tiers, task type → tier, fallback chains). Not “model A/B” in the sense of two fixed alternatives; fallback is sequential. |

### What’s implemented

- **Executor A/B**  
  - **Config:** `orchestrator_policy.json` → `executors.ab_candidate_priority`, `forced_challenger_priority`, and `ab` (target_challenger_pct, regression_cooldown_seconds, etc.).  
  - **Code:** `agent_service_executor` hashes a task fingerprint and assigns variant A or B, then picks an executor from a pair. Regression/quarantine and challenger % are applied from this config.

- **Prompt variant names (only)**  
  - **Config:** `orchestrator_policy.json` → `prompt_variants.control`, `prompt_variants.by_task_type` (e.g. spec → `spec_structure_v2`, impl → `patch_preservation_v2`).  
  - **Code:** `orchestrator_policy_service.prompt_variant_control()` and `prompt_variant_for_task(task_type)` return these **names**.  
  - **Gap:** Nothing in the codebase uses these names to choose **different prompt/direction text**. So we have variant labels for A/B, but no prompt templates keyed by variant and no A/B switch for prompt content.

- **Model selection**  
  - **Config:** `model_routing.json` (tiers, task_type_tier, fallback_chains).  
  - **Code:** Routing uses config for model and for fallback on rate-limit/quota. There is no separate “model A/B” (e.g. 50% model A, 50% model B) beyond that.

### What’s not implemented (spec 026 Phase 2)

- **Prompt A/B:** Store `context.prompt_variant` (or prompt ID) on the task and log it; **and** map variant → actual prompt template so different variants produce different direction text. Today only the variant **name** is in config; the **content** of each variant is not.
- **Aggregation by variant:** Success rate and duration by `prompt_variant` (and by model/executor) for comparison. Depends on storing and exporting variant on tasks and in metrics.

---

## Summary

| Question | Answer |
|----------|--------|
| Where are spec/impl/review prompts? | In **`api/config/prompt_templates.json`**. Loader: `prompt_templates_loader`; used by project_manager, agent_service_executor, flow_helpers, inventory_service, run_cli_task_flow_matrix. |
| Where is A/B config? | **Executor + prompt variant names + A/B params:** `api/config/orchestrator_policy.json`. **Model selection (no model A/B):** `api/config/model_routing.json`. **Prompts:** `api/config/prompt_templates.json`. |
| How is A/B done for models? | Model choice is from `model_routing.json` (tiers, fallback). There is no 50/50 model A/B; fallback is sequential on failure. |
| How is A/B done for prompts? | Variant **names** per task type are in `orchestrator_policy.json`; prompt **content** is in `prompt_templates.json`. No code yet maps variant name → alternate template for A/B; content is single template per use. |
