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
    is the value-leaf primitive. Unlike the legacy hash-based encoding
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

    Unlike the legacy `frontmatter_to_*` encoder (which produces type-marker
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
    legacy encoder for backward compatibility during migration. See
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
) -> Tuple[Any, NodeID, NodeID]:
    """Shared ingest core — operates on already-parsed markdown.

    `structured=True` activates the new composition-discipline encoder
    (frontmatter_to_structured_ctor) which produces a fully-expressed
    CTOR with named-pair recipes and substrate-resident values, instead
    of the legacy type-marker encoder. See
    docs/coherence-substrate/structural-composition.md.
    """
    name = None
    if name_field:
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
