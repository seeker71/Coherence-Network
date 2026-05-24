"""Tests for the substrate-surprise adjacency refinement.

The wellness organ surfaces shapes with unseen structural twins. Two
kinds of twinship coexist at the Blueprint level: template-twins
(same frontmatter schema across unrelated work) and semantic-adjacency
(same schema AND a shared semantic axis, like idea_id for specs).

These tests attest that:
  - `_spec_idea_id` reads idea_id from the spec frontmatter
  - `_adjacency_for_shape` returns shared idea_ids between touched and unseen
  - `format_for_wellness` marks adjacent clusters with ✦ and ranks them first
"""
from __future__ import annotations

import textwrap

from app.services.substrate.sense_surprise import (
    _adjacency_for_shape,
    _spec_idea_id,
    format_for_wellness,
)


SPEC_TPL = textwrap.dedent("""\
    ---
    idea_id: {idea_id}
    status: done
    source: api/x.py
    requirements: do X
    done_when: X is done
    test: pytest x
    ---
    Spec body.
    """)


def _write_spec(root, name, idea_id):
    specs_dir = root / "specs"
    specs_dir.mkdir(exist_ok=True)
    p = specs_dir / f"{name}.md"
    p.write_text(SPEC_TPL.format(idea_id=idea_id))
    return p


def test_spec_idea_id_reads_frontmatter(tmp_path):
    _write_spec(tmp_path, "asset-renderer-plugin", "value-attribution")
    assert _spec_idea_id("asset-renderer-plugin", tmp_path) == "value-attribution"


def test_spec_idea_id_missing_file_returns_none(tmp_path):
    assert _spec_idea_id("does-not-exist", tmp_path) is None


def test_spec_idea_id_ignores_body_mentions(tmp_path):
    # `idea_id:` inside the body, not the frontmatter, must not match.
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    p = specs_dir / "x.md"
    p.write_text(textwrap.dedent("""\
        ---
        idea_id: real-one
        ---

        Body text containing idea_id: fake-one inside prose.
        """))
    assert _spec_idea_id("x", tmp_path) == "real-one"


def test_adjacency_returns_shared_idea_id(tmp_path):
    # Two specs share idea_id → adjacent
    _write_spec(tmp_path, "asset-renderer-plugin", "value-attribution")
    _write_spec(tmp_path, "story-protocol-integration", "value-attribution")

    touched = [("spec", "asset-renderer-plugin")]
    unseen = [("spec", "story-protocol-integration")]
    shared = _adjacency_for_shape(touched, unseen, tmp_path)
    assert shared == ["value-attribution"]


def test_adjacency_empty_when_different_ideas(tmp_path):
    # Two specs on different ideas → template-twin only
    _write_spec(tmp_path, "identity-driven-onboarding-tofu", "identity-and-onboarding")
    _write_spec(tmp_path, "data-driven-timeout-resume", "pipeline-reliability")

    touched = [("spec", "identity-driven-onboarding-tofu")]
    unseen = [("spec", "data-driven-timeout-resume")]
    shared = _adjacency_for_shape(touched, unseen, tmp_path)
    assert shared == []


def test_adjacency_ignores_non_spec_domains(tmp_path):
    # The current implementation only resolves spec-domain adjacency
    touched = [("concept", "lc-foo")]
    unseen = [("concept", "lc-bar")]
    shared = _adjacency_for_shape(touched, unseen, tmp_path)
    assert shared == []


def test_format_marks_adjacent_clusters(tmp_path):
    # An adjacent cluster gets ✦; a template-only cluster does not.
    adjacent_rec = {
        "shape": (1, 8, 4, 2),
        "touched": [("spec", "asset-renderer-plugin")],
        "unseen": [("spec", "story-protocol-integration")],
        "adjacent_idea_ids": ["value-attribution"],
    }
    template_rec = {
        "shape": (1, 8, 4, 7),
        "touched": [("spec", "identity-driven-onboarding-tofu")],
        "unseen": [("spec", "data-driven-timeout-resume")],
        "adjacent_idea_ids": [],
    }
    lines = format_for_wellness(2, [adjacent_rec, template_rec])
    text = "\n".join(lines)

    # Summary names the adjacency count
    assert "1 ✦ adjacent" in text
    # Adjacent cluster gets ✦ + idea note
    assert "✦ shape @1.8.4.2 [idea: value-attribution]" in text
    # Template cluster has no ✦ and no idea note
    template_line = [
        ln for ln in lines if "@1.8.4.7" in ln
    ][0]
    assert "✦" not in template_line
    assert "[idea:" not in template_line


def test_format_ranks_adjacent_first(tmp_path):
    # The ranking in find_unseen_twins is what places adjacent clusters
    # first; format_for_wellness preserves that order. Verify the output
    # shows the adjacent cluster line ahead of the template-only line.
    adjacent_rec = {
        "shape": (1, 8, 4, 2),
        "touched": [("spec", "a")],
        "unseen": [("spec", "b")],
        "adjacent_idea_ids": ["shared"],
    }
    template_rec = {
        "shape": (1, 8, 4, 7),
        "touched": [("spec", "c")],
        "unseen": [("spec", "d")],
        "adjacent_idea_ids": [],
    }
    # When the records are passed in adjacent-first order, the output
    # mirrors that order — format_for_wellness does not re-sort.
    lines = format_for_wellness(2, [adjacent_rec, template_rec])
    adjacent_idx = next(i for i, ln in enumerate(lines) if "@1.8.4.2" in ln)
    template_idx = next(i for i, ln in enumerate(lines) if "@1.8.4.7" in ln)
    assert adjacent_idx < template_idx


def test_format_silent_when_no_touched(tmp_path):
    lines = format_for_wellness(0, [])
    assert any("no substrate-ingested paths touched" in ln for ln in lines)


def test_format_walked_message_when_no_twins(tmp_path):
    lines = format_for_wellness(5, [])
    assert any("walked 5 touched cell" in ln for ln in lines)
