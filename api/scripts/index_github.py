#!/usr/bin/env python3
"""Index GitHub contributors + recent activity for projects in GraphStore — spec 029.

Usage:
  python scripts/index_github.py [--persist PATH] [--limit N] [--eco npm|pypi] [--window-days 90] [-v]

Notes:
- Resolves GitHub repo from npm / PyPI metadata (best-effort)
- Stores Contributor + Organization nodes and edges in GraphStore
- Sets last_contribution_date on Contributors for activity_cadence
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

import httpx

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)
os.chdir(os.path.dirname(_api_dir))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_api_dir, ".env"))
except ImportError:
    pass

from app.adapters.graph_store import Contributor, InMemoryGraphStore, Organization
from app.services.github_client import GitHubClient

NPM_REGISTRY = "https://registry.npmjs.org"
PYPI_JSON = "https://pypi.org/pypi"

log = logging.getLogger(__name__)


_GH_RE = re.compile(r"github\.com[:/]+([^/]+)/([^/#]+)", re.IGNORECASE)


def _extract_github_owner_repo(url: str) -> Optional[tuple[str, str]]:
    if not url:
        return None
    u = url.strip().replace("git+", "")
    m = _GH_RE.search(u)
    if not m:
        return None
    owner = m.group(1).strip()
    repo = m.group(2).strip()
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    return (owner, repo)


def _resolve_npm_repo(package_name: str) -> Optional[tuple[str, str]]:
    try:
        r = httpx.get(f"{NPM_REGISTRY}/{quote(package_name, safe='')}", timeout=15.0)
        if r.status_code != 200:
            return None
        data = r.json()
        repo = data.get("repository")
        if isinstance(repo, dict):
            url = repo.get("url") or ""
        elif isinstance(repo, str):
            url = repo
        else:
            url = ""
        return _extract_github_owner_repo(url)
    except Exception as e:
        log.debug("npm resolve %s: %s", package_name, e)
        return None


def _resolve_pypi_repo(project_name: str) -> Optional[tuple[str, str]]:
    try:
        r = httpx.get(f"{PYPI_JSON}/{quote(project_name, safe='')}/json", timeout=15.0)
        if r.status_code != 200:
            return None
        data = r.json()
        info = data.get("info") or {}
        urls: list[str] = []
        home = info.get("home_page") or ""
        if isinstance(home, str) and home:
            urls.append(home)
        proj_urls = info.get("project_urls") or {}
        if isinstance(proj_urls, dict):
            for v in proj_urls.values():
                if isinstance(v, str) and v:
                    urls.append(v)
        for k in ("project_url", "download_url", "package_url"):
            v = info.get(k)
            if isinstance(v, str) and v:
                urls.append(v)
        for u in urls:
            hit = _extract_github_owner_repo(u)
            if hit:
                return hit
        return None
    except Exception as e:
        log.debug("pypi resolve %s: %s", project_name, e)
        return None


def _get_last_commit_date(
    gh: GitHubClient, owner: str, repo: str, login: str, window_days: int
) -> Optional[str]:
    """Get the most recent commit date for a contributor (ISO 8601 UTC)."""
    since = (datetime.now(timezone.utc) - timedelta(days=window_days)).replace(microsecond=0)
    since_iso = since.isoformat().replace("+00:00", "Z")
    try:
        commits = gh.get_json(
            f"/repos/{owner}/{repo}/commits?author={login}&since={since_iso}&per_page=1"
        )
        if isinstance(commits, list) and commits:
            commit_data = commits[0].get("commit", {})
            author_data = commit_data.get("author", {})
            date_str = author_data.get("date")
            if date_str:
                return date_str
    except Exception:
        pass
    return None


def _index_one(
    store: InMemoryGraphStore,
    gh: GitHubClient,
    eco: str,
    name: str,
    window_days: int,
    repo_cache: dict[str, Optional[tuple[str, str]]],
) -> bool:
    cache_key = f"{eco}:{name}"

    # Resolve GitHub repo (best-effort, cached per run)
    if cache_key in repo_cache:
        hit = repo_cache[cache_key]
    else:
        if eco.lower() == "npm":
            hit = _resolve_npm_repo(name)
        elif eco.lower() == "pypi":
            hit = _resolve_pypi_repo(name)
        else:
            hit = None
        repo_cache[cache_key] = hit

    if not hit:
        return False
    owner, repo = hit

    try:
        repo_info = gh.get_repo(owner, repo)
    except Exception as e:
        log.info("GitHub repo fetch failed %s/%s for %s:%s: %s", owner, repo, eco, name, e)
        return False

    # Upsert repo owner as Organization
    owner_info = repo_info.get("owner") or {}
    owner_login = (owner_info.get("login") or "").strip()
    owner_type = (owner_info.get("type") or "").strip() or "Organization"
    if owner_login:
        org = Organization(id=f"github:{owner_login}", login=owner_login, type=owner_type)
        store.upsert_organization(org)

    # Contributors
    try:
        contributors = gh.list_contributors(owner, repo)
    except Exception as e:
        log.info("GitHub contributors fetch failed %s/%s: %s", owner, repo, e)
        return False

    # Top 3 by contributions = maintainers (best-effort heuristic)
    top_logins: list[str] = []
    for c in contributors[:3]:
        login = (c.get("login") or "").strip()
        if login:
            top_logins.append(login.lower())

    for c in contributors:
        login = (c.get("login") or "").strip()
        if not login:
            continue
        cid = f"github:{login}"
        contributions = int(c.get("contributions") or 0)

        # Check for recent commit to set last_contribution_date
        last_date = _get_last_commit_date(gh, owner, repo, login, window_days)

        cc = Contributor(
            id=cid,
            source="github",
            login=login,
            name=c.get("name"),
            avatar_url=c.get("avatar_url"),
            contributions_count=contributions,
            last_contribution_date=last_date,
        )
        store.upsert_contributor(cc)
        store.add_contributes_to(cid, eco, name)
        if login.lower() in top_logins:
            store.add_maintains(cid, eco, name)

        # MEMBER_OF: link contributor to repo owner org
        if owner_login and login.lower() == owner_login.lower():
            store.add_member_of(cid, f"github:{owner_login}")

    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Index GitHub contributors into GraphStore")
    ap.add_argument(
        "--persist", default=None,
        help="Path to persist JSON (default: api/logs/graph_store.json)",
    )
    ap.add_argument(
        "--limit", type=int, default=None,
        help="Max projects to attempt",
    )
    ap.add_argument(
        "--eco", default=None,
        help="Only index a single ecosystem (npm or pypi). Default: all.",
    )
    ap.add_argument(
        "--window-days", type=int, default=90,
        help="Days window for last_contribution_date lookup (default 90).",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    persist = args.persist or os.path.join(_api_dir, "logs", "graph_store.json")
    store = InMemoryGraphStore(persist_path=persist)
    gh = GitHubClient()

    projects = list(store._projects.values())
    if args.eco:
        projects = [p for p in projects if p.ecosystem.lower() == args.eco.lower()]
    if args.limit is not None:
        projects = projects[: max(0, int(args.limit))]

    repo_cache: dict[str, Optional[tuple[str, str]]] = {}
    ok = 0
    tried = 0
    for p in projects:
        tried += 1
        if _index_one(store, gh, p.ecosystem, p.name, int(args.window_days), repo_cache):
            ok += 1
        if tried % 25 == 0:
            log.info("GitHub indexed %d/%d projects...", ok, tried)

    store.save()
    log.info("GitHub indexing complete: %d/%d succeeded", ok, tried)
    print(f"GitHub indexing complete: {ok}/{tried} succeeded")


if __name__ == "__main__":
    main()
