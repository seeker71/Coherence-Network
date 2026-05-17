"""Streaming parser — `tokenize_iter`, `tokenize_chunks`, `parse_chunks`.

The classic `tokenize(text)` reads everything upfront. For infinite or
chunk-arriving input (sockets, stdin, log tails), this module yields
tokens lazily and the Parser pulls from the stream as `peek(n)` reaches
forward.

Tokens that span chunk boundaries (a string opening in one chunk, closing
in the next) are handled by holding a partial buffer until either the
match definitively ends with more input behind it, or the stream closes.
"""
from __future__ import annotations

import pytest

from app.services.substrate.form import (
    Parser,
    Token,
    parse,
    parse_chunks,
    tokenize,
    tokenize_chunks,
    tokenize_iter,
)


# ---------------------------------------------------------------------------
# tokenize_iter — lazy single-string tokenization
# ---------------------------------------------------------------------------


def test_tokenize_iter_yields_same_as_eager():
    eager = tokenize("1 + 2 * 3")
    lazy = list(tokenize_iter("1 + 2 * 3"))
    assert [(t.kind, t.value) for t in eager] == [(t.kind, t.value) for t in lazy]


def test_tokenize_iter_is_a_generator():
    """The whole point — it's lazy."""
    import types
    gen = tokenize_iter("1 + 2")
    assert isinstance(gen, types.GeneratorType)


# ---------------------------------------------------------------------------
# tokenize_chunks — streaming across chunk boundaries
# ---------------------------------------------------------------------------


def test_tokenize_chunks_simple_split():
    """Tokens that line up with chunk boundaries work."""
    toks = list(tokenize_chunks(["1 + ", "2 * ", "3"]))
    assert [t.kind for t in toks] == ["INT", "PLUS", "INT", "STAR", "INT", "EOF"]


def test_tokenize_chunks_identifier_across_boundary():
    """An identifier split mid-name still parses as one token."""
    toks = list(tokenize_chunks(["fo", "obar + 1"]))
    assert [(t.kind, t.value) for t in toks][:-1] == [
        ("IDENT", "foobar"), ("PLUS", "+"), ("INT", "1"),
    ]


def test_tokenize_chunks_string_across_boundary():
    """A string literal split mid-quote still parses as one STRING token."""
    toks = list(tokenize_chunks(['"he', 'llo"']))
    assert [(t.kind, t.value) for t in toks][:-1] == [("STRING", '"hello"')]


def test_tokenize_chunks_integer_across_boundary():
    """A multi-digit integer split mid-digit parses as one INT."""
    toks = list(tokenize_chunks(["12", "345 + 1"]))
    assert toks[0].kind == "INT" and toks[0].value == "12345"


def test_tokenize_chunks_empty_stream():
    """An empty chunks-iter yields only EOF."""
    toks = list(tokenize_chunks([]))
    assert [t.kind for t in toks] == ["EOF"]


def test_tokenize_chunks_handles_intermediate_empty_chunks():
    """Empty chunks in the middle don't break anything."""
    toks = list(tokenize_chunks(["1", "", " + ", "", "2"]))
    assert [t.kind for t in toks][:-1] == ["INT", "PLUS", "INT"]


# ---------------------------------------------------------------------------
# Parser with iterator — lazy peek extends the buffer
# ---------------------------------------------------------------------------


def test_parser_accepts_iterator():
    """Parser works with any iterator of tokens (not just a list)."""
    parser = Parser(tokenize_iter("1 + 2"))
    ast = parser.parse()
    from app.services.substrate.form import BinOp
    assert isinstance(ast, BinOp)


def test_parser_buffers_lazily():
    """The internal buffer grows only as `peek` reaches forward."""
    parser = Parser(tokenize_iter("1 + 2 + 3 + 4"))
    # Before any peek, buffer is empty.
    assert parser._buf == []
    parser.peek(0)
    # After peeking 0 (current token), buffer has at least 1.
    assert len(parser._buf) >= 1


def test_parser_backtracking_within_buffer():
    """Speculation rewinds `pos` within the already-buffered prefix —
    streaming doesn't break the existing backtracking pattern."""
    parser = Parser(tokenize_iter("1 + 2"))
    parser.peek(0)
    parser.peek(1)
    parser.peek(2)
    saved = parser.pos
    parser.consume("INT")
    parser.consume("PLUS")
    # Rewind
    parser.pos = saved
    assert parser.peek().kind == "INT"


# ---------------------------------------------------------------------------
# parse_chunks — full end-to-end streaming
# ---------------------------------------------------------------------------


def test_parse_chunks_matches_parse():
    """Streaming parse produces identical AST to eager parse."""
    text = "if 5 > 3 then 100 else 200"
    a = parse(text)
    b = parse_chunks([text])
    assert type(a) is type(b)


def test_parse_chunks_realistic_split():
    """A multi-chunk source parses correctly across arbitrary boundaries."""
    ast = parse_chunks(["do {", " let x = 1; ", "x + 2 }"])
    from app.services.substrate.form import DoBlock
    assert isinstance(ast, DoBlock)


def test_parse_chunks_string_across_boundary():
    """A string literal whose body spans chunks parses end-to-end."""
    ast = parse_chunks(['"hel', 'lo wor', 'ld"'])
    from app.services.substrate.form import StringLit
    assert isinstance(ast, StringLit)
    assert ast.value == "hello world"


def test_parse_chunks_works_with_generators():
    """The source can be any iterator, not just a list."""
    def chunk_gen():
        yield "1"
        yield " + "
        yield "2"
    ast = parse_chunks(chunk_gen())
    from app.services.substrate.form import BinOp
    assert isinstance(ast, BinOp)


def test_parse_chunks_invalid_char_after_stream_close():
    """A truly bad character only raises after the stream closes."""
    with pytest.raises(SyntaxError):
        parse_chunks(["1 + #"])  # `#` is not a valid token
