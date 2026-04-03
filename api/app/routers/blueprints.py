"""Blueprints router — project roadmap templates."""

from __future__ import annotations

import json
import os
from typing import List, Any
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.services import idea_service, graph_service, contribution_ledger_service

router = APIRouter()

BLUEPRINTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config", "blueprints"
)

class BlueprintIdea(BaseModel):
    id: str
    name: str
    description: str
    work_type: str = "feature"
    potential_value: float = 100.0
    estimated_cost: float = 50.0

class BlueprintEdge(BaseModel):
    from_id: str = os.environ.get("FIELD_NAME_FROM", "from") # handle 'from' reserved word
    to_id: str
    type: str

class Blueprint(BaseModel):
    name: str
    description: str
    author_id: str | None = None
    price_cc: float = 0.0
    ideas: List[dict]
    edges: List[dict]

@router.get("/blueprints")
def list_blueprints() -> List[dict]:
    """List available project roadmap blueprints."""
    if not os.path.exists(BLUEPRINTS_DIR):
        return []
    
    blueprints = []
    for filename in os.listdir(BLUEPRINTS_DIR):
        if filename.endswith(".json"):
            with open(os.path.join(BLUEPRINTS_DIR, filename), "r") as f:
                data = json.load(f)
                blueprints.append({
                    "id": filename.replace(".json", ""),
                    "name": data.get("name"),
                    "description": data.get("description"),
                    "author_id": data.get("author_id"),
                    "price_cc": data.get("price_cc", 0.0)
                })
    return blueprints

@router.post("/blueprints/{blueprint_id}/apply")
def apply_blueprint(blueprint_id: str, prefix: str = "", applicant_id: str | None = None) -> dict:
    """Apply a blueprint by creating its ideas and edges in the network."""
    path = os.path.join(BLUEPRINTS_DIR, f"{blueprint_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Blueprint not found")

    with open(path, "r") as f:
        data = json.load(f)

    # Monetize packaged knowledge: Transfer CC from applicant to author
    author_id = data.get("author_id")
    price_cc = data.get("price_cc", 0.0)
    
    if price_cc > 0 and author_id and applicant_id:
        # Pay the guide for their packaged knowledge
        contribution_ledger_service.record_contribution(
            contributor_id=applicant_id,
            contribution_type="blueprint_purchase",
            amount_cc=-price_cc,
            idea_id=None,
            meta={"blueprint": blueprint_id}
        )
        contribution_ledger_service.record_contribution(
            contributor_id=author_id,
            contribution_type="blueprint_royalty",
            amount_cc=price_cc,
            idea_id=None,
            meta={"blueprint": blueprint_id, "buyer": applicant_id}
        )

    results = {"ideas_created": [], "edges_created": []}
    
    # 1. Create Ideas
    id_map = {}
    for idea_data in data.get("ideas", []):
        original_id = idea_data["id"]
        new_id = f"{prefix}{original_id}" if prefix else original_id
        id_map[original_id] = new_id
        
        created = idea_service.create_idea(
            id=new_id,
            name=idea_data["name"],
            description=idea_data["description"],
            work_type=idea_data.get("work_type", "feature"),
            potential_value=idea_data.get("potential_value", 100),
            estimated_cost=idea_data.get("estimated_cost", 50)
        )
        results["ideas_created"].append(new_id)

    # 2. Create Edges
    for edge_data in data.get("edges", []):
        # Handle 'from' vs 'from_id'
        fid = edge_data.get("from") or edge_data.get("from_id")
        tid = edge_data.get("to") or edge_data.get("to_id")
        
        if fid in id_map: fid = id_map[fid]
        if tid in id_map: tid = id_map[tid]
        
        created = graph_service.create_edge(
            from_id=fid,
            to_id=tid,
            type=edge_data["type"]
        )
        results["edges_created"].append(f"{fid} --({edge_data['type']})--> {tid}")

    return results
