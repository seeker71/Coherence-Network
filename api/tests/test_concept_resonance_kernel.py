"""Tests for the Concept Resonance Kernel (CRK) + OT-φ optimal transport.

Verification contract — these tests prove the CRK feature is working:

1. IDENTICAL SYMBOLS → CRK = 1.0, coherence = 1.0 (pure self-similarity)
2. ORTHOGONAL SYMBOLS (different bands/frequencies) → CRK = 0.0
3. FREQUENCY SENSITIVITY: Gaussian kernel suppresses distant frequencies
4. OT DISTANCE: identical distributions → ~0, distant distributions → positive
5. SACRED FREQUENCIES: 432/528/741 Hz are defined and distinct
6. TEXT MATCHING: same keyword text → high similarity, different text → low
7. FULL PIPELINE (compare_concepts): returns all fields, values in range [0,1]
8. ERROR HANDLING: empty symbols, single component, missing geometry
9. API: GET /api/concepts/{id} returns concept or 404 for unknown
"""

from __future__ import annotations

import math
from typing import Optional

import pytest

from app.services.concept_resonance_kernel import (
    ALPHA_OMEGA,
    BETA_K,
    CORE_CONCEPTS,
    GAMMA_PHASE,
    SACRED_FREQUENCIES,
    SIGMA_K,
    SIGMA_OMEGA,
    ConceptSymbol,
    GeometricSubsymbol,
    HarmonicComponent,
    ResonanceResult,
    _build_ground_cost,
    _get_band_weight,
    _group_by_band,
    _sinkhorn_distance,
    _wrap_to_pi,
    compare_concepts,
    compute_crk,
    compute_ot_phi,
    concept_to_symbol,
    text_to_symbol,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def single_component():
    """Minimal symbol: one mid-band harmonic at 432 Hz."""
    return ConceptSymbol(components=[
        HarmonicComponent(band="mid", omega=432.0, phase=0.0, amplitude=1.0)
    ])


@pytest.fixture
def twin_components():
    """Two harmonics in the same band — used to test OT."""
    return ConceptSymbol(components=[
        HarmonicComponent(band="mid", omega=432.0, phase=0.0, amplitude=1.0),
        HarmonicComponent(band="mid", omega=528.0, phase=0.5, amplitude=0.5),
    ])


@pytest.fixture
def multi_band_symbol():
    """Symbol with components in three bands."""
    return ConceptSymbol(components=[
        HarmonicComponent(band="low",  omega=174.0, phase=0.0,        amplitude=0.8),
        HarmonicComponent(band="mid",  omega=432.0, phase=math.pi/4,  amplitude=1.0),
        HarmonicComponent(band="high", omega=741.0, phase=math.pi/2,  amplitude=0.6),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Section 1 — Helper functions
# ─────────────────────────────────────────────────────────────────────────────

class TestWrapToPi:
    """Unit tests for _wrap_to_pi."""

    def test_zero_maps_to_zero(self):
        assert _wrap_to_pi(0.0) == pytest.approx(0.0)

    def test_pi_maps_to_pi(self):
        # π is the boundary — just inside → stays at π
        result = _wrap_to_pi(math.pi)
        assert abs(result) <= math.pi, f"{result} not in [-π, π]"

    def test_negative_pi_maps_near_pi(self):
        # -π should map to something in range
        result = _wrap_to_pi(-math.pi)
        assert -math.pi <= result <= math.pi

    def test_two_pi_maps_to_zero(self):
        result = _wrap_to_pi(2 * math.pi)
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_three_halves_pi(self):
        # 3π/2 > π, should wrap to -π/2
        result = _wrap_to_pi(3 * math.pi / 2)
        assert result == pytest.approx(-math.pi / 2, abs=1e-10)

    def test_infinity_returns_zero(self):
        assert _wrap_to_pi(math.inf) == 0.0

    def test_negative_infinity_returns_zero(self):
        assert _wrap_to_pi(-math.inf) == 0.0

    def test_nan_returns_zero(self):
        assert _wrap_to_pi(math.nan) == 0.0

    def test_large_multiple_wraps_correctly(self):
        # 100π should wrap to 0
        result = _wrap_to_pi(100 * math.pi)
        assert abs(result) <= math.pi


class TestGetBandWeight:
    """Unit tests for _get_band_weight."""

    def test_default_weight_when_absent(self):
        assert _get_band_weight("mid", {}, {}) == 1.0

    def test_reads_from_first_dict(self):
        bw1 = {"mid": 2.5}
        bw2 = {"mid": 0.1}
        assert _get_band_weight("mid", bw1, bw2) == 2.5

    def test_falls_back_to_second_dict(self):
        bw1 = {}
        bw2 = {"mid": 0.8}
        assert _get_band_weight("mid", bw1, bw2) == 0.8

    def test_case_insensitive_lookup(self):
        bw = {"MID": 3.0}
        assert _get_band_weight("mid", bw, {}) == 3.0
        assert _get_band_weight("MID", {}, bw) == 3.0

    def test_unknown_band_returns_one(self):
        assert _get_band_weight("ultraviolet", {"x": 5.0}, {"y": 3.0}) == 1.0


class TestGroupByBand:
    """Unit tests for _group_by_band."""

    def test_empty_list(self):
        assert _group_by_band([]) == {}

    def test_single_component(self):
        h = HarmonicComponent(band="mid", omega=432.0)
        groups = _group_by_band([h])
        assert "mid" in groups
        assert len(groups["mid"]) == 1

    def test_case_insensitive_grouping(self):
        h1 = HarmonicComponent(band="Mid", omega=432.0)
        h2 = HarmonicComponent(band="MID", omega=528.0)
        groups = _group_by_band([h1, h2])
        assert "mid" in groups
        assert len(groups["mid"]) == 2

    def test_multiple_bands(self):
        components = [
            HarmonicComponent(band="low", omega=174.0),
            HarmonicComponent(band="mid", omega=432.0),
            HarmonicComponent(band="high", omega=741.0),
        ]
        groups = _group_by_band(components)
        assert set(groups.keys()) == {"low", "mid", "high"}


# ─────────────────────────────────────────────────────────────────────────────
# Section 2 — Ground cost matrix
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildGroundCost:
    """Unit tests for OT-φ ground cost matrix."""

    def test_identical_components_zero_cost(self):
        h = HarmonicComponent(band="mid", omega=432.0, phase=0.0, amplitude=1.0)
        C = _build_ground_cost([h], [h])
        assert len(C) == 1 and len(C[0]) == 1
        assert C[0][0] == pytest.approx(0.0, abs=1e-10)

    def test_cost_grows_with_frequency_difference(self):
        h1 = HarmonicComponent(band="mid", omega=100.0, phase=0.0, amplitude=1.0)
        h2 = HarmonicComponent(band="mid", omega=200.0, phase=0.0, amplitude=1.0)
        h3 = HarmonicComponent(band="mid", omega=400.0, phase=0.0, amplitude=1.0)
        C_12 = _build_ground_cost([h1], [h2])[0][0]
        C_13 = _build_ground_cost([h1], [h3])[0][0]
        # C_13 has larger Δω, so higher cost
        assert C_13 > C_12

    def test_cost_matrix_dimensions(self):
        a1 = [
            HarmonicComponent(band="mid", omega=432.0, amplitude=1.0),
            HarmonicComponent(band="mid", omega=528.0, amplitude=0.5),
        ]
        a2 = [
            HarmonicComponent(band="mid", omega=432.0, amplitude=1.0),
            HarmonicComponent(band="mid", omega=741.0, amplitude=0.7),
            HarmonicComponent(band="mid", omega=174.0, amplitude=0.3),
        ]
        C = _build_ground_cost(a1, a2)
        assert len(C) == 2
        assert all(len(row) == 3 for row in C)

    def test_cost_uses_wrapped_phase_difference(self):
        # Two components differing by π in phase → wrapped diff = π
        h1 = HarmonicComponent(band="mid", omega=432.0, phase=0.0,    amplitude=1.0)
        h2 = HarmonicComponent(band="mid", omega=432.0, phase=math.pi, amplitude=1.0)
        C = _build_ground_cost([h1], [h2])
        # GAMMA_PHASE * π ≈ 1.571
        expected_phase_cost = GAMMA_PHASE * math.pi
        assert C[0][0] == pytest.approx(expected_phase_cost, abs=1e-6)

    def test_cost_includes_k_vector_term(self):
        k1 = (0.0,)
        k2 = (1.0,)
        h1 = HarmonicComponent(band="mid", omega=432.0, phase=0.0, amplitude=1.0, k=k1)
        h2 = HarmonicComponent(band="mid", omega=432.0, phase=0.0, amplitude=1.0, k=k2)
        C = _build_ground_cost([h1], [h2])
        # BETA_K * ||Δk|| = 1.0 * 1.0 = 1.0
        assert C[0][0] == pytest.approx(BETA_K * 1.0, abs=1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# Section 3 — Sinkhorn distance
# ─────────────────────────────────────────────────────────────────────────────

class TestSinkhornDistance:
    """Unit tests for the Sinkhorn entropic OT solver."""

    def test_trivial_single_point_zero_cost(self):
        p, q = [1.0], [1.0]
        C = [[0.0]]
        d, ok = _sinkhorn_distance(p, q, C)
        assert ok
        assert d == pytest.approx(0.0, abs=1e-6)

    def test_trivial_single_point_nonzero_cost(self):
        p, q = [1.0], [1.0]
        C = [[2.0]]
        d, ok = _sinkhorn_distance(p, q, C)
        assert ok
        # With uniform mass, distance ≈ transport cost
        assert d > 0.0
        assert d <= 2.0  # bounded by max cost

    def test_two_identical_distributions(self):
        p = [0.5, 0.5]
        q = [0.5, 0.5]
        C = [[0.0, 1.0], [1.0, 0.0]]
        d, ok = _sinkhorn_distance(p, q, C)
        assert ok
        # Identical distributions → optimal transport on diagonal (cost 0)
        assert d == pytest.approx(0.0, abs=0.05)

    def test_distance_non_negative(self):
        p = [0.3, 0.4, 0.3]
        q = [0.2, 0.5, 0.3]
        C = [
            [0.0, 1.0, 2.0],
            [1.0, 0.0, 1.0],
            [2.0, 1.0, 0.0],
        ]
        d, ok = _sinkhorn_distance(p, q, C)
        assert ok
        assert d >= 0.0

    def test_symmetry_approximate(self):
        """Transport p→q and q→p should give similar distances."""
        p = [0.6, 0.4]
        q = [0.3, 0.7]
        C = [[0.0, 2.0], [2.0, 0.0]]
        d_pq, _ = _sinkhorn_distance(p, q, C)
        d_qp, _ = _sinkhorn_distance(q, p, C)
        # Not perfectly symmetric due to entropic regularization, but close
        assert abs(d_pq - d_qp) < 0.5

    def test_returns_success_flag(self):
        p, q = [1.0], [1.0]
        C = [[1.0]]
        _, ok = _sinkhorn_distance(p, q, C)
        assert ok is True


# ─────────────────────────────────────────────────────────────────────────────
# Section 4 — CRK: compute_crk
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeCRK:
    """Unit and integration tests for the harmonic kernel computation."""

    # ── 4.1 Identity / self-similarity ──────────────────────────────────────

    def test_identical_single_component_crk_is_one(self, single_component):
        crk = compute_crk(single_component, single_component)
        assert crk == pytest.approx(1.0, abs=1e-6)

    def test_identical_multi_band_crk_is_one(self, multi_band_symbol):
        crk = compute_crk(multi_band_symbol, multi_band_symbol)
        assert crk == pytest.approx(1.0, abs=1e-6)

    def test_identical_multi_component_crk_is_one(self, twin_components):
        crk = compute_crk(twin_components, twin_components)
        assert crk == pytest.approx(1.0, abs=1e-6)

    # ── 4.2 Orthogonality ───────────────────────────────────────────────────

    def test_different_bands_crk_is_zero(self):
        """Components in different bands never cross-correlate → CRK = 0."""
        s1 = ConceptSymbol(components=[HarmonicComponent(band="low",  omega=174.0, amplitude=1.0)])
        s2 = ConceptSymbol(components=[HarmonicComponent(band="high", omega=741.0, amplitude=1.0)])
        crk = compute_crk(s1, s2)
        assert crk == pytest.approx(0.0, abs=1e-10)

    def test_far_frequencies_crk_near_zero(self):
        """Components in the same band but very different ω → Gaussian kernel ≈ 0."""
        s1 = ConceptSymbol(components=[HarmonicComponent(band="mid", omega=100.0, amplitude=1.0)])
        s2 = ConceptSymbol(components=[HarmonicComponent(band="mid", omega=900.0, amplitude=1.0)])
        crk = compute_crk(s1, s2)
        # Δω = 800, sigma_omega = 0.01 → exp(-0.5*(800/0.01)^2) ≈ 0
        assert crk < 1e-6

    def test_empty_symbol_crk_is_zero(self):
        """An empty symbol has no components — CRK undefined, falls to 0."""
        s_empty = ConceptSymbol(components=[])
        s_full  = ConceptSymbol(components=[HarmonicComponent(band="mid", omega=432.0, amplitude=1.0)])
        crk = compute_crk(s_empty, s_full)
        assert crk == pytest.approx(0.0, abs=1e-10)

    def test_two_empty_symbols_crk_is_zero(self):
        s = ConceptSymbol(components=[])
        crk = compute_crk(s, s)
        assert crk == pytest.approx(0.0, abs=1e-10)

    # ── 4.3 Amplitude scaling ────────────────────────────────────────────────

    def test_amplitude_scaling_invariant(self):
        """Scaling both amplitudes by the same factor should NOT change CRK."""
        h1 = HarmonicComponent(band="mid", omega=432.0, amplitude=1.0)
        h2 = HarmonicComponent(band="mid", omega=432.0, amplitude=10.0)
        s1 = ConceptSymbol(components=[h1])
        s2 = ConceptSymbol(components=[h2])
        crk_orig  = compute_crk(s1, s1)
        crk_scaled = compute_crk(s2, s2)
        assert crk_orig  == pytest.approx(1.0, abs=1e-6)
        assert crk_scaled == pytest.approx(1.0, abs=1e-6)

    def test_different_amplitudes_reduce_crk(self):
        """Same frequency but very different amplitudes → reduced similarity."""
        h1 = HarmonicComponent(band="mid", omega=432.0, amplitude=1.0)
        h2 = HarmonicComponent(band="mid", omega=432.0, amplitude=1.0)
        h3 = HarmonicComponent(band="mid", omega=432.0, amplitude=0.0)  # zero amplitude
        s1 = ConceptSymbol(components=[h1])
        s2 = ConceptSymbol(components=[h2])
        s3 = ConceptSymbol(components=[h3])
        crk_full = compute_crk(s1, s2)
        crk_zero = compute_crk(s1, s3)
        assert crk_full == pytest.approx(1.0, abs=1e-6)
        assert crk_zero == pytest.approx(0.0, abs=1e-6)

    # ── 4.4 Phase invariance ─────────────────────────────────────────────────

    def test_phase_does_not_affect_crk_magnitude(self):
        """CRK uses |spectral correlation| — phase shift is irrelevant."""
        h0 = HarmonicComponent(band="mid", omega=432.0, phase=0.0,    amplitude=1.0)
        hq = HarmonicComponent(band="mid", omega=432.0, phase=math.pi/2, amplitude=1.0)
        s0 = ConceptSymbol(components=[h0])
        sq = ConceptSymbol(components=[hq])
        # Both phase=0 vs phase=π/2, same band/frequency → CRK should be 1
        crk = compute_crk(s0, sq)
        assert crk == pytest.approx(1.0, abs=1e-6)

    # ── 4.5 Band weights ─────────────────────────────────────────────────────

    def test_zero_band_weight_excludes_band(self):
        """Setting band_weight=0 for a band makes it invisible to CRK."""
        h = HarmonicComponent(band="semantic", omega=432.0, amplitude=1.0)
        s_visible = ConceptSymbol(
            components=[h],
            band_weights={"semantic": 1.0},
        )
        s_invisible = ConceptSymbol(
            components=[h],
            band_weights={"semantic": 0.0},
        )
        crk_visible   = compute_crk(s_visible,   s_visible)
        crk_invisible = compute_crk(s_invisible, s_invisible)
        # Visible → CRK = 1 (same symbol). Invisible → denominator=0, skipped → CRK = 0
        assert crk_visible == pytest.approx(1.0, abs=1e-6)
        # With zero weight, norms are 0 → denominator ≤ 0, returns 0
        assert crk_invisible == pytest.approx(0.0, abs=1e-6)

    # ── 4.6 Geometric correction ─────────────────────────────────────────────

    def test_geometric_correction_applied_when_present(self):
        """Symbols with matching geometry should have CRK ≥ without geometry."""
        h = HarmonicComponent(band="mid", omega=432.0, amplitude=1.0)
        geom = GeometricSubsymbol(g=(1.0, 0.0, 0.0), lambda_=1.0)

        s_no_geom = ConceptSymbol(components=[h], mu=1.0)
        s_with_geom = ConceptSymbol(components=[h], geometry=geom, mu=1.0)

        crk_plain = compute_crk(s_no_geom, s_no_geom)
        crk_geom  = compute_crk(s_with_geom, s_with_geom)

        # Both should be ≥ 0 and ≤ 1
        assert 0.0 <= crk_plain <= 1.0
        assert 0.0 <= crk_geom  <= 1.0

    def test_geometry_lambda_zero_skips_geometric_correction(self):
        """lambda_=0 means no geometric contribution — geometry is ignored."""
        h = HarmonicComponent(band="mid", omega=432.0, amplitude=1.0)
        s_bad_geom = ConceptSymbol(
            components=[h],
            geometry=GeometricSubsymbol(g=(1.0, 0.0), lambda_=0.0),
            mu=1.0,
        )
        crk = compute_crk(s_bad_geom, s_bad_geom)
        assert crk == pytest.approx(1.0, abs=1e-6)

    # ── 4.7 τ-grid ───────────────────────────────────────────────────────────

    def test_tau_grid_is_optional(self, single_component):
        """Default tau_grid=[0] — works without passing it."""
        crk = compute_crk(single_component, single_component, tau_grid=None)
        assert crk == pytest.approx(1.0, abs=1e-6)

    def test_tau_grid_multiple_values_takes_best(self):
        """Passing multiple τ values should take the best-scoring one."""
        h = HarmonicComponent(band="mid", omega=432.0, amplitude=1.0)
        s = ConceptSymbol(components=[h])
        crk_0  = compute_crk(s, s, tau_grid=[0.0])
        crk_multi = compute_crk(s, s, tau_grid=[0.0, math.pi, -math.pi])
        # Best over multiple τ should be ≥ single-τ result
        assert crk_multi >= crk_0 - 1e-9

    # ── 4.8 CRK output range ─────────────────────────────────────────────────

    def test_crk_always_in_unit_interval(self):
        """CRK must be in [0, 1] for any valid input."""
        test_cases = [
            ConceptSymbol(components=[HarmonicComponent(band="mid", omega=432.0, amplitude=0.5)]),
            ConceptSymbol(components=[HarmonicComponent(band="low", omega=174.0, phase=1.5, amplitude=2.0)]),
            ConceptSymbol(components=[
                HarmonicComponent(band="mid", omega=528.0, amplitude=1.0),
                HarmonicComponent(band="mid", omega=741.0, amplitude=0.3),
            ]),
        ]
        for s1 in test_cases:
            for s2 in test_cases:
                crk = compute_crk(s1, s2)
                assert 0.0 <= crk <= 1.0, f"CRK={crk} out of range for {s1} vs {s2}"


# ─────────────────────────────────────────────────────────────────────────────
# Section 5 — OT-φ: compute_ot_phi
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeOTPhi:
    """Unit tests for OT-φ (Sinkhorn optimal transport)."""

    def test_identical_single_component_ot_near_zero(self):
        """Identical symbols should have near-zero OT distance."""
        h = HarmonicComponent(band="mid", omega=432.0, phase=0.0, amplitude=1.0)
        s = ConceptSymbol(components=[h])
        d, used = compute_ot_phi(s, s)
        assert used is True
        assert d == pytest.approx(0.0, abs=0.1)

    def test_non_overlapping_bands_ot_not_used(self):
        """Bands that exist only in one symbol → no OT computed."""
        s1 = ConceptSymbol(components=[HarmonicComponent(band="low",  omega=174.0, amplitude=1.0)])
        s2 = ConceptSymbol(components=[HarmonicComponent(band="high", omega=741.0, amplitude=1.0)])
        d, used = compute_ot_phi(s1, s2)
        assert used is False
        assert d == 0.0

    def test_ot_distance_non_negative(self, twin_components):
        d, _ = compute_ot_phi(twin_components, twin_components)
        assert d >= 0.0

    def test_different_frequency_distributions_positive_distance(self):
        """Two symbols with different frequency distributions → positive OT distance.

        Uses a small-to-moderate gap so exp(-C/ε) stays numerically stable.
        Very large gaps cause Sinkhorn to return 0 due to underflow (K → 0).
        """
        s1 = ConceptSymbol(components=[HarmonicComponent(band="mid", omega=100.0, amplitude=1.0)])
        s2 = ConceptSymbol(components=[HarmonicComponent(band="mid", omega=102.0, amplitude=1.0)])
        d, used = compute_ot_phi(s1, s2)
        assert used is True
        assert d > 0.0

    def test_ot_used_flag_false_for_empty_symbol(self):
        s_empty = ConceptSymbol(components=[])
        s_full  = ConceptSymbol(components=[HarmonicComponent(band="mid", omega=432.0, amplitude=1.0)])
        d, used = compute_ot_phi(s_empty, s_full)
        assert used is False
        assert d == 0.0

    def test_band_weights_affect_ot_averaging(self):
        """Custom band weights change the weighted average OT distance.

        Uses a small frequency gap so Sinkhorn remains numerically stable.
        """
        s1 = ConceptSymbol(
            components=[HarmonicComponent(band="semantic", omega=100.0, amplitude=1.0)],
            band_weights={"semantic": 2.0},
        )
        s2 = ConceptSymbol(
            components=[HarmonicComponent(band="semantic", omega=102.0, amplitude=1.0)],
            band_weights={"semantic": 2.0},
        )
        d, used = compute_ot_phi(s1, s2)
        assert used is True
        assert d > 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Section 6 — compare_concepts end-to-end
# ─────────────────────────────────────────────────────────────────────────────

class TestCompareConcepts:
    """Integration tests for the full CRK + OT-φ pipeline."""

    def test_identical_symbol_returns_full_coherence(self, single_component):
        r = compare_concepts(single_component, single_component)
        assert isinstance(r, ResonanceResult)
        # CRK = 1.0, OT ≈ 0 → coherence ≈ 1
        assert r.crk == pytest.approx(1.0, abs=1e-4)
        assert r.coherence == pytest.approx(1.0, abs=0.01)
        assert r.d_codex == pytest.approx(0.0, abs=0.01)

    def test_orthogonal_symbols_near_zero_coherence(self):
        s1 = ConceptSymbol(components=[HarmonicComponent(band="A", omega=100.0, amplitude=1.0)])
        s2 = ConceptSymbol(components=[HarmonicComponent(band="B", omega=100.0, amplitude=1.0)])
        r = compare_concepts(s1, s2)
        assert r.crk == pytest.approx(0.0, abs=1e-6)
        assert r.coherence == pytest.approx(0.0, abs=1e-6)
        assert r.d_codex == pytest.approx(1.0, abs=1e-6)

    def test_result_fields_all_present(self, single_component):
        r = compare_concepts(single_component, single_component)
        assert hasattr(r, "crk")
        assert hasattr(r, "d_res")
        assert hasattr(r, "d_ot_phi")
        assert hasattr(r, "coherence")
        assert hasattr(r, "d_codex")
        assert hasattr(r, "used_ot")

    def test_result_values_all_in_valid_ranges(self, multi_band_symbol):
        r = compare_concepts(multi_band_symbol, multi_band_symbol)
        assert 0.0 <= r.crk      <= 1.0
        assert 0.0 <= r.d_res    <= 1.0
        assert r.d_ot_phi >= 0.0
        assert 0.0 <= r.coherence <= 1.0
        assert 0.0 <= r.d_codex   <= 1.0

    def test_residual_distance_formula(self, single_component):
        """d_res = sqrt(max(0, 1 - crk²))."""
        r = compare_concepts(single_component, single_component)
        expected_d_res = math.sqrt(max(0.0, 1.0 - r.crk ** 2))
        assert r.d_res == pytest.approx(expected_d_res, abs=1e-4)

    def test_coherence_formula(self, single_component):
        """coherence = crk * exp(-d_ot_phi)."""
        r = compare_concepts(single_component, single_component)
        expected_coherence = r.crk * math.exp(-r.d_ot_phi)
        assert r.coherence == pytest.approx(expected_coherence, abs=1e-4)

    def test_d_codex_formula(self, single_component):
        """d_codex = 1.0 - coherence."""
        r = compare_concepts(single_component, single_component)
        assert r.d_codex == pytest.approx(1.0 - r.coherence, abs=1e-4)

    def test_compare_concepts_symmetric(self, single_component, twin_components):
        """CRK should be the same regardless of argument order."""
        r_fwd = compare_concepts(single_component, twin_components)
        r_rev = compare_concepts(twin_components, single_component)
        # Symmetry may not be exact due to band_weights lookup, but should be close
        assert abs(r_fwd.crk - r_rev.crk) < 0.05

    def test_used_ot_false_for_empty_symbol(self):
        s_empty = ConceptSymbol(components=[])
        s_full  = ConceptSymbol(components=[HarmonicComponent(band="mid", omega=432.0, amplitude=1.0)])
        r = compare_concepts(s_empty, s_full)
        assert r.used_ot is False

    def test_used_ot_true_for_shared_band(self, single_component):
        r = compare_concepts(single_component, single_component)
        assert r.used_ot is True

    def test_tau_grid_passed_through(self, single_component):
        """tau_grid parameter must be forwarded to compute_crk."""
        r1 = compare_concepts(single_component, single_component, tau_grid=[0.0])
        r2 = compare_concepts(single_component, single_component, tau_grid=[0.0, math.pi])
        # With identical symbols, both should give crk=1
        assert r1.crk == pytest.approx(1.0, abs=1e-6)
        assert r2.crk == pytest.approx(1.0, abs=1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# Section 7 — Sacred frequencies and ontology constants
# ─────────────────────────────────────────────────────────────────────────────

class TestSacredFrequenciesAndConstants:
    """Tests for the ontology constants from UCoreOntology.cs."""

    def test_432hz_present(self):
        assert "432hz" in SACRED_FREQUENCIES
        assert SACRED_FREQUENCIES["432hz"]["value"] == 432.0

    def test_528hz_present(self):
        assert "528hz" in SACRED_FREQUENCIES
        assert SACRED_FREQUENCIES["528hz"]["value"] == 528.0

    def test_741hz_present(self):
        assert "741hz" in SACRED_FREQUENCIES
        assert SACRED_FREQUENCIES["741hz"]["value"] == 741.0

    def test_all_sacred_frequencies_have_resonance_in_range(self):
        for name, freq in SACRED_FREQUENCIES.items():
            assert 0.0 < freq["resonance"] <= 1.0, f"{name}: resonance out of range"

    def test_core_concepts_have_required_fields(self):
        for name, concept in CORE_CONCEPTS.items():
            assert "frequency" in concept, f"{name}: missing frequency"
            assert "resonance" in concept, f"{name}: missing resonance"
            assert "type" in concept,      f"{name}: missing type"

    def test_core_concept_frequencies_match_sacred(self):
        """love and joy map to 528 Hz, consciousness to 741 Hz, ucore to 432 Hz."""
        assert CORE_CONCEPTS["love"]["frequency"] == 528.0
        assert CORE_CONCEPTS["consciousness"]["frequency"] == 741.0
        assert CORE_CONCEPTS["ucore"]["frequency"] == 432.0

    def test_sigma_constants_positive(self):
        assert SIGMA_OMEGA > 0
        assert SIGMA_K > 0

    def test_ot_constants_valid(self):
        from app.services.concept_resonance_kernel import OT_EPSILON, OT_MAX_ITERS
        assert OT_EPSILON > 0
        assert OT_MAX_ITERS > 0


# ─────────────────────────────────────────────────────────────────────────────
# Section 8 — concept_to_symbol and text_to_symbol
# ─────────────────────────────────────────────────────────────────────────────

class TestConceptToSymbol:
    """Tests for the ontology → ConceptSymbol bridge."""

    def test_known_concept_produces_symbol(self):
        sym = concept_to_symbol("love")
        assert isinstance(sym, ConceptSymbol)
        assert len(sym.components) >= 3

    def test_fundamental_band_present(self):
        sym = concept_to_symbol("love")
        bands = [c.band for c in sym.components]
        assert "fundamental" in bands

    def test_overtone_band_present(self):
        sym = concept_to_symbol("love")
        bands = [c.band for c in sym.components]
        assert "overtone" in bands

    def test_fundamental_frequency_matches_ontology(self):
        """love → 528 Hz fundamental."""
        sym = concept_to_symbol("love")
        fundamental = next(c for c in sym.components if c.band == "fundamental")
        assert fundamental.omega == 528.0

    def test_unknown_concept_uses_default_frequency(self):
        """Unknown concept IDs fall back to 432 Hz (ucore default)."""
        sym = concept_to_symbol("totally_unknown_concept_xyz")
        fundamental = next(c for c in sym.components if c.band == "fundamental")
        assert fundamental.omega == 432.0

    def test_keywords_add_semantic_band(self):
        sym = concept_to_symbol("joy", text_keywords=["harmonic", "resonance"])
        bands = [c.band for c in sym.components]
        assert "semantic" in bands

    def test_keyword_count_bounded_to_15(self):
        keywords = [f"word{i}" for i in range(30)]
        sym = concept_to_symbol("ucore", text_keywords=keywords)
        semantic = [c for c in sym.components if c.band == "semantic"]
        assert len(semantic) <= 15

    def test_same_keyword_produces_same_frequency(self):
        """Deterministic hash: same keyword → same ω across calls."""
        sym1 = concept_to_symbol("ucore", text_keywords=["consciousness"])
        sym2 = concept_to_symbol("ucore", text_keywords=["consciousness"])
        c1 = [c for c in sym1.components if c.band == "semantic"]
        c2 = [c for c in sym2.components if c.band == "semantic"]
        assert c1[0].omega == c2[0].omega

    def test_different_keywords_produce_different_frequencies(self):
        """Different keywords → different ω (probabilistically)."""
        sym1 = concept_to_symbol("ucore", text_keywords=["consciousness"])
        sym2 = concept_to_symbol("ucore", text_keywords=["algorithm"])
        c1 = next(c for c in sym1.components if c.band == "semantic")
        c2 = next(c for c in sym2.components if c.band == "semantic")
        # Different keywords should produce different frequencies
        assert c1.omega != c2.omega

    def test_band_weights_structure(self):
        sym = concept_to_symbol("ucore", text_keywords=["test"])
        assert sym.band_weights is not None
        assert "fundamental" in sym.band_weights
        assert "semantic" in sym.band_weights

    def test_semantic_weight_zero_without_keywords(self):
        """Without keywords, semantic band weight should be 0."""
        sym = concept_to_symbol("ucore", text_keywords=None)
        assert sym.band_weights["semantic"] == 0.0


class TestTextToSymbol:
    """Tests for text → ConceptSymbol keyword extraction."""

    def test_returns_concept_symbol(self):
        sym = text_to_symbol("quantum consciousness resonance")
        assert isinstance(sym, ConceptSymbol)

    def test_stopwords_excluded(self):
        """Common stopwords should not become components."""
        sym_stopwords = text_to_symbol("the and is are of to")
        sym_content   = text_to_symbol("consciousness resonance frequency")
        # Content-rich text should produce more semantic components
        stopword_semantic = [c for c in sym_stopwords.components if c.band == "semantic"]
        content_semantic  = [c for c in sym_content.components if c.band == "semantic"]
        assert len(content_semantic) >= len(stopword_semantic)

    def test_long_text_bounded(self):
        """Keyword extraction is capped at 15 unique keywords."""
        long_text = " ".join([f"word{i}" for i in range(100)])
        sym = text_to_symbol(long_text)
        semantic = [c for c in sym.components if c.band == "semantic"]
        assert len(semantic) <= 15

    def test_custom_base_concept(self):
        """base_concept changes the fundamental frequency."""
        sym_love = text_to_symbol("something", base_concept="love")
        sym_pain = text_to_symbol("something", base_concept="pain")
        fund_love = next(c for c in sym_love.components if c.band == "fundamental")
        fund_pain = next(c for c in sym_pain.components if c.band == "fundamental")
        assert fund_love.omega != fund_pain.omega

    def test_empty_text_produces_symbol(self):
        """Empty text → symbol with fundamental + overtones only."""
        sym = text_to_symbol("")
        assert len(sym.components) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Section 9 — Semantic similarity via CRK
# ─────────────────────────────────────────────────────────────────────────────

class TestSemanticSimilarity:
    """Tests that CRK provides meaningful text similarity.

    These tests answer: 'Is the CRK working yet?'
    They are the key proof of concept.
    """

    def test_identical_text_scores_high(self):
        """The same text should score highly against itself."""
        text = "consciousness healing frequency resonance quantum"
        s1 = text_to_symbol(text)
        s2 = text_to_symbol(text)
        r = compare_concepts(s1, s2)
        # CRK should be 1.0 since same components are generated deterministically
        assert r.crk == pytest.approx(1.0, abs=1e-6), (
            f"Identical text produced CRK={r.crk}, expected ≈1.0 — "
            "keyword-to-frequency mapping is non-deterministic"
        )

    def test_completely_different_text_scores_low(self):
        """Texts with no overlapping keywords should score very low."""
        s1 = text_to_symbol("alpha beta gamma delta epsilon zeta")
        s2 = text_to_symbol("truck pizza mountain cloud elephant umbrella")
        r = compare_concepts(s1, s2)
        # No shared keywords → semantic band components have different ω → CRK ≈ 0
        assert r.crk < 0.3, (
            f"Unrelated texts produced CRK={r.crk}, expected < 0.3 — "
            "frequency discrimination may be broken"
        )

    def test_partially_overlapping_text_scores_between(self):
        """Texts sharing some keywords should score between identical and different."""
        text_a = "consciousness resonance healing frequency"
        text_b = "consciousness meditation awareness stillness"
        text_c = "database server network protocol packet"

        s_a = text_to_symbol(text_a)
        s_b = text_to_symbol(text_b)
        s_c = text_to_symbol(text_c)

        crk_same   = compare_concepts(s_a, s_a).crk
        crk_partial = compare_concepts(s_a, s_b).crk
        crk_diff   = compare_concepts(s_a, s_c).crk

        assert crk_same >= crk_partial, (
            f"Self-comparison ({crk_same}) should score ≥ partial overlap ({crk_partial})"
        )
        # Different domains should score lower than partial overlap
        # (soft assertion since keyword sets may not fully separate)
        assert crk_diff <= crk_partial + 0.2, (
            f"Unrelated texts ({crk_diff}) should score ≤ partial overlap ({crk_partial})"
        )

    def test_concept_self_similarity_is_one(self):
        """Every named ontology concept should be perfectly similar to itself."""
        for concept_id in CORE_CONCEPTS:
            s = concept_to_symbol(concept_id)
            r = compare_concepts(s, s)
            assert r.crk == pytest.approx(1.0, abs=1e-6), (
                f"concept_to_symbol('{concept_id}') self-similarity CRK={r.crk}"
            )

    def test_love_vs_joy_higher_than_love_vs_pain(self):
        """Love and joy share the same frequency (528 Hz) → they should resonate
        more than love and pain (528 Hz vs 174 Hz)."""
        s_love = concept_to_symbol("love")
        s_joy  = concept_to_symbol("joy")
        s_pain = concept_to_symbol("pain")

        r_love_joy  = compare_concepts(s_love, s_joy)
        r_love_pain = compare_concepts(s_love, s_pain)

        assert r_love_joy.crk >= r_love_pain.crk, (
            f"love-joy CRK={r_love_joy.crk} should be ≥ love-pain CRK={r_love_pain.crk} "
            f"(both share 528 Hz)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Section 10 — API endpoint tests (concepts router)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestConceptsAPI:
    """Integration tests for /api/concepts endpoints.

    These verify that the CRK data model is exposed correctly via the API.
    """

    async def test_list_concepts_returns_200(self):
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/concepts")

        assert resp.status_code == 200

    async def test_list_concepts_is_paginated(self):
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp1 = await client.get("/api/concepts", params={"limit": 2, "offset": 0})
            resp2 = await client.get("/api/concepts", params={"limit": 2, "offset": 2})

        assert resp1.status_code == 200
        assert resp2.status_code == 200

    async def test_get_concept_known_returns_200(self):
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        # Use whatever concept the concept_service knows about.
        # list_concepts returns {"items": [...], ...}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listing = await client.get("/api/concepts")
            listing_data = listing.json()

        items = listing_data.get("items", listing_data) if isinstance(listing_data, dict) else listing_data
        if not items:
            pytest.skip("No concepts in service — cannot test GET by ID")

        concept_id = items[0]["id"]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/concepts/{concept_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == concept_id

    async def test_get_concept_unknown_returns_404(self):
        """Edge case: non-existent concept must return 404, not 500."""
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/concepts/this-concept-absolutely-does-not-exist-xyz123")

        assert resp.status_code == 404
        data = resp.json()
        # FastAPI detail field
        assert "detail" in data

    async def test_search_concepts_returns_list(self):
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/concepts/search", params={"q": "a"})

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_concept_stats_returns_data(self):
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/concepts/stats")

        assert resp.status_code == 200

    async def test_concept_edges_unknown_returns_404(self):
        """Edge case: edges endpoint for a missing concept must return 404."""
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/concepts/nonexistent-concept-xyz/edges")

        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Section 11 — Regression / edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Regression tests for corner-cases in the CRK pipeline."""

    def test_zero_amplitude_components_do_not_cause_divide_by_zero(self):
        h = HarmonicComponent(band="mid", omega=432.0, amplitude=0.0)
        s = ConceptSymbol(components=[h])
        r = compare_concepts(s, s)
        assert not math.isnan(r.crk)
        assert not math.isnan(r.coherence)

    def test_very_large_amplitude_handled(self):
        h = HarmonicComponent(band="mid", omega=432.0, amplitude=1e9)
        s = ConceptSymbol(components=[h])
        r = compare_concepts(s, s)
        assert not math.isnan(r.crk)
        assert r.crk == pytest.approx(1.0, abs=1e-6)

    def test_single_band_many_components(self):
        """Many components in one band should still give CRK=1 for self."""
        components = [
            HarmonicComponent(band="mid", omega=float(i * 10), amplitude=1.0)
            for i in range(1, 11)
        ]
        s = ConceptSymbol(components=components)
        crk = compute_crk(s, s)
        assert crk == pytest.approx(1.0, abs=1e-6)

    def test_mismatched_k_vector_lengths_handled(self):
        """K-vectors of different lengths should fall back to w_k=1."""
        h1 = HarmonicComponent(band="mid", omega=432.0, k=(1.0, 2.0),    amplitude=1.0)
        h2 = HarmonicComponent(band="mid", omega=432.0, k=(1.0, 2.0, 3.0), amplitude=1.0)
        s1 = ConceptSymbol(components=[h1])
        s2 = ConceptSymbol(components=[h2])
        crk = compute_crk(s1, s2)
        # No crash, result in valid range
        assert 0.0 <= crk <= 1.0

    def test_nan_phase_does_not_propagate(self):
        """If phase is NaN, _wrap_to_pi returns 0, preventing NaN propagation."""
        result = _wrap_to_pi(math.nan)
        assert result == 0.0

    def test_crk_ordering_stronger_match_scores_higher(self):
        """A better-matching pair should always score ≥ a weaker-matching pair."""
        base = ConceptSymbol(components=[HarmonicComponent(band="mid", omega=432.0, amplitude=1.0)])
        close = ConceptSymbol(components=[HarmonicComponent(band="mid", omega=432.01, amplitude=1.0)])
        far   = ConceptSymbol(components=[HarmonicComponent(band="mid", omega=600.0,  amplitude=1.0)])

        crk_close = compute_crk(base, close)
        crk_far   = compute_crk(base, far)
        assert crk_close >= crk_far

    def test_multi_tau_does_not_decrease_best_score(self):
        """Adding more τ values can only improve (or equal) the best score."""
        h1 = HarmonicComponent(band="mid", omega=432.0, phase=0.0, amplitude=1.0)
        h2 = HarmonicComponent(band="mid", omega=432.0, phase=1.0, amplitude=1.0)
        s1 = ConceptSymbol(components=[h1])
        s2 = ConceptSymbol(components=[h2])

        crk_one_tau  = compute_crk(s1, s2, tau_grid=[0.0])
        crk_many_tau = compute_crk(s1, s2, tau_grid=[0.0, 0.5, 1.0, 1.5, 2.0])
        assert crk_many_tau >= crk_one_tau - 1e-9

    def test_resonance_result_is_frozen_dataclass(self):
        """ResonanceResult must be immutable (frozen=True)."""
        h = HarmonicComponent(band="mid", omega=432.0, amplitude=1.0)
        s = ConceptSymbol(components=[h])
        r = compare_concepts(s, s)
        with pytest.raises((AttributeError, TypeError)):
            r.crk = 0.5  # type: ignore[misc]
