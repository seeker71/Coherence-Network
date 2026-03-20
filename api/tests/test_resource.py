"""Tests for generic resource endpoint (TEMPLATE spec example).

Referenced by: specs/TEMPLATE.md
Status: Stub -- template example resource endpoint does not exist.
"""

import pytest


@pytest.mark.skip(reason="Template example resource -- not a real endpoint")
class TestResource:
    def test_get_resource_200(self):
        """GET /api/resource/{id} returns 200 when found."""
        pass

    def test_get_resource_404(self):
        """GET /api/resource/{id} returns 404 when not found."""
        pass
