"""Tests for the Geolocation Interface.

Covers AC-1 to AC-9 from geolocation spec.
"""
from __future__ import annotations
import types, sys
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from app.main import app
from app.models.geolocation import (
    ContributorLocationSet, LocalNewsResonanceResponse,
    LocationVisibility, NearbyContributor, NearbyIdea, NearbyResult,
)
from app.services import geolocation_service, graph_service
