"""Category vocabulary for the coherence-substrate.

The kernel is universal — NodeID 4-tuples, TreeDB interning, content-addressing
all stay the same regardless of domain. The *alphabet* (the leaf categories at
levels 1 and 2) is what changes per-domain. A code-comprehension substrate
would have a code-language vocabulary (Compare / Math / BitMath / Cond /
Loop / ...). The Network has its own vocabulary matching what the body holds:
ideas, specs, concepts, memories, presences, lineages, tasks, witnesses.

See `docs/field/urs/artifacts/nums-go-2023/network-substrate-design.md` for
the architectural lineage and the design rationale.
"""
from __future__ import annotations

from enum import IntEnum


# ---------------------------------------------------------------------------
# Levels — the universal compositional-depth axis
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
    GRAMMAR = 9     # parse rule: (pattern, action) — substrate-resident BMF-shaped grammar


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
    """Recipe basic-types (Level 2) — the verb-graph categories.

    Two layers of vocabulary:
    - Network-relational verbs (Realize, Compose, Transmit, Tend, ...)
    - Computational primitives (Math, Compare, Logic, Cond, Block, ...)

    The substrate doesn't execute these — it interns them as content-addressed
    Recipe NodeIDs. Two structurally-identical expressions hash to the same
    NodeID regardless of how they were typed.
    """
    UNDEFINED = 0
    # Network-relational
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
    # Computational primitives — added when Form became expressible as code
    MATH = 12       # +  -  *  /  %
    COMPARE = 13    # ==  !=  <  <=  >  >=
    LOGIC = 14      # &&  ||  !
    ACCESS = 15     # .field, [index], dereference
    WRITE = 16      # =, +=, -=, etc. (binding to a slot)
    LOOP = 17       # for, while, foreach
    JUMP = 18       # return, break, continue, yield
    MATCH = 19      # match/switch (pattern-based dispatch)
    # The angelic-nondeterminism trio (BML lineage) —
    # see docs/field/urs/artifacts/master-thesis-2000/companion/
    # angelic-assembler.txt and bml-search-algorithms.txt
    CHOICE = 20     # choose, fail, stop — speculative branching


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


# ---------------------------------------------------------------------------
# Computational-primitive instance enums
# ---------------------------------------------------------------------------


class RMath(IntEnum):
    UNDEFINED = 0
    PLUS = 1            # a + b
    MINUS = 2           # a - b
    MULTIPLY = 3        # a * b
    DIVIDE = 4          # a / b
    MODULO = 5          # a % b
    NEGATE = 6          # -a (unary)


class RCompare(IntEnum):
    UNDEFINED = 0
    EQUAL = 1           # ==
    NOT_EQUAL = 2       # !=
    LESS = 3            # <
    LESS_EQUAL = 4      # <=
    GREATER = 5         # >
    GREATER_EQUAL = 6   # >=


class RLogic(IntEnum):
    UNDEFINED = 0
    AND = 1             # &&
    OR = 2              # ||
    NOT = 3             # ! (unary)


class RCond(IntEnum):
    UNDEFINED = 0
    IF_THEN = 1         # if cond then body
    IF_THEN_ELSE = 2    # if cond then a else b
    TERNARY = 3         # cond ? a : b


class RMatch(IntEnum):
    UNDEFINED = 0
    SWITCH = 1          # match x { ... }


class RBlock(IntEnum):
    UNDEFINED = 0
    DO = 1              # do { stmts; expr }
    SEQUENCE = 2        # one statement after another
    LET = 3             # let name = expr (a binding statement)


class RJump(IntEnum):
    UNDEFINED = 0
    RETURN = 1
    BREAK = 2
    CONTINUE = 3
    YIELD = 4


class RChoice(IntEnum):
    """Angelic nondeterminism — the BML / Prolog speculation primitives.

    From sgb-bml-objects.txt + angelic-assembler.txt:
    - choose: pick a branch from candidates; backtracks on downstream fail
    - fail:   signal failure; unwinds speculation to nearest choose
    - stop:   commit current speculation; no more backtracking from here

    The substrate interns these as Recipe NodeIDs the same way it interns
    arithmetic. Execution semantics (the actual speculation engine) is a
    future concern; the structural form is what gets stored.
    """
    UNDEFINED = 0
    CHOOSE = 1
    FAIL = 2
    STOP = 3
