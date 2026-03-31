"""Tests for GitHub API client (spec 029).

Validates rate limiting, ETag caching, error handling, and pagination.
Uses mocked HTTP responses (respx) to avoid real GitHub API calls.
"""

import time
from unittest.mock import patch

import pytest
import respx
from httpx import Response

from app.services.github_client import GitHubClient


@respx.mock
def test_github_client_basic_get():
    """Client should make basic GET request with proper headers."""
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(200, json={"name": "repo", "full_name": "owner/repo"})
    )

    client = GitHubClient()
    data = client.get_repo("owner", "repo")

    assert data["name"] == "repo"
    assert len(respx.calls) == 1
    request = respx.calls[0].request
    assert "user-agent" in request.headers
    assert "accept" in request.headers


@respx.mock
def test_github_client_with_token_auth():
    """Client should include Bearer token when configured."""
    route = respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(200, json={"name": "repo"})
    )

    client = GitHubClient(token="test-token-123")
    client.get_repo("owner", "repo")

    request = route.calls[0].request
    assert "authorization" in request.headers
    assert request.headers["authorization"] == "Bearer test-token-123"


@respx.mock
def test_github_client_etag_caching():
    """Client should use ETag for conditional requests and cache responses."""
    # First request returns ETag
    route = respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(200, json={"name": "repo", "version": 1}, headers={"ETag": '"abc123"'})
    )

    client = GitHubClient()
    data1 = client.get_repo("owner", "repo")
    assert data1["version"] == 1

    # Second request with If-None-Match should return 304
    route.mock(return_value=Response(304, json={}))

    data2 = client.get_repo("owner", "repo")
    assert data2["version"] == 1  # From cache

    # Verify If-None-Match header was sent
    assert len(route.calls) == 2
    second_request = route.calls[1].request
    assert "if-none-match" in second_request.headers
    assert second_request.headers["if-none-match"] == '"abc123"'


@respx.mock
def test_github_client_rate_limit_exhausted():
    """Client should sleep and retry when rate limit exhausted (403)."""
    # First request hits rate limit
    route = respx.get("https://api.github.com/repos/owner/repo")
    route.mock(
        side_effect=[
            Response(
                403,
                json={"message": "API rate limit exceeded"},
                headers={
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + 2),
                },
            ),
            Response(200, json={"name": "repo"}),
        ]
    )

    client = GitHubClient()

    with patch("time.sleep") as mock_sleep:
        data = client.get_repo("owner", "repo")

        # Should have called sleep
        assert mock_sleep.called
        # Should have retried and succeeded
        assert data["name"] == "repo"
        assert len(route.calls) == 2


@respx.mock
def test_github_client_rate_limit_remaining_zero():
    """Client should sleep when rate limit remaining is 0."""
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(
            200,
            json={"name": "repo"},
            headers={
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + 1),
            },
        )
    )

    client = GitHubClient()

    with patch("time.sleep") as mock_sleep:
        client.get_repo("owner", "repo")

        # Should sleep when remaining is 0
        assert mock_sleep.called
        sleep_duration = mock_sleep.call_args[0][0]
        assert sleep_duration > 0


@respx.mock
def test_github_client_error_handling():
    """Client should raise error for 4xx/5xx responses."""
    respx.get("https://api.github.com/repos/owner/nonexistent").mock(
        return_value=Response(404, json={"message": "Not Found"})
    )

    client = GitHubClient()

    with pytest.raises(RuntimeError) as exc_info:
        client.get_repo("owner", "nonexistent")

    assert "404" in str(exc_info.value)
    assert "GitHub API error" in str(exc_info.value)


@respx.mock
def test_github_client_list_contributors_pagination():
    """Client should paginate contributors correctly."""
    # Page 1: full page
    route = respx.get("https://api.github.com/repos/owner/repo/contributors")
    route.mock(
        side_effect=[
            Response(200, json=[{"login": f"user{i}", "contributions": 100 - i} for i in range(100)]),
            Response(200, json=[{"login": f"user{i}", "contributions": 50 - i} for i in range(50)]),
        ]
    )

    client = GitHubClient()
    contributors = client.list_contributors("owner", "repo", per_page=100)

    assert len(contributors) == 150  # 100 + 50
    assert contributors[0]["login"] == "user0"
    assert len(route.calls) == 2


@respx.mock
def test_github_client_list_contributors_max_pages():
    """Client should respect max_pages limit to avoid runaway API usage."""
    # Return full pages to test max_pages cap
    route = respx.get("https://api.github.com/repos/owner/repo/contributors")
    route.mock(
        return_value=Response(200, json=[{"login": f"user{i}"} for i in range(100)])
    )

    client = GitHubClient()
    contributors = client.list_contributors("owner", "repo", per_page=100, max_pages=3)

    # Should stop at max_pages even though more data available
    assert len(contributors) == 300  # 100 * 3
    assert len(route.calls) == 3  # Only 3 requests made


@respx.mock
def test_github_client_list_commits_with_since():
    """Client should filter commits by since parameter."""
    since = "2026-02-01T00:00:00Z"

    route = respx.get(f"https://api.github.com/repos/owner/repo/commits?since={since}&per_page=100&page=1")
    route.mock(
        return_value=Response(
            200,
            json=[
                {"sha": "abc123", "commit": {"message": "feat: add feature"}},
                {"sha": "def456", "commit": {"message": "fix: bug fix"}},
            ],
        )
    )

    client = GitHubClient()
    commits = client.list_commits("owner", "repo", since_iso_utc=since)

    assert len(commits) == 2
    assert commits[0]["sha"] == "abc123"
    assert len(route.calls) == 1


@respx.mock
def test_github_client_list_commits_pagination():
    """Client should paginate commits correctly."""
    since = "2026-02-01T00:00:00Z"

    # Page 1
    route1 = respx.get(f"https://api.github.com/repos/owner/repo/commits?since={since}&per_page=100&page=1")
    route1.mock(return_value=Response(200, json=[{"sha": f"sha{i}"} for i in range(100)]))

    # Page 2 (partial)
    route2 = respx.get(f"https://api.github.com/repos/owner/repo/commits?since={since}&per_page=100&page=2")
    route2.mock(return_value=Response(200, json=[{"sha": f"sha{i}"} for i in range(30)]))

    client = GitHubClient()
    commits = client.list_commits("owner", "repo", since_iso_utc=since)

    assert len(commits) == 130
    assert len(respx.calls) == 2


@respx.mock
def test_github_client_custom_base_url():
    """Client should support custom base URL (e.g., GitHub Enterprise)."""
    respx.get("https://github.enterprise.com/api/v3/repos/owner/repo").mock(
        return_value=Response(200, json={"name": "repo"})
    )

    client = GitHubClient(base_url="https://github.enterprise.com/api/v3")
    data = client.get_repo("owner", "repo")

    assert data["name"] == "repo"


@respx.mock
def test_github_client_custom_timeout():
    """Client should use custom timeout when specified."""
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(200, json={"name": "repo"})
    )

    client = GitHubClient(timeout=30.0)
    # Just verify it doesn't error - timeout is used internally
    data = client.get_repo("owner", "repo")
    assert data["name"] == "repo"


@respx.mock
def test_github_client_304_with_lost_cache():
    """Client should retry without condition if cache is lost after 304."""
    # First request
    route = respx.get("https://api.github.com/repos/owner/repo")
    route.mock(
        side_effect=[
            Response(200, json={"name": "repo", "version": 1}, headers={"ETag": '"abc123"'}),
            Response(304, json={}),
            Response(200, json={"name": "repo", "version": 2}),
        ]
    )

    client = GitHubClient()
    client.get_repo("owner", "repo")

    # Manually clear cache to simulate cache loss
    client._json_cache_by_url.clear()

    data = client.get_repo("owner", "repo")
    assert data["version"] == 2  # Got fresh data
    assert len(route.calls) == 3


@respx.mock
def test_github_client_get_json_with_full_url():
    """Client should handle full URLs in addition to paths."""
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(200, json={"name": "repo"})
    )

    client = GitHubClient()
    data = client.get_json("https://api.github.com/repos/owner/repo")

    assert data["name"] == "repo"


@respx.mock
def test_github_client_rate_limit_headers_missing():
    """Client should handle missing rate limit headers gracefully."""
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(200, json={"name": "repo"})
        # No rate limit headers
    )

    client = GitHubClient()
    # Should not error
    data = client.get_repo("owner", "repo")
    assert data["name"] == "repo"


@respx.mock
def test_github_client_list_contributors_non_list_response():
    """Client should handle non-list responses in pagination gracefully."""
    respx.get("https://api.github.com/repos/owner/repo/contributors").mock(
        return_value=Response(200, json={"message": "Some error"})  # Not a list
    )

    client = GitHubClient()
    contributors = client.list_contributors("owner", "repo")

    # Should return empty list, not crash
    assert contributors == []
