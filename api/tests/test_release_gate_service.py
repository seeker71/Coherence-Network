"""Tests for the pure-helper layer of release_gate_service (spec: release-gates).

The full router surface (subprocess, HTTP, cache) is integration territory.
This test exercises the spec-aligned pure logic inside the service:

  _ensure_job_defaults    — job construction + input clamping
  _is_job_due             — polling predicate
  _next_retry_delay_seconds — retry-delay floor
  _headers                — GitHub API headers + auth
  branch-head cache       — TTL-bound caching of git SHAs

Covers the spec's named requirements where they live in pure code:
  - "Polling with timeout for async CI completion"
  - "Returns detailed reports with pass/fail reasons" (job shape)
  - "Integrates with GitHub API for PR status, checks, approvals" (headers)
"""
from __future__ import annotations

import time

from app.services import release_gate_service as rgs


# ---------------------------------------------------------------------------
# _ensure_job_defaults
# ---------------------------------------------------------------------------


def test_ensure_job_defaults_returns_full_job_shape():
    """Job dict carries every key the polling loop expects."""
    job = rgs._ensure_job_defaults(
        repository="owner/repo",
        branch="main",
        api_base="https://api.example.com",
        web_base="https://example.com",
        expected_sha=None,
        max_attempts=5,
        timeout=10.0,
        poll_seconds=30.0,
    )
    for key in (
        "job_id", "repository", "branch", "api_base", "web_base",
        "expected_sha", "timeout", "poll_seconds", "status",
        "attempts", "max_attempts", "next_run_at",
        "created_at", "updated_at", "completed_at",
    ):
        assert key in job


def test_ensure_job_defaults_clamps_timeout_and_poll_to_minimum_one():
    """timeout and poll_seconds floor at 1.0 — no zero-second busy loops."""
    job = rgs._ensure_job_defaults(
        repository="r", branch="b",
        api_base="a", web_base="w",
        expected_sha=None, max_attempts=None,
        timeout=0.0, poll_seconds=0.0,
    )
    assert job["timeout"] == 1.0
    assert job["poll_seconds"] == 1.0


def test_ensure_job_defaults_clamps_max_attempts_to_minimum_one():
    """max_attempts floors at 1 — at least one attempt always runs."""
    job = rgs._ensure_job_defaults(
        repository="r", branch="b",
        api_base="a", web_base="w",
        expected_sha=None, max_attempts=-3,
        timeout=8.0, poll_seconds=30.0,
    )
    assert job["max_attempts"] == 1


def test_ensure_job_defaults_falls_back_to_canonical_repo():
    """Empty repository / branch fall back to the network's defaults."""
    job = rgs._ensure_job_defaults(
        repository="   ", branch="   ",
        api_base="   ", web_base="   ",
        expected_sha=None, max_attempts=3,
        timeout=8.0, poll_seconds=30.0,
    )
    assert job["repository"] == "seeker71/Coherence-Network"
    assert job["branch"] == "main"
    assert job["api_base"] == "https://api.coherencycoin.com"
    assert job["web_base"] == "https://coherencycoin.com"


def test_ensure_job_defaults_strips_expected_sha():
    """expected_sha is trimmed; empty/whitespace becomes None."""
    j1 = rgs._ensure_job_defaults(
        repository="r", branch="b", api_base="a", web_base="w",
        expected_sha="  abc123  ", max_attempts=1, timeout=8.0, poll_seconds=30.0,
    )
    j2 = rgs._ensure_job_defaults(
        repository="r", branch="b", api_base="a", web_base="w",
        expected_sha="   ", max_attempts=1, timeout=8.0, poll_seconds=30.0,
    )
    assert j1["expected_sha"] == "abc123"
    assert j2["expected_sha"] is None


# ---------------------------------------------------------------------------
# _is_job_due
# ---------------------------------------------------------------------------


def test_is_job_due_returns_false_for_non_scheduled_status():
    """Only scheduled/retrying jobs are due — completed/failed/anything else skipped."""
    for status in ("completed", "failed", "running", ""):
        job = {"status": status, "next_run_at": 0.0}
        assert rgs._is_job_due(job, now=1e10) is False


def test_is_job_due_returns_true_when_next_run_at_in_past():
    """A scheduled job whose next_run_at has passed is due."""
    job = {"status": "scheduled", "next_run_at": 100.0}
    assert rgs._is_job_due(job, now=200.0) is True


def test_is_job_due_returns_false_when_next_run_at_in_future():
    """A scheduled job whose next_run_at is in the future is not due yet."""
    job = {"status": "scheduled", "next_run_at": 1000.0}
    assert rgs._is_job_due(job, now=500.0) is False


def test_is_job_due_returns_true_when_next_run_at_is_none():
    """Missing next_run_at means run immediately."""
    job = {"status": "retrying", "next_run_at": None}
    assert rgs._is_job_due(job, now=time.time()) is True


def test_is_job_due_handles_iso_timestamp():
    """ISO 8601 string next_run_at is parsed and compared correctly."""
    job = {"status": "scheduled", "next_run_at": "2020-01-01T00:00:00Z"}
    assert rgs._is_job_due(job, now=time.time()) is True


# ---------------------------------------------------------------------------
# _next_retry_delay_seconds
# ---------------------------------------------------------------------------


def test_next_retry_delay_floors_at_one_second():
    """Even with base_seconds=0, the delay is at least 1 second (no busy loop)."""
    assert rgs._next_retry_delay_seconds(attempt=3, base_seconds=0) == 1
    assert rgs._next_retry_delay_seconds(attempt=1, base_seconds=-5) == 1


def test_next_retry_delay_returns_base_when_positive():
    """When base_seconds is positive, it's returned as-is (no growth — bounded retries)."""
    assert rgs._next_retry_delay_seconds(attempt=2, base_seconds=30) == 30
    assert rgs._next_retry_delay_seconds(attempt=10, base_seconds=60) == 60


# ---------------------------------------------------------------------------
# _headers
# ---------------------------------------------------------------------------


def test_headers_always_include_github_api_version_and_accept(monkeypatch):
    """Every GitHub API call carries the API version + accept headers."""
    monkeypatch.setattr(rgs, "_github_token_fallback", lambda _t=None: None)
    headers = rgs._headers(github_token=None)
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert "Authorization" not in headers


def test_headers_include_authorization_when_token_present(monkeypatch):
    """When a token resolves (passed or env fallback), Authorization is set as Bearer."""
    monkeypatch.setattr(rgs, "_github_token_fallback", lambda _t=None: "ghp_secrettoken")
    headers = rgs._headers(github_token="ghp_secrettoken")
    assert headers["Authorization"] == "Bearer ghp_secrettoken"


# ---------------------------------------------------------------------------
# Branch-head SHA cache
# ---------------------------------------------------------------------------


def test_branch_head_cache_stores_and_returns_within_ttl(monkeypatch):
    """A cached SHA within TTL is returned; the cache is keyed by (repo, branch)."""
    monkeypatch.setattr(rgs, "_branch_head_cache_ttl_seconds", lambda: 60.0)
    rgs._BRANCH_HEAD_SHA_CACHE.clear()

    rgs._cache_branch_head_sha("owner/repo", "main", "abc123")
    assert rgs._read_cached_branch_head_sha("owner/repo", "main") == "abc123"
    # Different branch is a separate cache entry
    assert rgs._read_cached_branch_head_sha("owner/repo", "develop") is None


def test_branch_head_cache_evicts_after_ttl(monkeypatch):
    """An entry past its expiry time is evicted on read and returns None."""
    monkeypatch.setattr(rgs, "_branch_head_cache_ttl_seconds", lambda: 0.0)
    rgs._BRANCH_HEAD_SHA_CACHE.clear()

    rgs._cache_branch_head_sha("owner/repo", "main", "abc123")
    # TTL is 0; the next read should evict.
    assert rgs._read_cached_branch_head_sha("owner/repo", "main") is None
    assert ("owner/repo", "main") not in rgs._BRANCH_HEAD_SHA_CACHE


def test_branch_head_cache_ignores_empty_sha():
    """Empty or non-string SHA is silently dropped — the cache never stores junk."""
    rgs._BRANCH_HEAD_SHA_CACHE.clear()
    rgs._cache_branch_head_sha("owner/repo", "main", "")
    assert ("owner/repo", "main") not in rgs._BRANCH_HEAD_SHA_CACHE
