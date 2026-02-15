# Living-Codex-CSharp ROI Import (Top 10)

Source repository: `https://github.com/seeker71/Living-Codex-CSharp`  
Local reference path: `references/living-codex/`

## Selection Basis

- Priority queue and effort ranges in `references/living-codex/IMPLEMENTATION_STATUS.md`
- Capability and backend readiness in `references/living-codex/LIVING_CODEX_SPECIFICATION.md`
- Route/UI grounding in `references/living-codex/specs/LIVING_UI_SPEC.md`

## Imported Ideas

| Imported idea id | Source spec/status anchor | Estimated effort basis | Why high ROI |
|---|---|---|---|
| `living-codex-csharp-profile-edit-completion` | `IMPLEMENTATION_STATUS.md` (Profile Management, high priority) | 1-2 days | Low effort, unlocks complete user management flow |
| `living-codex-csharp-concept-creation-ui` | `IMPLEMENTATION_STATUS.md` (Concept Creation Flow, high priority) | 2-3 days | Directly enables user contribution pipeline |
| `living-codex-csharp-contribution-dashboard-ui` | `IMPLEMENTATION_STATUS.md` (Contribution dashboard, medium priority) | 2-3 days | Makes contribution value visible and trackable |
| `living-codex-csharp-enhanced-news-ui` | `IMPLEMENTATION_STATUS.md` (Enhanced News Experience) | 2-3 days | Better signal extraction for idea generation loops |
| `living-codex-csharp-graph-visualization-ui` | `IMPLEMENTATION_STATUS.md` + `LIVING_UI_SPEC.md` (`/graph`, `/nodes`) | 3-5 days | Exposes core "everything is a node" model |
| `living-codex-csharp-people-discovery-ui` | `IMPLEMENTATION_STATUS.md` (`/people`) + `LIVING_UI_SPEC.md` | 3-4 days | Improves contributor matching and collaboration |
| `living-codex-csharp-portal-management-ui` | `IMPLEMENTATION_STATUS.md` (`/portals`) + `LIVING_UI_SPEC.md` | 4-5 days | Enables external integration workflows |
| `living-codex-csharp-ucore-ontology-browser-ui` | `IMPLEMENTATION_STATUS.md` (`/ontology`) + `LIVING_UI_SPEC.md` | 3-4 days | Improves ontology navigation and precision |
| `living-codex-csharp-realtime-ui-completion` | `LIVING_CODEX_SPECIFICATION.md` (real-time features partial) | 3-5 days | Increases live collaboration and feedback speed |
| `living-codex-csharp-temporal-ui` | `IMPLEMENTATION_STATUS.md` (`/temporal`) | 4-5 days | Activates temporal capability already in backend |

## Where It Is Tracked

- Portfolio defaults: `api/app/services/idea_service.py`
- Validation test: `api/tests/test_ideas.py`
- Spec: `specs/061-import-living-codex-csharp-top-roi-ideas.md`
