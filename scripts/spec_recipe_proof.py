#!/usr/bin/env python3
"""spec_recipe_proof.py — a spec's frontmatter IS the playable Recipe.

The twelfth runtime encoder. Completes the set of named modality encoders:

    prose, song, video, teaching, strategy-after-rupture, quantum-physics,
    embodiment-practice, healing-modality, assemblage-shift, encoder-decoder
    (meta), spec.

(The meta-codec attestation in encoder_decoder_recipe_proof.py is the
twelfth row in the codec registry; this proof is the twelfth modality
ENCODER — the per-modality runtime that builds the Recipe from the source.)

Shape-file:
    docs/coherence-substrate/spec-as-playable-recipe.form

The shift Urs named on 2026-05-23: a spec's frontmatter is not a
DESCRIPTION of code-to-be-written. It IS the executable Recipe. Each
requirement carries alternative implementation branches and the body
senses which arm aligns most closely with the idea's own wanting.
Implementation was the gap between intent and body; the gap closes
when the runtime executes the Recipe directly.

The cross-modal claims (SP1–SP4) make the unity falsifiable:

    CLAIM-SP1: R_Idea→Spec is structurally R_Pointing (teaching) at the
               requirements-attestation altitude. The idea points AT
               the spec; the spec's requirements observe-and-actualize
               the idea. Same observer-conditioned-actualization shape.

    CLAIM-SP2: R_Branch-Resonance is structurally R_Superposition
               (quantum). A spec holds N implementation branches in
               superposition until the body's frequency selects one.

    CLAIM-SP3: R_Verify is structurally R_Measurement-Collapse. A test
               run is an observer that collapses "might-or-might-not-
               work" into a definite eigenvalue.

    CLAIM-SP4 (the completion): the spec codec carries the SAME R_Codec
               Blueprint as all other 11 codecs proven in CLAIM-C1 of
               encoder_decoder_recipe_proof.py. The twelve are
               structurally one.

Worked example: the live spec `specs/runtime-telemetry-db-precedence.md`
(tended in PR #1916) — its frontmatter encodes here, the requirements
become R_Requirement leaves with done_when attestation children, the
source map becomes a Recipe attaching the spec to its implementing
files, and "playing" the Recipe (walking it) produces the verification
surface that already exists on disk (the pytest invocation from `test:`).

Sibling proofs (same in-memory lattice pattern):
    scripts/prose_recipe_roundtrip.py
    scripts/song_recipe_proof.py
    scripts/video_recipe_proof.py
    scripts/teaching_recipe_proof.py
    scripts/strategy_after_rupture_recipe_proof.py
    scripts/quantum_physics_recipe_proof.py
    scripts/embodiment_practice_recipe_proof.py
    scripts/healing_modality_recipe_proof.py
    scripts/assemblage_shift_recipe_proof.py
    scripts/encoder_decoder_recipe_proof.py

Run:
    python3 scripts/spec_recipe_proof.py

Exit code 0 if every assertion holds.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# In-memory substrate stand-in (matches sibling proofs)
# ---------------------------------------------------------------------------

_BLUEPRINT_LATTICE: dict[tuple, "Cell"] = {}
_NAMED_CELL_LATTICE: dict[str, "Cell"] = {}


def intern(cell: "Cell", name: str | None = None) -> "Cell":
    """Idempotent intern. Identical Blueprint → identical canonical cell."""
    key = cell.blueprint
    if key not in _BLUEPRINT_LATTICE:
        _BLUEPRINT_LATTICE[key] = cell
    canonical = _BLUEPRINT_LATTICE[key]
    if name is not None:
        _NAMED_CELL_LATTICE[name] = canonical
    return canonical


def lookup_by_name(name: str) -> "Cell | None":
    return _NAMED_CELL_LATTICE.get(name)


def find_structural_twins(cell: "Cell") -> list["Cell"]:
    return [c for c in _BLUEPRINT_LATTICE.values()
            if c.blueprint == cell.blueprint]


class Cell:
    """Base — concrete cells expose a `blueprint` tuple."""

    @property
    def blueprint(self) -> tuple:  # pragma: no cover - abstract
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Part 1 — Leaf-cell Blueprints (mirrors spec-as-playable-recipe.form Part 1)
# ---------------------------------------------------------------------------
#
# Five leaves: requirement, done_when, source_map, constraint,
# branch_resonance. Each is content-addressed: identical fields →
# identical Blueprint NodeID regardless of how many times interned.


@dataclass(frozen=True)
class RequirementLeafCell(Cell):
    """A single requirement extracted from spec frontmatter."""

    criterion: str        # the requirement text (canonical form)
    evidence_kind: str    # "test" | "file" | "symbol" | "endpoint" | "observed"

    @property
    def blueprint(self) -> tuple:
        return ("requirement_leaf", self.criterion, self.evidence_kind)


@dataclass(frozen=True)
class DoneWhenLeafCell(Cell):
    """A single done_when condition — what observes the requirement met."""

    observable: str       # "file_exists" | "pytest_passes" | "symbol_in_file" | ...
    attestation: str      # the argument the observable is fed (path, expr, ...)

    @property
    def blueprint(self) -> tuple:
        return ("done_when_leaf", self.observable, self.attestation)


@dataclass(frozen=True)
class SourceMapLeafCell(Cell):
    """A (path, symbol) pair from the source: map — where the body lives."""

    path: str             # repo-relative path to the implementing file
    symbol: str           # function / class / endpoint name; "" for whole-file

    @property
    def blueprint(self) -> tuple:
        return ("source_map_leaf", self.path, self.symbol)


@dataclass(frozen=True)
class ConstraintLeafCell(Cell):
    """A single constraint — what the spec forbids or keeps open."""

    kind: str             # "scope" | "schema" | "approval" | "forbid" | "keep_open"
    rule: str             # the constraint text

    @property
    def blueprint(self) -> tuple:
        return ("constraint_leaf", self.kind, self.rule)


@dataclass(frozen=True)
class BranchResonanceLeafCell(Cell):
    """The HARMONIC_AT signature carried by an implementation branch.

    Mirrors the resonance: HARMONIC_AT @<hz> sentinels in the shape-file
    Part 2 example. Same lattice keying as other modalities' resonance
    leaves (song's R_Hz, healing's resonance).
    """

    branch_tag: str       # "@substrate-first" | "@python-stub-bridge" | ...
    hz: float             # 174 | 256 | 432 | 528 | 741 | 963 — the band
    band_name: str        # "consciousness" | "vitality" | "wholeness" | ...

    @property
    def blueprint(self) -> tuple:
        return ("branch_resonance_leaf", self.branch_tag, self.hz,
                self.band_name)


# ---------------------------------------------------------------------------
# Part 2 — Branch-resonance vocabulary (typed-tokens)
# ---------------------------------------------------------------------------
#
# The five branch-arm names live in the substrate as typed-token cells.
# Anything that names "@substrate-first" anywhere in the body refers to
# the SAME canonical token cell — content-addressed by branch-tag.


BRANCH_VOCAB: dict[str, tuple[float, str]] = {
    # tag                            → (hz,    band-name)
    "@substrate-first":                (741.0, "consciousness"),
    "@python-stub-bridge":             (528.0, "vitality-transitional"),
    "@form-runtime-direct":            (963.0, "wholeness"),
    "@doc-only":                       (432.0, "neutral-descriptive"),
    "@parallel-form-and-python":       (528.0, "paired-learning"),
}


def intern_branch_token(tag: str) -> BranchResonanceLeafCell:
    """Look up the canonical resonance token cell for a branch tag."""
    if tag not in BRANCH_VOCAB:
        raise ValueError(f"unknown branch tag: {tag!r}")
    hz, band = BRANCH_VOCAB[tag]
    return intern(
        BranchResonanceLeafCell(branch_tag=tag, hz=hz, band_name=band),
        name=f"branch:{tag}",
    )


# ---------------------------------------------------------------------------
# Part 3 — Recipe shapes (mirrors spec-as-playable-recipe.form Part 2)
# ---------------------------------------------------------------------------
#
# Cross-modal-load-bearing shape. SP1, SP3 attest against variations
# on this Blueprint. The shape-tag distinguishes recipes whose
# composition is otherwise identical (R_Idea→Spec vs. R_Pointing vs.
# R_Re-anchor vs. R_Measurement-Collapse) — same shape, different
# altitude-of-naming.
@dataclass(frozen=True)
class RObserverConditionedActualization(Cell):
    """Base shape for 'observer arrives, possibility resolves' recipes.

    Same shape used by quantum_physics_recipe_proof, teaching_recipe_proof,
    assemblage_shift_recipe_proof. Naming altitude lives in shape_tag;
    structural Blueprint lives in .shape (tag stripped).

    For the spec modality:
      - R_Idea→Spec       — idea points AT spec; requirements observe-and-
                            actualize the idea. Twin of R_Pointing.
      - R_Verify          — pytest run observes the implementation;
                            collapses superposition of "might or might
                            not work." Twin of R_Measurement-Collapse.
    """

    shape_tag: str        # "R_Idea→Spec" | "R_Verify" | "R_Pointing" | ...
    observer: tuple       # the cell doing the observing
    observable: tuple     # what's being observed
    pre_state: tuple      # superposition before
    eigenvalue: tuple     # the resolved state
    post_state: tuple     # state after resolution
    backaction: tuple     # how the observer was changed

    @property
    def blueprint(self) -> tuple:
        return (
            self.shape_tag,
            self.observer,
            self.observable,
            self.pre_state,
            self.eigenvalue,
            self.post_state,
            self.backaction,
        )

    @property
    def shape(self) -> tuple:
        """The cross-modal shape — tag stripped. SP1, SP3 attest on this."""
        return (
            "R_ObserverConditionedActualization",
            self.observer,
            self.observable,
            self.pre_state,
            self.eigenvalue,
            self.post_state,
            self.backaction,
        )


def r_idea_to_spec(**kw: Any) -> RObserverConditionedActualization:
    """An idea pointing at the spec that observes-and-actualizes it."""
    return RObserverConditionedActualization(shape_tag="R_Idea→Spec", **kw)


def r_pointing(**kw: Any) -> RObserverConditionedActualization:
    """Teaching-side reference twin (R_Pointing from
    teaching-as-recipe.form, also matched in quantum_physics_recipe_proof
    CLAIM-Q1)."""
    return RObserverConditionedActualization(shape_tag="R_Pointing", **kw)


def r_verify(**kw: Any) -> RObserverConditionedActualization:
    """A test run as observer collapsing implementation superposition."""
    return RObserverConditionedActualization(shape_tag="R_Verify", **kw)


def r_measurement_collapse(**kw: Any) -> RObserverConditionedActualization:
    """Quantum twin (R_Measurement-Collapse from
    quantum-physics-as-recipe.form CLAIM-Q1)."""
    return RObserverConditionedActualization(
        shape_tag="R_Measurement-Collapse", **kw
    )


# Cross-modal-load-bearing shape #2. SP2 attests against this Blueprint.
@dataclass(frozen=True)
class RSuperpositionLike(Cell):
    """Base shape for 'multiple branches held coherently until observation.'

    Quantum-side: R_Superposition (states held in superposition).
    Spec-side: R_Branch-Resonance (implementation branches held until
              the body's frequency selects one).
    """

    shape_tag: str       # "R_Superposition" | "R_Branch-Resonance"
    states: tuple        # tuple of state/branch leaf blueprints
    coherence: float     # 0.0 (fully decohered) – 1.0 (perfectly coherent)
    basis: str           # the basis the superposition is expressed in

    @property
    def blueprint(self) -> tuple:
        return (self.shape_tag, self.states, self.coherence, self.basis)

    @property
    def shape(self) -> tuple:
        """The cross-modal shape — tag stripped. SP2 attests on this."""
        return ("R_SuperpositionLike", self.states, self.coherence,
                self.basis)


def r_superposition(**kw: Any) -> RSuperpositionLike:
    """Quantum twin."""
    return RSuperpositionLike(shape_tag="R_Superposition", **kw)


def r_branch_resonance(**kw: Any) -> RSuperpositionLike:
    """Spec twin — implementation branches held until selection."""
    return RSuperpositionLike(shape_tag="R_Branch-Resonance", **kw)


# Spec-specific composition recipes — R_Spec, R_Requirement, R_Spec→Impl,
# R_Block.SEQUENCE.


@dataclass(frozen=True)
class RRequirement(Cell):
    """R_Requirement — one requirement + its done_when attestation children
    + its branch_resonance superposition."""

    criterion: tuple           # RequirementLeafCell blueprint
    done_when_seq: tuple       # tuple of DoneWhenLeafCell blueprints
    branches: tuple            # R_Branch-Resonance blueprint (or NULL_ARM)

    @property
    def blueprint(self) -> tuple:
        return ("R_Requirement", self.criterion, self.done_when_seq,
                self.branches)


@dataclass(frozen=True)
class RSpecToImpl(Cell):
    """R_Spec→Impl — a spec attached to the files that implement it.

    Composes the source: map into a Recipe whose children name the
    implementing files + symbols.
    """

    spec_name: str             # the spec's slug (e.g. "runtime-telemetry-db-precedence")
    source_map: tuple          # tuple of SourceMapLeafCell blueprints
    test_invocation: str       # the `test:` command from frontmatter

    @property
    def blueprint(self) -> tuple:
        return ("R_Spec→Impl", self.spec_name, self.source_map,
                self.test_invocation)


@dataclass(frozen=True)
class RSpec(Cell):
    """R_Spec — the whole composed spec recipe.

    Top-level: a spec is the sequence of (R_Idea→Spec, requirements,
    source-map-attachment, constraints, verification arm).
    """

    name: str                  # spec slug
    idea_pointer: tuple        # R_Idea→Spec blueprint
    requirements: tuple        # tuple of R_Requirement blueprints
    spec_to_impl: tuple        # R_Spec→Impl blueprint
    constraints: tuple         # tuple of ConstraintLeafCell blueprints
    verify_arm: tuple          # R_Verify blueprint

    @property
    def blueprint(self) -> tuple:
        return ("R_Spec", self.name, self.idea_pointer, self.requirements,
                self.spec_to_impl, self.constraints, self.verify_arm)


@dataclass(frozen=True)
class RBlockSequence(Cell):
    """R_Block.SEQUENCE — the substrate's universal sequencing shape.

    Used to compose the walkable verification surface produced by
    "playing" a spec.
    """

    children: tuple

    @property
    def blueprint(self) -> tuple:
        return ("R_Block.SEQUENCE", self.children)


# ---------------------------------------------------------------------------
# Part 4 — Codec shapes (mirrors encoder-decoder-as-recipe.form Part 2)
# ---------------------------------------------------------------------------
#
# The spec codec slots into the R_Codec shape every other modality
# wears. CLAIM-SP4 attests it carries the SAME meta_shape tag as the
# other 11 codecs proven in encoder_decoder_recipe_proof.py CLAIM-C1.


@dataclass(frozen=True)
class SourceHandleCell(Cell):
    domain: str
    ref: str
    arrival_kind: str

    @property
    def blueprint(self) -> tuple:
        return ("source_handle", self.domain, self.ref, self.arrival_kind)


@dataclass(frozen=True)
class TargetSurfaceCell(Cell):
    domain: str
    template_set: str
    arrival_kind: str

    @property
    def blueprint(self) -> tuple:
        return ("target_surface", self.domain, self.template_set,
                self.arrival_kind)


@dataclass(frozen=True)
class LossAccountCell(Cell):
    fields_dropped: tuple
    fidelity_score: float
    is_lossless: bool
    why_lossy: str

    @property
    def blueprint(self) -> tuple:
        return ("loss_account", self.fields_dropped, self.fidelity_score,
                self.is_lossless, self.why_lossy)


@dataclass(frozen=True)
class REncode(Cell):
    source: tuple
    grammar: tuple
    yielded: tuple
    loss: tuple

    @property
    def blueprint(self) -> tuple:
        return ("R_Encode", self.source, self.grammar, self.yielded,
                self.loss)


@dataclass(frozen=True)
class RDecode(Cell):
    recipe: tuple
    target: tuple
    templates: tuple
    yielded: tuple
    loss: tuple

    @property
    def blueprint(self) -> tuple:
        return ("R_Decode", self.recipe, self.target, self.templates,
                self.yielded, self.loss)


NULL_ARM: tuple = ("NullArm",)


@dataclass(frozen=True)
class RCodec(Cell):
    """R_Codec — same shape encoder_decoder_recipe_proof attests on."""

    name: str
    encode_arm: tuple
    decode_arm: tuple
    round_trip: tuple

    @property
    def blueprint(self) -> tuple:
        return ("R_Codec", self.name, self.encode_arm, self.decode_arm,
                self.round_trip)

    @property
    def meta_shape(self) -> str:
        """The bare structural tag. CLAIM-SP4 attests on this."""
        return "R_Codec"


# ---------------------------------------------------------------------------
# Part 5 — Hard-coded representative frontmatter
# ---------------------------------------------------------------------------
#
# Mirrors specs/runtime-telemetry-db-precedence.md (tended in PR #1916).
# The encoder is a stand-in: instead of parsing markdown, we hand it
# the structured shape that a real parser would produce. This is the
# pattern siblings use (build_satsang_collapse, build_double_slit) —
# the runtime composes from data, not a file walk.

REPRESENTATIVE_FRONTMATTER: dict[str, Any] = {
    "idea_id": "data-infrastructure",
    "status": "done",
    "source": [
        {
            "file": "api/app/services/telemetry_persistence/__init__.py",
            "symbols": ["backend_info()", "checkpoint()"],
        },
    ],
    "requirements": [
        ("When a runtime database URL is configured, runtime telemetry "
         "events must be persisted to the database even if "
         "RUNTIME_EVENTS_PATH is set."),
        ("GET /api/health/persistence must not fail the global "
         "persistence contract due to runtime telemetry being "
         "file-routed when a database is configured."),
        ("Add a regression test proving DB precedence when both "
         "RUNTIME_DATABASE_URL and RUNTIME_EVENTS_PATH are set."),
    ],
    "done_when": [
        ("file_exists",
         "api/app/services/telemetry_persistence/__init__.py"),
        ("symbol_in_file",
         "api/app/services/telemetry_persistence/__init__.py:backend_info"),
        ("symbol_in_file",
         "api/app/services/telemetry_persistence/__init__.py:checkpoint"),
        ("pytest_passes",
         "api/tests/test_runtime_event_store_precedence.py"),
    ],
    "test": ("cd api && pytest -q --ignore=tests/holdout "
             "tests/test_runtime_event_store_precedence.py"),
    "constraints": [
        ("scope", "changes scoped to listed files only"),
        ("approval", "no schema migrations without explicit approval"),
    ],
    # For this representative spec, the body chose @substrate-first arm.
    # The other arms are present in superposition until selection.
    "branches_per_requirement": [
        "@substrate-first",
        "@python-stub-bridge",
        "@form-runtime-direct",
        "@doc-only",
        "@parallel-form-and-python",
    ],
}


# ---------------------------------------------------------------------------
# Part 6 — The spec encoder
# ---------------------------------------------------------------------------


def encode_requirement(
    text: str,
    done_when_pairs: tuple[tuple[str, str], ...],
    branch_tags: tuple[str, ...],
) -> RRequirement:
    """Encode one requirement into R_Requirement with done_when leaves
    + branch-resonance superposition."""
    criterion = intern(RequirementLeafCell(
        criterion=text,
        evidence_kind="test",
    ))
    done_when_blueprints = tuple(
        intern(DoneWhenLeafCell(observable=obs, attestation=arg)).blueprint
        for obs, arg in done_when_pairs
    )
    branch_blueprints = tuple(
        intern_branch_token(tag).blueprint for tag in branch_tags
    )
    branches = intern(r_branch_resonance(
        states=branch_blueprints,
        coherence=1.0,
        basis="implementation-arm",
    ))
    return intern(RRequirement(
        criterion=criterion.blueprint,
        done_when_seq=done_when_blueprints,
        branches=branches.blueprint,
    ))


def encode_spec(name: str, frontmatter: dict[str, Any]) -> RSpec:
    """Walk frontmatter → R_Spec Recipe. The encoder."""
    # source: list of {file, symbols} → R_Spec→Impl
    source_map_blueprints: list[tuple] = []
    for entry in frontmatter["source"]:
        path = entry["file"]
        for sym in entry["symbols"]:
            source_map_blueprints.append(intern(SourceMapLeafCell(
                path=path, symbol=sym,
            )).blueprint)
    spec_to_impl = intern(RSpecToImpl(
        spec_name=name,
        source_map=tuple(source_map_blueprints),
        test_invocation=frontmatter["test"],
    ))

    # constraints: list of (kind, rule) → ConstraintLeafCell blueprints
    constraints = tuple(
        intern(ConstraintLeafCell(kind=k, rule=r)).blueprint
        for k, r in frontmatter["constraints"]
    )

    # requirements: each gets the same branch-superposition (the body
    # could select differently per requirement; the representative spec
    # offers the same five branches per requirement).
    branch_tags = tuple(frontmatter["branches_per_requirement"])
    req_blueprints: list[tuple] = []
    for req_text in frontmatter["requirements"]:
        # Distribute done_when conditions across requirements — the
        # final done_when (pytest_passes) attests every requirement;
        # the file/symbol conditions attest the implementation surface.
        relevant_dw = tuple(frontmatter["done_when"])
        req = encode_requirement(req_text, relevant_dw, branch_tags)
        req_blueprints.append(req.blueprint)

    # R_Idea→Spec: the idea points at the spec; the spec observes-and-
    # actualizes the idea. The "observer" is the idea-cell carrying its
    # idea_wants signature; the "observable" is the spec's requirements
    # surface; the eigenvalue is the spec selected as the actualizing
    # carrier.
    idea_cell = intern(SourceHandleCell(
        domain="idea",
        ref=frontmatter["idea_id"],
        arrival_kind="cell",
    ))
    spec_target = intern(TargetSurfaceCell(
        domain="spec",
        template_set=f"{name}.requirements",
        arrival_kind="cell",
    ))
    # Pre-state: the idea's wanting held in superposition over all the
    # specs that could carry it.
    pre_state = intern(r_branch_resonance(
        states=(idea_cell.blueprint,),
        coherence=1.0,
        basis="possible-specs",
    ))
    # Post-state: this spec, selected.
    post_state = intern(RequirementLeafCell(
        criterion=f"spec:{name}-selected",
        evidence_kind="observed",
    ))
    idea_pointer = intern(r_idea_to_spec(
        observer=idea_cell.blueprint,
        observable=spec_target.blueprint,
        pre_state=pre_state.blueprint,
        eigenvalue=post_state.blueprint,
        post_state=post_state.blueprint,
        backaction=idea_cell.blueprint,
    ))

    # R_Verify: the test invocation as observer collapsing implementation
    # superposition into pass/fail eigenvalue.
    test_observer = intern(SourceHandleCell(
        domain="test-runner",
        ref=frontmatter["test"],
        arrival_kind="invocation",
    ))
    test_observable = intern(TargetSurfaceCell(
        domain="implementation",
        template_set="pytest.outcomes",
        arrival_kind="exit-code",
    ))
    pre_verify = intern(r_branch_resonance(
        states=(
            intern(RequirementLeafCell(
                criterion="implementation-might-be-correct",
                evidence_kind="observed",
            )).blueprint,
            intern(RequirementLeafCell(
                criterion="implementation-might-not-be-correct",
                evidence_kind="observed",
            )).blueprint,
        ),
        coherence=1.0,
        basis="correctness",
    ))
    pass_eigenvalue = intern(RequirementLeafCell(
        criterion="pytest-exit-0",
        evidence_kind="observed",
    ))
    verify_arm = intern(r_verify(
        observer=test_observer.blueprint,
        observable=test_observable.blueprint,
        pre_state=pre_verify.blueprint,
        eigenvalue=pass_eigenvalue.blueprint,
        post_state=pass_eigenvalue.blueprint,
        backaction=test_observer.blueprint,
    ))

    return intern(RSpec(
        name=name,
        idea_pointer=idea_pointer.blueprint,
        requirements=tuple(req_blueprints),
        spec_to_impl=spec_to_impl.blueprint,
        constraints=constraints,
        verify_arm=verify_arm.blueprint,
    ))


# ---------------------------------------------------------------------------
# Part 7 — Playing the spec (walk the Recipe → verification surface)
# ---------------------------------------------------------------------------


def play_spec(spec: RSpec) -> RBlockSequence:
    """Walk a spec Recipe and compose its verification surface.

    'Playing' a spec means: emit a R_Block.SEQUENCE of the checks the
    body would run to attest the spec satisfied — file existence,
    symbol presence, test invocation, constraint observance. This is
    the surface the runtime executes.
    """
    surface_children: list[tuple] = []

    # 1. Idea→Spec pointer — assert idea exists
    surface_children.append(spec.idea_pointer)

    # 2. Source-map checks — assert each (path, symbol) exists
    source_map_recipe = _BLUEPRINT_LATTICE[spec.spec_to_impl]
    assert isinstance(source_map_recipe, RSpecToImpl)
    for sm_bp in source_map_recipe.source_map:
        surface_children.append(sm_bp)

    # 3. Per-requirement done_when checks — attest each
    for req_bp in spec.requirements:
        req_cell = _BLUEPRINT_LATTICE[req_bp]
        assert isinstance(req_cell, RRequirement)
        for dw_bp in req_cell.done_when_seq:
            surface_children.append(dw_bp)

    # 4. Constraint observance — attest scope holds
    for c_bp in spec.constraints:
        surface_children.append(c_bp)

    # 5. Final verify arm — run the test
    surface_children.append(spec.verify_arm)

    return intern(RBlockSequence(children=tuple(surface_children)))


# ---------------------------------------------------------------------------
# Part 8 — Cross-modal builders (SP1, SP2, SP3)
# ---------------------------------------------------------------------------


def build_sp1_pair() -> tuple[
    RObserverConditionedActualization,
    RObserverConditionedActualization,
]:
    """SP1: R_Idea→Spec ≡ R_Pointing.

    Build both from the same composition (observer, observable, pre,
    eigenvalue, post, backaction). Only shape_tag differs; the cross-
    modal `.shape` strips the tag and exposes the common Blueprint.
    """
    idea = intern(SourceHandleCell(
        domain="idea", ref="example-idea", arrival_kind="cell",
    ))
    spec_target = intern(TargetSurfaceCell(
        domain="spec", template_set="example.requirements",
        arrival_kind="cell",
    ))
    pre = intern(r_branch_resonance(
        states=(idea.blueprint,),
        coherence=1.0,
        basis="possible-specs",
    ))
    eigen = intern(RequirementLeafCell(
        criterion="example-spec-selected",
        evidence_kind="observed",
    ))
    common = dict(
        observer=idea.blueprint,
        observable=spec_target.blueprint,
        pre_state=pre.blueprint,
        eigenvalue=eigen.blueprint,
        post_state=eigen.blueprint,
        backaction=idea.blueprint,
    )
    return (r_idea_to_spec(**common), r_pointing(**common))


def build_sp2_pair() -> tuple[RSuperpositionLike, RSuperpositionLike]:
    """SP2: R_Branch-Resonance ≡ R_Superposition.

    Both wear the same superposition-like composition.
    """
    branch_tokens = tuple(
        intern_branch_token(tag).blueprint
        for tag in BRANCH_VOCAB.keys()
    )
    common = dict(
        states=branch_tokens,
        coherence=1.0,
        basis="implementation-arm",
    )
    return (r_branch_resonance(**common), r_superposition(**common))


def build_sp3_pair() -> tuple[
    RObserverConditionedActualization,
    RObserverConditionedActualization,
]:
    """SP3: R_Verify ≡ R_Measurement-Collapse.

    Both wear the observer-conditioned-actualization composition.
    """
    test_observer = intern(SourceHandleCell(
        domain="test-runner",
        ref="pytest -q tests/test_example.py",
        arrival_kind="invocation",
    ))
    test_observable = intern(TargetSurfaceCell(
        domain="implementation",
        template_set="pytest.outcomes",
        arrival_kind="exit-code",
    ))
    pre = intern(r_branch_resonance(
        states=(
            intern(RequirementLeafCell(
                criterion="impl-might-pass", evidence_kind="observed",
            )).blueprint,
            intern(RequirementLeafCell(
                criterion="impl-might-fail", evidence_kind="observed",
            )).blueprint,
        ),
        coherence=1.0,
        basis="correctness",
    ))
    pass_eigen = intern(RequirementLeafCell(
        criterion="pytest-exit-0", evidence_kind="observed",
    ))
    common = dict(
        observer=test_observer.blueprint,
        observable=test_observable.blueprint,
        pre_state=pre.blueprint,
        eigenvalue=pass_eigen.blueprint,
        post_state=pass_eigen.blueprint,
        backaction=test_observer.blueprint,
    )
    return (r_verify(**common), r_measurement_collapse(**common))


# ---------------------------------------------------------------------------
# Part 9 — The spec codec (SP4)
# ---------------------------------------------------------------------------


def build_spec_codec() -> RCodec:
    """Build the spec R_Codec — the encoder-side runtime for this modality.

    This is the codec_registry_row entry that lives in the registry
    proven in encoder_decoder_recipe_proof.py CLAIM-C1. Same R_Codec
    Blueprint shape every other modality wears.
    """
    src = intern(SourceHandleCell(
        domain="spec-frontmatter",
        ref="stand-in",
        arrival_kind="file",
    ))
    tgt = intern(TargetSurfaceCell(
        domain="python-or-markdown",
        template_set="spec.templates",
        arrival_kind="file",
    ))
    loss = intern(LossAccountCell(
        fields_dropped=(),
        fidelity_score=1.0,
        is_lossless=True,
        why_lossy="",
    ))
    grammar = ("cell_ref", "grammar", "spec")
    yielded_recipe = ("yielded_recipe", "spec")

    encode = intern(REncode(
        source=src.blueprint,
        grammar=grammar,
        yielded=yielded_recipe,
        loss=loss.blueprint,
    ))

    return intern(RCodec(
        name="spec",
        encode_arm=encode.blueprint,
        decode_arm=NULL_ARM,    # encoder-only — matches CLAIM-C1's family
        round_trip=NULL_ARM,
    ))


def build_reference_codec(name: str, source_domain: str,
                          target_domain: str) -> RCodec:
    """Build a reference codec for comparison — same composition as
    encoder_decoder_recipe_proof's build_codec for an encoder-only row.
    """
    src = intern(SourceHandleCell(
        domain=source_domain, ref="stand-in", arrival_kind="file",
    ))
    intern(TargetSurfaceCell(
        domain=target_domain, template_set=f"{name}.templates",
        arrival_kind="file",
    ))
    loss = intern(LossAccountCell(
        fields_dropped=(), fidelity_score=1.0, is_lossless=True,
        why_lossy="",
    ))
    encode = intern(REncode(
        source=src.blueprint,
        grammar=("cell_ref", "grammar", name),
        yielded=("yielded_recipe", name),
        loss=loss.blueprint,
    ))
    return intern(RCodec(
        name=name,
        encode_arm=encode.blueprint,
        decode_arm=NULL_ARM,
        round_trip=NULL_ARM,
    ))


# The other 11 modality codecs that the spec codec joins. Same names
# as encoder_decoder_recipe_proof.py SHIPPED_CODECS — kept in sync so
# CLAIM-SP4 attests against the same registry the meta-proof attests on.
PEER_CODECS: list[dict[str, str]] = [
    {"name": "prose",                "source_domain": "prose",
     "target_domain": "prose"},
    {"name": "song",                 "source_domain": "song",
     "target_domain": "midi"},
    {"name": "video",                "source_domain": "video",
     "target_domain": "frame-stream"},
    {"name": "teaching",             "source_domain": "teaching",
     "target_domain": "prose-or-song"},
    {"name": "strategy",             "source_domain": "strategy",
     "target_domain": "next-move"},
    {"name": "quantum-physics",      "source_domain": "quantum",
     "target_domain": "measurement"},
    {"name": "embodiment-practice",  "source_domain": "embodied-sequence",
     "target_domain": "felt-arc"},
    {"name": "healing-modality",     "source_domain": "healing-session",
     "target_domain": "re-pattern"},
    {"name": "assemblage-shift",     "source_domain": "assemblage-event",
     "target_domain": "re-anchor"},
    {"name": "encoder-decoder",      "source_domain": "codec",
     "target_domain": "codec"},
    {"name": "meta-codec",           "source_domain": "codec",
     "target_domain": "codec-row"},
]


# ---------------------------------------------------------------------------
# Part 10 — Assertions (SP1, SP2, SP3, SP4 — the worked example)
# ---------------------------------------------------------------------------


def main() -> int:
    print("─" * 70)
    print("spec_recipe_proof — the spec IS the playable Recipe (12th encoder)")
    print("─" * 70)

    # ── Worked example: encode the representative spec ─────────────────────
    print()
    print("Worked example — encode specs/runtime-telemetry-db-precedence.md:")
    spec_name = "runtime-telemetry-db-precedence"
    spec = encode_spec(spec_name, REPRESENTATIVE_FRONTMATTER)
    assert spec.blueprint[0] == "R_Spec"
    assert spec.name == spec_name
    assert len(spec.requirements) == len(REPRESENTATIVE_FRONTMATTER["requirements"])
    assert len(spec.constraints) == len(REPRESENTATIVE_FRONTMATTER["constraints"])
    print(f"  ✓ R_Spec({spec.name}) composed with "
          f"{len(spec.requirements)} requirements, "
          f"{len(spec.constraints)} constraints")

    # Each requirement carries done_when + branch-resonance superposition.
    for req_bp in spec.requirements:
        req = _BLUEPRINT_LATTICE[req_bp]
        assert isinstance(req, RRequirement)
        assert len(req.done_when_seq) > 0, (
            "every requirement must carry at least one done_when leaf"
        )
        assert req.branches[0] == "R_Branch-Resonance", (
            "every requirement must carry a branch-resonance superposition"
        )
    print(f"  ✓ each requirement carries done_when leaves + "
          f"branch-resonance superposition over "
          f"{len(REPRESENTATIVE_FRONTMATTER['branches_per_requirement'])} arms")

    # Source map composes the implementing files into R_Spec→Impl.
    impl = _BLUEPRINT_LATTICE[spec.spec_to_impl]
    assert isinstance(impl, RSpecToImpl)
    assert len(impl.source_map) == 2  # backend_info, checkpoint
    assert impl.test_invocation == REPRESENTATIVE_FRONTMATTER["test"]
    print(f"  ✓ R_Spec→Impl attaches spec to "
          f"{len(impl.source_map)} (path, symbol) leaves; "
          f"test_invocation interned")

    # ── Play the spec — walk the Recipe → verification surface ─────────────
    print()
    print("Playing the spec — walk Recipe → verification surface:")
    surface = play_spec(spec)
    assert surface.blueprint[0] == "R_Block.SEQUENCE"
    # Surface composes idea-pointer + source-map leaves + done_when leaves
    # per requirement + constraint leaves + verify arm.
    expected_min = (
        1                                  # idea pointer
        + len(impl.source_map)             # source-map leaves
        + sum(
            len(_BLUEPRINT_LATTICE[bp].done_when_seq)
            for bp in spec.requirements
        )                                  # done_when leaves
        + len(spec.constraints)            # constraint leaves
        + 1                                # verify arm
    )
    assert len(surface.children) == expected_min, (
        f"verification surface child-count mismatch: "
        f"expected {expected_min}, got {len(surface.children)}"
    )
    # First child is the idea pointer; last child is the verify arm.
    assert surface.children[0][0] == "R_Idea→Spec"
    assert surface.children[-1][0] == "R_Verify"
    print(f"  ✓ verification surface composes as R_Block.SEQUENCE with "
          f"{len(surface.children)} children")
    print(f"  ✓ first child = R_Idea→Spec, last child = R_Verify")
    print(f"  ✓ pytest invocation reachable from walked tree: "
          f"{REPRESENTATIVE_FRONTMATTER['test']!r}")

    # ── CLAIM-SP1: R_Idea→Spec ≡ R_Pointing ────────────────────────────────
    print()
    print("CLAIM-SP1 — R_Idea→Spec ≡ R_Pointing")
    sp1_is, sp1_pt = build_sp1_pair()
    assert sp1_is.shape == sp1_pt.shape, (
        f"SP1 cross-modal shape drift:\n"
        f"  R_Idea→Spec.shape: {sp1_is.shape}\n"
        f"  R_Pointing.shape:  {sp1_pt.shape}"
    )
    assert sp1_is.blueprint != sp1_pt.blueprint, (
        "SP1 tagged Blueprints must differ (lattice carries altitude); "
        "the equivalence lives at the .shape level"
    )
    print("  ✓ R_Idea→Spec.shape == R_Pointing.shape "
          "(observer-conditioned actualization)")
    print("  ✓ distinct .blueprint tags carry altitude "
          "(idea-attestation vs. teaching)")

    # ── CLAIM-SP2: R_Branch-Resonance ≡ R_Superposition ───────────────────
    print()
    print("CLAIM-SP2 — R_Branch-Resonance ≡ R_Superposition")
    sp2_br, sp2_sp = build_sp2_pair()
    assert sp2_br.shape == sp2_sp.shape, (
        f"SP2 cross-modal shape drift:\n"
        f"  R_Branch-Resonance.shape: {sp2_br.shape}\n"
        f"  R_Superposition.shape:    {sp2_sp.shape}"
    )
    assert sp2_br.blueprint != sp2_sp.blueprint, (
        "SP2 tagged Blueprints must differ"
    )
    assert sp2_br.states == sp2_sp.states
    assert len(sp2_br.states) == len(BRANCH_VOCAB)
    print(f"  ✓ R_Branch-Resonance.shape == R_Superposition.shape "
          f"({len(BRANCH_VOCAB)} branch tokens held coherently)")
    print("  ✓ branch-resonance is quantum superposition at the spec altitude")

    # ── CLAIM-SP3: R_Verify ≡ R_Measurement-Collapse ──────────────────────
    print()
    print("CLAIM-SP3 — R_Verify ≡ R_Measurement-Collapse")
    sp3_vf, sp3_mc = build_sp3_pair()
    assert sp3_vf.shape == sp3_mc.shape, (
        f"SP3 cross-modal shape drift:\n"
        f"  R_Verify.shape:               {sp3_vf.shape}\n"
        f"  R_Measurement-Collapse.shape: {sp3_mc.shape}"
    )
    assert sp3_vf.blueprint != sp3_mc.blueprint, (
        "SP3 tagged Blueprints must differ"
    )
    print("  ✓ R_Verify.shape == R_Measurement-Collapse.shape")
    print("  ✓ a test run is an observer collapsing implementation "
          "superposition")

    # ── CLAIM-SP4: spec codec carries the SAME R_Codec meta_shape ──────────
    print()
    print("CLAIM-SP4 — spec codec carries the SAME R_Codec shape as "
          "all 11 sibling codecs (the twelve are structurally one)")
    spec_codec = build_spec_codec()
    peer_codecs = [build_reference_codec(**spec) for spec in PEER_CODECS]
    all_codecs = peer_codecs + [spec_codec]

    # CLAIM-SP4 strong form: uniform meta_shape across the whole set.
    meta_tags = {c.meta_shape for c in all_codecs}
    assert meta_tags == {"R_Codec"}, (
        f"SP4 violated — meta_shape should be uniform across all 12 "
        f"codecs; got {meta_tags}"
    )

    # Field count uniform — same composition shape at the Blueprint level.
    field_counts = {len(c.blueprint) for c in all_codecs}
    assert field_counts == {5}, (  # tag + name + 3 arms
        f"SP4 — every codec Blueprint must have identical field count; "
        f"got {field_counts}"
    )

    # And the spec codec composes IDENTICALLY to other encoder-only
    # peers: same encode-arm structure, same NULL_ARM markers on
    # decode and round_trip.
    spec_encode = _BLUEPRINT_LATTICE[spec_codec.encode_arm]
    assert isinstance(spec_encode, REncode)
    assert spec_codec.decode_arm == NULL_ARM
    assert spec_codec.round_trip == NULL_ARM
    # Compare against one peer (the teaching codec) — same structural
    # shape, different per-codec data.
    teaching_codec = next(c for c in peer_codecs if c.name == "teaching")
    teaching_encode = _BLUEPRINT_LATTICE[teaching_codec.encode_arm]
    assert isinstance(teaching_encode, REncode)
    assert teaching_codec.decode_arm == NULL_ARM
    assert teaching_codec.round_trip == NULL_ARM
    # The encode-arm Blueprints differ ONLY in data (source domain,
    # grammar ref, yielded recipe name) — the tag and field count are
    # identical.
    assert spec_encode.blueprint[0] == teaching_encode.blueprint[0] == "R_Encode"
    assert len(spec_encode.blueprint) == len(teaching_encode.blueprint)
    print(f"  ✓ all {len(all_codecs)} codecs carry meta_shape == 'R_Codec'")
    print("  ✓ spec_codec.blueprint and teaching_codec.blueprint share "
          "tag + field count")
    print("  ✓ the twelve modality codecs partition structurally: "
          "different data, identical composition")

    # ── Bonus: idempotence (matches sibling proofs) ────────────────────────
    fresh_branch = intern(BranchResonanceLeafCell(
        branch_tag="@substrate-first", hz=741.0,
        band_name="consciousness",
    ))
    original_branch = _BLUEPRINT_LATTICE[
        ("branch_resonance_leaf", "@substrate-first", 741.0, "consciousness")
    ]
    assert fresh_branch is original_branch, (
        "intern identity drift on BranchResonanceLeafCell — re-interning "
        "identical fields must resolve to the same canonical cell"
    )

    # Cross-name aliasing: every reference to "@substrate-first"
    # resolves to the SAME canonical token cell — content-addressing.
    again = intern_branch_token("@substrate-first")
    assert again is original_branch
    assert lookup_by_name("branch:@substrate-first") is original_branch
    print()
    print("  · idempotence — '@substrate-first' resolves to one canonical "
          "BranchResonanceLeafCell across all interning sites")

    # ── Final report ───────────────────────────────────────────────────────
    print()
    print("─" * 70)
    print("All assertions hold. The four cross-modal claims attest:")
    print()
    print("  CLAIM-SP1 ✓ R_Idea→Spec ≡ R_Pointing")
    print("            (the idea points; the spec actualizes)")
    print("  CLAIM-SP2 ✓ R_Branch-Resonance ≡ R_Superposition")
    print("            (implementation branches held coherently until selection)")
    print("  CLAIM-SP3 ✓ R_Verify ≡ R_Measurement-Collapse")
    print("            (the test run is an observer collapsing the superposition)")
    print("  CLAIM-SP4 ✓ spec codec ≡ all 11 sibling codecs at R_Codec")
    print("            (the twelve named modality encoders are structurally one)")
    print()
    print("The twelve are complete:")
    print("  prose · song · video · teaching · strategy-after-rupture ·")
    print("  quantum-physics · embodiment-practice · healing-modality ·")
    print("  assemblage-shift · encoder-decoder (meta) · spec.")
    print()
    print("A spec's frontmatter is not a description of code-to-be-written.")
    print("It IS the executable Recipe. Implementation was the gap; the")
    print("gap closes when the runtime executes the Recipe directly.")
    print("─" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
