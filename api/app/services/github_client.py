"""GitHub API client — spec 029.

REST wrapper with:
- optional token auth (GITHUB_TOKEN)
- rate-limit handling (sleep until reset when exhausted)
- basic ETag conditional requests + in-memory response cache
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import httpx


class GitHubClient:
    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = "https://api.github.com",
        user_agent: str = "coherence-network/1.0",
        timeout: float = 20.0,
    ) -> None:
        env_token = os.getenv("GITHUB_TOKEN")
        if not env_token:
            env_token = os.getenv("GH_TOKEN")
        if env_token:
            env_token = env_token.strip() or None
        self._token = token or env_token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": user_agent,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"

        # Per-process caches (good enough for scripts / API pod lifetime)
        self._etag_by_url: dict[str, str] = {}
        self._json_cache_by_url: dict[str, Any] = {}

    def _sleep_for_rate_limit_if_needed(self, r: httpx.Response) -> None:
        remaining = r.headers.get("X-RateLimit-Remaining")
        reset = r.headers.get("X-RateLimit-Reset")
        try:
            rem_i = int(remaining) if remaining is not None else None
            reset_i = int(reset) if reset is not None else None
        except ValueError:
            rem_i, reset_i = None, None

        if rem_i == 0 and reset_i:
            now = int(time.time())
            delay = max(0, reset_i - now) + 1
            time.sleep(delay)

    def _request(self, method: str, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        h = dict(self._headers)
        if headers:
            h.update(headers)
        with httpx.Client(timeout=self._timeout, headers=h) as client:
            r = client.request(method, url)
        self._sleep_for_rate_limit_if_needed(r)

        # If 403 is rate-limit, back off until reset then retry once.
        if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
            self._sleep_for_rate_limit_if_needed(r)
            with httpx.Client(timeout=self._timeout, headers=h) as client:
                r = client.request(method, url)
        return r

    def get_json(self, path: str) -> Any:
        """GET JSON for a path or full URL. Uses ETag conditional requests when possible."""
        url = path if path.startswith("http") else f"{self._base_url}{path}"

        extra_headers: dict[str, str] = {}
        etag = self._etag_by_url.get(url)
        if etag:
            extra_headers["If-None-Match"] = etag

        r = self._request("GET", url, headers=extra_headers)

        if r.status_code == 304:
            if url in self._json_cache_by_url:
                return self._json_cache_by_url[url]
            # If cache was lost, retry without condition.
            r = self._request("GET", url, headers={})

        if r.status_code >= 400:
            # Keep it simple for now; callers can catch and continue.
            raise RuntimeError(f"GitHub API error {r.status_code} for {url}: {r.text[:200]}")

        new_etag = r.headers.get("ETag")
        if new_etag:
            self._etag_by_url[url] = new_etag

        data = r.json()
        self._json_cache_by_url[url] = data
        return data

    def get_repo(self, owner: str, repo: str) -> dict:
        return self.get_json(f"/repos/{owner}/{repo}")

    def list_contributors(self, owner: str, repo: str, per_page: int = 100, max_pages: int = 5) -> list[dict]:
        """List contributors. Caps pages to avoid runaway API usage."""
        out: list[dict] = []
        for page in range(1, max_pages + 1):
            data = self.get_json(
                f"/repos/{owner}/{repo}/contributors?per_page={per_page}&page={page}&anon=false"
            )
            if not isinstance(data, list):
                break
            out.extend(data)
            if len(data) < per_page:
                break
        return out

    def list_commits(
        self,
        owner: str,
        repo: str,
        since_iso_utc: str,
        per_page: int = 100,
        max_pages: int = 3,
    ) -> list[dict]:
        """List commits since ISO-8601 UTC timestamp (e.g., 2026-02-01T00:00:00Z)."""
        out: list[dict] = []
        for page in range(1, max_pages + 1):
            data = self.get_json(
                f"/repos/{owner}/{repo}/commits?since={since_iso_utc}&per_page={per_page}&page={page}"
            )
            if not isinstance(data, list):
                break
            out.extend(data)
            if len(data) < per_page:
                break
        return out
