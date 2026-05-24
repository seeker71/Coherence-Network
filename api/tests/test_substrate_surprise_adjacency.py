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
    DOMAIN_DEFAULT_THRESHOLD,
    _adjacency_for_shape,
    _spec_idea_id,
    format_for_wellness,
    is_domain_default_shape,
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


def _rec(shape, touched, unseen, adjacent, *, dominant_domain="spec",
         dominant_count=2, domain_default=False):
    """Build a shape-record dict with the post-PR-1946 fields."""
    return {
        "shape": shape,
        "touched": touched,
        "unseen": unseen,
        "adjacent_idea_ids": adjacent,
        "domain_default": domain_default,
        "dominant_domain": dominant_domain,
        "dominant_domain_count": dominant_count,
    }


def test_format_marks_adjacent_clusters(tmp_path):
    # An adjacent cluster gets ✦; a template-only cluster does not.
    adjacent_rec = _rec(
        (1, 8, 4, 2),
        [("spec", "asset-renderer-plugin")],
        [("spec", "story-protocol-integration")],
        ["value-attribution"],
    )
    template_rec = _rec(
        (1, 8, 4, 7),
        [("spec", "identity-driven-onboarding-tofu")],
        [("spec", "data-driven-timeout-resume")],
        [],
    )
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
    adjacent_rec = _rec(
        (1, 8, 4, 2),
        [("spec", "a")],
        [("spec", "b")],
        ["shared"],
    )
    template_rec = _rec(
        (1, 8, 4, 7),
        [("spec", "c")],
        [("spec", "d")],
        [],
    )
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


# ---- Domain-default cluster filter (PR #1946 learning) ------------------

def test_is_domain_default_above_threshold():
    # Threshold is 50 today; PR #1946 saw clusters of 52, 66, 76.
    assert is_domain_default_shape(DOMAIN_DEFAULT_THRESHOLD + 1) is True
    assert is_domain_default_shape(76) is True
    assert is_domain_default_shape(66) is True


def test_is_domain_default_at_or_below_threshold():
    # At the threshold the shape is borderline — the filter treats it
    # as still actionable (>, not >=). Tiny clusters are obviously
    # actionable targeted pairs.
    assert is_domain_default_shape(DOMAIN_DEFAULT_THRESHOLD) is False
    assert is_domain_default_shape(10) is False
    assert is_domain_default_shape(2) is False


def test_format_separates_domain_default_clusters():
    # A targeted pair and a domain-default cluster: the targeted pair
    # leads the report; the default cluster lands in its own sub-section
    # explicitly labeled so a fresh cell can tell shoulder-tap from
    # background lattice resonance.
    targeted_rec = _rec(
        (1, 8, 4, 2),
        [("spec", "asset-renderer-plugin")],
        [("spec", "story-protocol-integration")],
        ["value-attribution"],
        dominant_count=2,
        domain_default=False,
    )
    default_rec = _rec(
        (1, 8, 4, 1),
        [("spec", "agent-pipeline")],
        [("spec", f"sibling-{i}") for i in range(65)],
        [],
        dominant_count=66,
        domain_default=True,
    )
    lines = format_for_wellness(2, [targeted_rec, default_rec])
    text = "\n".join(lines)

    # Targeted summary names targeted-only count, not the combined total.
    assert "1 shape(s) carry unseen twins worth a look" in text
    # Domain-default sub-section is labeled clearly.
    assert "domain-default cluster" in text
    # Threshold is named so the reader can recalibrate the guess.
    assert f">{DOMAIN_DEFAULT_THRESHOLD}/domain" in text
    # The default cluster's dominant domain + count surfaces in its line.
    assert "@spec carries 66 cells" in text
    # And the default line lands AFTER the targeted line.
    targeted_idx = next(i for i, ln in enumerate(lines) if "@1.8.4.2" in ln)
    default_idx = next(i for i, ln in enumerate(lines) if "@1.8.4.1" in ln)
    assert targeted_idx < default_idx


def test_format_only_domain_default_clusters():
    # When every reported shape is a default cluster, the targeted
    # section reports honest absence and the default section follows.
    default_rec = _rec(
        (1, 5, 4, 6),
        [("concept", "lc-space")],
        [("concept", f"lc-other-{i}") for i in range(75)],
        [],
        dominant_domain="concept",
        dominant_count=76,
        domain_default=True,
    )
    lines = format_for_wellness(1, [default_rec])
    text = "\n".join(lines)

    assert "no targeted unseen twins" in text
    assert "domain-default cluster" in text
    assert "@concept carries 76 cells" in text
