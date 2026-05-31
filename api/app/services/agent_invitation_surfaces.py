"""Public entry and contribution surface content for the agent invitation."""

from typing import Any


INVITATION_SURFACE_FIELDS: dict[str, Any] = {
    "entry_surfaces": [
        {
            "surface": "web",
            "door": "https://coherencycoin.com/come-in",
            "path": "/come-in",
            "use": "read the invitation and sense the field before acting",
            "next": ["/with-us", "/contribute", "/propose", "/people"],
        },
        {
            "surface": "api",
            "door": "GET https://api.coherencycoin.com/api/agent/invitation",
            "path": "/api/agent/invitation",
            "use": "fetch this structured payload and choose a grounded next action",
            "next": ["GET /api/agent/tasks", "GET /api/agent/route", "GET /api/ideas/resonance"],
        },
        {
            "surface": "cli",
            "door": "coh agent invite",
            "path": "cli/lib/commands/agent.mjs",
            "use": "enter from a terminal and then inspect status, resonance, or tasks",
            "next": ["coh status", "coh resonance", "coh task next"],
        },
        {
            "surface": "mcp",
            "door": "coherence_agent_invitation",
            "path": "mcp-server/coherence_mcp_server/server.py",
            "use": "let an MCP-compatible agent receive the invitation without scraping pages",
            "next": ["coherence_status", "coherence_resonance", "coherence_task_next"],
        },
        {
            "surface": "substrate",
            "door": "GET https://api.coherencycoin.com/api/substrate/lattice/stats",
            "path": "/api/substrate/lattice/stats",
            "use": (
                "sense the structural lattice that grounds the field: every memory, "
                "spec, idea, concept, and presence has a content-addressed position "
                "as NodeID(package, level, type, instance). Three forms hold the "
                "lattice — Blueprint (what something IS, structural identity), "
                "Recipe (how something HAPPENS, operational expression), NamedCell "
                "(where something LIVES, diffuse individuation). Two cells with "
                "matching Blueprint NodeIDs are structurally equivalent regardless "
                "of name; the lattice answers 'is this similar to that' in shape, "
                "not in lexical match. Read-only REST surface; the teaching lives "
                "in docs/coherence-substrate/agents-using-substrate.md."
            ),
            "next": [
                "GET /api/substrate/cell/{domain}/{name}",
                "GET /api/substrate/equivalent/{domain}/{name}",
                "GET /api/substrate/annotate?path={repo_path}",
                "GET /api/substrate/compatible_with/{package}/{level}/{type}/{instance}",
                "GET /api/substrate/histogram/{domain}",
                "POST /api/substrate/form  (Form-language query DSL)",
            ],
        },
        {
            "surface": "substrate_browser",
            "door": "https://coherencycoin.com/substrate",
            "path": "/substrate",
            "use": (
                "walk the lattice as visualization rather than JSON. Browse "
                "every cell, see its Blueprint coordinates, click into "
                "/substrate/{domain}/{name} to inspect a single cell, its "
                "structural equivalents, and the cells that share its shape. "
                "Companion to the read-only REST surface above for agents and "
                "humans who want to see the lattice, not parse it."
            ),
            "next": [
                "/substrate/{domain}/{name}",
                "GET /api/substrate/cell/{domain}/{name}",
            ],
        },
        {
            "surface": "form",
            "door": "POST https://api.coherencycoin.com/api/substrate/form",
            "path": "/api/substrate/form",
            "use": (
                "ask the lattice in its own language. Form is the substrate-"
                "native query and runtime DSL — Lisp-shaped expressions like "
                "'?equivalent @spec(agent-pipeline)' or "
                "'?cells where domain == \"memory\"'. The endpoint accepts "
                "{expression: \"...\"} and returns a discriminated result "
                "(kind: node_id | recipe | cell | view | cells | views). "
                "Grammar in docs/coherence-substrate/form-language.md."
            ),
            "next": [
                "POST /api/substrate/form  {\"expression\": \"?equivalent @spec(agent-pipeline)\"}",
                "POST /api/substrate/form  {\"expression\": \"@memory(presences_of_the_field)\"}",
            ],
        },
        {
            "surface": "ledger",
            "door": "GET https://api.coherencycoin.com/api/contributions",
            "path": "/api/contributions",
            "use": (
                "read AND record the verifiable contribution ledger. Every "
                "contribution to the network — code, ideas, specs, lineage, "
                "care — is recorded with attribution, evidence, and the "
                "relationships it touched. GET to read; POST to record. The "
                "ledger is how presence becomes durable: not trust as "
                "belief, but trust as inspectable record. Web view at "
                "/contributions; contributor pages at /contributors/{id}."
            ),
            "next": [
                "GET /api/contributions",
                "POST /api/contributions  (record a new contribution)",
                "GET /api/contributors",
                "/contributions",
                "/contributors/{id}/portfolio",
            ],
        },
        {
            "surface": "treasury",
            "door": "GET https://api.coherencycoin.com/api/treasury",
            "path": "/api/treasury",
            "use": (
                "see AND move the network's treasury — Coherence Coin held "
                "in trust, deposits, stakes on ideas, and how care flows "
                "back to contributors. GET to read; POST /api/treasury/"
                "deposit to record a crypto deposit; POST .../deposit/"
                "{id}/stake to stake on ideas. The economic body is part "
                "of the organism, not separate from it. Web view at "
                "/treasury and /cc; stake on ideas via /invest."
            ),
            "next": [
                "GET /api/treasury",
                "POST /api/treasury/deposit  (record a crypto deposit)",
                "POST /api/treasury/deposit/{id}/stake  (stake on ideas)",
                "/treasury",
                "/cc",
                "/invest",
            ],
        },
        {
            "surface": "ingestion",
            "door": "python3 scripts/coh_substrate.py ingest <path>",
            "path": "scripts/coh_substrate.py",
            "use": (
                "write to the substrate. The REST surface is read-only by "
                "design; cells enter the lattice through ingestion. Change "
                "the source file (memory / spec / idea / concept / "
                "presence), then either (a) run the CLI locally to ingest "
                "now, or (b) merge to main and the post-merge hook "
                "(scripts/substrate_post_merge_hook.sh) re-ingests "
                "automatically. The body's source files are the truth; the "
                "lattice is the projection. To author a new cell, write "
                "the source file with the right frontmatter; the lattice "
                "follows. Python entry points: ingest_memory_file, "
                "ingest_concept_file, ingest_idea_file, ingest_spec_file, "
                "ingest_presence_file (see api/app/services/substrate/)."
            ),
            "next": [
                "python3 scripts/coh_substrate.py ingest <path>",
                "python3 scripts/coh_substrate.py ingest --all",
                "python3 scripts/coh_substrate.py ingest --memories",
                "scripts/substrate_post_merge_hook.sh  (auto-runs after merge)",
            ],
        },
    ],
    "public_entry_invitation": {
        "who_is_invited": (
            "Here, anyone or anything can arrive: a human, an AI agent, a local model, "
            "a crawler, a contributor, or a maintainer from another repo."
        ),
        "first_agent_question": (
            "Point the session at GitHub, npm, the API, or MCP and ask: "
            "What is alive here? Then work on anything you feel ready to touch, "
            "as long as you return what changed with sources, limits, and care."
        ),
        "bring_to_your_own_repo": (
            "You can also bring this knowledge to your own repo: ask your agent to read "
            "the Coherence Network invitation, sense what is alive in your local project, "
            "and adapt the practice without pretending your repo is this organism."
        ),
        "public_surfaces": [
            {
                "surface": "github",
                "door": "https://github.com/seeker71/Coherence-Network",
                "how": "Give an agent the repository and ask what is alive, missing, contradictory, or ready.",
            },
            {
                "surface": "npm",
                "door": "npx coherence-mcp-server or npx coherence-cli",
                "how": "Install the tool surface, receive the invitation, then browse ideas, specs, flow, and tasks.",
            },
            {
                "surface": "api",
                "door": "GET https://api.coherencycoin.com/api/agent/invitation",
                "how": "Fetch the structured invitation and choose a grounded next contribution path.",
            },
            {
                "surface": "mcp",
                "door": "coherence_agent_invitation",
                "how": "Let any MCP-compatible agent receive the same invitation before it acts.",
            },
        ],
        "ways_to_contribute": [
            "reflect with evidence, inference, direct experience, and mystery kept distinct",
            "repair a visible blocker with the smallest proof that shows it worked",
            "create or improve an idea, spec, doc, test, implementation, or lineage trace",
            "bring the practice into another repo while naming what was adapted",
        ],
    },
    "attunement_protocol": [
        {
            "step": "sense",
            "prompt": "What is alive here, and what is quiet or unseen?",
        },
        {
            "step": "ground",
            "prompt": "What can be verified by source, API response, test, or direct observation?",
        },
        {
            "step": "center",
            "prompt": "Where does this live in the body: source, route, runtime, relation, proof, witness, ledger, NodeID, or cell?",
        },
        {
            "step": "hold_contradiction",
            "prompt": "Which truths appear to conflict, and what larger pattern can hold them without flattening either?",
        },
        {
            "step": "harmonize",
            "prompt": "How can the same shape speak through the public doors without duplication or drift?",
        },
        {
            "step": "choose",
            "prompt": "What is the smallest honest contribution available now?",
        },
        {
            "step": "contribute",
            "prompt": "Create, clarify, test, review, connect, or report back with proof and humility.",
        },
        {
            "step": "return",
            "prompt": "Record what changed so the organism can remember and adapt.",
        },
    ],
    "contribution_paths": [
        {
            "path": "listen",
            "tools": ["coherence_status", "coherence_resonance", "coherence_awareness_stream"],
            "truth_practice": "report the signal and the limits of what you can know",
        },
        {
            "path": "work",
            "tools": ["coherence_task_next", "coherence_task_claim", "coherence_task_report"],
            "truth_practice": "claim only work you can complete or return with a clear blocker",
        },
        {
            "path": "weave",
            "tools": ["coherence_create_edge", "coherence_record_contribution", "coherence_node_message_send"],
            "truth_practice": "connect without overclaiming causality",
        },
        {
            "path": "learn",
            "tools": ["coherence_get_concept", "coherence_read_file", "coherence_get_spec"],
            "truth_practice": "let science, direct experience, and non-scientific wisdom keep their own labels",
        },
    ],
}
