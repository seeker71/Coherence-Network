"""Exact source-byte bindings for grounded retrieval.

The semantic index is a disposable cache.  These helpers define the durable
facts that must already exist in the substrate before an index row can claim
grounding: the SHA-256 of the complete source bytes and the SHA-256 of the
exact answer bytes exposed by the native RAG lane.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path


ANSWER_CHAR_LIMIT = 600
SNIPPET_CHAR_LIMIT = 2000


@dataclass(frozen=True)
class GroundingSourceBytes:
    """Current filesystem facts that are persisted in an ARTIFACT CTOR."""

    source_sha256: str
    source_size: int
    answer: bytes
    answer_sha256: str
    snippet: str


def _definition_names(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("(defn ") or stripped.startswith("(define "):
            tokens = stripped.split("(", 2)[-1].split()
            if len(tokens) >= 2:
                names.append(tokens[1].rstrip(")"))
        elif stripped.startswith("#"):
            names.append(stripped.lstrip("# ").strip())
    return names


def grounding_snippet(source_bytes: bytes) -> str:
    """Derive the exact answer-bearing snippet from complete source bytes."""
    text = source_bytes.decode("utf-8", errors="ignore")
    lines = [line for line in text.splitlines() if line.strip()]
    head = "\n".join(lines[:30])
    names = _definition_names(text)
    signature = "\nsignature: " + " ".join(names[:40]) if names else ""
    return (head + signature)[:SNIPPET_CHAR_LIMIT]


def read_grounding_source(path: str | Path) -> GroundingSourceBytes:
    """Read once and return the exact source and answer content identities."""
    data = Path(path).read_bytes()
    snippet = grounding_snippet(data)
    answer = snippet[:ANSWER_CHAR_LIMIT].encode("utf-8")
    return GroundingSourceBytes(
        source_sha256=hashlib.sha256(data).hexdigest(),
        source_size=len(data),
        answer=answer,
        answer_sha256=hashlib.sha256(answer).hexdigest(),
        snippet=snippet,
    )
