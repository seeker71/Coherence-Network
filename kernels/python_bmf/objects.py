# Auto-emitted by form/form-stdlib/emits/python-native.fk
# Target file: kernels/python_bmf/objects.py
# Hand edits will be overwritten; edit the Form source instead.
from kernels.python_bmf import sdk

from enum import IntEnum

from dataclasses import dataclass

class PyBmfCategory(IntEnum):
    """Python BMF object categories — emitted from form-ontology.json via the .fkb lens."""
    IMPORT = 501
    FROM_IMPORT = 502
    DEF = 503
    CLASS = 504
    ASSIGN = 505
    RETURN = 506
    RAISE = 507
    PASS = 508
    IF = 509
    WHILE = 510
    FOR = 511
    CALL = 512
    INT = 513
    STRING = 514
    IDENT = 515
    ATTR = 516
    METHOD_CALL = 517
    LIST = 518
    DICT = 519
    ANNOTATED = 520
    AUG_ASSIGN = 521
    BINOP = 522
    MODULE = 523
    BOOL = 524
    NONE = 525
    UNARY = 526
    COMPARE = 527
    BOOL_OP = 528
    SUBSCRIPT = 529
    SLICE = 530
    TUPLE = 531
    SET = 532
    LAMBDA = 533
    AWAIT = 534
    YIELD = 535
    BREAK = 536
    CONTINUE = 537
    GLOBAL = 538
    NONLOCAL = 539
    DEL = 540
    ASSERT = 541
    WITH = 542
    TRY = 543
    ASYNC_DEF = 544
    DECORATOR = 545
    ASYNC_FOR = 546
    ASYNC_WITH = 547
    IF_ELSE = 548
    ELIF = 549
    RAISE_FROM = 550
    IMPORT_STAR = 551
    IMPORT_MANY = 552
    EXCEPT_AS = 553
    MATCH = 554
    CASE = 555
    COMP = 556
    GENEXP = 557
    KWARG = 558
    STARARG = 559
    DEFAULT = 560
    TYPED_PARAM = 561
    RET_ANN = 562
    WALRUS = 563
    FLOAT = 564
    BYTES = 565
    ELLIPSIS = 566
    ATTR_ASSIGN = 567
    SUB_ASSIGN = 568
    UNPACK = 569
    FSTRING = 570
    IFEXP = 571
    SETCOMP = 572
    YIELD_FROM = 573
    MATCH_AS = 574


@dataclass(frozen=True)
class PyKeyword:
    value: str

def py_keyword(value):
    return PyKeyword(value=value)
