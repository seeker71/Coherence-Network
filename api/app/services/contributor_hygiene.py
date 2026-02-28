from __future__ import annotations

import os

DEFAULT_TEST_EMAIL_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "invalid",
    "invalid.local",
    "localhost",
    "test",
    "test.local",
}

DEFAULT_PLUS_ALIAS_DOMAINS = {
    "coherence.network",
}

DEFAULT_INTERNAL_EMAIL_PREFIXES = {
    "deploy-test",
    "ci-bot",
    "e2e",
    "automation",
    "machine-reviewer",
}


def _configured_test_domains() -> set[str]:
    raw = os.getenv("TEST_CONTRIBUTOR_EMAIL_DOMAINS", "").strip()
    if not raw:
        return set(DEFAULT_TEST_EMAIL_DOMAINS)
    domains = {chunk.strip().lower() for chunk in raw.split(",") if chunk.strip()}
    return domains or set(DEFAULT_TEST_EMAIL_DOMAINS)


def _configured_plus_alias_domains() -> set[str]:
    raw = os.getenv("CONTRIBUTOR_PLUS_ALIAS_DOMAINS", "").strip()
    if not raw:
        return set(DEFAULT_PLUS_ALIAS_DOMAINS)
    domains = {chunk.strip().lower() for chunk in raw.split(",") if chunk.strip()}
    return domains or set(DEFAULT_PLUS_ALIAS_DOMAINS)


def _configured_alias_map() -> dict[str, str]:
    raw = os.getenv("CONTRIBUTOR_EMAIL_ALIAS_MAP", "").strip()
    if not raw:
        return {}
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        text = pair.strip()
        if not text or "=" not in text:
            continue
        source_raw, target_raw = text.split("=", 1)
        source = _normalize_email_basic(source_raw)
        target = _normalize_email_basic(target_raw)
        if source and target:
            mapping[source] = target
    return mapping


def _configured_internal_prefixes() -> set[str]:
    raw = os.getenv("INTERNAL_CONTRIBUTOR_EMAIL_PREFIXES", "").strip()
    if not raw:
        return set(DEFAULT_INTERNAL_EMAIL_PREFIXES)
    prefixes = {chunk.strip().lower() for chunk in raw.split(",") if chunk.strip()}
    return prefixes or set(DEFAULT_INTERNAL_EMAIL_PREFIXES)


def normalize_contributor_email(email: str | None) -> str:
    """Normalize contributor email for stable identity matching."""
    value = _normalize_email_basic(email)
    if not value:
        return ""
    alias_map = _configured_alias_map()
    return alias_map.get(value, value)


def _normalize_email_basic(email: str | None) -> str:
    if not email:
        return ""
    value = str(email).strip().lower()
    if "@" not in value:
        return value
    local, domain = value.rsplit("@", 1)
    if domain in _configured_plus_alias_domains() and "+" in local:
        local = local.split("+", 1)[0]
    return f"{local}@{domain}"


def is_test_contributor_email(email: str | None) -> bool:
    value = normalize_contributor_email(email)
    if not value:
        return False
    if "@" not in value:
        return False
    domain = value.rsplit("@", 1)[1]
    return domain in _configured_test_domains()


def is_internal_contributor_email(email: str | None) -> bool:
    """Heuristic classifier for non-human/system verification identities."""
    value = normalize_contributor_email(email)
    if not value:
        return False
    if is_test_contributor_email(value):
        return True
    if "@" not in value:
        return False
    local = value.rsplit("@", 1)[0]
    for prefix in _configured_internal_prefixes():
        if local == prefix or local.startswith(f"{prefix}-") or local.startswith(f"{prefix}_"):
            return True
    return False
