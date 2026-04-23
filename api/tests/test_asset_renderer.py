"""Tests for the asset-renderer-plugin spec pure-logic pieces.

Covers CC split validation and attribution (spec R4, R5, R9). Integration
tests — registering assets, registering renderers, rendering events
through the graph — remain TODO and belong in a subsequent PR that wires
up the router and graph storage.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.renderer import (
    MAX_RENDERER_BUNDLE_BYTES,
    RenderCCSplit,
    RendererCreate,
)
from app.services.render_attribution_service import (
    attribute_render_cc,
    resolve_split,
)


# ---------- RenderCCSplit validation (spec R5) ----------


def test_cc_split_default_is_80_15_5():
    split = RenderCCSplit()
    assert split.asset_creator == Decimal("0.80")
    assert split.renderer_creator == Decimal("0.15")
    assert split.host_node == Decimal("0.05")
    total = split.asset_creator + split.renderer_creator + split.host_node
    assert total == Decimal("1.00")


def test_cc_split_custom_sums_to_one():
    split = RenderCCSplit(
        asset_creator=Decimal("0.75"),
        renderer_creator=Decimal("0.20"),
        host_node=Decimal("0.05"),
    )
    total = split.asset_creator + split.renderer_creator + split.host_node
    assert total == Decimal("1.00")


def test_cc_split_validation_rejects_oversum():
    with pytest.raises(ValidationError):
        RenderCCSplit(
            asset_creator=Decimal("0.80"),
            renderer_creator=Decimal("0.15"),
            host_node=Decimal("0.10"),  # total = 1.05
        )


def test_cc_split_validation_rejects_undersum():
    with pytest.raises(ValidationError):
        RenderCCSplit(
            asset_creator=Decimal("0.50"),
            renderer_creator=Decimal("0.15"),
            host_node=Decimal("0.05"),  # total = 0.70
        )


def test_cc_split_rejects_negative_share():
    with pytest.raises(ValidationError):
        RenderCCSplit(
            asset_creator=Decimal("1.10"),
            renderer_creator=Decimal("-0.05"),
            host_node=Decimal("-0.05"),
        )


# ---------- attribute_render_cc (spec R4) ----------


def test_attribute_uses_platform_default_when_no_overrides():
    attribution = attribute_render_cc(Decimal("1.00"))
    assert attribution.cc_asset_creator == Decimal("0.8000")
    assert attribution.cc_renderer_creator == Decimal("0.1500")
    assert attribution.cc_host_node == Decimal("0.0500")


def test_attribute_uses_renderer_default_when_no_asset_override():
    renderer_split = RenderCCSplit(
        asset_creator=Decimal("0.70"),
        renderer_creator=Decimal("0.25"),
        host_node=Decimal("0.05"),
    )
    attribution = attribute_render_cc(
        Decimal("1.00"),
        renderer_default=renderer_split,
    )
    assert attribution.cc_asset_creator == Decimal("0.7000")
    assert attribution.cc_renderer_creator == Decimal("0.2500")
    assert attribution.cc_host_node == Decimal("0.0500")


def test_attribute_asset_override_beats_renderer_default():
    renderer_split = RenderCCSplit(
        asset_creator=Decimal("0.70"),
        renderer_creator=Decimal("0.25"),
        host_node=Decimal("0.05"),
    )
    asset_split = RenderCCSplit(
        asset_creator=Decimal("0.90"),
        renderer_creator=Decimal("0.05"),
        host_node=Decimal("0.05"),
    )
    attribution = attribute_render_cc(
        Decimal("1.00"),
        asset_override=asset_split,
        renderer_default=renderer_split,
    )
    assert attribution.cc_asset_creator == Decimal("0.9000")
    assert attribution.cc_renderer_creator == Decimal("0.0500")
    assert attribution.cc_host_node == Decimal("0.0500")


def test_attribute_preserves_pool_total():
    attribution = attribute_render_cc(Decimal("10.00"))
    total = (
        attribution.cc_asset_creator
        + attribution.cc_renderer_creator
        + attribution.cc_host_node
    )
    assert total == Decimal("10.0000")


def test_attribute_zero_pool_returns_zero_shares():
    attribution = attribute_render_cc(Decimal("0"))
    assert attribution.cc_asset_creator == Decimal("0")
    assert attribution.cc_renderer_creator == Decimal("0")
    assert attribution.cc_host_node == Decimal("0")


def test_resolve_split_returns_platform_default_when_both_none():
    split = resolve_split(None, None)
    assert split.asset_creator == Decimal("0.80")


# ---------- RendererCreate bundle-size constraint (spec R9) ----------


def test_renderer_create_rejects_oversize_bundle():
    with pytest.raises(ValidationError):
        RendererCreate(
            id="oversize-v1",
            name="Oversize Renderer",
            mime_types=["text/plain"],
            creator_id="contributor:alice",
            component_url="https://example.com/r.js",
            creation_cost_cc=Decimal("1.00"),
            version="1.0.0",
            max_bundle_bytes=MAX_RENDERER_BUNDLE_BYTES + 1,
        )


def test_renderer_create_accepts_bundle_at_max():
    renderer = RendererCreate(
        id="max-v1",
        name="Max-size Renderer",
        mime_types=["text/plain"],
        creator_id="contributor:alice",
        component_url="https://example.com/r.js",
        creation_cost_cc=Decimal("1.00"),
        version="1.0.0",
        max_bundle_bytes=MAX_RENDERER_BUNDLE_BYTES,
    )
    assert renderer.max_bundle_bytes == MAX_RENDERER_BUNDLE_BYTES


def test_renderer_create_requires_at_least_one_mime_type():
    with pytest.raises(ValidationError):
        RendererCreate(
            id="empty-mimes",
            name="Empty MIMEs",
            mime_types=[],  # min_length=1
            creator_id="contributor:alice",
            component_url="https://example.com/r.js",
            creation_cost_cc=Decimal("1.00"),
            version="1.0.0",
        )
