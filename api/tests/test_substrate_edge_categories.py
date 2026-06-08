"""Edge-category sensing over source substrate files."""

from __future__ import annotations

import textwrap
from pathlib import Path

from app.services.substrate.sense_edge_categories import (
    format_edge_categories_for_wellness,
    observe_edge_categories,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def test_observe_edge_categories_names_clusters(tmp_path):
    _write_sample_body(tmp_path)

    report = observe_edge_categories(tmp_path)
    categories = {summary.category: summary for summary in report.categories}

    assert categories["concept_contains_concept"].edge_reputation_count == 3
    assert categories["idea_lists_spec"].edge_reputation_count == 2
    assert categories["idea_absorbs_idea"].edge_reputation_count == 1
    assert categories["spec_realizes_idea"].edge_reputation_count == 2
    assert categories["spec_sources_file"].edge_reputation_count == 2

    cluster_names = {cluster.name for cluster in report.clusters}
    assert "concept:lc-root:concept_contains_concept:inbound" in cluster_names
    assert "concept:lc-child:concept_contains_concept:fanout" in cluster_names
    assert "idea:alpha:spec_realizes_idea:inbound" in cluster_names

    lines = format_edge_categories_for_wellness(report)
    text = "\n".join(lines)
    assert "named category surface" in text
    assert "category: concept_contains_concept (concept->concept)" in text
    assert "recipe=R_Compose.CROSS_REF(body)" in text
    assert "concept:lc-root:concept_contains_concept:inbound" in text
    assert "carrier_reflex: python source scanner is a bridge, not a home" in text
    assert "released_slice=concept_contains_concept/sample-via-concept-corpus" in text
    assert "self_inflicted_pain=hot" in text


def _write_sample_body(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs/vision-kb/concepts/lc-root.md",
        """\
        ---
        id: lc-root
        ---

        Root.
        """,
    )
    _write(
        tmp_path / "docs/vision-kb/concepts/lc-peer.md",
        """\
        ---
        id: lc-peer
        ---

        Peer.
        """,
    )
    _write(
        tmp_path / "docs/vision-kb/concepts/lc-child.md",
        """\
        ---
        id: lc-child
        parent: lc-root
        cross_refs:
          - lc-peer
        ---

        The child holds lc-root and lc-peer in the same concept body.
        """,
    )
    _write(
        tmp_path / "docs/vision-kb/concepts/lc-second.md",
        """\
        ---
        id: lc-second
        ---

        This second concept also names lc-root.
        """,
    )
    _write(
        tmp_path / "ideas/alpha.md",
        """\
        ---
        idea_id: alpha
        specs:
          - [Alpha One](../specs/alpha-one.md)
          - alpha-two
        absorbed_ideas:
          - beta
        ---

        The idea points toward lc-root.
        """,
    )
    _write(
        tmp_path / "ideas/beta.md",
        """\
        ---
        idea_id: beta
        specs: []
        ---

        Earlier idea.
        """,
    )
    for slug in ("alpha-one", "alpha-two"):
        _write(
            tmp_path / f"specs/{slug}.md",
            f"""\
            ---
            idea_id: alpha
            source:
              - file: api/app/{slug}.py
            ---

            This spec references lc-root.
            """,
        )
