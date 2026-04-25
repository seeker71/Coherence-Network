#!/usr/bin/env python3
"""Seed U-Core integration ideas as a super-idea with children."""

import httpx
import sys

API = "https://api.coherencycoin.com"
c = httpx.Client(timeout=30)
H = {"X-Api-Key": "dev-key"}

super_id = "ucore-integration"
r = c.post(f"{API}/api/ideas", json={
    "id": super_id,
    "name": "U-Core architecture adoption from Living Codex",
    "description": (
        "Adopt the Living-Codex-CSharp U-Core architecture as the foundation layer. "
        "Everything becomes a Node with TypeId, State (Ice/Water/Gas), Content, Meta. "
        "Relationships become Edges with semantic roles and weights. A unified "
        "NodeRegistry replaces fragmented data access. Not a feature — the DNA."
    ),
    "potential_value": 200,
    "estimated_cost": 60,
    "confidence": 0.7,
    "idea_type": "super",
    "interfaces": ["api", "web", "cli"],
}, headers=H)
print(f"Super: {r.status_code} {super_id}")

children = [
    {
        "id": "ucore-news-ingestion-daily-brief",
        "name": "News ingestion + resonance matching for daily contributor briefs",
        "description": (
            "Borrow NewsFeedModule and RealtimeNewsStreamModule from Living Codex. "
            "Ingest RSS feeds and news APIs (NewsAPI, Guardian, NYT). Match articles "
            "to contributor interests and active ideas using Concept Resonance Kernel. "
            "Surface as daily brief via OpenClaw skill."
        ),
        "potential_value": 70,
        "estimated_cost": 15,
        "confidence": 0.8,
    },
    {
        "id": "ucore-concept-resonance-kernel",
        "name": "Concept Resonance Kernel — harmonic similarity matching",
        "description": (
            "Port the CRK algorithm from Living Codex ConceptResonanceModule. "
            "Concepts as harmonic symbols with frequency bands, k-vectors, phase, "
            "amplitude. Gaussian kernel + OT-phi optimal transport. Replace keyword "
            "matching with resonance-based scoring across the platform."
        ),
        "potential_value": 80,
        "estimated_cost": 20,
        "confidence": 0.7,
    },
    {
        "id": "ucore-node-edge-registry",
        "name": "Universal Node and Edge data layer with Ice/Water/Gas states",
        "description": (
            "Implement core U-Core abstractions: Node (id, type_id, state, content, "
            "meta), Edge (from_id, to_id, role, weight, meta), INodeRegistry interface. "
            "Ideas, specs, tasks, contributors all become nodes. Relationships become "
            "edges with semantic roles. Ice/Water/Gas determines persistence."
        ),
        "potential_value": 90,
        "estimated_cost": 30,
        "confidence": 0.6,
    },
    {
        "id": "ucore-event-streaming",
        "name": "Real-time event streaming with cross-service pub/sub",
        "description": (
            "Port EventStreamingModule from Living Codex. WebSocket pub/sub for "
            "real-time activity. Subscriptions filter by event type, entity, ID. "
            "Cross-service exchange enables MCP server, CLI, web to share live stream."
        ),
        "potential_value": 50,
        "estimated_cost": 12,
        "confidence": 0.75,
    },
    {
        "id": "ucore-geolocation-nearby",
        "name": "Geolocation awareness — nearby contributors, local ideas, regional news",
        "description": (
            "Borrow GeocodingService from Living Codex (OpenCage + Nominatim + "
            "fallback). Enrich contributor profiles with location. Filter ideas, "
            "news, tasks by geographic proximity. Surface nearby collaborators."
        ),
        "potential_value": 40,
        "estimated_cost": 10,
        "confidence": 0.75,
    },
    {
        "id": "ucore-future-knowledge-patterns",
        "name": "Future knowledge — pattern discovery, trend analysis, prediction",
        "description": (
            "Port FutureKnowledgeModule from Living Codex. LLM-powered pattern "
            "discovery across idea portfolio. Trending patterns with growth rates. "
            "Prediction generation with probability-weighted scenarios."
        ),
        "potential_value": 55,
        "estimated_cost": 18,
        "confidence": 0.65,
    },
    {
        "id": "ucore-temporal-consciousness",
        "name": "Temporal portals — time-aware exploration with causality tracking",
        "description": (
            "Port TemporalConsciousnessModule from Living Codex. Connect to past, "
            "present, future, eternal temporal dimensions. Fractal exploration with "
            "depth/branch control. Causality chains. Sacred temporal frequencies."
        ),
        "potential_value": 45,
        "estimated_cost": 15,
        "confidence": 0.6,
    },
    {
        "id": "ucore-belief-translation",
        "name": "Belief system translation — see any idea through any worldview",
        "description": (
            "Borrow concept exchange and translation patterns from Living Codex. "
            "Any idea translated through different belief systems, cultural contexts, "
            "professional domains. Meet contributors where they are."
        ),
        "potential_value": 40,
        "estimated_cost": 12,
        "confidence": 0.65,
    },
    {
        "id": "ucore-meta-nodes-self-describing",
        "name": "Meta-node system — self-describing code and API introspection",
        "description": (
            "Port meta-node pattern from Living Codex. Every API route becomes a "
            "codex.meta/route node. Every model becomes codex.meta/type. System "
            "introspects its own capabilities, auto-generates docs, exposes "
            "structure as navigable data."
        ),
        "potential_value": 50,
        "estimated_cost": 15,
        "confidence": 0.7,
    },
    {
        "id": "ucore-daily-engagement-skill",
        "name": "OpenClaw daily engagement skill — morning brief + contribution opportunities",
        "description": (
            "OpenClaw skill that generates a personalized daily brief: news resonating "
            "with your ideas, ideas needing your skills, tasks ready for your providers, "
            "contributors nearby, patterns the network is discovering. The two-way "
            "engagement channel that turns browsing into participation."
        ),
        "potential_value": 60,
        "estimated_cost": 10,
        "confidence": 0.85,
    },
]

created = 0
for child in children:
    child["parent_idea_id"] = super_id
    child["idea_type"] = "child"
    child["interfaces"] = ["api", "cli", "mcp"]
    r = c.post(f"{API}/api/ideas", json=child, headers=H)
    roi = child["potential_value"] / max(child["estimated_cost"], 1)
    if r.status_code < 300:
        print(f"  {roi:5.1f}x  {child['name'][:60]}")
        created += 1
    else:
        print(f"  FAIL ({r.status_code}): {child['name'][:50]}")

print(f"\nCreated {created} child ideas under {super_id}")
