"""Pure text helpers for idea identifiers — tag normalization and slugify.

Extracted from idea_service.py to reduce that module under the modularity
threshold (#163). These are pure functions with no idea-state dependencies.
Re-exported from idea_service for backward compat.
"""

from __future__ import annotations

import re
import unicodedata


_TAG_SLUG_PATTERN = re.compile(r"[^a-z0-9-]")


def normalize_tags(raw_tags: list[str]) -> list[str]:
    """Normalize tags: trim, lowercase, slugify, deduplicate, sort ascending."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in raw_tags:
        tag = raw.strip().lower()
        tag = re.sub(r"\s+", "-", tag)
        tag = _TAG_SLUG_PATTERN.sub("", tag)
        tag = tag.strip("-")
        if tag and tag not in seen:
            seen.add(tag)
            result.append(tag)
    return sorted(result)


def validate_raw_tags(raw_tags: list[str]) -> tuple[list[str], bool]:
    """Validate and normalize tags. Returns (normalized, is_valid).

    is_valid is False when a non-empty raw tag normalizes to empty string.
    """
    normalized = []
    for raw in raw_tags:
        stripped = raw.strip()
        if not stripped:
            continue  # silently drop empty/whitespace-only tags
        tag = stripped.lower()
        tag = re.sub(r"\s+", "-", tag)
        tag = _TAG_SLUG_PATTERN.sub("", tag)
        tag = tag.strip("-")
        if not tag:
            return [], False  # non-empty raw → empty after normalization = invalid
        normalized.append(tag)
    return normalize_tags(normalized), True


def slugify(text: str) -> str:
    """Convert free-form text to a URL-safe slug.

    Rules: lowercase → strip non-alphanum/slash/hyphen → collapse hyphens →
    strip leading/trailing hyphens per segment → max 80 chars.
    Slashes are preserved to allow namespaced slugs like 'finance/cc-minting'.
    """
    # Normalize unicode
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower()
    # Replace spaces and non-slug chars (keeping / for namespacing) with -
    text = re.sub(r"[^a-z0-9/]+", "-", text)
    # Clean up per-segment
    segments = [re.sub(r"-+", "-", s).strip("-") for s in text.split("/")]
    slug = "/".join(s for s in segments if s)
    return slug[:80]
