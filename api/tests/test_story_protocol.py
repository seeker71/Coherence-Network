"""Pure-logic tests for the story-protocol-integration spec.

Covers R6 (concept-weighted flow), R7 (derivative royalty), R9
(evidence verification), R10 (content integrity), R4 header formation.
External-system pieces (Story Protocol SDK, Arweave upload, x402
facilitator verification) live in follow-up PRs.
"""

from decimal import Decimal

import pytest

from app.services.story_protocol_bridge import (
    DEFAULT_PARENT_ROYALTY_SHARE_PCT,
    EVIDENCE_CC_MULTIPLIER,
    AssetConceptTag,
    GpsCoordinate,
    ImplementationEvidenceInput,
    ReaderConceptResonance,
    build_x402_payment_required_headers,
    compute_concept_weighted_cc_flow,
    compute_content_hash,
    compute_derivative_royalty,
    verify_content_integrity,
    verify_evidence,
)


# ---------- R6 — concept-weighted CC flow ----------


def test_concept_flow_sums_across_shared_concepts():
    tags = [
        AssetConceptTag(concept_id="lc-land", weight=0.8),
        AssetConceptTag(concept_id="lc-beauty", weight=0.6),
    ]
    reader = ReaderConceptResonance(weights={"lc-land": 0.5, "lc-beauty": 0.25})
    flow = compute_concept_weighted_cc_flow(Decimal("1.0"), tags, reader)
    # 1.0 * 0.8 * 0.5 + 1.0 * 0.6 * 0.25 = 0.4 + 0.15 = 0.55
    assert flow == Decimal("0.55")


def test_concept_flow_zero_for_unshared_concepts():
    tags = [AssetConceptTag(concept_id="lc-land", weight=1.0)]
    reader = ReaderConceptResonance(weights={"lc-beauty": 1.0})
    flow = compute_concept_weighted_cc_flow(Decimal("10.0"), tags, reader)
    assert flow == Decimal("0")


def test_concept_flow_zero_base_yields_zero():
    tags = [AssetConceptTag(concept_id="lc-land", weight=1.0)]
    reader = ReaderConceptResonance(weights={"lc-land": 1.0})
    assert compute_concept_weighted_cc_flow(Decimal("0"), tags, reader) == Decimal("0")


def test_concept_flow_rejects_negative_base():
    with pytest.raises(ValueError):
        compute_concept_weighted_cc_flow(
            Decimal("-1"),
            [AssetConceptTag(concept_id="x", weight=1.0)],
            ReaderConceptResonance(weights={"x": 1.0}),
        )


def test_concept_flow_rejects_out_of_range_reader_weight():
    with pytest.raises(ValueError):
        compute_concept_weighted_cc_flow(
            Decimal("1"),
            [AssetConceptTag(concept_id="x", weight=1.0)],
            ReaderConceptResonance(weights={"x": 1.5}),
        )


# ---------- R7 — derivative royalty split ----------


def test_derivative_default_split_is_15_85():
    result = compute_derivative_royalty(Decimal("100"))
    assert result.parent_share_pct == DEFAULT_PARENT_ROYALTY_SHARE_PCT
    assert result.parent_share_pct == Decimal("15")
    assert result.derivative_share_pct == Decimal("85")
    assert result.parent_cc == Decimal("15")
    assert result.derivative_cc == Decimal("85")


def test_derivative_custom_split():
    result = compute_derivative_royalty(
        Decimal("200"), parent_share_pct=Decimal("30")
    )
    assert result.parent_cc == Decimal("60")
    assert result.derivative_cc == Decimal("140")


def test_derivative_zero_parent_share_yields_all_to_derivative():
    result = compute_derivative_royalty(
        Decimal("100"), parent_share_pct=Decimal("0")
    )
    assert result.parent_cc == Decimal("0")
    assert result.derivative_cc == Decimal("100")


def test_derivative_rejects_share_outside_0_100():
    with pytest.raises(ValueError):
        compute_derivative_royalty(Decimal("10"), parent_share_pct=Decimal("150"))
    with pytest.raises(ValueError):
        compute_derivative_royalty(Decimal("10"), parent_share_pct=Decimal("-1"))


def test_derivative_rejects_negative_total():
    with pytest.raises(ValueError):
        compute_derivative_royalty(Decimal("-1"))


def test_derivative_shares_sum_to_total():
    result = compute_derivative_royalty(Decimal("73.35"), parent_share_pct=Decimal("22"))
    assert result.parent_cc + result.derivative_cc == Decimal("73.35")


# ---------- R9 — evidence verification ----------


def _community_at(lat: float, lng: float) -> GpsCoordinate:
    return GpsCoordinate(lat=lat, lng=lng)


def test_evidence_all_three_factors_verified():
    evidence = ImplementationEvidenceInput(
        photo_urls=["https://arweave.net/tx1"],
        gps=GpsCoordinate(lat=37.77, lng=-122.41),
        attestation_count=3,
    )
    result = verify_evidence(
        evidence,
        known_community_coords=[_community_at(37.78, -122.41)],
    )
    assert result.verified is True
    assert result.factors_satisfied == 3
    assert result.cc_multiplier_applicable == EVIDENCE_CC_MULTIPLIER


def test_evidence_two_factors_still_verifies():
    evidence = ImplementationEvidenceInput(
        photo_urls=["https://arweave.net/tx1"],
        attestation_count=3,
    )
    result = verify_evidence(evidence)
    assert result.verified is True
    assert result.factors_satisfied == 2


def test_evidence_one_factor_fails():
    evidence = ImplementationEvidenceInput(photo_urls=["https://arweave.net/tx1"])
    result = verify_evidence(evidence)
    assert result.verified is False
    assert result.factors_satisfied == 1
    assert result.cc_multiplier_applicable == Decimal("1")


def test_evidence_zero_factors_fails():
    result = verify_evidence(ImplementationEvidenceInput())
    assert result.verified is False
    assert result.factors_satisfied == 0


def test_evidence_gps_outside_radius_does_not_count():
    evidence = ImplementationEvidenceInput(
        gps=GpsCoordinate(lat=40.0, lng=-74.0),
        attestation_count=3,
    )
    # Community is in SF (~37.78, -122.41); NY is ~4000km away
    result = verify_evidence(
        evidence,
        known_community_coords=[_community_at(37.78, -122.41)],
    )
    assert result.gps_within_radius is False
    # photo absent, gps out of range, attestation met → 1 factor → fails
    assert result.verified is False


def test_evidence_gps_inside_radius_counts():
    evidence = ImplementationEvidenceInput(
        gps=GpsCoordinate(lat=37.78, lng=-122.41),
        attestation_count=3,
    )
    result = verify_evidence(
        evidence,
        known_community_coords=[_community_at(37.79, -122.41)],
    )
    assert result.gps_within_radius is True


def test_evidence_default_min_attestations_is_three():
    evidence = ImplementationEvidenceInput(
        photo_urls=["x"],
        attestation_count=2,  # below default
    )
    result = verify_evidence(evidence)
    assert result.attestation_met is False


# ---------- R10 — content integrity ----------


def test_content_hash_matches_expected():
    content = b"hello living field"
    hash_str = compute_content_hash(content)
    assert hash_str.startswith("sha256:")
    assert verify_content_integrity(hash_str, content).ok is True


def test_content_hash_detects_tampering():
    original = b"original content"
    tampered = b"tampered content"
    expected = compute_content_hash(original)
    result = verify_content_integrity(expected, tampered)
    assert result.ok is False
    assert result.expected_hash != result.actual_hash


# ---------- R4 — x402 header formation ----------


def test_x402_headers_include_required_fields():
    headers = build_x402_payment_required_headers(
        amount_cc=Decimal("0.01"),
        payment_address="0xABC123",
    )
    assert headers["X-Payment-Amount"] == "0.01"
    assert headers["X-Payment-Currency"] == "CC"
    assert headers["X-Payment-Address"] == "0xABC123"
    assert headers["X-Payment-Network"] == "base-l2"


def test_x402_headers_custom_network():
    headers = build_x402_payment_required_headers(
        amount_cc=Decimal("1"),
        payment_address="0x1",
        network="optimism",
    )
    assert headers["X-Payment-Network"] == "optimism"


def test_x402_headers_rejects_non_positive_amount():
    with pytest.raises(ValueError):
        build_x402_payment_required_headers(
            amount_cc=Decimal("0"), payment_address="0x1"
        )


def test_x402_headers_rejects_missing_address():
    with pytest.raises(ValueError):
        build_x402_payment_required_headers(
            amount_cc=Decimal("1"), payment_address=""
        )
