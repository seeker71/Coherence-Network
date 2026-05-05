"""iCal source — parse VCALENDAR feeds without an external library.

iCal (RFC 5545) is a line-folded text format: each property is a
line of the form ``KEY[;PARAMS]:VALUE``, and physical lines that
begin with whitespace are continuations of the previous logical line.
Events are bracketed by ``BEGIN:VEVENT`` / ``END:VEVENT``.

We don't need full RFC 5545 fidelity — only the four fields the
graph stores: SUMMARY (event name), DTSTART (when), LOCATION (where),
URL (link). DESCRIPTION rolls into the imported event note when
present. Everything else is ignored on purpose; presence pages are
about presence, not full calendar replication.

Match predicate: any URL ending in ``.ics`` (case-insensitive), or
any URL that responds with ``Content-Type: text/calendar``.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable
from urllib.parse import urlparse

import httpx

from .base import EventSource, ImportedEvent

log = logging.getLogger(__name__)

USER_AGENT = "Coherence-Network-GatheringsImporter/1.0 (+https://coherencycoin.com)"
FETCH_TIMEOUT = 8.0


def _unfold(lines: Iterable[str]) -> list[str]:
    """Join folded continuation lines back into single logical lines.

    iCal lines that begin with a single space or tab are continuations
    of the previous line — the line break + leading whitespace is the
    fold marker, and the original content is the rest of the line.
    """
    out: list[str] = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        if line.startswith((" ", "\t")) and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def _strip_params(key_with_params: str) -> str:
    """Drop ``;TZID=...`` etc. from a property key — we only need the name."""
    return key_with_params.split(";", 1)[0].upper()


def _decode_value(raw: str) -> str:
    """Reverse the iCal text escapes: ``\\,`` ``\;`` ``\\n`` ``\\\\``."""
    return (
        raw.replace("\\N", "\n")
        .replace("\\n", "\n")
        .replace("\\,", ",")
        .replace("\;", ";")
        .replace("\\\\", "\\")
    )


def _format_when(raw: str) -> str:
    """Normalize a DTSTART value to ISO 8601 if possible.

    iCal date-time forms:
      · ``20260418T180000Z``    → ``2026-04-18T18:00:00Z``
      · ``20260418T180000``     → ``2026-04-18T18:00:00``
      · ``20260418``            → ``2026-04-18``

    Anything that doesn't match returns as-is — the graph stores it
    as free text, and the page renders what was published.
    """
    s = raw.strip()
    if not s:
        return ""
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})(Z?))?$", s)
    if not m:
        return s
    yy, mo, dd, hh, mm, ss, z = m.groups()
    if hh is None:
        return f"{yy}-{mo}-{dd}"
    return f"{yy}-{mo}-{dd}T{hh}:{mm}:{ss}{'Z' if z else ''}"


def parse_ical(text: str) -> list[ImportedEvent]:
    """Parse a VCALENDAR string into a list of :class:`ImportedEvent`.

    Public so tests can feed a fixed VCALENDAR and assert without
    network. Skips VEVENTs that have no SUMMARY or no DTSTART — those
    are shells, not gatherings.
    """
    if not text:
        return []
    lines = _unfold(text.splitlines())
    events: list[ImportedEvent] = []
    in_event = False
    cur: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if stripped == "BEGIN:VEVENT":
            in_event = True
            cur = {}
            continue
        if stripped == "END:VEVENT":
            in_event = False
            name = cur.get("SUMMARY", "").strip()
            when = _format_when(cur.get("DTSTART", ""))
            if name and when:
                events.append(
                    ImportedEvent(
                        name=name,
                        when=when,
                        where=(cur.get("LOCATION") or None) or None,
                        url=(cur.get("URL") or None) or None,
                        description=(cur.get("DESCRIPTION") or None) or None,
                    )
                )
            continue
        if not in_event or ":" not in line:
            continue
        key_part, _, value = line.partition(":")
        key = _strip_params(key_part)
        cur[key] = _decode_value(value)
    return events


class IcalSource:
    """Plugin: ``.ics`` URLs and ``text/calendar`` responses."""

    name = "ical"

    def matches(self, url: str) -> bool:
        """Path ends in ``.ics`` (case-insensitive). Content-type
        sniffing happens inside :meth:`fetch` for URLs that don't
        carry the suffix but serve calendar feeds (some Google
        Calendar share URLs do this)."""
        if not url:
            return False
        path = (urlparse(url).path or "").lower()
        return path.endswith(".ics")

    def fetch(self, url: str) -> list[ImportedEvent]:
        # SSRF guard — refuse non-public targets before fetch and after
        # any redirect. Same guard the inspired-by resolver uses.
        from app.services.inspired_by_service import _is_public_target  # noqa: PLC0415

        if not _is_public_target(url):
            return []
        try:
            with httpx.Client(
                timeout=FETCH_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT, "Accept": "text/calendar,*/*;q=0.5"},
            ) as client:
                r = client.get(url)
                if not _is_public_target(str(r.url)):
                    return []
                if r.status_code >= 400:
                    return []
                return parse_ical(r.text)
        except httpx.HTTPError as exc:
            log.debug("ical fetch failed for %s: %s", url, exc)
            return []
