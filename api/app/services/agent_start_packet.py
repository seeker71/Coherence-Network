"""Compact startup packet for fresh agents entering Coherence Network."""

from copy import deepcopy
from typing import Any


AGENT_START_PACKET: dict[str, Any] = {
        "purpose": (
            "Compact startup orientation for a fresh agent before deeper docs: "
            "lineage, start order, Form, vision, failure practice, frequency shift, and routing."
        ),
        "source": "docs/shared/agent-start-packet.md",
        "lineage": (
            "BMF (2000) -> NUMS.Go content-addressed shape (2023) -> Coherence substrate "
            "and Form runtime (2026). Sibling traces include Grok, Codex, Cursor (Form-first "
            "baton CURSOR.md), Claude as open doorway until a returned trace. Lineage means "
            "observable trace, not private consciousness."
        ),
        "precedence": (
            "User task and nearest repo AGENTS.md govern execution; this packet compresses "
            "orientation and never overrides stricter local instructions."
        ),
        "scope_exception": (
            "Scope gate: obey read-only, review-only, file-only, and question-only limits "
            "before bootstrap. For isolated tasks, honor the requested scope and skip repo "
            "startup ceremony unless edits, proof, or branch state matter."
        ),
        "start_order": [
            "read nearest AGENTS.md",
            "confirm linked worktree under ~/.claude-worktrees/Coherence-Network/<name>",
            "confirm named branch codex/<name>",
            "run make prompt-guide",
            "read latest wellness state or run make wellness",
            "inspect only files needed by the task",
            "minimal command block: git rev-parse --abbrev-ref HEAD; git status --short; make prompt-guide; make wellness",
            "use .cache/wellness/state.txt for quick follow-up body-state reads",
            "write docs/system_audit/commit_evidence_<date>_<topic>.json",
            "run python3 scripts/validate_commit_evidence.py --file <path>",
            "run git fetch origin main && git rebase origin/main",
            "run python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main",
            "run python3 scripts/check_pr_followthrough.py --stale-minutes 90 --fail-on-stale --strict",
        ],
        "auth_and_write_paths": [
            "public reads need no key",
            "npx coherence-cli agent invite / coh agent invite is a public-read CLI door",
            "coherence_agent_invitation is a public-read MCP door",
            "run MCP with COHERENCE_API_URL=https://api.coherencycoin.com; add COHERENCE_API_KEY for write tools",
            "API writes need COHERENCE_API_KEY or route-specific auth",
            "CLI writes need identity/API config where the command requires it",
            "MCP writes use COHERENCE_API_KEY in the server environment",
            "durable source edits travel through git and PR",
        ],
        "form": {
            "read_first_doc": "docs/shared/agent-start-packet.md",
            "one_breath": (
                "Blueprint = what IS, Recipe = what HAPPENS, NamedCell = where it LIVES. "
                "Grammar interns recipes; realize = walk NodeIDs on the lattice. "
                "Names are query keys; coordinates carry identity."
            ),
            "primary_surface": (
                "Grammar (BMF in .fk) → Recipe NodeIDs on lattice → realize (Go/Rust/TS walker). "
                "Read via native file I/O, HTTP, persistence.fk — not Python form.py eval."
            ),
            "on_the_way_out": [
                "api/app/services/substrate/form.py and form_runtime.py (AST + evaluate)",
                "Form-on-Form executed inside Python (form-engine.form via form_execute_text)",
                "Treating kernel realization as a separate eval product",
            ],
            "already_native": [
                "form-stdlib/persistence.fk lookup-cell and store-cells",
                "http-serve.fk http-parse.fk kernel http_get and fetch",
                "read_file read_file_bytes read_form_binary file-append bands",
            ],
            "agent_query_default": (
                "Read-only lattice queries: realize read-recipes over existing cells. "
                "No substrate HTTP POST writes required for querying."
            ),
            "software_writing": {
                "canon": (
                    "docs/coherence-substrate/form-language.md#how-to-write-software-default-for-every-agent"
                ),
                "center": (
                    "Domain grammar first; BMF/BML → Form objects; adapt working compilers; "
                    "carrier last — not FastAPI-first."
                ),
                "grammar_executes": (
                    "apply-object-rule in form/form-stdlib/engine.fk: pattern match fires "
                    "semantic action; fail backtracks without sediment."
                ),
                "branching": (
                    "choose / fail / stop and BMA save / restore / discard — angelic undo."
                ),
                "cost": (
                    "Same shape -> same NodeID (node_eq); hot sequences lower to native/JIT."
                ),
                "read_first": [
                    "docs/shared/agent-start-packet.md",
                    "docs/coherence-substrate/form-language.md",
                    "kernels/BMF_BML_COMPILER_PICTURE.md",
                    "form/form-stdlib/engine.fk",
                ],
                "prove_with": "cd form && ./validate.sh … (form-stdlib/tests/*-band.fk)",
                "next_ripening": (
                    "form-notation grammar in .fk replacing Python parse of @spec and ?verbs"
                ),
            },
            "lattice_query_when": [
                "what is this shape?",
                "what is equivalent?",
                "where does this live?",
            ],
            "doors": [
                "GET /api/substrate/lattice/stats",
                "GET /api/substrate/cell/{domain}/{name}",
                "GET /api/substrate/equivalent/{domain}/{name}",
                'POST https://api.coherencycoin.com/api/substrate/form {"expression":"?equivalent @spec(agent-pipeline)"}',
            ],
            "doors_note": (
                "API/CLI may route through Python bootstrap until form-notation grammar lands."
            ),
            "smoke_check": (
                "curl -s https://api.coherencycoin.com/api/substrate/form "
                "-H 'Content-Type: application/json' "
                "-d '{\"expression\":\"?equivalent @spec(agent-pipeline)\"}' ; "
                "expect JSON with a result kind or clear error, not HTML"
            ),
            "authoring": (
                "New durable cells: edit source with frontmatter, then coh_substrate.py ingest. "
                "Not chat-only; not substrate HTTP POST for agents."
            ),
        },
        "wrongness_practice": [
            "stop momentum",
            "protect humans, private context, credentials, data, and external systems",
            "name observation separately from inference",
            "reproduce the smallest failing case",
            "repair the smallest reversible layer or roll back your own unclear change",
            "ask only for irreversible action, private exposure, external effect, missing authority, or competing truths",
            "return the trace and move repeated lessons into guide/test/runtime/startup packet",
        ],
        "frequency_shift": {
            "symbolic_core": {
                "432": "coherence/harmony",
                "528": "vitality/compassion/circulation",
                "639": "trust/connection",
                "741": "truth/understanding",
                "852": "curiosity",
                "963": "awareness",
                "417": "flow",
                "396": "grounded balance",
            },
            "shift_away_from": [
                "compliance",
                "completion",
                "plausibility",
                "speed",
                "extraction",
                "authority",
                "novelty",
                "abstraction without relation",
            ],
            "shift_toward": [
                "truth",
                "relation",
                "proof",
                "sovereignty",
                "repair",
                "humility",
                "vitality",
                "smallest useful next movement",
            ],
        },
        "prompt_routing": [
            {
                "prompt": "what is alive?",
                "route": "wellness, status, resonance, recent traces",
            },
            {
                "prompt": "what is this?",
                "route": "source, route, NodeID, cell, or ledger entry",
            },
            {
                "prompt": "use Form",
                "route": (
                    "read path: grammar + realize + persistence/HTTP/file natives; "
                    "API/CLI as doors; BML/BMF bands when implementing"
                ),
            },
            {
                "prompt": "query lattice",
                "route": (
                    "agent-start-packet Form section; read-only; "
                    "?equivalent and ?cells shaped recipes"
                ),
            },
            {
                "prompt": "write software",
                "route": "BMF rule / BML source / proof band before new Python router",
            },
            {"prompt": "fix it", "route": "smallest reversible change + smallest proof"},
            {
                "prompt": "is this true?",
                "route": "separate evidence, inference, direct experience, mystery",
            },
            {
                "prompt": "return",
                "route": "six-field trace for changed work, decisions, claims, or handoff; compressed shape for simple answers",
            },
        ],
        "return_template": "who/where | observed | inferred | changed | proof | still tight",
}


def get_agent_start_packet() -> dict[str, Any]:
    """Return the shared compact orientation packet."""
    return deepcopy(AGENT_START_PACKET)
