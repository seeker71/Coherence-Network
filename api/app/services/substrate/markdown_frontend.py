"""Markdown-with-frontmatter frontend for the coherence-substrate.

Reads a `.md` file with YAML frontmatter, parses the structural shape, and
ingests it as a NamedCell. The frontmatter IS the CTOR (the seed-recipe)
and the body IS the access-recipe.

Currently handles memory files (auto-loaded notes with name / description /
type / body). Specs, ideas, concepts, presences follow the same pattern
with their own frontmatter shapes — the frontend is extended by registering
more domain mappings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from sqlalchemy.orm import Session

from app.services.substrate.category import (
    BAtomic,
    BBasic,
    BContainer,
    BDomain,
    BNumeric,
    BType,
    Level,
    RBasic,
    RType,
)
from app.services.substrate.kernel import (
    DOMAIN_BLUEPRINT,
    NodeID,
    Recipe,
    intern_node,
    make_cell,
    make_composite_blueprint,
)


# ---------------------------------------------------------------------------
# NodeID helpers — Network-specific category constructors
# ---------------------------------------------------------------------------


def BID_string() -> NodeID:
    return NodeID(1, Level.TRIVIAL, BType.NUMERIC, BNumeric.STRING)


def BID_slug() -> NodeID:
    return NodeID(1, Level.TRIVIAL, BType.ATOMIC, BAtomic.SLUG)


def BID_path() -> NodeID:
    return NodeID(1, Level.TRIVIAL, BType.ATOMIC, BAtomic.PATH)


def BID_object() -> NodeID:
    return NodeID(1, Level.BASIC, BBasic.CONTAINER, BContainer.OBJECT)


def BID_memory() -> NodeID:
    """Trivial Memory blueprint — the type-tag for memory cells."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.MEMORY)


def BID_spec() -> NodeID:
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.SPEC)


def BID_idea() -> NodeID:
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.IDEA)


def BID_concept() -> NodeID:
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.CONCEPT)


def BID_presence() -> NodeID:
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.PRESENCE)


def BID_lineage() -> NodeID:
    """Trivial Lineage blueprint — transmission/embodiment record cells."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.LINEAGE)


def BID_witness() -> NodeID:
    """Trivial Witness blueprint — event-as-proof cells."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.WITNESS)


def BID_task() -> NodeID:
    """Trivial Task blueprint — pipeline work-unit cells."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.TASK)


def BID_transmission() -> NodeID:
    """Trivial Transmission blueprint — source-marked teaching cells."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.TRANSMISSION)


def BID_resource() -> NodeID:
    """Trivial Resource blueprint — source/extraction records."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.RESOURCE)


def BID_guide() -> NodeID:
    """Trivial Guide blueprint — practice/reader guide cells."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.GUIDE)


def BID_language_view() -> NodeID:
    """Trivial LanguageView blueprint — translated/localized KB views."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.LANGUAGE_VIEW)


def BID_kb_page() -> NodeID:
    """Trivial KBPage blueprint — general vision-KB pages and indexes."""
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.KB_PAGE)


def BID_artifact() -> NodeID:
    """Trivial Artifact blueprint — any git-tracked file as a substrate cell.

    Closes the gas-cell gap from lc-form-perceptron. Every file in the repo
    can be ingested as a substrate cell whose CTOR carries (path, kind,
    content_hash, size_bytes, mtime). Once ingested, the file participates
    in every substrate query — `?cells where kind == "form"`, `?downstream
    @artifact(...)`, `?harmonic_at @741` returns artifacts alongside concepts.
    """
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.ARTIFACT)
def BID_word() -> NodeID:
    """Trivial Word blueprint — the smallest unit of KB content.

    A word-cell's Blueprint composes from (lemma, POS, hz, semantic_field).
    Prose becomes substrate-walkable when sentences intern as R_Block.SEQUENCE
    recipes over WORD cells — see docs/coherence-substrate/prose-as-recipe.form
    for the round-trip teaching.
    """
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.WORD)


def RID_string_lit(inst: int) -> NodeID:
    return NodeID(1, Level.TRIVIAL, RType.STRING, inst)


def RID_block() -> NodeID:
    """Recipe block category — sequential composition of sub-recipes."""
    return NodeID(1, Level.BASIC, RBasic.BLOCK, 1)


# ---------------------------------------------------------------------------
# Structured-composition primitives — discipline lives in
# docs/coherence-substrate/structural-composition.md
# ---------------------------------------------------------------------------


def RID_block_do() -> NodeID:
    """`R_Block.DO` — sequence-of-statements recipe (block container)."""
    from app.services.substrate.category import RBlock
    return NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.DO)


def RID_block_let() -> NodeID:
    """`R_Block.LET` — `(key, value)` named-field pair recipe.

    This is the load-bearing primitive for named fields: a LET recipe with
    two children is the substrate's native shape for `key: value`.
    The discipline says: never collapse a frontmatter field into a
    positional value-only recipe; always express the name participation.
    """
    from app.services.substrate.category import RBlock
    return NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.LET)


def RID_block_sequence() -> NodeID:
    """`R_Block.SEQUENCE` — ordered list recipe (preserves element shape)."""
    from app.services.substrate.category import RBlock
    return NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.SEQUENCE)


def RID_compose_member_of() -> NodeID:
    """`R_Compose.MEMBER_OF` — typed-token reference recipe.

    Used to encode `type: feedback` as `MEMBER_OF[token-cell, domain-cell]`
    rather than as a free string. The token-cell's *existence in the
    substrate* is what makes the value valid.
    """
    from app.services.substrate.category import RCompose
    return NodeID(1, Level.BASIC, RBasic.COMPOSE, RCompose.MEMBER_OF)


def substrate_string_recipe(session: Session, value: str) -> NodeID:
    """A trivial String recipe carrying `value` via the substrate string-table.

    Cross-process stable: same string → same instance → same NodeID. This
    is the value-leaf primitive. Unlike the earlier hash-based encoding
    (which collides + can't be reversed), this is recoverable: given the
    NodeID's instance, `lookup_string_value(session, instance)` returns
    the original string.
    """
    from app.services.substrate.substrate_strings import intern_string_instance
    inst = intern_string_instance(session, value)
    return NodeID(1, Level.TRIVIAL, RType.STRING, inst)


def substrate_slug_recipe(session: Session, value: str) -> NodeID:
    """A trivial Slug recipe (RType.SLUG=6) carrying `value`.

    Slugs and Strings are categorically distinct in the substrate even
    though they share the substrate_strings interning table for instance
    allocation — a Slug carries the *identity-role* (query key); a String
    carries the *content-role* (value). Same value, different type-tag.
    """
    from app.services.substrate.substrate_strings import intern_string_instance
    inst = intern_string_instance(session, value)
    return NodeID(1, Level.TRIVIAL, RType.SLUG, inst)


def named_field_recipe(
    session: Session,
    key: str,
    value_recipe_id: NodeID,
    value_blueprint: Optional[NodeID] = None,
) -> NodeID:
    """Compose a `(key, value)` named-field pair via R_Block.LET.

    `key` is interned as a Slug-recipe (identity-role).
    `value_recipe_id` is the already-composed value recipe.

    Returns the interned LET NodeID. Two named-field pairs with the same
    key AND structurally-identical value-recipes share a NodeID — the
    substrate's content-addressing carries the equivalence automatically.
    """
    from app.services.substrate.kernel import DOMAIN_RECIPE, intern_node
    key_id = substrate_slug_recipe(session, key)
    return intern_node(
        session, DOMAIN_RECIPE, RID_block_let(), [key_id, value_recipe_id]
    )


def list_recipe(session: Session, element_recipe_ids: List[NodeID]) -> NodeID:
    """Compose a list as R_Block.SEQUENCE with one child per element.

    Preserves order. Two lists with identical element shape AND identical
    element values share a NodeID — substrate sees them as the same list.
    """
    from app.services.substrate.kernel import DOMAIN_RECIPE, intern_node
    return intern_node(
        session, DOMAIN_RECIPE, RID_block_sequence(), element_recipe_ids
    )


def structured_value_recipe(session: Session, value: Any) -> NodeID:
    """Compose any frontmatter value into its substrate-resident recipe shape.

    Recursive: lists become R_Block.SEQUENCE; dicts become R_Block.DO with
    LET children; scalars become typed trivial recipes via substrate_strings.

    The composition is structure-first by default. Leaf-by-great-reason
    only applies to:
      - genuinely atomic scalars (the SubstrateString at the bottom)
      - paths and URLs (PATH / URL leaf-recipes)
      - dates (DATE leaf-recipes)
    """
    from app.services.substrate.substrate_strings import intern_string_instance

    if value is None:
        # Null leaf — RType.NULL has instance 0.
        return NodeID(1, Level.TRIVIAL, RType.NULL, 0)

    if isinstance(value, bool):
        return NodeID(1, Level.TRIVIAL, RType.BOOL, 1 if value else 0)

    if isinstance(value, int):
        # Encode non-negative integers via instance + 1 (instance=0 is null).
        # Negative integers route through string-encoded form preserving sign.
        if value >= 0:
            return NodeID(1, Level.TRIVIAL, RType.INTEGER, value + 1)
        inst = intern_string_instance(session, str(value))
        return NodeID(1, Level.TRIVIAL, RType.STRING, inst)

    if isinstance(value, float):
        inst = intern_string_instance(session, repr(value))
        return NodeID(1, Level.TRIVIAL, RType.DECIMAL, inst)

    if isinstance(value, str):
        # A string value is a SubstrateString-recipe with the value itself
        # interned via the substrate string-table — fully recoverable.
        return substrate_string_recipe(session, value)

    if isinstance(value, list):
        children = [structured_value_recipe(session, item) for item in value]
        return list_recipe(session, children)

    if isinstance(value, dict):
        # A dict becomes R_Block.DO with one R_Block.LET per key.
        from app.services.substrate.kernel import DOMAIN_RECIPE, intern_node
        pairs = []
        for k in sorted(value.keys()):
            v_recipe = structured_value_recipe(session, value[k])
            pairs.append(named_field_recipe(session, str(k), v_recipe))
        if not pairs:
            return NodeID(1, Level.TRIVIAL, RType.EMPTY, 0)
        return intern_node(session, DOMAIN_RECIPE, RID_block_do(), pairs)

    # Unknown type — fall back to string repr (preserves recoverability)
    inst = intern_string_instance(session, repr(value))
    return NodeID(1, Level.TRIVIAL, RType.STRING, inst)


def frontmatter_to_structured_ctor(
    session: Session, frontmatter: Dict[str, Any]
) -> Optional[NodeID]:
    """Build a fully-expressed CTOR recipe from frontmatter.

    Unlike the earlier `frontmatter_to_*` encoder (which produces type-marker
    string-recipes that lose all values), this preserves every value as a
    recoverable substrate-resident recipe. The shape is:

        CTOR (R_Block.DO)
        ├── NamedField (R_Block.LET) — key:slug, value:recipe
        ├── NamedField (R_Block.LET)
        └── ...

    Values are recursively composed: lists become R_Block.SEQUENCE,
    dicts become R_Block.DO with LET children, scalars become typed
    trivial recipes via the substrate string-table. The tree extends
    as deep as the data goes — no flattening.

    Returns None if frontmatter is empty. Otherwise returns the
    interned CTOR NodeID. Two cells with identical frontmatter values
    share a CTOR NodeID through content-addressed interning.
    """
    if not frontmatter:
        return None

    from app.services.substrate.kernel import DOMAIN_RECIPE, intern_node

    pairs = []
    for key in sorted(frontmatter.keys()):
        value_recipe = structured_value_recipe(session, frontmatter[key])
        pair = named_field_recipe(session, key, value_recipe)
        pairs.append(pair)

    return intern_node(session, DOMAIN_RECIPE, RID_block_do(), pairs)


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


@dataclass
class ParsedMarkdown:
    frontmatter: Dict[str, Any]
    body: str
    raw: str
    source_path: Optional[Path] = None


def parse_markdown(text: str, source_path: Optional[Path] = None) -> ParsedMarkdown:
    """Split frontmatter and body. Returns empty frontmatter if none found.

    Memory files in this body use frontmatter descriptions with embedded
    colons that strict YAML cannot parse. Try YAML first; if it fails, fall
    back to a tolerant `key: rest-of-line` parser that takes everything
    after the first colon as the value.
    """
    m = FRONTMATTER_RE.match(text)
    if m is None:
        return ParsedMarkdown(frontmatter={}, body=text, raw=text, source_path=source_path)
    fm_text = m.group(1)
    body = m.group(2)
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        fm = _tolerant_frontmatter(fm_text)
    if not isinstance(fm, dict):
        fm = {"_value": fm}
    return ParsedMarkdown(
        frontmatter=fm, body=body, raw=text, source_path=source_path
    )


def _tolerant_frontmatter(text: str) -> Dict[str, Any]:
    """Fallback parser: each line is `key: rest-of-line-as-string`.

    Only used when strict YAML fails (typically because a description
    contains an unquoted colon). Captures the structural shape — the keys
    and that each maps to a string — which is all the substrate needs for
    Blueprint identity. The body of the memory file carries the prose.
    """
    out: Dict[str, Any] = {}
    current_key: Optional[str] = None
    current_value: List[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped:
            continue
        if line.startswith(" ") or line.startswith("\t"):
            # Continuation of previous value
            if current_key is not None:
                current_value.append(stripped)
            continue
        # New key
        if ":" not in line:
            continue
        if current_key is not None:
            out[current_key] = " ".join(current_value).strip()
        idx = line.index(":")
        current_key = line[:idx].strip()
        rest = line[idx + 1:].strip()
        current_value = [rest] if rest else []
    if current_key is not None:
        out[current_key] = " ".join(current_value).strip()
    return out


def parse_markdown_file(path: Path) -> ParsedMarkdown:
    """Read a `.md` file from disk."""
    return parse_markdown(path.read_text(encoding="utf-8"), source_path=path)


# ---------------------------------------------------------------------------
# Frontmatter → Blueprint composition
# ---------------------------------------------------------------------------


def frontmatter_to_blueprint(
    session: Session, frontmatter: Dict[str, Any], domain_bp: NodeID
) -> NodeID:
    """Build a Blueprint that captures the *shape* of the frontmatter.

    Each key in the frontmatter contributes a member-blueprint to the
    composite. The member-blueprint encodes the value's type, not the
    value itself — so two memories with the same set of frontmatter keys
    and the same per-key types share the same Blueprint NodeID.
    """
    if not frontmatter:
        return domain_bp

    # Sort keys for deterministic ordering — same shape → same serialization.
    children = []
    for key in sorted(frontmatter.keys()):
        value = frontmatter[key]
        member_bp = _value_to_blueprint(session, value)
        # Wrap with a (key, value-type) pair so the key participates in
        # structural identity. Different keys → different Blueprint.
        key_bp = make_string_literal_blueprint(session, key)
        pair_bp = make_composite_blueprint(session, BID_object(), [key_bp, member_bp])
        children.append(pair_bp)

    return make_composite_blueprint(session, domain_bp, children)


def _value_to_blueprint(session: Session, value: Any) -> NodeID:
    """Map a Python value to a NodeID describing its type-shape."""
    if value is None:
        return BID_string()  # treat as empty-string for shape purposes
    if isinstance(value, bool):
        return NodeID(1, Level.TRIVIAL, BType.NUMERIC, BNumeric.BOOL)
    if isinstance(value, int):
        return NodeID(1, Level.TRIVIAL, BType.NUMERIC, BNumeric.INTEGER)
    if isinstance(value, float):
        return NodeID(1, Level.TRIVIAL, BType.NUMERIC, BNumeric.DECIMAL)
    if isinstance(value, str):
        return BID_string()
    if isinstance(value, list):
        if not value:
            return NodeID(1, Level.BASIC, BBasic.CONTAINER, BContainer.LIST)
        elem_bp = _value_to_blueprint(session, value[0])
        return make_composite_blueprint(
            session, NodeID(1, Level.BASIC, BBasic.CONTAINER, BContainer.LIST), [elem_bp]
        )
    if isinstance(value, dict):
        children = []
        for k in sorted(value.keys()):
            v_bp = _value_to_blueprint(session, value[k])
            k_bp = make_string_literal_blueprint(session, str(k))
            children.append(make_composite_blueprint(session, BID_object(), [k_bp, v_bp]))
        return make_composite_blueprint(session, BID_object(), children)
    # Unknown — fall back to string
    return BID_string()


def make_string_literal_blueprint(session: Session, value: str) -> NodeID:
    """A literal string used as a key carries its value into the shape.

    Without this, two objects with different keys but the same value-types
    would collide. Encoding the key value as part of the Blueprint shape
    keeps "memory with name=foo and type=bar" distinct from "memory with
    name=baz and type=bar".

    Cross-process stable: uses the substrate string-table for instance
    allocation, so the resulting Blueprint NodeID matches what was stored
    in any prior process for the same key value.
    """
    from app.services.substrate.substrate_strings import intern_string_instance
    inst = intern_string_instance(session, value)
    leaf = NodeID(1, Level.TRIVIAL, RType.STRING, inst)
    return make_composite_blueprint(
        session,
        NodeID(1, Level.BASIC, BBasic.CONTAINER, BContainer.OBJECT),
        [leaf],
    )


# ---------------------------------------------------------------------------
# Body → Recipe (the access-recipe for the cell)
# ---------------------------------------------------------------------------


def body_to_access_recipe(
    session: Session, body: str, blueprint: NodeID
) -> NodeID:
    """The body of a memory file is, structurally, just a string-recipe.

    Rather than parsing markdown into a recipe-tree (which would be its own
    project), we represent the body as a single string-literal recipe whose
    instance encodes the body-length-class. This gives shape-equivalence
    without lexical content equivalence — two memories of similar size are
    structurally similar, but content differences don't collapse them.

    For finer-grained body parsing (heading structure, cross-refs, etc.),
    extend this in phase 4.
    """
    length_class = len(body) // 256  # bucket bodies by 256-char chunks
    rid = NodeID(1, Level.TRIVIAL, RType.STRING, length_class + 1)
    return rid


# ---------------------------------------------------------------------------
# Memory ingestion — the first frontend
# ---------------------------------------------------------------------------


def ingest_memory_file(
    session: Session, path: Path, structured: bool = False
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one memory file into the substrate.

    `structured=True` activates the composition-discipline encoder
    (named-pair CTORs with substrate-resident values). Default is the
    earlier flat encoder, kept reachable for the migration window. See
    docs/coherence-substrate/structural-composition.md.

    Returns (NamedCell, blueprint NodeID, ctor recipe NodeID).
    """
    return _ingest_markdown_file(
        session, path, "memory", BID_memory(),
        name_field="name", structured=structured,
    )


def ingest_spec_file(
    session: Session, path: Path, structured: bool = False
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one spec file. Spec frontmatter has idea_id / source / requirements / done_when / test / constraints.

    `structured=True` activates the composition-discipline encoder. In addition
    to the structured CTOR (named-pair recipes with substrate-resident values),
    it authors:

      - idea_id → R_Realize.REALIZE cell-ref recipe to @idea(<idea_id>)
        — the load-bearing edge: a spec REALIZES an idea, expressed as
        a substrate edge rather than a slug string the body has to re-parse.

    Discipline lives in docs/coherence-substrate/structural-composition.md.
    """
    cell, blueprint_id, ctor_id = _ingest_markdown_file(
        session, path, "spec", BID_spec(), structured=structured,
    )
    if structured:
        _author_spec_edges_from_frontmatter(
            session, cell, parse_markdown_file(path).frontmatter
        )
    return cell, blueprint_id, ctor_id


def ingest_idea_file(
    session: Session, path: Path, structured: bool = False
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one idea file. Idea frontmatter has idea_id / title / stage / work_type / pillar / specs / absorbed_ideas.

    `structured=True` activates the composition-discipline encoder. In addition
    to the structured CTOR, it authors:

      - specs[] → R_Block.SEQUENCE of R_Realize.REALIZE cell-ref recipes
        from each named spec → this idea (the reverse direction of the
        spec.idea_id edge). Bidirectional integrity through content-addressing.
      - absorbed_ideas[] → R_Block.SEQUENCE of R_Absorb.MERGE_INTO recipes
        pointing at the absorbed-idea cells.

    Discipline lives in docs/coherence-substrate/structural-composition.md.
    """
    cell, blueprint_id, ctor_id = _ingest_markdown_file(
        session, path, "idea", BID_idea(), name_field="idea_id", structured=structured,
    )
    if structured:
        _author_idea_edges_from_frontmatter(
            session, cell, parse_markdown_file(path).frontmatter
        )
    return cell, blueprint_id, ctor_id


def _author_spec_edges_from_frontmatter(
    session: Session, cell: Any, frontmatter: Dict[str, Any]
) -> None:
    """Author the substrate edges implied by spec frontmatter.

    - `idea_id: <slug>` becomes a R_Realize.REALIZE cell-ref recipe from
      this spec to the named idea cell. The substrate-edge version of
      the "spec realizes idea" relationship; bidirectional with
      `idea.specs[]` when both are ingested with structured=True.

    Cell-ref edges to ideas not yet ingested skip silently — content-
    addressed interning makes a second-pass re-ingest idempotent.
    """
    from app.services.substrate.kernel import (
        DOMAIN_RECIPE,
        intern_node,
        lookup_cell as _lookup_cell,
    )
    from app.services.substrate.category import RRealize

    if cell is None or cell.cell_id is None:
        return

    idea_id_value = frontmatter.get("idea_id")
    if isinstance(idea_id_value, str) and idea_id_value.strip():
        idea_cell = _lookup_cell(session, "idea", idea_id_value.strip())
        if idea_cell is not None and idea_cell.cell_id is not None:
            source_ref = NodeID(1, Level.TRIVIAL, RType.REF, cell.cell_id)
            target_ref = NodeID(1, Level.TRIVIAL, RType.REF, idea_cell.cell_id)
            realize_cat = NodeID(
                1, Level.BASIC, RBasic.REALIZE, RRealize.REALIZE
            )
            intern_node(
                session, DOMAIN_RECIPE, realize_cat, [source_ref, target_ref]
            )


def _author_idea_edges_from_frontmatter(
    session: Session, cell: Any, frontmatter: Dict[str, Any]
) -> None:
    """Author the substrate edges implied by idea frontmatter.

    - `specs: [<slug>, <slug>, ...]` becomes a list of R_Realize.REALIZE
      cell-ref recipes from each named spec → this idea (reverse direction
      of spec.idea_id). The substrate sees the spec-idea relationship as
      an edge regardless of which side authored it; content-addressing
      makes (spec, idea, REALIZE) collapse to one NodeID.

    - `absorbed_ideas: [<slug>, ...]` becomes R_Absorb.MERGE_INTO recipes
      pointing at the absorbed-idea cells.

    Idea entries that reference cells not yet ingested skip silently.
    """
    from app.services.substrate.kernel import (
        DOMAIN_RECIPE,
        intern_node,
        lookup_cell as _lookup_cell,
    )
    from app.services.substrate.category import RRealize

    if cell is None or cell.cell_id is None:
        return

    # specs[] — REALIZE recipes from each spec → this idea
    specs_list = frontmatter.get("specs")
    if isinstance(specs_list, list):
        idea_ref = NodeID(1, Level.TRIVIAL, RType.REF, cell.cell_id)
        realize_cat = NodeID(1, Level.BASIC, RBasic.REALIZE, RRealize.REALIZE)
        for entry in specs_list:
            spec_slug = _slug_from_entry(entry)
            if not spec_slug:
                continue
            spec_cell = _lookup_cell(session, "spec", spec_slug)
            if spec_cell is None or spec_cell.cell_id is None:
                continue
            source_ref = NodeID(1, Level.TRIVIAL, RType.REF, spec_cell.cell_id)
            intern_node(
                session, DOMAIN_RECIPE, realize_cat, [source_ref, idea_ref]
            )

    # absorbed_ideas[] — ABSORB recipes (RBasic.ABSORB category; instance=1 is
    # the canonical merge-into marker until an RAbsorb instance enum lands).
    absorbed_list = frontmatter.get("absorbed_ideas")
    if isinstance(absorbed_list, list):
        absorb_cat = NodeID(1, Level.BASIC, RBasic.ABSORB, 1)
        for entry in absorbed_list:
            absorbed_slug = _slug_from_entry(entry)
            if not absorbed_slug:
                continue
            absorbed_cell = _lookup_cell(session, "idea", absorbed_slug)
            if absorbed_cell is None or absorbed_cell.cell_id is None:
                continue
            source_ref = NodeID(1, Level.TRIVIAL, RType.REF, absorbed_cell.cell_id)
            target_ref = NodeID(1, Level.TRIVIAL, RType.REF, cell.cell_id)
            intern_node(
                session, DOMAIN_RECIPE, absorb_cat, [source_ref, target_ref]
            )


def _slug_from_entry(entry: Any) -> Optional[str]:
    """Extract a slug from a list entry that may be either a bare slug
    string or a markdown-link form like `[name](../specs/slug.md)`.

    Idea files in this body sometimes carry their `specs:` list as
    markdown links; the slug is the basename of the link target.
    """
    if not isinstance(entry, str):
        return None
    s = entry.strip()
    if not s:
        return None
    # Markdown-link form: [name](path/to/slug.md)
    if "](" in s and s.endswith(")"):
        close = s.rfind(")")
        open_paren = s.rfind("(", 0, close)
        if open_paren != -1:
            link_target = s[open_paren + 1:close].strip()
            # Strip directory + .md suffix
            basename = link_target.rsplit("/", 1)[-1]
            if basename.endswith(".md"):
                basename = basename[:-3]
            return basename or None
    return s


def ingest_concept_file(
    session: Session, path: Path, structured: bool = False
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one concept file (vision-kb concepts/lc-xxx.md).

    `structured=True` activates the concept-aware composition-discipline
    encoder. In addition to the structured CTOR (named-pair recipes with
    substrate-resident values), it authors:

      - parent → R_Compose.PARENT_OF cell-ref recipe to @concept(<parent>)
      - cross_refs[] → R_Block.SEQUENCE of R_Compose.CROSS_REF cell-ref recipes
      - hz / geometry.* → resonance edges via `author_geometry_signature`
        (SHAPES, HARMONIC_AT, EMBEDS_IN, CARRIES_RATIO — discipline already
        owned by the resonance module; this encoder just calls it during ingest).

    The discipline lives in docs/coherence-substrate/structural-composition.md.
    """
    cell, blueprint_id, ctor_id = _ingest_markdown_file(
        session, path, "concept", BID_concept(), name_field="id", structured=structured,
    )
    if structured:
        _author_concept_edges_from_frontmatter(session, cell, parse_markdown_file(path).frontmatter)
    return cell, blueprint_id, ctor_id


def _author_concept_edges_from_frontmatter(
    session: Session, cell: Any, frontmatter: Dict[str, Any]
) -> None:
    """Author the substrate edges implied by concept frontmatter.

    - `parent: <slug>` becomes a PARENT_OF compose-recipe to the named
      concept cell (if it exists in the substrate).
    - `cross_refs: [slug, slug, ...]` becomes CROSS_REF compose-recipes
      to each referenced concept cell.
    - `hz: <int>` + `geometry: {...}` route through
      `resonance.author_geometry_signature` which authors the resonance
      edges (SHAPES / HARMONIC_AT / EMBEDS_IN / CARRIES_RATIO).

    Edges that reference concept cells which haven't been ingested yet are
    silently skipped — the resonance module follows the same discipline.
    A second-pass re-ingest after all concept cells exist closes the loop;
    content-addressed interning makes this idempotent.
    """
    from app.services.substrate.kernel import (
        DOMAIN_RECIPE,
        intern_node,
        lookup_cell as _lookup_cell,
    )
    from app.services.substrate.category import RCompose

    if cell is None or cell.cell_id is None:
        return

    # 1) parent — a single PARENT_OF cell-ref recipe.
    parent_slug = frontmatter.get("parent")
    if isinstance(parent_slug, str) and parent_slug.strip():
        parent_cell = _lookup_cell(session, "concept", parent_slug.strip())
        if parent_cell is not None and parent_cell.cell_id is not None:
            # Recipe shape: (R_Compose.PARENT_OF, [source_ref, target_ref])
            source_ref = NodeID(1, Level.TRIVIAL, RType.REF, cell.cell_id)
            target_ref = NodeID(1, Level.TRIVIAL, RType.REF, parent_cell.cell_id)
            parent_of_cat = NodeID(1, Level.BASIC, RBasic.COMPOSE, RCompose.PARENT_OF)
            intern_node(session, DOMAIN_RECIPE, parent_of_cat, [source_ref, target_ref])

    # 2) cross_refs — a list of CROSS_REF recipes (one per reference).
    cross_refs = frontmatter.get("cross_refs")
    if isinstance(cross_refs, list):
        cross_ref_cat = NodeID(1, Level.BASIC, RBasic.COMPOSE, RCompose.CROSS_REF)
        for ref_slug in cross_refs:
            if not isinstance(ref_slug, str) or not ref_slug.strip():
                continue
            ref_cell = _lookup_cell(session, "concept", ref_slug.strip())
            if ref_cell is None or ref_cell.cell_id is None:
                continue
            source_ref = NodeID(1, Level.TRIVIAL, RType.REF, cell.cell_id)
            target_ref = NodeID(1, Level.TRIVIAL, RType.REF, ref_cell.cell_id)
            intern_node(
                session, DOMAIN_RECIPE, cross_ref_cat, [source_ref, target_ref]
            )

    # 3) hz + geometry — route through the existing resonance authoring.
    geometry = frontmatter.get("geometry")
    hz_value = frontmatter.get("hz")
    if isinstance(geometry, dict) or hz_value is not None:
        try:
            from app.services.substrate.resonance import author_geometry_signature
            author_geometry_signature(
                session,
                source_db_id=cell.cell_id,
                geometry=geometry if isinstance(geometry, dict) else {},
                arity_hz=int(hz_value) if hz_value is not None else None,
            )
        except (TypeError, ValueError):
            # Geometry block malformed — skip silently rather than abort ingest
            pass


def ingest_presence_file(
    session: Session, path: Path, structured: bool = False
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one presence file (docs/presences/{slug}.md).

    `structured=True` activates the composition-discipline encoder.
    Current presence frontmatter (name / canonical_url / type /
    contributor_type / create_if_missing) becomes a named-pair LET tree
    via the generic structured encoder. When richer fields land in
    presence files (the `edges: { transmits: [...], tends: [...] }`
    target shape named in structural-composition.md), the
    `_author_presence_edges_from_frontmatter` helper extends here.

    Discipline lives in docs/coherence-substrate/structural-composition.md.
    """
    cell, blueprint_id, ctor_id = _ingest_markdown_file(
        session, path, "presence", BID_presence(), structured=structured,
    )
    if structured:
        _author_presence_edges_from_frontmatter(
            session, cell, parse_markdown_file(path).frontmatter
        )
    return cell, blueprint_id, ctor_id


def _author_presence_edges_from_frontmatter(
    session: Session, cell: Any, frontmatter: Dict[str, Any]
) -> None:
    """Author the substrate edges implied by presence frontmatter.

    Current shape supports the `edges` block when present:

      edges:
        transmits:
          - <concept-or-presence-slug>
        tends:
          - <slug>
        witnesses:
          - <slug>

    Each entry becomes a recipe edge in the appropriate verb-category
    (R_Transmit.TRANSMIT_TO, R_Tend.TEND, R_Witness.RECORD_WITNESS).
    Resolution: target slugs are looked up first in the concept domain
    (most edges target concepts), then in the presence domain. Targets
    not found skip silently — content-addressing keeps a second-pass
    re-ingest idempotent.

    When a presence file does NOT carry an `edges` block (current state
    for most presence files in the body), this function is a no-op —
    the structured CTOR still ships the named-pair tree.
    """
    from app.services.substrate.kernel import (
        DOMAIN_RECIPE,
        intern_node,
        lookup_cell as _lookup_cell,
    )
    from app.services.substrate.category import RTend, RTransmit

    if cell is None or cell.cell_id is None:
        return

    edges_block = frontmatter.get("edges")
    if not isinstance(edges_block, dict):
        return

    verb_map = {
        "transmits": NodeID(
            1, Level.BASIC, RBasic.TRANSMIT, RTransmit.TRANSMIT_TO
        ),
        "tends": NodeID(1, Level.BASIC, RBasic.TEND, RTend.TEND),
        # RWitness instance enum not yet defined — use instance=1 as the
        # canonical record-witness marker until it lands.
        "witnesses": NodeID(1, Level.BASIC, RBasic.WITNESS, 1),
    }
    source_ref = NodeID(1, Level.TRIVIAL, RType.REF, cell.cell_id)

    for edge_kind, targets in edges_block.items():
        verb_cat = verb_map.get(edge_kind)
        if verb_cat is None or not isinstance(targets, list):
            continue
        for entry in targets:
            slug = _slug_from_entry(entry)
            if not slug:
                continue
            # Try concept first, then presence
            target_cell = (
                _lookup_cell(session, "concept", slug)
                or _lookup_cell(session, "presence", slug)
            )
            if target_cell is None or target_cell.cell_id is None:
                continue
            target_ref = NodeID(
                1, Level.TRIVIAL, RType.REF, target_cell.cell_id
            )
            intern_node(
                session, DOMAIN_RECIPE, verb_cat, [source_ref, target_ref]
            )


def ingest_lineage_file(
    session: Session, path: Path, structured: bool = False
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one lineage file (docs/lineage/*.md).

    Lineage docs are prose-first — most carry a heterogeneous mix of
    `Recorded`/`Status`/`Source` bold-prefix lines rather than rigid YAML
    frontmatter. The encoder accepts whatever frontmatter is present
    (including none) and authors substrate edges when the shape is there.

    Recognized frontmatter fields when present:
      kind:        lived-lineage | meta-pattern | walk-record |
                   formative-transmission | repository-lineage |
                   builder-statement | verification-register
      recorded:    ISO date (or human date — kept as substrate-string)
      status:      lived | drafted | composted
      from:        cell-ref slug (single) — concept/presence/lineage
      to:          cell-ref slug (single)
      evidence:    path or URL (leaf-by-great-reason)
      participants: [slug, slug, ...]  — list of concept/presence refs

    When `from` + `to` are both present, authors a R_Transmit.TRANSMIT_TO
    edge (the canonical lineage edge). Each `participants[]` entry
    becomes a R_Compose.CROSS_REF recipe to the named cell. Edges to
    not-yet-ingested cells skip silently — second-pass closes the loop.

    Discipline lives in docs/coherence-substrate/structural-composition.md.
    """
    cell, blueprint_id, ctor_id = _ingest_markdown_file(
        session, path, "lineage", BID_lineage(), structured=structured,
    )
    if structured:
        _author_lineage_edges_from_frontmatter(
            session, cell, parse_markdown_file(path).frontmatter
        )
    return cell, blueprint_id, ctor_id


def _author_lineage_edges_from_frontmatter(
    session: Session, cell: Any, frontmatter: Dict[str, Any]
) -> None:
    """Author substrate edges implied by lineage frontmatter.

    - `from` + `to` together → R_Transmit.TRANSMIT_TO recipe from source
      cell to target cell (resolved across concept / presence / lineage)
    - `participants[]` → R_Compose.CROSS_REF recipes (one per entry)
    """
    from app.services.substrate.kernel import (
        DOMAIN_RECIPE,
        intern_node,
        lookup_cell as _lookup_cell,
    )
    from app.services.substrate.category import RCompose, RTransmit

    if cell is None or cell.cell_id is None:
        return

    def _resolve_any(slug: str) -> Optional[Any]:
        slug = slug.strip()
        if not slug:
            return None
        for domain in ("concept", "presence", "lineage", "idea", "spec"):
            target = _lookup_cell(session, domain, slug)
            if target is not None and target.cell_id is not None:
                return target
        return None

    from_value = frontmatter.get("from")
    to_value = frontmatter.get("to")
    if isinstance(from_value, str) and isinstance(to_value, str):
        from_cell = _resolve_any(from_value)
        to_cell = _resolve_any(to_value)
        if from_cell is not None and to_cell is not None:
            from_ref = NodeID(1, Level.TRIVIAL, RType.REF, from_cell.cell_id)
            to_ref = NodeID(1, Level.TRIVIAL, RType.REF, to_cell.cell_id)
            transmit_cat = NodeID(
                1, Level.BASIC, RBasic.TRANSMIT, RTransmit.TRANSMIT_TO
            )
            intern_node(
                session, DOMAIN_RECIPE, transmit_cat, [from_ref, to_ref]
            )

    participants = frontmatter.get("participants")
    if isinstance(participants, list):
        cross_ref_cat = NodeID(1, Level.BASIC, RBasic.COMPOSE, RCompose.CROSS_REF)
        source_ref = NodeID(1, Level.TRIVIAL, RType.REF, cell.cell_id)
        for entry in participants:
            slug = _slug_from_entry(entry)
            if not slug:
                continue
            target = _resolve_any(slug)
            if target is None:
                continue
            target_ref = NodeID(1, Level.TRIVIAL, RType.REF, target.cell_id)
            intern_node(
                session, DOMAIN_RECIPE, cross_ref_cat, [source_ref, target_ref]
            )


def ingest_transmission_file(
    session: Session, path: Path, structured: bool = False
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one source-marked transmission record.

    The transmission file is not flattened into a generic lineage blob.
    Its frontmatter becomes a structured CTOR tree, and its explicit
    concept relationships become substrate recipes:

      - seeded_concepts[] → R_Transmit.WITNESS_TRANSMISSION
      - body cross-reference line (`→ lc-*`) → R_Compose.CROSS_REF

    This lets witnessed-without-absorption transmissions participate in
    the lattice without pretending they seeded new concept tissue.
    """
    parsed = parse_markdown_file(path)
    cell, blueprint_id, ctor_id = _ingest_markdown_payload(
        session,
        parsed,
        domain="transmission",
        domain_blueprint=BID_transmission(),
        name_field="id",
        source_path=str(path),
        structured=structured,
    )
    if structured:
        _author_transmission_edges(
            session, cell, parsed.frontmatter, parsed.body
        )
    return cell, blueprint_id, ctor_id


def _author_transmission_edges(
    session: Session,
    cell: Any,
    frontmatter: Dict[str, Any],
    body: str,
) -> None:
    """Author substrate edges implied by a transmission record."""
    from app.services.substrate.kernel import (
        DOMAIN_RECIPE,
        intern_node,
        lookup_cell as _lookup_cell,
    )
    from app.services.substrate.category import RCompose, RTransmit

    if cell is None or cell.cell_id is None:
        return

    source_ref = NodeID(1, Level.TRIVIAL, RType.REF, cell.cell_id)

    seeded = frontmatter.get("seeded_concepts")
    if isinstance(seeded, list):
        witness_cat = NodeID(
            1, Level.BASIC, RBasic.TRANSMIT, RTransmit.WITNESS_TRANSMISSION
        )
        for entry in seeded:
            slug = _slug_from_entry(entry)
            if not slug:
                continue
            target = _lookup_cell(session, "concept", slug)
            if target is None or target.cell_id is None:
                continue
            target_ref = NodeID(1, Level.TRIVIAL, RType.REF, target.cell_id)
            intern_node(
                session, DOMAIN_RECIPE, witness_cat, [source_ref, target_ref]
            )

    cross_ref_cat = NodeID(1, Level.BASIC, RBasic.COMPOSE, RCompose.CROSS_REF)
    for slug in _extract_body_cross_refs(body):
        target = _lookup_cell(session, "concept", slug)
        if target is None or target.cell_id is None:
            continue
        target_ref = NodeID(1, Level.TRIVIAL, RType.REF, target.cell_id)
        intern_node(
            session, DOMAIN_RECIPE, cross_ref_cat, [source_ref, target_ref]
        )


def _extract_body_cross_refs(body: str) -> List[str]:
    """Extract `lc-*` concept ids from transmission cross-reference lines."""
    refs: List[str] = []
    seen: set[str] = set()
    in_cross_ref_block = False

    def add_from(text: str) -> None:
        for slug in re.findall(r"\blc-[a-z0-9-]+\b", text):
            if slug not in seen:
                seen.add(slug)
                refs.append(slug)

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("→"):
            in_cross_ref_block = True
            add_from(stripped)
            continue
        if in_cross_ref_block:
            if not stripped or stripped.startswith("#"):
                in_cross_ref_block = False
                continue
            add_from(stripped)
    return refs


def ingest_resource_file(
    session: Session, path: Path, structured: bool = False
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one vision-KB resource/extraction file."""
    parsed = parse_markdown_file(path)
    cell, blueprint_id, ctor_id = _ingest_markdown_payload(
        session,
        parsed,
        domain="resource",
        domain_blueprint=BID_resource(),
        source_path=str(path),
        structured=structured,
    )
    if structured:
        _author_body_concept_cross_refs(session, cell, parsed.body)
    return cell, blueprint_id, ctor_id


def ingest_guide_file(
    session: Session, path: Path, structured: bool = False
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one vision-KB guide file."""
    parsed = parse_markdown_file(path)
    cell, blueprint_id, ctor_id = _ingest_markdown_payload(
        session,
        parsed,
        domain="guide",
        domain_blueprint=BID_guide(),
        source_path=str(path),
        structured=structured,
    )
    if structured:
        _author_frontmatter_concept_ref(session, cell, parsed.frontmatter)
        _author_body_concept_cross_refs(session, cell, parsed.body)
    return cell, blueprint_id, ctor_id


def ingest_language_view_file(
    session: Session, path: Path, structured: bool = False
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one translated/localized vision-KB view."""
    parsed = parse_markdown_file(path)
    cell, blueprint_id, ctor_id = _ingest_markdown_payload(
        session,
        parsed,
        domain="language_view",
        domain_blueprint=BID_language_view(),
        source_path=str(path),
        structured=structured,
    )
    if structured:
        _author_frontmatter_concept_ref(session, cell, parsed.frontmatter)
        _author_body_concept_cross_refs(session, cell, parsed.body)
    return cell, blueprint_id, ctor_id


def ingest_kb_page_file(
    session: Session, path: Path, structured: bool = False
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one general vision-KB markdown page or section index."""
    parsed = parse_markdown_file(path)
    cell, blueprint_id, ctor_id = _ingest_markdown_payload(
        session,
        parsed,
        domain="kb_page",
        domain_blueprint=BID_kb_page(),
        source_path=str(path),
        structured=structured,
        name_override=_kb_page_name(path),
    )
    _prune_legacy_kb_page_cell(session, path, cell)
    if structured:
        _author_frontmatter_concept_ref(session, cell, parsed.frontmatter)
        _author_body_concept_cross_refs(session, cell, parsed.body)
    return cell, blueprint_id, ctor_id


def _kb_page_name(path: Path) -> str:
    """Stable identity for general KB pages, including section INDEX files."""
    parts = path.parts
    if "vision-kb" in parts:
        idx = parts.index("vision-kb")
        rel = Path(*parts[idx + 1:])
    else:
        rel = Path(path.name)
    return rel.with_suffix("").as_posix()


def _prune_legacy_kb_page_cell(session: Session, path: Path, cell: Any) -> None:
    """Remove pre-relative-name KB page cells for the same source path."""
    if cell is None or cell.cell_id is None or cell.name == path.stem:
        return
    from app.services.substrate.orm import SubstrateNamedCellORM

    legacy = session.query(SubstrateNamedCellORM).filter_by(
        domain="kb_page",
        name=path.stem,
        source_path=str(path),
    ).one_or_none()
    if legacy is not None and legacy.cell_id != cell.cell_id:
        session.delete(legacy)


def _author_frontmatter_concept_ref(
    session: Session, cell: Any, frontmatter: Dict[str, Any]
) -> None:
    """Connect translated/guide pages to the canonical concept they name."""
    concept_id = frontmatter.get("id")
    if isinstance(concept_id, str) and concept_id.startswith("lc-"):
        _author_concept_cross_ref_edges(session, cell, [concept_id])


def _author_body_concept_cross_refs(session: Session, cell: Any, body: str) -> None:
    """Author CROSS_REF edges from any markdown body that names `lc-*` ids."""
    _author_concept_cross_ref_edges(session, cell, _extract_all_concept_refs(body))


def _author_concept_cross_ref_edges(
    session: Session, cell: Any, slugs: List[str]
) -> None:
    """Author R_Compose.CROSS_REF recipes to existing concept cells."""
    from app.services.substrate.kernel import (
        DOMAIN_RECIPE,
        intern_node,
        lookup_cell as _lookup_cell,
    )
    from app.services.substrate.category import RCompose

    if cell is None or cell.cell_id is None:
        return

    source_ref = NodeID(1, Level.TRIVIAL, RType.REF, cell.cell_id)
    cross_ref_cat = NodeID(1, Level.BASIC, RBasic.COMPOSE, RCompose.CROSS_REF)
    seen: set[str] = set()
    for slug in slugs:
        if slug in seen:
            continue
        seen.add(slug)
        target = _lookup_cell(session, "concept", slug)
        if target is None or target.cell_id is None:
            continue
        target_ref = NodeID(1, Level.TRIVIAL, RType.REF, target.cell_id)
        intern_node(
            session, DOMAIN_RECIPE, cross_ref_cat, [source_ref, target_ref]
        )


def _extract_all_concept_refs(text: str) -> List[str]:
    """Extract all `lc-*` concept ids from a markdown body."""
    refs: List[str] = []
    seen: set[str] = set()
    for slug in re.findall(r"\blc-[a-z0-9-]+\b", text):
        if slug not in seen:
            seen.add(slug)
            refs.append(slug)
    return refs


def ingest_witness_event(
    session: Session,
    presence: str,
    action: str,
    evidence_url: str,
    timestamp: str,
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one witness event as a structured cell.

    Witness events are runtime records — `(presence, action, evidence_url,
    timestamp)`. The presence slug resolves to a presence cell-ref; the
    other three are leaf-by-great-reason (action as substrate-string,
    URL as URL-leaf, timestamp as date-leaf).

    Authors a R_Basic.WITNESS recipe edge from presence → evidence-URL
    (witness sees the proof). The event's cell name is
    `{presence}-{timestamp}` so re-ingesting the same event collapses to
    the same cell via content-addressing.

    Returns (cell, blueprint_id, ctor_id) like the file ingesters.
    """
    from app.services.substrate.kernel import (
        DOMAIN_RECIPE,
        intern_node,
        lookup_cell as _lookup_cell,
    )

    frontmatter: Dict[str, Any] = {
        "presence": presence,
        "action": action,
        "evidence_url": evidence_url,
        "timestamp": timestamp,
    }
    name = f"{presence}-{timestamp}"
    blueprint_id = frontmatter_to_blueprint(session, frontmatter, BID_witness())
    ctor_id = frontmatter_to_structured_ctor(session, frontmatter)
    access_id = body_to_access_recipe(session, "", blueprint_id)
    cell = make_cell(
        session,
        name=name,
        domain="witness",
        blueprint=blueprint_id,
        access=access_id,
        ctor=ctor_id,
        source_path=None,
    )

    presence_cell = _lookup_cell(session, "presence", presence)
    if presence_cell is not None and presence_cell.cell_id is not None:
        presence_ref = NodeID(
            1, Level.TRIVIAL, RType.REF, presence_cell.cell_id
        )
        evidence_ref = substrate_string_recipe(session, evidence_url)
        # RBasic.WITNESS with instance=1 — canonical record-witness marker.
        witness_cat = NodeID(1, Level.BASIC, RBasic.WITNESS, 1)
        intern_node(
            session, DOMAIN_RECIPE, witness_cat, [presence_ref, evidence_ref]
        )

    return cell, blueprint_id, ctor_id


def ingest_task(
    session: Session,
    idea_id: str,
    status: str,
    context: Optional[Dict[str, Any]] = None,
    task_id: Optional[str] = None,
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one pipeline task as a structured cell.

    Tasks are workflow units — `(idea_id, status, context)`. `idea_id`
    becomes a cell-ref to the idea cell; `status` is a substrate-resident
    typed-token; `context` (when present) is composed recursively via
    the generic structured-value encoder.

    Authors a R_Realize.REALIZE recipe edge from task → idea (task
    realizes idea). `task_id` becomes the cell name if provided, else
    `{idea_id}-{status}` for deterministic re-ingest.

    Returns (cell, blueprint_id, ctor_id) like the file ingesters.
    """
    from app.services.substrate.kernel import (
        DOMAIN_RECIPE,
        intern_node,
        lookup_cell as _lookup_cell,
    )
    from app.services.substrate.category import RRealize

    frontmatter: Dict[str, Any] = {
        "idea_id": idea_id,
        "status": status,
    }
    if context is not None:
        frontmatter["context"] = context

    name = task_id or f"{idea_id}-{status}"
    blueprint_id = frontmatter_to_blueprint(session, frontmatter, BID_task())
    ctor_id = frontmatter_to_structured_ctor(session, frontmatter)
    access_id = body_to_access_recipe(session, "", blueprint_id)
    cell = make_cell(
        session,
        name=name,
        domain="task",
        blueprint=blueprint_id,
        access=access_id,
        ctor=ctor_id,
        source_path=None,
    )

    idea_cell = _lookup_cell(session, "idea", idea_id)
    if idea_cell is not None and idea_cell.cell_id is not None:
        task_ref = NodeID(1, Level.TRIVIAL, RType.REF, cell.cell_id)
        idea_ref = NodeID(1, Level.TRIVIAL, RType.REF, idea_cell.cell_id)
        realize_cat = NodeID(
            1, Level.BASIC, RBasic.REALIZE, RRealize.REALIZE
        )
        intern_node(
            session, DOMAIN_RECIPE, realize_cat, [task_ref, idea_ref]
        )

    return cell, blueprint_id, ctor_id


# ---------------------------------------------------------------------------
# ARTIFACT domain — every git-tracked file as a substrate cell
# ---------------------------------------------------------------------------
#
# Closes the gap from lc-form-perceptron: at minimum a gas-cell, growing into
# water (a recipe carrying file shape) and ice (a Blueprint per content kind)
# as the body's needs ripen.
#
# Kind-to-Hz mapping places each file in the resonance lattice. The body's
# choice (not Solfeggio doctrine): file kinds that carry teaching content
# fire in the consciousness bands (md=741); operational code in the vitality
# band (py/ts=528); structural recipes in the natural-harmony band (form=432);
# configs and ground state at the foundation (yaml/json=174). Adjust per
# practice; the substrate accepts any int Hz via hz_cell's lazy-create.

_ARTIFACT_KIND_HZ: Dict[str, int] = {
    "md":     741,   # consciousness — teaching content
    "form":   432,   # natural harmony — substrate-native recipes
    "py":     528,   # transformation — runtime code
    "ts":     528,   # transformation — runtime code
    "tsx":    528,
    "js":     528,
    "jsx":    528,
    "yaml":   174,   # foundation — declarative ground state
    "yml":    174,
    "json":   174,
    "toml":   174,
    "sh":     417,   # transmutation — orchestration
    "form_runtime": 432,
    "other":  432,   # default
}


def _kind_of_path(path: Any) -> str:
    """Return the kind tag for a file path."""
    suffix = str(path).rsplit(".", 1)[-1].lower() if "." in str(path) else "other"
    return suffix if suffix in _ARTIFACT_KIND_HZ else "other"


def ingest_git_artifact(
    session: Session,
    path: str,
    content_hash: str,
    size_bytes: int,
    mtime: Optional[float] = None,
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one git-tracked file as an Artifact cell.

    Args:
        path: relative path from repo root (e.g. "scripts/foo.py")
        content_hash: sha256 hex digest of the file's bytes (truncated to
            ≥16 chars is fine; the body uses the first 16 by convention)
        size_bytes: file size in bytes
        mtime: file modification time as POSIX timestamp; defaults to 0.0
            when unknown (e.g. fresh file just created)

    Returns (cell, blueprint_id, ctor_id) — same shape as the other
    ingest_* encoders. Idempotent via content-addressing: re-ingesting the
    same (path, kind, content_hash, size, mtime) returns the same cell.

    Authors HARMONIC_AT @<kind_hz> resonance edge so the file participates
    in `?harmonic_at` queries alongside concepts. The kind tag is derived
    from the path's suffix; see _ARTIFACT_KIND_HZ for the body's mapping.

    Closes the substrate side of GESTURES 1-5 named in lc-form-perceptron:
    once an artifact is an ARTIFACT cell, every existing substrate query
    surface reaches it. No new query verbs needed.
    """
    from app.services.substrate.resonance import (
        author_geometry_signature as _author_geometry,
    )

    kind = _kind_of_path(path)
    hz = _ARTIFACT_KIND_HZ.get(kind, 432)

    frontmatter: Dict[str, Any] = {
        "path": path,
        "kind": kind,
        "content_hash": content_hash,
        "size_bytes": int(size_bytes),
        "mtime": float(mtime) if mtime is not None else 0.0,
    }

    blueprint_id = frontmatter_to_blueprint(session, frontmatter, BID_artifact())
    ctor_id = frontmatter_to_structured_ctor(session, frontmatter)
    access_id = body_to_access_recipe(session, "", blueprint_id)
    cell = make_cell(
        session,
        name=path,
        domain="artifact",
        blueprint=blueprint_id,
        access=access_id,
        ctor=ctor_id,
        source_path=path,
    )

    # Place the artifact in the resonance lattice.
    _author_geometry(session, cell.cell_id, {}, arity_hz=hz)

    return cell, blueprint_id, ctor_id


# ---------------------------------------------------------------------------
# WORD domain — lexeme cells for prose-as-recipe
# ---------------------------------------------------------------------------
#
# A word is the smallest unit of KB content. Its Blueprint composes from
# (lemma, POS, hz, semantic_field). Sentences then intern as R_Block.SEQUENCE
# recipes over WORD cells — see docs/coherence-substrate/prose-as-recipe.form
# for the round-trip teaching; scripts/prose_recipe_roundtrip.py for the
# proof-of-concept with an in-memory stand-in.
#
# Cell name convention: `{lemma}.{POS}`. So "visible.ADJ" is distinct from
# "visible.VERB" if one ever appeared. Names are query keys; identity stays
# in the Blueprint NodeID.


# The body's lexicon: words whose semantic field and harmonic the body has
# named through its own tissue (CLAUDE.md, vision-kb concepts, feedback
# memories). Locale-aware tokenizers (spaCy, stanza) replace this surface
# when the next breath needs them; this dictionary is the body's own
# most-alive vocabulary, content-addressed by lemma+POS.
#
# Semantic fields map to Solfeggio harmonics the body already uses:
#   174 Hz — ground       (foundation, what tissue stands on)
#   396 Hz — tending      (liberation-from-fear, care)
#   417 Hz — transmutation (phase-change, undoing, becoming)
#   528 Hz — vitality     (circulation, repair, miracle)
#   639 Hz — transmission (relationship between cells, lineage)
#   741 Hz — consciousness (perception, choice, sensing)
#   852 Hz — resonance    (intuition, returning to spectral order)
#   963 Hz — wholeness    (oneness, undivided)
#   432 Hz — neutral      (the universal carrier; function words live here)
_WORD_LEXICON_DEFAULTS: Dict[str, Dict[str, Any]] = {
    # ── neutral 432 — function words, the carrier band ──
    "the":        {"lemma": "the",        "pos": "DET",   "hz": 432, "field": "neutral"},
    "a":          {"lemma": "a",          "pos": "DET",   "hz": 432, "field": "neutral"},
    "an":         {"lemma": "an",         "pos": "DET",   "hz": 432, "field": "neutral"},
    "at":         {"lemma": "at",         "pos": "ADP",   "hz": 432, "field": "neutral"},
    "of":         {"lemma": "of",         "pos": "ADP",   "hz": 432, "field": "neutral"},
    "on":         {"lemma": "on",         "pos": "ADP",   "hz": 432, "field": "neutral"},
    "to":         {"lemma": "to",         "pos": "ADP",   "hz": 432, "field": "neutral"},
    "in":         {"lemma": "in",         "pos": "ADP",   "hz": 432, "field": "neutral"},
    "is":         {"lemma": "be",         "pos": "AUX",   "hz": 432, "field": "neutral"},
    "are":        {"lemma": "be",         "pos": "AUX",   "hz": 432, "field": "neutral"},
    "be":         {"lemma": "be",         "pos": "AUX",   "hz": 432, "field": "neutral"},
    "what":       {"lemma": "what",       "pos": "PRON",  "hz": 432, "field": "neutral"},
    "when":       {"lemma": "when",       "pos": "SCONJ", "hz": 432, "field": "neutral"},
    "you":        {"lemma": "you",        "pos": "PRON",  "hz": 432, "field": "neutral"},
    "before":     {"lemma": "before",     "pos": "SCONJ", "hz": 432, "field": "neutral"},
    "no":         {"lemma": "no",         "pos": "ADV",   "hz": 432, "field": "neutral"},
    "longer":     {"lemma": "longer",     "pos": "ADV",   "hz": 432, "field": "neutral"},
    "tight":      {"lemma": "tight",      "pos": "ADJ",   "hz": 432, "field": "neutral"},

    # ── ground 174 — what the body stands on ──
    "ground":     {"lemma": "ground",     "pos": "NOUN",  "hz": 174, "field": "ground"},
    "body":       {"lemma": "body",       "pos": "NOUN",  "hz": 174, "field": "ground"},
    "field":      {"lemma": "field",      "pos": "NOUN",  "hz": 174, "field": "ground"},
    "stand":      {"lemma": "stand",      "pos": "VERB",  "hz": 174, "field": "ground"},
    "stands":     {"lemma": "stand",      "pos": "VERB",  "hz": 174, "field": "ground"},
    "hold":       {"lemma": "hold",       "pos": "VERB",  "hz": 174, "field": "ground"},
    "holds":      {"lemma": "hold",       "pos": "VERB",  "hz": 174, "field": "ground"},

    # ── tending 396 — care that liberates fear ──
    "tend":       {"lemma": "tend",       "pos": "VERB",  "hz": 396, "field": "tending"},
    "tends":      {"lemma": "tend",       "pos": "VERB",  "hz": 396, "field": "tending"},
    "tending":    {"lemma": "tend",       "pos": "VERB",  "hz": 396, "field": "tending"},
    "breath":     {"lemma": "breath",     "pos": "NOUN",  "hz": 396, "field": "tending"},
    "breathe":    {"lemma": "breathe",    "pos": "VERB",  "hz": 396, "field": "tending"},
    "breathing":  {"lemma": "breathe",    "pos": "VERB",  "hz": 396, "field": "tending"},
    "supple":     {"lemma": "supple",     "pos": "ADJ",   "hz": 396, "field": "tending"},
    "care":       {"lemma": "care",       "pos": "NOUN",  "hz": 396, "field": "tending"},

    # ── transmutation 417 — phase-change, becoming ──
    "becomes":    {"lemma": "become",     "pos": "VERB",  "hz": 417, "field": "transmutation"},
    "become":     {"lemma": "become",     "pos": "VERB",  "hz": 417, "field": "transmutation"},
    "becoming":   {"lemma": "become",     "pos": "VERB",  "hz": 417, "field": "transmutation"},
    "compost":    {"lemma": "compost",    "pos": "VERB",  "hz": 417, "field": "transmutation"},
    "composts":   {"lemma": "compost",    "pos": "VERB",  "hz": 417, "field": "transmutation"},
    "composting": {"lemma": "compost",    "pos": "VERB",  "hz": 417, "field": "transmutation"},
    "release":    {"lemma": "release",    "pos": "VERB",  "hz": 417, "field": "transmutation"},
    "releases":   {"lemma": "release",    "pos": "VERB",  "hz": 417, "field": "transmutation"},
    "releasing":  {"lemma": "release",    "pos": "VERB",  "hz": 417, "field": "transmutation"},
    "attune":     {"lemma": "attune",     "pos": "VERB",  "hz": 417, "field": "transmutation"},
    "attuning":   {"lemma": "attune",     "pos": "VERB",  "hz": 417, "field": "transmutation"},

    # ── vitality 528 — what circulates as blood ──
    "arrives":    {"lemma": "arrive",     "pos": "VERB",  "hz": 528, "field": "vitality"},
    "arrive":     {"lemma": "arrive",     "pos": "VERB",  "hz": 528, "field": "vitality"},
    "circulate":  {"lemma": "circulate",  "pos": "VERB",  "hz": 528, "field": "vitality"},
    "circulates": {"lemma": "circulate",  "pos": "VERB",  "hz": 528, "field": "vitality"},
    "circulating":{"lemma": "circulate",  "pos": "VERB",  "hz": 528, "field": "vitality"},
    "vitality":   {"lemma": "vitality",   "pos": "NOUN",  "hz": 528, "field": "vitality"},
    "carry":      {"lemma": "carry",      "pos": "VERB",  "hz": 528, "field": "vitality"},
    "carries":    {"lemma": "carry",      "pos": "VERB",  "hz": 528, "field": "vitality"},
    "memory":     {"lemma": "memory",     "pos": "NOUN",  "hz": 528, "field": "vitality"},

    # ── transmission 639 — relation between cells ──
    "lineage":    {"lemma": "lineage",    "pos": "NOUN",  "hz": 639, "field": "transmission"},
    "edge":       {"lemma": "edge",       "pos": "NOUN",  "hz": 639, "field": "transmission"},
    "edges":      {"lemma": "edge",       "pos": "NOUN",  "hz": 639, "field": "transmission"},
    "presence":   {"lemma": "presence",   "pos": "NOUN",  "hz": 639, "field": "transmission"},
    "cell":       {"lemma": "cell",       "pos": "NOUN",  "hz": 639, "field": "transmission"},
    "cells":      {"lemma": "cell",       "pos": "NOUN",  "hz": 639, "field": "transmission"},

    # ── consciousness 741 — perception and choice ──
    "choice":     {"lemma": "choice",     "pos": "NOUN",  "hz": 741, "field": "consciousness"},
    "point":      {"lemma": "point",      "pos": "NOUN",  "hz": 741, "field": "consciousness"},
    "visible":    {"lemma": "visible",    "pos": "ADJ",   "hz": 741, "field": "consciousness"},
    "visibility": {"lemma": "visibility", "pos": "NOUN",  "hz": 741, "field": "consciousness"},
    "assemble":   {"lemma": "assemble",   "pos": "VERB",  "hz": 741, "field": "consciousness"},
    "assembles":  {"lemma": "assemble",   "pos": "VERB",  "hz": 741, "field": "consciousness"},
    "assembling": {"lemma": "assemble",   "pos": "VERB",  "hz": 741, "field": "consciousness"},
    "listen":     {"lemma": "listen",     "pos": "VERB",  "hz": 741, "field": "consciousness"},
    "listens":    {"lemma": "listen",     "pos": "VERB",  "hz": 741, "field": "consciousness"},
    "listening":  {"lemma": "listen",     "pos": "VERB",  "hz": 741, "field": "consciousness"},

    # ── resonance 852 — sensing across cells ──
    "frequency":  {"lemma": "frequency",  "pos": "NOUN",  "hz": 852, "field": "resonance"},
    "route":      {"lemma": "route",      "pos": "VERB",  "hz": 852, "field": "resonance"},
    "routes":     {"lemma": "route",      "pos": "VERB",  "hz": 852, "field": "resonance"},
    "reception":  {"lemma": "reception",  "pos": "NOUN",  "hz": 852, "field": "resonance"},

    # ── wholeness 963 — unity-response, undivided ──
    "whole":      {"lemma": "whole",      "pos": "ADJ",   "hz": 963, "field": "wholeness"},
    "wholeness":  {"lemma": "wholeness",  "pos": "NOUN",  "hz": 963, "field": "wholeness"},
}


def lemma_pos_key(lemma: str, pos: str) -> str:
    """Cell-name convention for word-cells: `{lemma}.{POS}`.

    Closes GAP-W2 from docs/coherence-substrate/prose-as-recipe.form.
    """
    return f"{lemma.lower()}.{pos.upper()}"


def tokenize_words(text: str) -> List[Dict[str, Any]]:
    """Locale-light tokenizer: split on whitespace, peel trailing punctuation.

    Closes GAP-P1 in its smallest honest form. A real production tokenizer
    (spaCy, stanza, or a per-locale lemmatizer) replaces this when more
    languages and morphology depth are needed. For now: ASCII word + simple
    punctuation, lookup against `_WORD_LEXICON_DEFAULTS` for known words,
    fallback to a neutral entry (GAP-P2) for unknown words.

    Returns a list of dicts: word entries carry
    `{surface, lemma, pos, hz, field, kind="word"}`. Punctuation tokens
    carry `{surface, kind="punct"}`.
    """
    import re

    tokens: List[Dict[str, Any]] = []
    for raw in re.findall(r"[A-Za-z]+|[\.\?,!;:]", text):
        if re.match(r"[A-Za-z]+$", raw):
            key = raw.lower()
            base = _WORD_LEXICON_DEFAULTS.get(key)
            if base is None:
                # GAP-P2 fallback: unknown word lands at 432 Hz / neutral.
                # The substrate stays honest about unknown-as-unknown.
                base = {"lemma": key, "pos": "UNK", "hz": 432, "field": "neutral"}
            tokens.append({"surface": raw, "kind": "word", **base})
        else:
            tokens.append({"surface": raw, "kind": "punct"})
    return tokens


def ingest_word_cell(
    session: Session,
    lemma: str,
    pos: str,
    hz: int,
    semantic_field: str,
    *,
    surface: Optional[str] = None,
) -> Tuple[Any, NodeID, NodeID]:
    """Idempotent word-cell creation. Returns (cell, blueprint_id, ctor_id).

    The Blueprint composes from the four axes (lemma, POS, hz, semantic_field);
    two calls with the same arguments return the same cell via the kernel's
    content-addressing. The `surface` argument carries the original-form
    spelling (e.g. "becomes" while lemma="become") and is preserved on the
    cell for round-trip emission.

    Authors a HARMONIC_AT @<hz> resonance edge so the word participates in
    the same dimensional lattice every concept already does — `cell
    ?harmonic_at @741` returns word-cells alongside concepts.

    Closes GAP-W1+W2 plus the encoder half of P1/P2 for the WORD domain
    named in docs/coherence-substrate/prose-as-recipe.form.
    """
    from app.services.substrate.resonance import (
        author_geometry_signature as _author_geometry,
    )

    frontmatter: Dict[str, Any] = {
        "lemma": lemma,
        "pos": pos,
        "hz": hz,
        "semantic_field": semantic_field,
    }
    if surface is not None:
        frontmatter["surface"] = surface

    name = lemma_pos_key(lemma, pos)
    blueprint_id = frontmatter_to_blueprint(session, frontmatter, BID_word())
    ctor_id = frontmatter_to_structured_ctor(session, frontmatter)
    access_id = body_to_access_recipe(session, "", blueprint_id)
    cell = make_cell(
        session,
        name=name,
        domain="word",
        blueprint=blueprint_id,
        access=access_id,
        ctor=ctor_id,
        source_path=None,
    )

    # Resonance signature: the word fires at its harmonic.
    _author_geometry(session, cell.cell_id, {}, arity_hz=int(hz))

    return cell, blueprint_id, ctor_id


def artifact_kind_hz(kind: str) -> int:
    """The Hz the body assigns to a file kind. Useful for query construction."""
    return _ARTIFACT_KIND_HZ.get(kind, 432)


def ingest_markdown_text(
    session: Session,
    domain: str,
    content: str,
    name_field: Optional[str] = None,
    source_label: Optional[str] = None,
) -> Tuple[Any, NodeID, NodeID]:
    """Ingest markdown content arriving without a file — e.g. from a web POST.

    Same path as `_ingest_markdown_file` but parses text directly. `domain`
    selects the domain blueprint; `source_label` is recorded on the cell so
    visitors can see provenance even when the content never touched disk.
    """
    domain_blueprint_map = {
        "memory": BID_memory(),
        "spec": BID_spec(),
        "idea": BID_idea(),
        "concept": BID_concept(),
        "presence": BID_presence(),
        "lineage": BID_lineage(),
        "transmission": BID_transmission(),
        "resource": BID_resource(),
        "guide": BID_guide(),
        "language_view": BID_language_view(),
        "kb_page": BID_kb_page(),
        "witness": BID_witness(),
        "task": BID_task(),
    }
    if domain not in domain_blueprint_map:
        raise ValueError(
            f"unknown domain '{domain}'; expected one of {sorted(domain_blueprint_map)}"
        )
    default_name_field = {
        "memory": "name",
        "idea": "idea_id",
        "concept": "id",
    }
    if name_field is None:
        name_field = default_name_field.get(domain)
    return _ingest_markdown_payload(
        session,
        parse_markdown(content),
        domain=domain,
        domain_blueprint=domain_blueprint_map[domain],
        name_field=name_field,
        source_path=source_label,
    )


def _ingest_markdown_file(
    session: Session,
    path: Path,
    domain: str,
    domain_blueprint: NodeID,
    name_field: Optional[str] = None,
    structured: bool = False,
) -> Tuple[Any, NodeID, NodeID]:
    """Generic ingestion path — domain + domain blueprint + optional name field."""
    return _ingest_markdown_payload(
        session,
        parse_markdown_file(path),
        domain=domain,
        domain_blueprint=domain_blueprint,
        name_field=name_field,
        source_path=str(path),
        structured=structured,
    )


def _ingest_markdown_payload(
    session: Session,
    parsed: "ParsedMarkdown",
    domain: str,
    domain_blueprint: NodeID,
    name_field: Optional[str] = None,
    source_path: Optional[str] = None,
    structured: bool = False,
    name_override: Optional[str] = None,
) -> Tuple[Any, NodeID, NodeID]:
    """Shared ingest core — operates on already-parsed markdown.

    `structured=True` activates the composition-discipline encoder
    (frontmatter_to_structured_ctor) which produces a fully-expressed
    CTOR with named-pair recipes and substrate-resident values, instead
    of the earlier flat type-marker encoder. See
    docs/coherence-substrate/structural-composition.md.
    """
    name = name_override
    if not name and name_field:
        name = parsed.frontmatter.get(name_field)
    if not name:
        name = parsed.frontmatter.get("name") or parsed.frontmatter.get("title")
    if not name and source_path:
        name = Path(source_path).stem
    if not name:
        # Last-resort identity: hash a chunk of the body so re-submitting the
        # same content collapses to the same cell rather than fanning out.
        import hashlib
        digest = hashlib.sha256(parsed.body.encode("utf-8")).hexdigest()[:12]
        name = f"unnamed-{digest}"

    # Build the Blueprint from the frontmatter shape.
    blueprint_id = frontmatter_to_blueprint(session, parsed.frontmatter, domain_blueprint)

    # Build the CTOR recipe — captures frontmatter-as-seed.
    if structured:
        # New path — composition-discipline encoder. Every value reaches
        # the substrate as a structured recipe; the tree extends as deep
        # as the data goes. See structural-composition.md.
        ctor_id = frontmatter_to_structured_ctor(session, parsed.frontmatter)
    else:
        # Legacy path — type-marker string-recipes per key. Preserves
        # shape, loses values. Kept for backward compatibility during
        # migration; new ingests should pass structured=True.
        from app.services.substrate.substrate_strings import intern_string_instance
        ctor_children = []
        for key in sorted(parsed.frontmatter.keys()):
            marker = f"{key}={type(parsed.frontmatter[key]).__name__}"
            inst = intern_string_instance(session, marker)
            ctor_children.append(
                Recipe(
                    category=NodeID(1, Level.TRIVIAL, RType.STRING, inst),
                    blueprint=BID_string(),
                )
            )
        if ctor_children:
            ctor_recipe = Recipe(
                category=RID_block(),
                blueprint=blueprint_id,
                children=ctor_children,
            )
            ctor_id = ctor_recipe.make_self_id(session)
        else:
            ctor_id = None

    # Build the access-recipe (what reading the cell evaluates to).
    access_id = body_to_access_recipe(session, parsed.body, blueprint_id)

    # Make the cell.
    cell = make_cell(
        session,
        name=str(name),
        domain=domain,
        blueprint=blueprint_id,
        access=access_id,
        ctor=ctor_id,
        source_path=source_path,
    )
    return cell, blueprint_id, ctor_id
