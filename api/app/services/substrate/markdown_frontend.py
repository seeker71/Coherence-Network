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

    We achieve this by interning the string value as a child blueprint
    under a special string-literal category.
    """
    # We use the BID_string trivial as the category, with a synthetic child
    # encoding the value via the SerializedTree path. To avoid collisions
    # with actual literal values, we treat string-literal-as-shape as a
    # composite at level COMPLEX_1 with a single trivial child carrying the
    # value's hash-instance.
    inst = abs(hash(value)) % (10**9) + 1  # stable across runs (within python session)
    # NOTE: hash() salt makes this NOT stable across processes. For real
    # cross-process determinism we'd use a content-addressed string symbol
    # table. Phase 3 MVP — see followup task.
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


def ingest_memory_file(session: Session, path: Path) -> Tuple[Any, NodeID, NodeID]:
    """Ingest one memory file into the substrate.

    Returns (NamedCell, blueprint NodeID, ctor recipe NodeID).
    """
    parsed = parse_markdown_file(path)
    name = parsed.frontmatter.get("name") or path.stem

    # Build the Blueprint from the frontmatter shape.
    blueprint_id = frontmatter_to_blueprint(session, parsed.frontmatter, BID_memory())

    # Build the CTOR recipe — captures frontmatter-as-seed.
    # We represent it as a Block recipe whose children are string-literal
    # recipes for each frontmatter key-value pair. This is enough for
    # structural identity (two memories with the same frontmatter keys+types
    # produce the same CTOR shape), and the actual values live in the
    # source file (and on disk).
    ctor_children = []
    for key in sorted(parsed.frontmatter.keys()):
        # Each entry is a string-literal whose instance encodes the key.
        inst = abs(hash(f"{key}={type(parsed.frontmatter[key]).__name__}")) % (10**9) + 1
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
        name=name,
        domain="memory",
        blueprint=blueprint_id,
        access=access_id,
        ctor=ctor_id,
        source_path=str(path),
    )
    return cell, blueprint_id, ctor_id
