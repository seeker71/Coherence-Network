"""Tests for InMemoryGraphStore — spec 019."""

import pytest

from app.adapters.graph_store import InMemoryGraphStore
from app.models.project import Project


@pytest.fixture
def store():
    return InMemoryGraphStore(persist_path=None)


def test_upsert_and_get_project(store):
    """upsert_project and get_project work correctly."""
    p = Project(
        name="react",
        ecosystem="npm",
        version="18.2.0",
        description="React",
        dependency_count=0,
    )
    store.upsert_project(p)
    got = store.get_project("npm", "react")
    assert got is not None
    assert got.name == "react"
    assert got.version == "18.2.0"


def test_get_project_missing_returns_none(store):
    """get_project returns None when not found."""
    assert store.get_project("npm", "nonexistent") is None


def test_search(store):
    """search returns projects matching name or description."""
    store.upsert_project(
        Project(name="react", ecosystem="npm", version="1", description="Lib", dependency_count=0)
    )
    store.upsert_project(
        Project(name="lodash", ecosystem="npm", version="1", description="React utils", dependency_count=0)
    )
    store.upsert_project(
        Project(name="vue", ecosystem="npm", version="1", description="Framework", dependency_count=0)
    )
    results = store.search("react", limit=10)
    assert len(results) >= 2  # react and lodash (description contains React)
    names = [r.name for r in results]
    assert "react" in names
    assert "lodash" in names


def test_add_dependency_recomputes_count(store):
    """add_dependency updates dependency_count."""
    store.upsert_project(
        Project(name="a", ecosystem="npm", version="1", description="", dependency_count=0)
    )
    store.upsert_project(
        Project(name="b", ecosystem="npm", version="1", description="", dependency_count=0)
    )
    store.add_dependency("npm", "a", "npm", "b")
    proj = store.get_project("npm", "a")
    assert proj is not None
    assert proj.dependency_count == 1


def test_count_projects(store):
    """count_projects returns correct count."""
    assert store.count_projects() == 0
    store.upsert_project(
        Project(name="a", ecosystem="npm", version="1", description="", dependency_count=0)
    )
    assert store.count_projects() == 1
    store.upsert_project(
        Project(name="b", ecosystem="npm", version="1", description="", dependency_count=0)
    )
    assert store.count_projects() == 2


def test_count_dependents(store):
    """count_dependents returns projects that depend on this one — spec 020."""
    for name in ["react", "lodash", "app"]:
        store.upsert_project(
            Project(name=name, ecosystem="npm", version="1", description="", dependency_count=0)
        )
    store.add_dependency("npm", "app", "npm", "react")
    store.add_dependency("npm", "app", "npm", "lodash")
    assert store.count_dependents("npm", "react") == 1
    assert store.count_dependents("npm", "lodash") == 1
    assert store.count_dependents("npm", "app") == 0
