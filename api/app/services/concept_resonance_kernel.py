"""Concept Resonance Kernel (CRK) + Optimal Transport (OT-φ).

Faithful Python port of Living-Codex-CSharp ConceptResonanceModule.cs.
Every formula, constant, and algorithm step matches the C# original.

The CRK computes harmonic similarity between two ConceptSymbols by:
1. Grouping harmonic components by frequency band
2. Computing Gaussian-tolerant kernel weights for frequency (ω) and k-vector
3. Phase-aligned correlation with time-shift robustness (τ grid)
4. Optional geometric correction via normalized dot product
5. Score = |spectral correlation + geometric correction| / normalization

The OT-φ computes entropic Optimal Transport (Sinkhorn distance) between
the amplitude distributions of two symbols, providing a complementary
distance metric that captures structural alignment.

Final coherence = CRK × exp(-OT_distance)
Codex distance  = 1.0 - coherence

References:
- Living-Codex-CSharp: src/CodexBootstrap/Modules/ConceptResonanceModule.cs
- Sinkhorn algorithm: Cuturi 2013 "Sinkhorn Distances"
- Sacred frequencies: UCoreOntology.cs (432 Hz, 528 Hz, 741 Hz)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
# Data structures — mirrors C# records exactly
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class HarmonicComponent:
    """Individual harmonic component with band, frequency, phase, and amplitude.

    band:      frequency band name (e.g. "low", "mid", "high")
    omega:     frequency (ω) in Hz or normalized units
    k:         k-vector (wavenumber), optional
    phase:     phase angle (φ) in radians
    amplitude: amplitude (a), non-negative
    """
    band: str
    omega: float
    k: Optional[tuple[float, ...]] = None
    phase: float = 0.0
    amplitude: float = 1.0


@dataclass(frozen=True)
class GeometricSubsymbol:
    """Geometric sub-symbol with triangle coordinates and scale.

    g:      coordinate vector (e.g. triangle vertices flattened)
    lambda_: scale factor (λ), must be > 0 to be used
    """
    g: tuple[float, ...]
    lambda_: float = 0.0


@dataclass
class ConceptSymbol:
    """Complete harmonic concept symbol with components and geometry.

    components:   list of HarmonicComponent
    geometry:     optional GeometricSubsymbol
    band_weights: optional per-band weight overrides
    mu:           geometric coupling strength (μ)
    """
    components: list[HarmonicComponent] = field(default_factory=list)
    geometry: Optional[GeometricSubsymbol] = None
    band_weights: Optional[dict[str, float]] = None
    mu: Optional[float] = None


@dataclass(frozen=True)
class ResonanceResult:
    """Full resonance comparison result.

    crk:       CRK similarity score [0, 1]
    d_res:     residual distance = sqrt(max(0, 1 - crk²))
    d_ot_phi:  OT-φ (Sinkhorn) distance
    coherence: crk × exp(-d_ot_phi)
    d_codex:   1.0 - coherence (the Codex distance)
    used_ot:   whether OT-φ was successfully computed
    """
    crk: float
    d_res: float
    d_ot_phi: float
    coherence: float
    d_codex: float
    used_ot: bool


# ═══════════════════════════════════════════════════════════════════
# Constants — matches C# ConceptResonanceModule exactly
# ═══════════════════════════════════════════════════════════════════

# CRK tolerant kernels
SIGMA_OMEGA = 1e-2      # frequency tolerance
SIGMA_K = 1e-2          # k-vector tolerance (Euclidean)

# OT-φ ground cost and Sinkhorn
ALPHA_OMEGA = 1.0       # weight for |Δω|
BETA_K = 1.0            # weight for ||Δk||
GAMMA_PHASE = 0.5       # weight for wrapped phase difference
OT_EPSILON = 0.05       # entropic regularization ε
OT_MAX_ITERS = 200      # Sinkhorn iterations
OT_STABILITY_FLOOR = 1e-12
OT_CONVERGENCE_TOL = 1e-6


# ═══════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════

def _wrap_to_pi(angle: float) -> float:
    """Wrap angle to [-π, π]. Mirrors C# WrapToPi exactly."""
    TWO_PI = math.pi * 2.0
    if math.isinf(angle) or math.isnan(angle):
        return 0.0
    angle = angle % TWO_PI
    if angle <= -math.pi:
        angle += TWO_PI
    elif angle > math.pi:
        angle -= TWO_PI
    return angle


def _get_band_weight(
    band: str,
    bw1: dict[str, float],
    bw2: dict[str, float],
) -> float:
    """Get band weight: check bw1 first, then bw2, default 1.0."""
    band_lower = band.lower()
    # Case-insensitive lookup
    for bw in (bw1, bw2):
        for k, v in bw.items():
            if k.lower() == band_lower:
                return v
    return 1.0


def _group_by_band(
    components: list[HarmonicComponent],
) -> dict[str, list[HarmonicComponent]]:
    """Group components by band name (case-insensitive)."""
    groups: dict[str, list[HarmonicComponent]] = {}
    for h in components:
        key = h.band.lower()
        if key not in groups:
            groups[key] = []
        groups[key].append(h)
    return groups


# ═══════════════════════════════════════════════════════════════════
# CRK — Concept Resonance Kernel
# ═══════════════════════════════════════════════════════════════════

def compute_crk(
    s1: ConceptSymbol,
    s2: ConceptSymbol,
    tau_grid: Optional[list[float]] = None,
) -> float:
    """Compute CRK similarity between two ConceptSymbols.

    This is the core harmonic kernel matching algorithm:
    - For each time delay τ in the grid:
      - Group harmonics by band
      - Compute Gaussian-tolerant kernel for each (h1, h2) pair
      - Phase-aligned correlation: kernel × a1 × a2 × cos(Δφ - ω·τ)
      - Optional geometric correction (normalized dot product)
      - Score = |spectral + geometric| / normalization
    - Return the best score across all τ values

    Returns: float in [0.0, 1.0]
    """
    bw1 = s1.band_weights or {}
    bw2 = s2.band_weights or {}

    by_band1 = _group_by_band(s1.components)
    by_band2 = _group_by_band(s2.components)

    taus = tau_grid if tau_grid else [0.0]
    best = 0.0

    for tau in taus:
        num_real = 0.0
        num_imag = 0.0
        norm1 = 0.0
        norm2 = 0.0

        # Compute norms
        for band, harmonics in by_band1.items():
            w_band = _get_band_weight(band, bw1, bw2)
            for h in harmonics:
                a = h.amplitude
                norm1 += w_band * a * a

        for band, harmonics in by_band2.items():
            w_band = _get_band_weight(band, bw1, bw2)
            for h in harmonics:
                a = h.amplitude
                norm2 += w_band * a * a

        # Cross-correlation with Gaussian-tolerant kernels
        for band, list1 in by_band1.items():
            if band not in by_band2:
                continue
            list2 = by_band2[band]
            w_band = _get_band_weight(band, bw1, bw2)

            for h1 in list1:
                a1 = h1.amplitude
                k1 = h1.k

                for h2 in list2:
                    a2 = h2.amplitude

                    # Frequency tolerance: Gaussian kernel on Δω
                    d_omega = h1.omega - h2.omega
                    w_omega = math.exp(
                        -0.5 * (d_omega * d_omega) / (SIGMA_OMEGA * SIGMA_OMEGA)
                    )

                    # K-vector tolerance: Gaussian kernel on ||Δk||
                    w_k = 1.0
                    if k1 is not None and len(k1) > 0 and h2.k is not None and len(h2.k) == len(k1):
                        dk2 = sum((k1[i] - h2.k[i]) ** 2 for i in range(len(k1)))
                        w_k = math.exp(-0.5 * dk2 / (SIGMA_K * SIGMA_K))

                    kernel = w_band * w_omega * w_k
                    if kernel <= 1e-12:
                        continue

                    # Phase-aligned correlation with time shift
                    phase = _wrap_to_pi((h1.phase - h2.phase) - h1.omega * tau)
                    num_real += kernel * a1 * a2 * math.cos(phase)
                    num_imag += kernel * a1 * a2 * math.sin(phase)

        # Geometric correction
        geo_num = 0.0
        geo_den = 0.0
        g1, lam1, has_g1 = _try_get_geometry(s1)
        g2, lam2, has_g2 = _try_get_geometry(s2)

        if has_g1 and has_g2 and len(g1) == len(g2):
            scale = lam1 * lam2
            if scale > 0.0:
                dot = sum(g1[i] * g2[i] for i in range(len(g1)))
                n1 = sum(x * x for x in g1)
                n2 = sum(x * x for x in g2)
                n1r = math.sqrt(max(n1, 0.0))
                n2r = math.sqrt(max(n2, 0.0))
                if n1r > 0 and n2r > 0:
                    spec_mag = math.sqrt(num_real ** 2 + num_imag ** 2)
                    geo_corr = dot / (n1r * n2r)
                    mu = s1.mu if s1.mu is not None else (s2.mu if s2.mu is not None else 0.0)
                    geo_num = mu * scale * geo_corr * spec_mag
                    geo_den = mu * scale * (n1r * n2r)

        # Final score
        spec_mag_final = math.sqrt(num_real ** 2 + num_imag ** 2)
        numerator = spec_mag_final + geo_num
        denominator = (
            math.sqrt(max(norm1, 0.0)) * math.sqrt(max(norm2, 0.0))
        ) + geo_den

        if denominator <= 0:
            continue

        score = max(0.0, min(1.0, numerator / denominator))
        if score > best:
            best = score

    return best


def _try_get_geometry(
    s: ConceptSymbol,
) -> tuple[tuple[float, ...], float, bool]:
    """Extract geometry if present and valid."""
    if (
        s.geometry is not None
        and s.geometry.g is not None
        and len(s.geometry.g) > 0
        and s.geometry.lambda_ > 0.0
    ):
        return s.geometry.g, s.geometry.lambda_, True
    return (), 0.0, False


# ═══════════════════════════════════════════════════════════════════
# OT-φ — Optimal Transport with Entropic Regularization (Sinkhorn)
# ═══════════════════════════════════════════════════════════════════

def _build_ground_cost(
    a1: list[HarmonicComponent],
    a2: list[HarmonicComponent],
) -> list[list[float]]:
    """Build ground cost matrix C[i,j] = α|Δω| + β||Δk|| + γ|Δφ_wrapped|.

    This is the transport cost between each pair of harmonics.
    """
    n, m = len(a1), len(a2)
    C = [[0.0] * m for _ in range(n)]

    for i in range(n):
        h1 = a1[i]
        k1 = h1.k
        for j in range(m):
            h2 = a2[j]

            # |Δω| — frequency difference
            d_omega = abs(h1.omega - h2.omega)

            # ||Δk|| — k-vector Euclidean distance
            d_k = 0.0
            if k1 is not None and len(k1) > 0 and h2.k is not None and len(h2.k) == len(k1):
                d_k = math.sqrt(sum((k1[t] - h2.k[t]) ** 2 for t in range(len(k1))))

            # |Δφ_wrapped| — wrapped phase difference in [0, π]
            d_phi = abs(_wrap_to_pi(h1.phase - h2.phase))

            # Linear ground cost
            C[i][j] = ALPHA_OMEGA * d_omega + BETA_K * d_k + GAMMA_PHASE * d_phi

    return C


def _sinkhorn_distance(
    p: list[float],
    q: list[float],
    C: list[list[float]],
    epsilon: float = OT_EPSILON,
    max_iters: int = OT_MAX_ITERS,
    tol: float = OT_CONVERGENCE_TOL,
) -> tuple[float, bool]:
    """Entropic OT via Sinkhorn iterations.

    Returns (Wasserstein-ε distance ≈ ⟨T, C⟩, success_flag).
    T = diag(u) · K · diag(v) is the optimal transport plan.

    Algorithm:
    1. K[i,j] = exp(-C[i,j] / ε)
    2. Iterate: u = p / (K·v),  v = q / (Kᵀ·u)
    3. T[i,j] = u[i] · K[i,j] · v[j]
    4. distance = Σ T[i,j] · C[i,j]
    """
    n, m = len(p), len(q)

    # Build kernel K = exp(-C/ε)
    K = [[0.0] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            K[i][j] = math.exp(-C[i][j] / max(epsilon, 1e-12))

    # Initialize scaling vectors
    u = [1.0 / n] * n
    v = [1.0 / m] * m

    prev_err = float("inf")

    for _it in range(max_iters):
        # u = p / (K · v)
        Kv = [0.0] * n
        for i in range(n):
            s = 0.0
            for j in range(m):
                s += K[i][j] * v[j]
            Kv[i] = max(s, OT_STABILITY_FLOOR)

        err_u = 0.0
        for i in range(n):
            new_u = p[i] / Kv[i]
            err_u += abs(new_u - u[i])
            u[i] = new_u

        # v = q / (Kᵀ · u)
        KTu = [0.0] * m
        for j in range(m):
            s = 0.0
            for i in range(n):
                s += K[i][j] * u[i]
            KTu[j] = max(s, OT_STABILITY_FLOOR)

        err_v = 0.0
        for j in range(m):
            new_v = q[j] / KTu[j]
            err_v += abs(new_v - v[j])
            v[j] = new_v

        err = (err_u + err_v) / (n + m)
        if err < tol or abs(prev_err - err) < tol * 1e-2:
            break
        prev_err = err

    # Compute transport plan T = diag(u) K diag(v) and distance = ⟨T, C⟩
    distance = 0.0
    for i in range(n):
        for j in range(m):
            T_ij = u[i] * K[i][j] * v[j]
            distance += T_ij * C[i][j]

    if math.isnan(distance) or math.isinf(distance):
        return 0.0, False

    return max(0.0, distance), True


def compute_ot_phi(
    s1: ConceptSymbol,
    s2: ConceptSymbol,
) -> tuple[float, bool]:
    """Compute OT-φ distance between two ConceptSymbols.

    Per-band Sinkhorn OT on amplitude distributions, then
    weighted average across bands.

    Returns: (distance, was_used)
    """
    by_band1 = _group_by_band(s1.components)
    by_band2 = _group_by_band(s2.components)

    all_bands = set(by_band1.keys()) | set(by_band2.keys())

    total_weighted = 0.0
    total_weight = 0.0
    any_used = False

    for band in all_bands:
        atoms1 = by_band1.get(band, [])
        atoms2 = by_band2.get(band, [])
        if not atoms1 or not atoms2:
            continue

        # Masses from amplitudes (non-negative)
        p = [max(0.0, a.amplitude) for a in atoms1]
        q = [max(0.0, a.amplitude) for a in atoms2]

        # Normalize to probability measures
        sum_p = sum(p)
        sum_q = sum(q)
        if sum_p <= 0.0 or sum_q <= 0.0:
            continue
        p = [x / sum_p for x in p]
        q = [x / sum_q for x in q]

        # Ground cost
        C = _build_ground_cost(atoms1, atoms2)

        # Sinkhorn distance
        w_distance, ok = _sinkhorn_distance(p, q, C)
        if ok:
            bw1 = s1.band_weights or {}
            bw2 = s2.band_weights or {}
            wb = 0.5 * (
                _get_band_weight(band, bw1, bw2)
                + _get_band_weight(band, bw2, bw1)
            )
            total_weighted += wb * w_distance
            total_weight += wb
            any_used = True

    if not any_used:
        return 0.0, False

    d = (total_weighted / total_weight) if total_weight > 0 else total_weighted
    return max(0.0, d), True


# ═══════════════════════════════════════════════════════════════════
# Top-level: compare two ConceptSymbols
# ═══════════════════════════════════════════════════════════════════

def compare_concepts(
    s1: ConceptSymbol,
    s2: ConceptSymbol,
    tau_grid: Optional[list[float]] = None,
) -> ResonanceResult:
    """Compare two concept symbols using CRK + OT-φ.

    Returns the full resonance result:
    - crk:       harmonic kernel similarity [0, 1]
    - d_res:     residual distance = √(max(0, 1 - crk²))
    - d_ot_phi:  optimal transport distance
    - coherence: crk × exp(-d_ot_phi) — the final metric
    - d_codex:   1 - coherence — the Codex distance
    """
    crk = compute_crk(s1, s2, tau_grid)
    d_res = math.sqrt(max(0.0, 1.0 - crk * crk))

    d_ot, used_ot = compute_ot_phi(s1, s2)
    coherence = crk * math.exp(-d_ot)
    d_codex = 1.0 - coherence

    return ResonanceResult(
        crk=round(crk, 6),
        d_res=round(d_res, 6),
        d_ot_phi=round(d_ot, 6),
        coherence=round(coherence, 6),
        d_codex=round(d_codex, 6),
        used_ot=used_ot,
    )


# ═══════════════════════════════════════════════════════════════════
# Sacred frequencies — from UCoreOntology.cs
# ═══════════════════════════════════════════════════════════════════

SACRED_FREQUENCIES = {
    "432hz": {"value": 432.0, "name": "432 Hz", "category": "healing", "resonance": 0.95,
              "description": "Natural frequency of the universe, promotes healing and harmony"},
    "528hz": {"value": 528.0, "name": "528 Hz", "category": "transformation", "resonance": 0.98,
              "description": "Love frequency, promotes transformation and DNA repair"},
    "741hz": {"value": 741.0, "name": "741 Hz", "category": "consciousness", "resonance": 0.92,
              "description": "Expression frequency, promotes consciousness expansion"},
    "174hz": {"value": 174.0, "name": "174 Hz", "category": "transformation", "resonance": 0.70,
              "description": "Pain frequency, transforms into wisdom and growth"},
}

# Core ontology concepts with their frequencies
CORE_CONCEPTS = {
    "ucore":         {"frequency": 432.0, "resonance": 0.95, "type": "core"},
    "joy":           {"frequency": 528.0, "resonance": 0.90, "type": "emotion"},
    "pain":          {"frequency": 174.0, "resonance": 0.70, "type": "transformation"},
    "consciousness": {"frequency": 741.0, "resonance": 0.98, "type": "core"},
    "love":          {"frequency": 528.0, "resonance": 0.99, "type": "core"},
}

# Ontology relationships with semantic edge types
CORE_RELATIONSHIPS = {
    "joy-amplifies-consciousness":  {"source": "joy", "target": "consciousness", "type": "amplifies", "strength": 0.9},
    "pain-transforms-to-wisdom":    {"source": "pain", "target": "consciousness", "type": "transforms", "strength": 0.8},
    "love-unifies-all":             {"source": "love", "target": "ucore", "type": "unifies", "strength": 1.0},
}


def concept_to_symbol(
    concept_id: str,
    text_keywords: Optional[list[str]] = None,
) -> ConceptSymbol:
    """Convert a named ontology concept into a ConceptSymbol for CRK comparison.

    Uses the concept's sacred frequency as the base harmonic, then adds
    harmonic overtones and keyword-derived components.

    This bridges the gap between the keyword world (ideas, news) and
    the harmonic world (CRK, OT-φ).
    """
    concept = CORE_CONCEPTS.get(concept_id, {"frequency": 432.0, "resonance": 0.5, "type": "core"})
    base_freq = concept["frequency"]
    base_resonance = concept["resonance"]

    components = []

    # Fundamental frequency
    components.append(HarmonicComponent(
        band="fundamental",
        omega=base_freq,
        phase=0.0,
        amplitude=base_resonance,
    ))

    # First overtone (octave)
    components.append(HarmonicComponent(
        band="overtone",
        omega=base_freq * 2.0,
        phase=math.pi / 4,
        amplitude=base_resonance * 0.5,
    ))

    # Third harmonic
    components.append(HarmonicComponent(
        band="overtone",
        omega=base_freq * 3.0,
        phase=math.pi / 3,
        amplitude=base_resonance * 0.25,
    ))

    # Keyword-derived components (each keyword gets a unique frequency)
    # Uses a deterministic hash that spreads keywords across the full
    # frequency range so different words produce different ω values.
    # Two texts sharing the keyword "claude" will have the same ω for it,
    # enabling the Gaussian kernel to match them. Different keywords
    # will have distant ω values, suppressing cross-matching.
    if text_keywords:
        for i, kw in enumerate(text_keywords[:15]):
            # Deterministic hash → stable frequency per keyword
            h = 0
            for c in kw.lower():
                h = (h * 31 + ord(c)) & 0xFFFFFFFF
            # Spread across 50-5000 Hz to maximize discrimination
            kw_freq = 50.0 + (h % 49500) / 10.0  # 50-5000 Hz, 0.1 Hz resolution
            # k-vector encodes character-level structure
            k_val = ((h >> 8) & 0xFFFF) / 65535.0
            # Phase from different hash bits
            kw_phase = ((h >> 16) & 0xFFF) / 651.8986  # 0 to ~2π
            # Amplitude decays for later keywords (position weighting)
            amp = 0.5 * (1.0 / (1.0 + 0.15 * i))
            components.append(HarmonicComponent(
                band="semantic",
                omega=kw_freq,
                k=(k_val,),
                phase=kw_phase,
                amplitude=amp,
            ))

    # Weight semantic band highest when keywords are present —
    # the ontological frequency serves as context, but the semantic
    # components carry the discriminative signal for text matching.
    semantic_weight = 1.0 if text_keywords else 0.0
    return ConceptSymbol(
        components=components,
        band_weights={"fundamental": 0.3, "overtone": 0.15, "semantic": semantic_weight},
        mu=0.1,
    )


def text_to_symbol(
    text: str,
    base_concept: str = "ucore",
) -> ConceptSymbol:
    """Convert arbitrary text to a ConceptSymbol by extracting keywords
    and mapping them to harmonic components.

    This is the bridge that lets us use CRK on news articles and idea
    descriptions — converting text into the frequency domain.
    """
    # Simple keyword extraction (reuse from news_resonance if available)
    words = text.lower().split()
    # Remove common stopwords
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "been", "be", "have",
        "has", "had", "do", "does", "did", "will", "would", "could", "should",
        "may", "might", "can", "shall", "of", "in", "to", "for", "with",
        "on", "at", "from", "by", "about", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "under", "again",
        "further", "then", "once", "and", "but", "or", "nor", "not", "so",
        "yet", "both", "each", "few", "more", "most", "other", "some", "such",
        "no", "only", "own", "same", "than", "too", "very", "just", "because",
        "it", "its", "this", "that", "these", "those", "what", "which", "who",
        "whom", "how", "when", "where", "why", "all", "any", "every",
    }
    keywords = [w for w in words if len(w) > 2 and w not in stopwords]
    # Deduplicate while preserving order
    seen = set()
    unique_kw = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_kw.append(kw)

    return concept_to_symbol(base_concept, unique_kw[:15])
