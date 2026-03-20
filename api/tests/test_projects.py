"""Tests for projects API (GraphStore abstraction).

Referenced by: spec 019-graph-store-abstraction
Status: Stub -- projects router not currently mounted.
"""

import pytest


@pytest.mark.skip(reason="Projects router not currently mounted -- spec 019")
class TestProjectsAPI:
    def test_get_project_returns_200(self):
        """GET /api/projects/{ecosystem}/{name} returns 200 when project exists."""
        pass

    def test_get_project_returns_404(self):
        """GET /api/projects/{ecosystem}/{name} returns 404 when not found."""
        pass
