#!/usr/bin/env python3
"""Register renderers and complex asset types as tracked provider nodes in the graph DB."""

import sys
from pathlib import Path

# Add project root to path so we can import kb_common
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.kb_common import api_post, DEFAULT_API

API = DEFAULT_API

# ── 1. Renderers ─────────────────────────────────────────────────────

renderers = [
    {
        "id": "renderer-story-content-v1",
        "name": "Story Content Renderer v1",
        "description": "Renders Living Collective concept stories with inline generated images, cross-references, blockquotes, headings, and lists. The primary web renderer for all concept pages.",
        "mime_types": ["text/markdown+story"],
        "component": "web/app/vision/[conceptId]/_components/StoryContent.tsx",
        "creator_id": "seeker71",
    },
    {
        "id": "renderer-pdf-viewer-v1",
        "name": "PDF Viewer v1",
        "description": "Renders PDF research papers and documents in the browser. Supports page navigation, zoom, and text selection.",
        "mime_types": ["application/pdf"],
        "component": "web/app/assets/[asset_id]/_components/PDFViewer.tsx",
        "creator_id": "seeker71",
    },
    {
        "id": "renderer-audio-player-v1",
        "name": "Audio Player v1",
        "description": "Renders audio assets — ceremony recordings, music, guided meditations. HTML5 audio with waveform visualization.",
        "mime_types": ["audio/mpeg", "audio/ogg", "audio/wav"],
        "component": "web/app/assets/[asset_id]/_components/AudioPlayer.tsx",
        "creator_id": "seeker71",
    },
    {
        "id": "renderer-image-viewer-v1",
        "name": "Image Viewer v1",
        "description": "Renders image assets — photographs, diagrams, generated visuals. Supports zoom and fullscreen.",
        "mime_types": ["image/jpeg", "image/png", "image/webp", "image/svg+xml"],
        "component": "web/app/assets/[asset_id]/_components/ImageViewer.tsx",
        "creator_id": "seeker71",
    },
    {
        "id": "renderer-markdown-v1",
        "name": "Markdown Renderer v1",
        "description": "Renders markdown documents — articles, research papers, reviews, guides. Supports headings, lists, links, code blocks, tables.",
        "mime_types": ["text/markdown"],
        "component": "web/app/assets/[asset_id]/_components/MarkdownRenderer.tsx",
        "creator_id": "seeker71",
    },
]

# ── 2. Complex asset type examples ──────────────────────────────────

complex_assets = [
    {
        "id": "asset-research-community-economics",
        "name": "Research: Community Economics — Gift Economy vs Market Exchange",
        "description": "Research paper analyzing how 47 intentional communities manage economic exchange. Covers gift economy (Gaviotas), internal currency (Damanhur Credito), hybrid models (Auroville), and CC-based alternatives.",
        "asset_type": "RESEARCH",
        "mime_type": "application/pdf",
        "concept_id": "lc-economy",
        "creator_id": "seeker71",
    },
    {
        "id": "asset-spec-story-protocol-integration",
        "name": "Spec: Story Protocol + x402 + Arweave Integration",
        "description": "Technical specification for integrating on-chain IP registration, HTTP micropayments, and permanent storage into the CC economy. 794 lines, 6-phase implementation plan.",
        "asset_type": "SPEC",
        "mime_type": "text/markdown",
        "concept_id": "lc-economy",
        "creator_id": "seeker71",
    },
    {
        "id": "asset-review-frequency-scoring",
        "name": "Review: Frequency Scoring Algorithm — Calibration Report",
        "description": "Analysis of the frequency scoring algorithm across 51 concept files. Documents marker calibration, negation detection accuracy, and field analysis results. Mean score 0.740, range 0.648-0.828.",
        "asset_type": "REVIEW",
        "mime_type": "text/markdown",
        "concept_id": "lc-economy",
        "creator_id": "seeker71",
    },
    {
        "id": "asset-ceremony-recording-solstice",
        "name": "Audio: First Solstice Ceremony Recording",
        "description": "Recording of a community's first solstice ceremony. Fire circle, singing, drum, shared silence. The ceremony that marks the turn of the year.",
        "asset_type": "AUDIO",
        "mime_type": "audio/mpeg",
        "concept_id": "lc-ceremony",
        "creator_id": "seeker71",
    },
    {
        "id": "asset-video-cob-building-timelapse",
        "name": "Video: Cob Building Timelapse — Community Kitchen",
        "description": "30-minute timelapse of 12 community members building a cob kitchen wall. Shows the entire process from foundation to finished wall in one day.",
        "asset_type": "VIDEO",
        "mime_type": "video/mp4",
        "concept_id": "lc-space",
        "creator_id": "seeker71",
    },
    {
        "id": "asset-blueprint-food-forest-7layer",
        "name": "Blueprint: 7-Layer Food Forest Design — Temperate Climate",
        "description": "Detailed planting plan for a 1-acre 7-layer food forest. Includes species selection, spacing, companion planting, and 7-year timeline. SVG with interactive layers.",
        "asset_type": "BLUEPRINT",
        "mime_type": "image/svg+xml",
        "concept_id": "lc-nourishment",
        "creator_id": "seeker71",
    },
]


def register_renderers():
    """Register each renderer as a graph node with type=asset, asset_type=RENDERER."""
    print("=== Registering Renderers ===\n")
    results = {"created": 0, "existed": 0, "failed": 0}

    for r in renderers:
        body = {
            "id": r["id"],
            "type": "asset",
            "name": r["name"],
            "description": r["description"],
            "properties": {
                "asset_type": "RENDERER",
                "mime_types": r["mime_types"],
                "component": r["component"],
                "creator_id": r["creator_id"],
                "nft": True,
                "version": "1.0.0",
                "cc_split": {
                    "asset_creator": 0.80,
                    "renderer_creator": 0.15,
                    "host_node": 0.05,
                },
            },
        }
        status = api_post(f"{API}/api/graph/nodes", body)
        if status in (200, 201):
            print(f"  CREATED  {r['id']}")
            results["created"] += 1
        elif status == 409:
            print(f"  EXISTS   {r['id']}")
            results["existed"] += 1
        else:
            print(f"  FAILED   {r['id']} (HTTP {status})")
            results["failed"] += 1

    print(f"\nRenderers: {results['created']} created, {results['existed']} existed, {results['failed']} failed\n")
    return results


def register_complex_assets():
    """Register each complex asset as a graph node and create implements edges to concepts."""
    print("=== Registering Complex Asset Types ===\n")
    node_results = {"created": 0, "existed": 0, "failed": 0}
    edge_results = {"created": 0, "existed": 0, "failed": 0}

    for a in complex_assets:
        # Create the asset node
        body = {
            "id": a["id"],
            "type": "asset",
            "name": a["name"],
            "description": a["description"],
            "properties": {
                "asset_type": a["asset_type"],
                "mime_type": a["mime_type"],
                "creator_id": a["creator_id"],
                "nft": True,
                "domains": ["living-collective"],
            },
        }
        status = api_post(f"{API}/api/graph/nodes", body)
        if status in (200, 201):
            print(f"  CREATED  node  {a['id']}")
            node_results["created"] += 1
        elif status == 409:
            print(f"  EXISTS   node  {a['id']}")
            node_results["existed"] += 1
        else:
            print(f"  FAILED   node  {a['id']} (HTTP {status})")
            node_results["failed"] += 1

        # Create implements edge: asset -> concept
        edge_body = {
            "from_id": a["id"],
            "to_id": a["concept_id"],
            "type": "implements",
            "strength": 1.0,
            "properties": {},
            "created_by": "system",
        }
        edge_status = api_post(f"{API}/api/graph/edges", edge_body)
        if edge_status in (200, 201):
            print(f"  CREATED  edge  {a['id']} --implements--> {a['concept_id']}")
            edge_results["created"] += 1
        elif edge_status == 409:
            print(f"  EXISTS   edge  {a['id']} --implements--> {a['concept_id']}")
            edge_results["existed"] += 1
        else:
            print(f"  FAILED   edge  {a['id']} --implements--> {a['concept_id']} (HTTP {edge_status})")
            edge_results["failed"] += 1

    print(f"\nAsset nodes: {node_results['created']} created, {node_results['existed']} existed, {node_results['failed']} failed")
    print(f"Implements edges: {edge_results['created']} created, {edge_results['existed']} existed, {edge_results['failed']} failed\n")
    return node_results, edge_results


def create_renderer_enables_edges():
    """Create enables edges from renderers to the assets they can render (by mime_type match)."""
    print("=== Creating Renderer -> Asset Edges (enables) ===\n")
    results = {"created": 0, "existed": 0, "failed": 0}

    for r in renderers:
        renderer_mimes = set(r["mime_types"])
        for a in complex_assets:
            if a["mime_type"] in renderer_mimes:
                edge_body = {
                    "from_id": r["id"],
                    "to_id": a["id"],
                    "type": "enables",
                    "strength": 1.0,
                    "properties": {
                        "matched_mime": a["mime_type"],
                    },
                    "created_by": "system",
                }
                edge_status = api_post(f"{API}/api/graph/edges", edge_body)
                if edge_status in (200, 201):
                    print(f"  CREATED  {r['id']} --enables--> {a['id']} ({a['mime_type']})")
                    results["created"] += 1
                elif edge_status == 409:
                    print(f"  EXISTS   {r['id']} --enables--> {a['id']} ({a['mime_type']})")
                    results["existed"] += 1
                else:
                    print(f"  FAILED   {r['id']} --enables--> {a['id']} (HTTP {edge_status})")
                    results["failed"] += 1

    print(f"\nEnables edges: {results['created']} created, {results['existed']} existed, {results['failed']} failed\n")
    return results


def main():
    print("Registering providers against:", API, "\n")

    r1 = register_renderers()
    r2_nodes, r2_edges = register_complex_assets()
    r3 = create_renderer_enables_edges()

    # Summary
    total_created = r1["created"] + r2_nodes["created"] + r2_edges["created"] + r3["created"]
    total_existed = r1["existed"] + r2_nodes["existed"] + r2_edges["existed"] + r3["existed"]
    total_failed = r1["failed"] + r2_nodes["failed"] + r2_edges["failed"] + r3["failed"]

    print("=" * 50)
    print(f"TOTAL: {total_created} created, {total_existed} already existed, {total_failed} failed")
    if total_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
