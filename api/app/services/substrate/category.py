"""Category vocabulary for the coherence-substrate.

The kernel is universal — same NodeID 4-tuples, same TreeDB interning, same
content-addressing — but the *alphabet* (the leaf categories at levels 1 and
2) is domain-specific. NUMS.Go has a code-language vocabulary (Compare /
Math / BitMath / Cond / Loop / ...). The Network has its own vocabulary
matching what the body actually holds: ideas, specs, concepts, memories,
presences, lineages, tasks, witnesses.

See `docs/field/urs/artifacts/nums-go-2023/network-substrate-design.md` for
the full design rationale.
"""
from __future__ import annotations

from enum import IntEnum


# ---------------------------------------------------------------------------
# Levels (universal — same as NUMS)
# ---------------------------------------------------------------------------


class Level(IntEnum):
    UNDEFINED = 0
    TRIVIAL = 1
    BASIC = 2
    COMPLEX_1 = 3
    COMPLEX_2 = 4
    COMPLEX_3 = 5
    COMPLEX_4 = 6
    COMPLEX_5 = 7
    COMPLEX_6 = 8
    COMPLEX_7 = 9


# ---------------------------------------------------------------------------
# Blueprint categories (the structural-identity types)
# ---------------------------------------------------------------------------


class BType(IntEnum):
    """Blueprint trivial-types (Level 1) — atomic primitives."""
    UNDEFINED = 0
    VOID = 1
    NUMERIC = 2
    ATOMIC = 3  # Slug, ID, Date, Token, Score, Path, URL, EdgeKind


class BNumeric(IntEnum):
    """Numeric instances (Level 1, Type=NUMERIC)."""
    UNDEFINED = 0
    BOOL = 1
    INTEGER = 2
    DECIMAL = 3
    STRING = 4


class BAtomic(IntEnum):
    """Atomic instances (Level 1, Type=ATOMIC) — Network primitives."""
    UNDEFINED = 0
    SLUG = 1
    UUID = 2
    DATE = 3
    TOKEN = 4
    SCORE = 5  # 0.0-1.0 float
    PATH = 6
    URL = 7
    EDGE_KIND = 8


class BBasic(IntEnum):
    """Blueprint basic-types (Level 2) — composite category groups."""
    UNDEFINED = 0
    CONTAINER = 1   # List, Dictionary, Set, Object
    REFERENCE = 2   # Pointer, Optional, Edge
    RECIPE = 3      # Function, Tend, Spec, Story (callable shapes)
    DOMAIN = 4      # Idea, Spec, Concept, Memory, Presence, Task, Lineage, Witness


class BContainer(IntEnum):
    UNDEFINED = 0
    LIST = 1
    DICTIONARY = 2
    SET = 3
    OBJECT = 4


class BReference(IntEnum):
    UNDEFINED = 0
    POINTER = 1
    OPTIONAL = 2
    EDGE = 3


class BRecipe(IntEnum):
    UNDEFINED = 0
    FUNCTION = 1
    TEND = 2
    SPEC = 3
    STORY = 4


class BDomain(IntEnum):
    """The Network's named entity types — what cells our body holds."""
    UNDEFINED = 0
    IDEA = 1        # problem-shape with capabilities, absorbed-ideas, spec-links
    SPEC = 2        # executable form: source, requirements, done_when, test
    CONCEPT = 3     # vision-kb story: cross_refs, visuals, parent
    MEMORY = 4      # auto-loaded note: name, description, type, body
    PRESENCE = 5    # contributor: HUMAN/AGENT/SYSTEM with role, edges
    TASK = 6        # work unit: idea_id, status, context, witness
    LINEAGE = 7     # transmission edge: kind, from, to, evidence
    WITNESS = 8     # event-as-proof: presence, action, evidence_url, timestamp


# ---------------------------------------------------------------------------
# Recipe categories (the operational verbs)
# ---------------------------------------------------------------------------


class RType(IntEnum):
    """Recipe trivial-types (Level 1)."""
    UNDEFINED = 0
    NULL = 1
    BOOL = 2
    INTEGER = 3
    DECIMAL = 4
    STRING = 5
    SLUG = 6
    DATE = 7
    SCORE = 8
    REF = 9  # reference to a cell by NodeID
    EMPTY = 10


class RBasic(IntEnum):
    """Recipe basic-types (Level 2) — the verb-graph categories."""
    UNDEFINED = 0
    REALIZE = 1     # spec realizes idea
    COMPOSE = 2     # cross-reference, parent-of, member-of, analogous-to
    TRANSMIT = 3    # lineage flows source → receiver
    TEND = 4        # tend / attune / compost / release
    RESOLVE = 5     # name → identity lookup
    WITNESS = 6     # event becomes proof
    ABSORB = 7      # idea absorbs another idea
    SCORE = 8       # numeric measurement applied
    BLOCK = 9       # composition: Sequence, Branch, Parallel
    CALL = 10       # invoke agent / tool / endpoint
    COND = 11       # conditional realization


class RTend(IntEnum):
    """The four commit verbs."""
    UNDEFINED = 0
    TEND = 1        # actively circulating what's alive
    ATTUNE = 2      # realigning the body's sense of itself
    COMPOST = 3     # releasing what no longer circulates
    RELEASE = 4     # letting go of once-loved forms with care


class RCompose(IntEnum):
    UNDEFINED = 0
    CROSS_REF = 1
    PARENT_OF = 2
    MEMBER_OF = 3
    ANALOGOUS_TO = 4
    EMBED = 5


class RTransmit(IntEnum):
    UNDEFINED = 0
    TRANSMIT_TO = 1
    INHERIT = 2
    CHANNEL = 3
    WITNESS_TRANSMISSION = 4


class RRealize(IntEnum):
    UNDEFINED = 0
    REALIZE = 1
    PARTIAL_REALIZE = 2
    SUPERSEDE = 3
