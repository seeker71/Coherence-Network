"""Base plugin shape for creation-source importers.

Every presence in the graph (musicians, teachers, communities,
projects) creates things — albums, tracks, books, teachings,
podcasts, courses, essays, articles, films. A creation source
knows how to read one platform's pages or feeds and surface those
creations as a uniform list.

The shape is deliberately small: ``matches(url)`` says whether
the source recognises a URL; ``fetch(url)`` returns the creations
it discovers. The worker (`creations_importer`) walks every
source against every presence's known URLs and writes the
creation nodes + ``contributes-to`` edges into the graph.

Creation kinds — the vocabulary:
  · album, track          (music)
  · book                  (long-form text)
  · teaching              (lineage transmission, course, retreat)
  · podcast, episode      (audio series)
  · video, film           (visual)
  · essay, article        (short-form text)
  · course, workshop      (structured learning)
  · work                  (catch-all)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


# Canonical creation kinds. Anything outside this set is invalid and
# must be rejected at the import boundary so the graph doesn't
# accumulate ad-hoc kind strings that the renderer can't recognise.
CREATION_KINDS: frozenset[str] = frozenset({
    "album", "track",
    "book",
    "teaching",
    "podcast", "episode",
    "video", "film",
    "essay", "article",
    "course", "workshop",
    "work",
})


def is_valid_kind(kind: str) -> bool:
    """True if ``kind`` is one of the canonical creation kinds."""
    return (kind or "").strip().lower() in CREATION_KINDS


@dataclass
class ImportedCreation:
    """One creation discovered by a source plugin.

    `name` and `kind` are required; `url` is strongly preferred
    because it's how dedupe keys against existing graph nodes.
    `image_url`, `description`, and `when` are best-effort
    enrichment that the renderer uses when present.
    """
    name: str
    kind: str
    url: str | None
    image_url: str | None = None
    description: str | None = None
    when: str | None = None  # release date if known (free-text ISO or label)


class CreationSource(Protocol):
    """Protocol every creation-source plugin implements."""

    name: str

    def matches(self, url: str) -> bool:
        """True if this source recognises the given URL."""
        ...

    def fetch(self, url: str) -> list[ImportedCreation]:
        """Fetch the source's creations from the URL. Implementations
        must respect the per-source 50-item cap and return an empty
        list on transient failure (4xx/5xx, network errors, parse
        errors). They never raise."""
        ...
