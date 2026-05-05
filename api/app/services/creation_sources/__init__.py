"""Creation-source plugins.

Every plugin in this package implements the :class:`CreationSource`
protocol from :mod:`base`. The worker imports each side-effectfully
so the registry stays in one place: add a new source by adding a
new module here, then registering its instance in
:data:`SOURCES`.
"""
from __future__ import annotations

from .base import (  # noqa: F401
    CREATION_KINDS,
    CreationSource,
    ImportedCreation,
    is_valid_kind,
)
from .bandcamp_source import BandcampSource
from .goodreads_source import GoodreadsSource
from .rss_source import RSSSource
from .substack_source import SubstackSource
from .youtube_source import YouTubeSource


# Order matters: more specific sources first so the generic RSS
# fallback only runs on URLs the platform-specific sources didn't
# claim. Substack uses RSS internally too — putting it before RSS
# means a substack.com URL goes through the substack source and
# returns "essay" creations, not the rss source's "article" default.
SOURCES: list[CreationSource] = [
    BandcampSource(),
    YouTubeSource(),
    SubstackSource(),
    GoodreadsSource(),
    RSSSource(),
]


__all__ = [
    "CREATION_KINDS",
    "CreationSource",
    "ImportedCreation",
    "is_valid_kind",
    "SOURCES",
    "BandcampSource",
    "YouTubeSource",
    "SubstackSource",
    "RSSSource",
    "GoodreadsSource",
]
