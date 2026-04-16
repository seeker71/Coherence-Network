"""Shared utilities for KB sync scripts.

All scripts that operate on docs/vision-kb/ concept files share these
constants, parsers, and HTTP helpers. Import from here — never duplicate.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    import urllib.request
    httpx = None  # type: ignore

# ── Paths ─────────────────────────────────────────────────────────────

KB_DIR = Path(__file__).resolve().parent.parent / "docs" / "vision-kb" / "concepts"
INDEX_FILE = Path(__file__).resolve().parent.parent / "docs" / "vision-kb" / "INDEX.md"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "web" / "public" / "visuals" / "generated"
DEFAULT_API = "https://api.coherencycoin.com"

# ── Status ordering ───────────────────────────────────────────────────

STATUS_ORDER = {"seed": 0, "expanding": 1, "deepening": 1, "mature": 2, "complete": 3}

# ── Pollinations ──────────────────────────────────────────────────────

def concept_seed(concept_id: str) -> int:
    """Deterministic seed from concept ID — shared between Python and JS."""
    return sum(ord(c) for c in concept_id)

SEED_STRIDE = 17  # offset multiplied by visual index for gallery images
STORY_SEED_STRIDE = 13  # offset multiplied by block index for story images

def pollinations_url(prompt: str, seed: int = 42, width: int = 1024, height: int = 576) -> str:
    """Build a deterministic Pollinations image URL."""
    encoded = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&model=flux&nologo=true&seed={seed}"


# ── Markdown parsing ──────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML-like frontmatter between --- markers.

    Handles single-line `key: value` pairs. The value is everything
    after the first colon (partition splits on first occurrence only).
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    fm: dict[str, str] = {}
    for line in match.group(1).strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm


def parse_section(text: str, heading: str) -> str | None:
    """Extract content under a ## heading, stopping at the next ## or end."""
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        return None
    content = match.group(1).strip()
    return content if content else None


def parse_list_items(text: str) -> list[str]:
    """Parse markdown bullet list into strings."""
    items = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            items.append(line[2:].strip())
    return items


def parse_crossrefs(text: str) -> list[str]:
    """Extract cross-reference concept IDs from text."""
    section = parse_section(text, "Cross-References") or parse_section(text, "Connected Frequencies")
    if not section:
        return []
    return re.findall(r"lc-[\w-]+", section)


def extract_story_content(text: str) -> str:
    """Extract the full markdown body after frontmatter, stripping the title line."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].strip()
    lines = text.split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def extract_inline_visuals(text: str) -> list[dict[str, str]]:
    """Extract inline visuals from ![caption](visuals:prompt) format."""
    visuals = []
    for m in re.finditer(r"!\[([^\]]*)\]\(visuals:([^)]+)\)", text):
        visuals.append({"caption": m.group(1).strip(), "prompt": m.group(2).strip()})
    return visuals


# ── Section-specific parsers ──────────────────────────────────────────

def parse_resource_items(text: str) -> list[dict[str, str]]:
    """Parse resource entries like: icon [Name](url) - description (type: blueprint)"""
    resources = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"[^\[]*\[([^\]]+)\]\(([^)]+)\)\s*[\u2014\u2013\-]\s*(.*)", line)
        if m:
            name, url, desc = m.group(1), m.group(2), m.group(3)
            rtype = "guide"
            tm = re.search(r"\((?:type:\s*)?(\w+)\)\s*$", desc)
            if tm:
                rtype = tm.group(1)
                desc = desc[:tm.start()].strip()
            resources.append({"name": name, "url": url, "type": rtype, "description": desc})
    return resources


def parse_materials(text: str) -> list[dict[str, str]]:
    """Parse materials entries like: **Name** - description"""
    materials = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"\*\*([^*]+)\*\*\s*[\u2014\u2013\-]\s*(.*)", line)
        if m:
            materials.append({"name": m.group(1), "description": m.group(2)})
        elif line.startswith("- ") or line.startswith("* "):
            inner = line[2:].strip()
            m2 = re.match(r"\*\*([^*]+)\*\*\s*[\u2014\u2013\-]\s*(.*)", inner)
            if m2:
                materials.append({"name": m2.group(1), "description": m2.group(2)})
    return materials


def parse_scale_notes(text: str) -> dict[str, str]:
    """Parse scale notes: **50 people**: ..., **100 people**: ..., **200 people**: ..."""
    notes: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        for marker, key in [("50", "small"), ("100", "medium"), ("200", "large")]:
            if f"**{marker}" in stripped or f"{marker} people" in stripped.lower():
                if current_key:
                    notes[current_key] = " ".join(current_lines).strip()
                current_key = key
                current_lines = [re.sub(r"^.*?:\s*", "", stripped.split("**")[-1]).strip()]
                break
        else:
            if current_key and stripped:
                current_lines.append(stripped)

    if current_key:
        notes[current_key] = " ".join(current_lines).strip()
    return notes if any(notes.values()) else {}


def parse_location_adaptations(text: str) -> list[dict[str, str]]:
    """Parse climate adaptations: **Temperate** - notes"""
    adaptations = []
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r"[-*]\s*\*\*(\w+)\*\*\s*[---:-]\s*(.*)", line)
        if m:
            adaptations.append({"climate": m.group(1).lower(), "notes": m.group(2)})
    return adaptations


def parse_visuals(text: str) -> list[dict[str, str]]:
    """Parse visual entries: N. **Caption** - `prompt text`"""
    visuals = []
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r"\d+\.\s*\*?\*?([^*`]+?)\*?\*?\s*[\u2014\u2013\-]\s*`([^`]+)`", line)
        if m:
            visuals.append({"caption": m.group(1).strip(), "prompt": m.group(2).strip()})
    return visuals


# ── Full concept file parser ──────────────────────────────────────────

def parse_concept_file(filepath: Path) -> dict[str, Any]:
    """Parse a concept KB markdown file into structured properties dict.

    Returns: {"id": str, "status": str, "properties": dict}
    """
    text = filepath.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    props: dict[str, Any] = {}
    title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
    quote_match = re.search(r"^>\s*(.+)$", text, re.MULTILINE)
    hz_raw = fm.get("hz", "").strip()
    hz: int | None = int(hz_raw) if hz_raw.isdigit() else None

    # Full story content (the living narrative)
    story = extract_story_content(text)
    if story:
        props["story_content"] = story

    # Inline visuals from ![caption](visuals:prompt)
    inline_visuals = extract_inline_visuals(text)
    if inline_visuals:
        props["visuals"] = inline_visuals

    # Structured sections (backward compatibility)
    for heading, parser, key in [
        ("Resources", parse_resource_items, "resources"),
        ("Materials & Methods", parse_materials, "materials_and_methods"),
        ("At Scale", parse_scale_notes, "scale_notes"),
        ("Climate Adaptations", parse_location_adaptations, "location_adaptations"),
    ]:
        section_text = parse_section(text, heading)
        if section_text:
            parsed = parser(section_text)
            if parsed:
                props[key] = parsed

    # Visual gallery (only if no inline visuals)
    visuals_text = parse_section(text, "Visuals")
    if visuals_text:
        v = parse_visuals(visuals_text)
        if v and not inline_visuals:
            props["visuals"] = v

    # Cost notes (raw text)
    costs_text = parse_section(text, "Costs")
    if costs_text:
        props["cost_notes"] = costs_text

    return {
        "id": fm.get("id", filepath.stem),
        "name": title_match.group(1).strip() if title_match else filepath.stem.replace("-", " ").title(),
        "description": quote_match.group(1).strip() if quote_match else "",
        "hz": hz,
        "status": fm.get("status", "seed"),
        "properties": props,
    }


# ── HTTP helpers ──────────────────────────────────────────────────────

def api_get(url: str, timeout: int = 30) -> Any:
    """GET JSON from URL. Returns parsed JSON or raises."""
    if httpx:
        resp = httpx.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    else:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read())


def api_patch(
    url: str,
    body: dict,
    timeout: int = 30,
    retries: int = 4,
    headers: dict[str, str] | None = None,
) -> bool:
    """PATCH JSON to URL. Returns True on 200. Backs off on 429 rate limits."""
    request_headers = headers or {}
    for attempt in range(retries):
        if httpx:
            resp = httpx.patch(url, json=body, timeout=timeout, headers=request_headers)
            if resp.status_code == 200:
                return True
            if resp.status_code == 429 and attempt < retries - 1:
                time.sleep(1.0 * (attempt + 1))
                continue
            print(f"  ERROR: {resp.status_code} {resp.text[:200]}", file=sys.stderr)
            return False
        else:
            data = json.dumps(body).encode()
            req = urllib.request.Request(url, data=data, method="PATCH")
            req.add_header("Content-Type", "application/json")
            for key, value in request_headers.items():
                req.add_header(key, value)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.status == 200
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < retries - 1:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                print(f"  ERROR: {e}", file=sys.stderr)
                return False
            except Exception as e:
                print(f"  ERROR: {e}", file=sys.stderr)
                return False
    return False


def api_post(
    url: str,
    body: dict,
    timeout: int = 30,
    retries: int = 3,
    headers: dict[str, str] | None = None,
) -> int:
    """POST JSON to URL with retries. Returns HTTP status code (0 on total failure)."""
    request_headers = headers or {}
    for attempt in range(retries):
        try:
            if httpx:
                resp = httpx.post(url, json=body, timeout=timeout, headers=request_headers)
                if resp.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                return resp.status_code
            else:
                data = json.dumps(body).encode()
                req = urllib.request.Request(url, data=data, method="POST")
                req.add_header("Content-Type", "application/json")
                for key, value in request_headers.items():
                    req.add_header(key, value)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.status
        except Exception as e:
            err_str = str(e)
            # urllib wraps HTTP errors in the exception message
            for code in ("409", "404", "429"):
                if code in err_str:
                    if code == "429":
                        time.sleep(2 ** attempt)
                        continue
                    return int(code)
            if attempt == retries - 1:
                print(f"  ERROR: {e}", file=sys.stderr)
    return 0


def download_image(url: str, dest: Path, retries: int = 5, min_bytes: int = 1000) -> bool:
    """Download an image with retries. Handles 503 (busy) and 429 (rate limit)."""
    for attempt in range(retries):
        try:
            if httpx:
                resp = httpx.get(url, timeout=120, follow_redirects=True)
                if resp.status_code == 200 and len(resp.content) > min_bytes:
                    dest.write_bytes(resp.content)
                    return True
                if resp.status_code in (503, 429):
                    wait = 10 * (attempt + 1)  # 10s, 20s, 30s, 40s, 50s
                    print(f"    {resp.status_code}, waiting {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
                print(f"    HTTP {resp.status_code}, {len(resp.content)} bytes", file=sys.stderr)
            else:
                urllib.request.urlretrieve(url, str(dest))
                if dest.stat().st_size > min_bytes:
                    return True
        except Exception as e:
            print(f"    Error: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    return False
