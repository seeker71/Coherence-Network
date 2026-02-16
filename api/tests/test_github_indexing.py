"""Tests for GitHub contributor/organization indexing (spec 029).

Validates GraphStore GitHub methods, GitHubContributor/GitHubOrganization models,
and index_github.py script integration.
"""

import tempfile
from datetime import datetime

import pytest

from app.adapters.graph_store import InMemoryGraphStore
from app.models.github_contributor import GitHubContributor, GitHubContributorCreate
from app.models.github_organization import GitHubOrganization, GitHubOrganizationCreate
from app.models.project import Project


def test_github_contributor_model():
    """GitHubContributor model should have required fields."""
    contrib = GitHubContributor(
        id="github:octocat",
        login="octocat",
        name="The Octocat",
        avatar_url="https://github.com/images/octocat.png",
        contributions_count=42,
    )

    assert contrib.id == "github:octocat"
    assert contrib.source == "github"
    assert contrib.login == "octocat"
    assert contrib.name == "The Octocat"
    assert contrib.contributions_count == 42
    assert contrib.created_at is not None


def test_github_contributor_create_model():
    """GitHubContributorCreate should validate input."""
    contrib = GitHubContributorCreate(
        login="octocat",
        name="The Octocat",
        contributions_count=10,
    )

    assert contrib.login == "octocat"
    assert contrib.name == "The Octocat"
    assert contrib.contributions_count == 10


def test_github_organization_model():
    """GitHubOrganization model should have required fields."""
    org = GitHubOrganization(
        id="github:facebook",
        login="facebook",
        type="Organization",
        name="Facebook",
    )

    assert org.id == "github:facebook"
    assert org.login == "facebook"
    assert org.type == "Organization"
    assert org.name == "Facebook"


def test_graphstore_upsert_github_contributor():
    """GraphStore should upsert GitHub contributors."""
    store = InMemoryGraphStore()

    contrib = GitHubContributor(
        id="github:alice",
        login="alice",
        name="Alice",
        contributions_count=10,
    )

    result = store.upsert_github_contributor(contrib)

    assert result.id == "github:alice"
    assert result.login == "alice"


def test_graphstore_get_github_contributor():
    """GraphStore should retrieve GitHub contributors by ID."""
    store = InMemoryGraphStore()

    contrib = GitHubContributor(
        id="github:bob",
        login="bob",
        contributions_count=5,
    )
    store.upsert_github_contributor(contrib)

    retrieved = store.get_github_contributor("github:bob")

    assert retrieved is not None
    assert retrieved.login == "bob"
    assert retrieved.contributions_count == 5


def test_graphstore_get_github_contributor_not_found():
    """GraphStore should return None for non-existent contributors."""
    store = InMemoryGraphStore()

    result = store.get_github_contributor("github:nonexistent")

    assert result is None


def test_graphstore_list_github_contributors():
    """GraphStore should list all GitHub contributors."""
    store = InMemoryGraphStore()

    contrib1 = GitHubContributor(id="github:alice", login="alice", contributions_count=10)
    contrib2 = GitHubContributor(id="github:bob", login="bob", contributions_count=5)

    store.upsert_github_contributor(contrib1)
    store.upsert_github_contributor(contrib2)

    contributors = store.list_github_contributors(limit=100)

    assert len(contributors) == 2
    logins = {c.login for c in contributors}
    assert "alice" in logins
    assert "bob" in logins


def test_graphstore_list_github_contributors_limit():
    """GraphStore should respect limit parameter."""
    store = InMemoryGraphStore()

    for i in range(10):
        contrib = GitHubContributor(id=f"github:user{i}", login=f"user{i}", contributions_count=i)
        store.upsert_github_contributor(contrib)

    contributors = store.list_github_contributors(limit=3)

    assert len(contributors) == 3


def test_graphstore_upsert_github_organization():
    """GraphStore should upsert GitHub organizations."""
    store = InMemoryGraphStore()

    org = GitHubOrganization(
        id="github:facebook",
        login="facebook",
        type="Organization",
        name="Facebook",
    )

    result = store.upsert_github_organization(org)

    assert result.id == "github:facebook"
    assert result.login == "facebook"


def test_graphstore_get_github_organization():
    """GraphStore should retrieve GitHub organizations by ID."""
    store = InMemoryGraphStore()

    org = GitHubOrganization(
        id="github:google",
        login="google",
        type="Organization",
    )
    store.upsert_github_organization(org)

    retrieved = store.get_github_organization("github:google")

    assert retrieved is not None
    assert retrieved.login == "google"


def test_graphstore_add_github_contributes_to():
    """GraphStore should create CONTRIBUTES_TO edges."""
    store = InMemoryGraphStore()

    # Create project
    project = Project(
        ecosystem="npm",
        name="react",
        version="18.2.0",
        description="React library",
        repository_url="https://github.com/facebook/react",
    )
    store.upsert_project(project)

    # Create contributor
    contrib = GitHubContributor(id="github:gaearon", login="gaearon", contributions_count=1000)
    store.upsert_github_contributor(contrib)

    # Add edge
    store.add_github_contributes_to("github:gaearon", "npm", "react")

    # Verify edge exists
    contributors = store.get_project_github_contributors("npm", "react")
    assert len(contributors) == 1
    assert contributors[0].login == "gaearon"


def test_graphstore_get_project_github_contributors():
    """GraphStore should retrieve all contributors for a project."""
    store = InMemoryGraphStore()

    # Create project
    project = Project(ecosystem="npm", name="lodash", version="4.17.21", description="Lodash utility library")
    store.upsert_project(project)

    # Create multiple contributors
    contrib1 = GitHubContributor(id="github:jdalton", login="jdalton", contributions_count=500)
    contrib2 = GitHubContributor(id="github:bnjmnt4n", login="bnjmnt4n", contributions_count=100)

    store.upsert_github_contributor(contrib1)
    store.upsert_github_contributor(contrib2)

    store.add_github_contributes_to("github:jdalton", "npm", "lodash")
    store.add_github_contributes_to("github:bnjmnt4n", "npm", "lodash")

    # Retrieve contributors
    contributors = store.get_project_github_contributors("npm", "lodash")

    assert len(contributors) == 2
    logins = {c.login for c in contributors}
    assert "jdalton" in logins
    assert "bnjmnt4n" in logins


def test_graphstore_get_project_github_contributors_empty():
    """GraphStore should return empty list for project with no contributors."""
    store = InMemoryGraphStore()

    project = Project(ecosystem="pypi", name="requests", version="2.31.0", description="HTTP library")
    store.upsert_project(project)

    contributors = store.get_project_github_contributors("pypi", "requests")

    assert contributors == []


def test_graphstore_persist_github_data():
    """GraphStore should persist GitHub data to JSON."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        persist_path = f.name

    try:
        # Create store and add GitHub data
        store = InMemoryGraphStore(persist_path=persist_path)

        contrib = GitHubContributor(id="github:test", login="test", contributions_count=1)
        org = GitHubOrganization(id="github:testorg", login="testorg", type="Organization")

        store.upsert_github_contributor(contrib)
        store.upsert_github_organization(org)

        project = Project(ecosystem="npm", name="test-pkg", version="1.0.0", description="Test package")
        store.upsert_project(project)
        store.add_github_contributes_to("github:test", "npm", "test-pkg")

        store.save()

        # Load into new store
        store2 = InMemoryGraphStore(persist_path=persist_path)

        # Verify data persisted
        loaded_contrib = store2.get_github_contributor("github:test")
        assert loaded_contrib is not None
        assert loaded_contrib.login == "test"

        loaded_org = store2.get_github_organization("github:testorg")
        assert loaded_org is not None
        assert loaded_org.login == "testorg"

        contributors = store2.get_project_github_contributors("npm", "test-pkg")
        assert len(contributors) == 1
        assert contributors[0].login == "test"

    finally:
        import os

        if os.path.exists(persist_path):
            os.unlink(persist_path)


def test_graphstore_upsert_github_contributor_updates_existing():
    """GraphStore should update existing GitHub contributors on upsert."""
    store = InMemoryGraphStore()

    # Create initial contributor
    contrib = GitHubContributor(id="github:alice", login="alice", contributions_count=10)
    store.upsert_github_contributor(contrib)

    # Update with new data
    updated = GitHubContributor(id="github:alice", login="alice", contributions_count=20, name="Alice Smith")
    store.upsert_github_contributor(updated)

    # Verify update
    retrieved = store.get_github_contributor("github:alice")
    assert retrieved.contributions_count == 20
    assert retrieved.name == "Alice Smith"


def test_graphstore_add_github_contributes_to_no_duplicates():
    """GraphStore should not create duplicate CONTRIBUTES_TO edges."""
    store = InMemoryGraphStore()

    project = Project(ecosystem="npm", name="react", version="18.2.0", description="React library")
    store.upsert_project(project)

    contrib = GitHubContributor(id="github:gaearon", login="gaearon", contributions_count=1000)
    store.upsert_github_contributor(contrib)

    # Add edge twice
    store.add_github_contributes_to("github:gaearon", "npm", "react")
    store.add_github_contributes_to("github:gaearon", "npm", "react")

    # Should only have one contributor
    contributors = store.get_project_github_contributors("npm", "react")
    assert len(contributors) == 1


def test_index_github_script_imports():
    """index_github.py should have correct imports."""
    import sys
    import os

    _api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(_api_dir, "scripts", "index_github.py")

    with open(script_path, "r") as f:
        content = f.read()

    # Verify correct imports
    assert "from app.models.github_contributor import GitHubContributor" in content
    assert "from app.models.github_organization import GitHubOrganization" in content
    assert "from app.adapters.graph_store import InMemoryGraphStore" in content
    assert "from app.services.github_client import GitHubClient" in content


def test_index_github_script_uses_correct_methods():
    """index_github.py should use GitHub-specific methods."""
    import sys
    import os

    _api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(_api_dir, "scripts", "index_github.py")

    with open(script_path, "r") as f:
        content = f.read()

    # Verify correct method calls
    assert "store.upsert_github_contributor" in content
    assert "store.upsert_github_organization" in content
    assert "store.add_github_contributes_to" in content
