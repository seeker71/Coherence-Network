from __future__ import annotations

from datetime import datetime, timezone

from scripts import collect_ai_agent_intel as intel


def test_build_n8n_advisory_sources_filters_window_and_severity() -> None:
    now = datetime(2026, 3, 2, tzinfo=timezone.utc)
    payload = [
        {
            "ghsa_id": "GHSA-CRIT-1234",
            "severity": "critical",
            "published_at": "2026-03-01T12:00:00Z",
            "html_url": "https://github.com/n8n-io/n8n/security/advisories/GHSA-CRIT-1234",
        },
        {
            "ghsa_id": "GHSA-MED-1234",
            "severity": "medium",
            "published_at": "2026-03-01T12:00:00Z",
            "html_url": "https://github.com/n8n-io/n8n/security/advisories/GHSA-MED-1234",
        },
        {
            "ghsa_id": "GHSA-HIGH-OLD",
            "severity": "high",
            "published_at": "2026-01-01T00:00:00Z",
            "html_url": "https://github.com/n8n-io/n8n/security/advisories/GHSA-HIGH-OLD",
        },
    ]

    rows = intel._build_n8n_advisory_sources(payload, now=now, window_days=14)

    assert len(rows) == 1
    assert rows[0].id == "n8n_ghsa-crit-1234"
    assert rows[0].severity == "critical"
    assert rows[0].category == "security"
    assert "n8n" in rows[0].tags


def test_build_digest_includes_dynamic_n8n_advisories(monkeypatch) -> None:
    source = intel.SourceSpec(
        id="base_source",
        url="https://example.com/base",
        title_hint="base",
        published_at="2026-03-01T00:00:00Z",
        source_type="official_blog",
        category="framework",
        tags=("framework",),
        why_it_matters="base source",
    )
    dynamic_source = intel.SourceSpec(
        id="n8n_ghsa-demo",
        url="https://github.com/n8n-io/n8n/security/advisories/GHSA-DEMO",
        title_hint="demo advisory",
        published_at="2026-03-01T00:00:00Z",
        source_type="official_advisory",
        category="security",
        tags=("security", "n8n"),
        why_it_matters="demo security advisory",
        severity="high",
    )

    monkeypatch.setattr(intel, "SOURCES", (source,))
    monkeypatch.setattr(
        intel,
        "_fetch_n8n_security_advisory_sources",
        lambda *args, **kwargs: [dynamic_source],  # noqa: ARG005
    )
    monkeypatch.setattr(
        intel,
        "_fetch_source",
        lambda _client, source, _timeout: {
            "fetch_ok": True,
            "http_status": 200,
            "final_url": source.url,
            "title": source.title_hint,
            "content_bytes": 10,
            "error": "",
        },
    )

    digest = intel._build_digest(window_days=14, timeout_seconds=0.1)

    ids = {row["id"] for row in digest["sources"]}
    assert ids == {"base_source", "n8n_ghsa-demo"}
    assert digest["source_count"] == 2


def test_build_security_watch_splits_high_and_critical() -> None:
    digest = {
        "generated_at": "2026-03-02T00:00:00Z",
        "sources": [
            {
                "id": "security_critical",
                "title": "critical advisory",
                "url": "https://example.com/critical",
                "published_at": "2026-03-01T00:00:00Z",
                "severity": "critical",
                "category": "security",
                "http_status": 200,
            },
            {
                "id": "security_high",
                "title": "high advisory",
                "url": "https://example.com/high",
                "published_at": "2026-03-01T00:00:00Z",
                "severity": "high",
                "category": "security",
                "http_status": 200,
            },
        ],
    }

    watch = intel._build_security_watch(digest)

    assert len(watch["open_critical_severity"]) == 1
    assert len(watch["open_high_severity"]) == 1
