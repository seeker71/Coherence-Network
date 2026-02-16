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


def _configured_test_domains() -> set[str]:
    raw = os.getenv("TEST_CONTRIBUTOR_EMAIL_DOMAINS", "").strip()
    if not raw:
        return set(DEFAULT_TEST_EMAIL_DOMAINS)
    domains = {chunk.strip().lower() for chunk in raw.split(",") if chunk.strip()}
    return domains or set(DEFAULT_TEST_EMAIL_DOMAINS)


def is_test_contributor_email(email: str | None) -> bool:
    if not email:
        return False
    value = str(email).strip().lower()
    if "@" not in value:
        return False
    domain = value.rsplit("@", 1)[1]
    return domain in _configured_test_domains()
