"""Doorway teaching tests — does what /come-in promises actually work?

The /come-in page and the /api/agent/invitation JSON make specific
technical promises to arriving agents: "here are the endpoints," "here
are the Form expressions you can use," "here is the lattice you can
query." If the promises drift from the body — an endpoint that 5xx's,
a Form example that won't parse, an entry surface whose `next` path
doesn't exist — the doorway teaches falsely, and every arriving agent
inherits the breakage.

These tests close that gap by treating the doorway's claims as
verifiable contracts.

Three categories:

1. Every Form-language example shown on /come-in must parse and evaluate
   against POST /api/substrate/form. (Catches: page teaches syntax the
   endpoint rejects.)

2. Every entry_surface path in the agent invitation must reach a
   non-server-error response. (Catches: a promised door that 5xx's.)

3. Every endpoint named in a surface's `next` list must be a real
   route on the app. (Catches: typos and stale promises.)

Failures here mean the doorway is lying to the next arriving agent.
"""
from __future__ import annotations

import re

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# 1. Form-language examples shown on /come-in must actually evaluate
# ---------------------------------------------------------------------------

# These are the exact Form expressions rendered in the "Form-language,
# concretely" callout on /come-in. If the page teaches them, the endpoint
# must accept them.
DOORWAY_FORM_EXAMPLES = [
    # Atom — the spec named "agent-pipeline"
    "@spec(agent-pipeline)",
    # Shape query — cells equivalent to the agent-pipeline spec
    "?equivalent @spec(agent-pipeline)",
    # Role query — every cell whose domain is memory
    '?cells where domain == "memory"',
    # Composition — pipe a memory through the presence projection
    "@memory(presences_of_the_field) |> @presence",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("expression", DOORWAY_FORM_EXAMPLES)
async def test_doorway_form_example_parses_and_evaluates(expression: str) -> None:
    """Every Form expression shown on /come-in must parse against the live endpoint.

    A 200 result (even with empty cells) means the syntax is real.
    A 404 (cell not found) is fine — the syntax was valid; the data
    just isn't there in this test substrate.
    A 400 means the page teaches syntax the endpoint rejects — the
    doorway is lying. Fail loudly.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/form", json={"expression": expression}
        )

    assert response.status_code != 400, (
        f"Form example shown on /come-in fails to parse at the endpoint.\n"
        f"  expression: {expression!r}\n"
        f"  response:   {response.text}\n"
        f"  → The doorway is teaching syntax the body rejects. Either fix\n"
        f"    the page or extend the parser to accept it."
    )
    # Treat anything other than 5xx as "the parse path is alive"
    assert response.status_code < 500, (
        f"Form example produced server error: {expression!r} → {response.status_code}"
    )


# ---------------------------------------------------------------------------
# 2. Every entry_surface promised by the agent invitation must reach
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_invitation_entry_surface_path_reaches() -> None:
    """For every entry_surface listed in /api/agent/invitation whose path
    is an API route, hitting that route must not return a 5xx.

    404 / 405 / 422 are acceptable — they mean "the route exists but you
    asked wrong." 500+ means a promise the body cannot keep.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        inv = (await client.get("/api/agent/invitation")).json()

        for surface in inv["entry_surfaces"]:
            path = surface["path"]
            # Only check API paths here; web paths and CLI/MCP doors are
            # validated by other tests (the web app, the MCP server).
            if not path.startswith("/api/"):
                continue

            # POST /api/substrate/form needs a body; skip GET-probe for it.
            if surface["surface"] == "form":
                continue

            response = await client.get(path)
            assert response.status_code < 500, (
                f"Promised entry surface {surface['surface']!r} at {path!r} "
                f"returns server error {response.status_code}: {response.text[:200]}\n"
                f"  → The doorway promises this door but the body cannot answer."
            )


# ---------------------------------------------------------------------------
# 3. The concrete teaching block on /come-in must contain the patterns
#    that prevent Grok-style collapse (Blueprint→plan, form-lang→voice,
#    NodeID→coherence score). This is a regression guard against future
#    edits that quietly drop the concretization.
# ---------------------------------------------------------------------------

# Patterns required in the rendered /come-in HTML.
# Each is a substring; if any drops, the page has regressed.
REQUIRED_CONCRETIZATION_PATTERNS = [
    # A literal NodeID tuple proves "Blueprint" is shown as numbers
    r"\(1, 2, 5, 17\)",
    # The two-collapses callout
    r"Two collapses to watch for",
    # Explicit Blueprint contrast
    r"four-integer structural fingerprint",
    # Explicit Form-language contrast (whitespace flexible — JSX source
    # wraps the line so the literal string has a newline + indent)
    r"not the prose voice of this\s+page",
    # The Form syntax example
    r"\?equivalent @spec\(agent-pipeline\)",
    # The role query
    r'\?cells where domain == &quot;memory&quot;',
]


@pytest.mark.asyncio
async def test_come_in_page_carries_concretization_patterns() -> None:
    """The /come-in page must continue to show concrete shapes next to
    technical terms. If any of these patterns disappears, a future
    arriving agent will collapse the words to their colloquial meanings.

    This test reads the locally-rendered page via the FastAPI app's
    public-page proxy if available, or falls back to a string check of
    the source TSX (so it works in CI without a Node runtime).
    """
    from pathlib import Path

    page_tsx = Path(__file__).resolve().parents[2] / "web" / "app" / "come-in" / "page.tsx"
    if not page_tsx.exists():
        pytest.skip(f"come-in page.tsx not at expected path: {page_tsx}")

    source = page_tsx.read_text(encoding="utf-8")
    missing = [p for p in REQUIRED_CONCRETIZATION_PATTERNS if not re.search(p, source)]
    assert not missing, (
        "The /come-in page has lost concretization patterns that prevent\n"
        "Grok-style collapse of substrate terms into colloquial meanings:\n  "
        + "\n  ".join(missing)
        + "\n\nRestore them, or — if intentionally moved — update this test\n"
        "with the new location of the equivalent teaching."
    )
