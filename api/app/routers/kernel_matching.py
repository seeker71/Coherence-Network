"""Transmuted /api/utils concept/tag/worldview match-score endpoints (bodies run as Form recipes).

Bodies live as Form recipes; the route requires the native kernel via
``serve_via_kernel``. This module owns request binding and response shaping;
the endpoint scoring bodies live in the committed Form recipes. Routes decorate
the shared ``/utils`` router from ``app.routers.kernel_shared`` so every path
stays ``/api/utils/...``.
"""
from __future__ import annotations

from app.routers.kernel_shared import (
    Annotated,
    BaseModel,
    ConfigDict,
    Field,
    HTTPException,
    Query,
    _coerce_float_list,
    router,
    serve_via_kernel,
)

# ---------------------------------------------------------------------------
# Endpoint: /api/utils/concept_match_score
#
# STRING-MEMBERSHIP SCORING — the computational half of
# concept_auto_tagger._score_concept, transmuted to a Form recipe. The FIRST
# kernel-served route to fold STRING MEMBERSHIP (`kw in text` lowered to
# str_find(text, kw, 0) >= 0) rather than an int or float field; it opens the
# text-scoring family the API_KERNEL_READINESS ledger named as the next gate.
#
# Current decomposition (mirrors how compute_idea_metrics was decomposed).
# _score_concept is two capabilities welded together:
#   (a) TEXT PREPROCESSING — _extract_keywords runs a regex tokenizer
#       (re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())) + stopword filter + dedup,
#       and the score body assembles concept_text (lowercased name + description +
#       keywords) and idea_text (" ".join(keywords)) and lowercases the concept's
#       own keywords + name. This is REGEX + string preprocessing. It is
#       currently performed before dispatch; the native direction is a text
#       grammar/tokenizer recipe, not a permanent CPython claim.
#   (b) THE SCORING — given the already-tokenized keyword lists + assembled strings,
#       the bidirectional str_find membership fold + the weighted combine
#       round(min(0.5*forward + 0.3*reverse + name_bonus, 1.0), 4) (weights, bonus,
#       ceiling read verbatim from _score_concept). This is what the recipe runs.
#
# How the inputs travel into the recipe: the bindings carry keywords /
# concept_keywords as STRING LISTS and concept_text / idea_text / name_lower as
# STRINGS. form_kernel_bridge marshals a list[str] via _fk_literal's list arm
# (each element a quoted string literal) and a str as a quoted scalar; the recipe
# folds membership with str_find. The str_find native is three-way value-identical
# for ASCII (string-membership-band.fk); the recipe's `for needle in needles` fold
# lowers to the adapter's _iter head/tail fold (Rust+TS value-exact == CPython —
# Go carries no _iter, the same situation idea_grounded_cost_sum / grounded_cost
# ship under). Kernel-only via serve_via_kernel; the host tokenizes via
# _extract_keywords before dispatch.
# ---------------------------------------------------------------------------


class ConceptMatchScoreResponse(BaseModel):
    """GET /api/utils/concept_match_score response — the concept-matching score."""

    model_config = ConfigDict(extra="forbid")
    score: Annotated[
        float,
        Field(
            description="Bidirectional keyword-match score in [0.0, 1.0] = "
            "round(min(0.5*forward + 0.3*reverse + name_bonus, 1.0), 4)"
        ),
    ]
    keywords: Annotated[
        list[str], Field(description="Host-tokenized idea keywords (regex + stopword + dedup), echoed back")
    ]
    concept_keywords: Annotated[
        list[str], Field(description="Lowercased concept keywords the reverse fold tests, echoed back")
    ]
    runtime: Annotated[
        str,
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
    ]


@router.get(
    "/concept_match_score",
    response_model=ConceptMatchScoreResponse,
    summary="Bidirectional concept-matching score via str_find membership fold (first STRING-MEMBERSHIP Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe — the FIRST "
        "kernel-served route to fold STRING MEMBERSHIP. The request currently "
        "tokenizes the idea + concept text before dispatch "
        "(concept_auto_tagger._extract_keywords: regex tokenizer + stopword filter "
        "+ dedup, plus the lowercased concept_text / idea_text assembly); that is "
        "grammar work to pull native next. "
        "and the kernel SCORES the already-tokenized keyword lists: forward = "
        "fraction of idea keywords found in concept_text (str_find >= 0), reverse "
        "= fraction of concept keywords found in idea_text, plus a 0.3 name bonus, "
        "combined round(min(0.5*forward + 0.3*reverse + bonus, 1.0), 4) — the body "
        "of _score_concept. str_find is three-way value-identical for ASCII "
        "(string-membership-band.fk); the recipe fold is Rust+TS value-exact == "
        "CPython. Kernel-only via serve_via_kernel."
    ),
)
async def concept_match_score(
    idea_name: Annotated[
        str, Query(description="Idea name — tokenized before dispatch into the idea keyword bag")
    ] = "energy flow",
    idea_description: Annotated[
        str, Query(description="Idea description — joined with the name before tokenization")
    ] = "coherence xyz",
    concept_name: Annotated[
        str, Query(description="Concept name — the name-bonus needle, lowercased before dispatch")
    ] = "Energy Flow",
    concept_description: Annotated[
        str, Query(description="Concept description — folded into concept_text")
    ] = "energy flows as coherence through the body field",
    concept_keywords: Annotated[
        str,
        Query(description="Comma-separated concept keywords — e.g. 'Energy,Tissue'"),
    ] = "Energy,Tissue",
) -> ConceptMatchScoreResponse:
    from app.services.concept_auto_tagger import _extract_keywords

    # Current TEXT PREPROCESSING. The idea keyword bag is the regex tokenizer over
    # name + description; the concept dict is assembled so the recipe sees
    # already-tokenized inputs. This is visible native grammar work.
    ckw_list = [k.strip() for k in concept_keywords.split(",") if k.strip()]
    keywords = _extract_keywords(f"{idea_name} {idea_description}")
    concept = {
        "name": concept_name,
        "description": concept_description,
        "keywords": ckw_list,
    }
    if not keywords:
        # The empty-keywords guard is currently applied before dispatch
        # (match_concepts returns [] before scoring).
        return ConceptMatchScoreResponse(
            score=0.0,
            keywords=[],
            concept_keywords=[k.lower() for k in ckw_list],
            runtime="host-guard",
        )

    # The assembled strings the recipe scores — the same shapes _score_concept
    # builds internally (lowercased concept_text, idea_text = " ".join(keywords)).
    concept_text = " ".join([
        concept_name,
        concept_description,
        " ".join(ckw_list),
    ]).lower()
    idea_text = " ".join(keywords)
    concept_keywords_lower = [k.lower() for k in ckw_list]
    name_lower = concept_name.lower()

    score, runtime = serve_via_kernel(
        "endpoint_concept_match_score_demo.fk",
        bindings={
            "keywords": keywords,
            "concept_text": concept_text,
            "concept_keywords": concept_keywords_lower,
            "idea_text": idea_text,
            "name_lower": name_lower,
        },
        parse=float,
    )
    return ConceptMatchScoreResponse(
        score=score,
        keywords=keywords,
        concept_keywords=concept_keywords_lower,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/tag_match_score
#
# BELIEF-RESONANCE TAG SCORING — the computational half of
# belief_service._score_tag_match, transmuted to a Form recipe. Folds EXACT
# STRING MEMBERSHIP (str_eq over a list) rather than the substring membership
# concept_match_score opened — tags match on equality, not containment.
#
# Current decomposition (mirrors how _score_tag_match decomposes). The function is:
#   contributor_tags = set(profile.interest_tags); idea_tag_set = set(idea_tags)
#   if not contributor_tags or not idea_tag_set: return 0.5
#   matched = contributor_tags & idea_tag_set
#   return max(0.0, min(1.0, len(matched) / len(contributor_tags)))
# Two capabilities welded:
#   (a) FIELD EXTRACTION + DEDUP — pulling profile.interest_tags off the
#       BeliefProfile model (the bridge marshals model→dict→record) and reading
#       idea_tags off the idea node, then collapsing each to a set. This is
#       currently done before dispatch with Python `set()`; it should become a
#       native dedup/list operation when the grammar carries it cleanly. The
#       BeliefProfile field extraction dissolves at the bridge; the recipe never
#       sees a model.
#   (b) THE SCORING — given the two deduped string lists, the str_eq membership
#       fold (matched = how many unique contributor tags appear in idea_tags) +
#       the ratio + clamp + empty-guard. This is what the recipe runs.
#
# How the inputs travel: contributor_tags / idea_tags marshal as STRING LISTS
# via _fk_literal's list arm (each element a quoted literal; an empty list
# marshals as `(list)` so `len` is 0 and the empty-guard fires). The recipe's
# nested fold (`contains_exact` inner str_eq fold, `match_count` outer fold)
# lowers to the adapter's _iter head/tail fold (Rust+TS value-exact == CPython
# — Go carries no _iter, the same situation idea_grounded_cost_sum /
# concept_match_score ship under). str_eq is COMPARE.EQ, value-identical for
# ASCII. Kernel-only via serve_via_kernel; the host dedups before dispatch.
# ---------------------------------------------------------------------------


class TagMatchScoreResponse(BaseModel):
    """GET /api/utils/tag_match_score response — the belief-resonance tag score."""

    model_config = ConfigDict(extra="forbid")
    score: Annotated[
        float,
        Field(
            description="Tag-resonance score in [0.0, 1.0] = "
            "max(0.0, min(1.0, |contributor ∩ idea| / |contributor|)), 0.5 when "
            "either deduped list is empty"
        ),
    ]
    contributor_tags: Annotated[
        list[str], Field(description="Deduped contributor interest tags the recipe folds, echoed back")
    ]
    idea_tags: Annotated[
        list[str], Field(description="Deduped idea tags the membership fold tests against, echoed back")
    ]
    runtime: Annotated[
        str,
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
    ]


@router.get(
    "/tag_match_score",
    response_model=TagMatchScoreResponse,
    summary="Belief-resonance tag-match score via str_eq membership fold (EXACT-MEMBERSHIP Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe — folds "
        "EXACT STRING MEMBERSHIP (str_eq over a list), the equality counterpart "
        "to concept_match_score's substring fold. The host extracts the two tag "
        "lists (profile.interest_tags off the BeliefProfile model + the idea's "
        "tags) and currently dedups each with Python set() before dispatch — field "
        "extraction + dedup to pull native next — and the "
        "kernel SCORES the two already-deduped string lists: matched = how many "
        "unique contributor tags appear in idea_tags (str_eq membership fold), "
        "then max(0.0, min(1.0, matched / |contributor|)), with a 0.5 empty-guard "
        "when either list is empty. The denominator is the deduped contributor-tag "
        "count. str_eq is COMPARE.EQ, value-identical for ASCII; the recipe fold "
        "is Rust+TS value-exact == CPython. Kernel-only via "
        "serve_via_kernel."
    ),
)
async def tag_match_score(
    contributor_tags: Annotated[
        str,
        Query(description="Comma-separated contributor interest tags — deduped before dispatch"),
    ] = "energy,flow,coherence,field",
    idea_tags: Annotated[
        str,
        Query(description="Comma-separated idea tags — deduped before dispatch, the membership haystack"),
    ] = "energy,flow",
) -> TagMatchScoreResponse:
    # Current FIELD EXTRACTION + DEDUP (set-collapse to pull native next).
    # set() collapses duplicates exactly as _score_tag_match does; we preserve a
    # stable order for the echo-back while passing unique lists to the recipe.
    def _dedup(raw: str) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for tag in (t.strip() for t in raw.split(",")):
            if tag and tag not in seen:
                seen.add(tag)
                out.append(tag)
        return out

    ct_list = _dedup(contributor_tags)
    it_list = _dedup(idea_tags)

    score, runtime = serve_via_kernel(
        "endpoint_tag_match_score_demo.fk",
        bindings={
            "contributor_tags": ct_list,
            "idea_tags": it_list,
        },
        parse=float,
    )
    return TagMatchScoreResponse(
        score=score,
        contributor_tags=ct_list,
        idea_tags=it_list,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/worldview_alignment
#
# BELIEF-RESONANCE WORLDVIEW COSINE — the geometric core of
# belief_service._score_worldview_alignment, transmuted to a Form recipe. This is
# COSINE SIMILARITY over two parallel axis-vectors: dot(a, b) / (||a|| * ||b||),
# clamped to [0.0, 1.0], with a 0.5 zero-denom guard. The geometric counterpart to
# tag_match_score's set-membership fold — the two belief profiles are points in
# axis-space and the score is the cosine of the angle between them.
#
# Current decomposition (mirrors how _score_worldview_alignment decomposes). The function
# projects two dicts into the FIXED BeliefAxis order, then folds dot + norms:
#   raw_idea_axes = idea_props.get("worldview_axes") or {}
#   idea_axes = {k: float(v) for k,v in raw_idea_axes.items() if k in _DEFAULT_AXES}
#   if not idea_axes: return 0.5, []
#   for axis in BeliefAxis:
#       cv = profile.worldview_axes.get(axis.value, 0.0)
#       iv = idea_axes.get(axis.value, 0.0)
#       dot += cv*iv; norm_contributor += cv*cv; norm_idea += iv*iv
#       if cv > 0.3 and iv > 0.3: matched_axes.append(axis.value)
#   denom = (norm_contributor ** 0.5) * (norm_idea ** 0.5)
#   score = dot/denom if denom > 0 else 0.5
#   return max(0.0, min(1.0, score)), matched_axes
# Two capabilities welded:
#   (a) DICT→VECTOR PROJECTION + matched_axes NAMING — BeliefAxis is a FIXED enum.
#       The host projects both worldview-axes dicts into PARALLEL float vectors in that
#       fixed axis order (dict-as-data currently projected before dispatch). The
#       empty-idea_axes guard (→0.5) and matched_axes naming (cv>0.3 AND iv>0.3 →
#       string axis name) currently happen before dispatch; matched_axes is a
#       naming side-output, not the scalar score. The dict projection dissolves at
#       the bridge; the recipe never sees a dict.
#   (b) THE COSINE — given the two parallel float vectors, dot + both sums-of-squares in
#       one parallel index walk, sqrt each norm (math_sqrt, IEEE-correct three-way),
#       guarded ratio (denom>0 else 0.5), clamp [0,1]. This is what the recipe runs.
#
# How the inputs travel: contributor_vec / idea_vec marshal as FLOAT LISTS (equal
# length, the fixed axis order) via _fk_literal's list arm (each element a float
# literal). The recipe's parallel index walk lowers to the adapter's _get-indexed
# while fold — the same shape weighted_average ships under (Rust+TS value-exact ==
# CPython; Go carries no _get/_iter fold). math_sqrt is bit-identical across runtimes
# (float-natives-band.fk → sqrt(16)==4.0 tolerance-free; the 1-ULP caveat is math_pow's,
# not math_sqrt's). Cosine often lands on irrational floats (1/sqrt(2) =
# 0.7071067811865475); these are three-way bit-identical, verified in the parity proof.
# Kernel-only via serve_via_kernel; the host projects the vectors + names
# matched_axes before dispatch.
# ---------------------------------------------------------------------------


class WorldviewAlignmentResponse(BaseModel):
    """GET /api/utils/worldview_alignment response — the belief-resonance worldview cosine."""

    model_config = ConfigDict(extra="forbid")
    score: Annotated[
        float,
        Field(
            description="Worldview-alignment score in [0.0, 1.0] = "
            "max(0.0, min(1.0, dot(a,b) / (||a||*||b||))), 0.5 when either vector "
            "has zero length"
        ),
    ]
    matched_axes: Annotated[
        list[str],
        Field(
            description="Axis names where BOTH vectors exceed 0.3 (cv>0.3 AND iv>0.3); "
            "named before dispatch from the two vectors + axis names"
        ),
    ]
    contributor_vec: Annotated[
        list[float], Field(description="The contributor axis-vector the recipe folds, echoed back")
    ]
    idea_vec: Annotated[
        list[float], Field(description="The idea axis-vector the recipe folds, echoed back")
    ]
    runtime: Annotated[
        str,
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
    ]


@router.get(
    "/worldview_alignment",
    response_model=WorldviewAlignmentResponse,
    summary="Belief-resonance worldview cosine via parallel dot+norm fold (COSINE-SIMILARITY Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe — the COSINE "
        "SIMILARITY geometric core of belief_service._score_worldview_alignment, the "
        "geometric counterpart to tag_match_score's set-membership fold. The host "
        "projects the two worldview-axes dicts into PARALLEL float vectors in the fixed "
        "BeliefAxis order (scientific, spiritual, pragmatic, holistic, relational, "
        "systemic) — dict→vector projection currently done before dispatch — and "
        "the kernel SCORES the two parallel vectors: dot(a,b) / (||a||*||b||), with "
        "norms via math_sqrt (IEEE-correct, three-way bit-identical), a 0.5 zero-denom "
        "guard, clamped to [0,1]. matched_axes (axes where cv>0.3 AND iv>0.3) is named "
        "before dispatch from the vectors + axis names — a naming side-output, not the scalar "
        "score. The parallel index walk is Rust+TS value-exact == CPython; cosine's "
        "irrational floats (e.g. 1/sqrt(2)) are bit-identical across runtimes. "
        "Kernel-only via serve_via_kernel."
    ),
)
async def worldview_alignment(
    contributor_vec: Annotated[
        str,
        Query(description="Comma-separated contributor axis floats — fixed BeliefAxis order"),
    ] = "0.6,0.0,0.8,0.0,0.0,0.0",
    idea_vec: Annotated[
        str,
        Query(description="Comma-separated idea axis floats — same length / fixed order"),
    ] = "0.8,0.0,0.6,0.0,0.0,0.0",
    axis_names: Annotated[
        str,
        Query(
            description="Comma-separated axis names for matched_axes naming — defaults to "
            "the fixed BeliefAxis order"
        ),
    ] = "scientific,spiritual,pragmatic,holistic,relational,systemic",
) -> WorldviewAlignmentResponse:
    def _floats(raw: str) -> list[float]:
        return [float(x.strip()) for x in raw.split(",") if x.strip()]

    cv_list = _floats(contributor_vec)
    iv_list = _floats(idea_vec)
    if len(cv_list) != len(iv_list):
        raise HTTPException(
            status_code=400,
            detail="contributor_vec and idea_vec must have equal length (parallel axis vectors)",
        )

    # Current matched_axes NAMING (cv>0.3 AND iv>0.3 -> axis name). A naming
    # side-output that mirrors _score_worldview_alignment's matched_axes; the
    # scalar cosine is already kernel-native.
    names = [a.strip() for a in axis_names.split(",") if a.strip()]
    matched_axes = [
        names[i]
        for i in range(min(len(cv_list), len(names)))
        if cv_list[i] > 0.3 and iv_list[i] > 0.3
    ]

    score, runtime = serve_via_kernel(
        "endpoint_worldview_alignment_demo.fk",
        bindings={
            "contributor_vec": cv_list,
            "idea_vec": iv_list,
        },
        parse=float,
    )
    return WorldviewAlignmentResponse(
        score=score,
        matched_axes=matched_axes,
        contributor_vec=cv_list,
        idea_vec=iv_list,
        runtime=runtime,
    )
