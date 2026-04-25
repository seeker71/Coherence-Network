"""Flow renderer data — real energy flows for visualization.

Returns the live topology of energy moving through the community:
nodes (entities) and flows (energy streams between them). Each flow
has a type, color, intensity, and rate. The frontend renders these
as animated particle streams.

Flow types:
  resonance  — concept-to-concept analogous connections (purple)
  attention  — viewer → asset views (golden)
  creation   — contributor → asset contributions (blue)
  discovery  — referrer → asset → viewer chain (green)
  treasury   — treasury → contributor CC mint (amber)
  staking    — contributor → idea stake (red)
  structure  — parent-of hierarchy (grey)
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query

log = logging.getLogger(__name__)

router = APIRouter()

# Flow type → visual properties
FLOW_STYLES = {
    "resonance":  {"color": "#a78bfa", "label": "Resonance",  "speed": 0.4},
    "attention":  {"color": "#fbbf24", "label": "Attention",   "speed": 0.7},
    "creation":   {"color": "#60a5fa", "label": "Creation",    "speed": 0.5},
    "discovery":  {"color": "#34d399", "label": "Discovery",   "speed": 0.8},
    "treasury":   {"color": "#f59e0b", "label": "Treasury",    "speed": 0.3},
    "staking":    {"color": "#f87171", "label": "Commitment",  "speed": 0.2},
    "structure":  {"color": "#6b7280", "label": "Structure",   "speed": 0.1},
}


@router.get(
    "/flow/render",
    summary="Energy flow topology for visualization",
    description=(
        "Real energy flows between entities. Each flow is a stream "
        "with type, color, intensity, and rate — ready for animated "
        "particle rendering."
    ),
)
async def render_flows(
    days: int = Query(7, ge=1, le=90),
    max_nodes: int = Query(60, ge=10, le=200),
    workspace_id: str = Query("coherence-network"),
) -> dict[str, Any]:
    """Assemble the live flow topology."""

    nodes: dict[str, dict[str, Any]] = {}
    flows: list[dict[str, Any]] = []

    # 1. Graph edges — resonance and structure
    _add_graph_flows(nodes, flows, max_nodes)

    # 2. View flows — attention
    _add_attention_flows(nodes, flows, days)

    # 3. Treasury flows — CC movement
    _add_treasury_flows(nodes, flows, days)

    # Assign positions (force-directed seed)
    node_list = _layout_nodes(nodes)

    return {
        "nodes": node_list,
        "flows": flows,
        "flow_styles": FLOW_STYLES,
        "stats": {
            "node_count": len(node_list),
            "flow_count": len(flows),
            "flow_types": list(set(f["type"] for f in flows)),
        },
    }


def _add_graph_flows(
    nodes: dict[str, dict],
    flows: list[dict],
    max_nodes: int,
) -> None:
    """Add resonance and structure flows from graph edges."""
    try:
        from app.services import graph_service

        # Get nodes
        result = graph_service.list_nodes(limit=max_nodes)
        for n in result.get("items", []):
            nid = n.get("id", "")
            ntype = n.get("type", "unknown")
            nodes[nid] = {
                "id": nid,
                "label": n.get("name", nid)[:30],
                "type": ntype,
                "size": _node_size(ntype),
                "color": _node_color(ntype),
            }

        # Get edges
        edges = graph_service.list_edges(limit=500)
        for e in edges.get("items", []):
            from_id = e.get("from_id", "")
            to_id = e.get("to_id", "")
            etype = e.get("type", "unknown")
            strength = float(e.get("strength", 1.0))

            # Ensure both nodes exist
            if from_id not in nodes or to_id not in nodes:
                continue

            flow_type = "resonance" if etype == "analogous-to" else "structure"
            style = FLOW_STYLES.get(flow_type, FLOW_STYLES["structure"])

            flows.append({
                "from": from_id,
                "to": to_id,
                "type": flow_type,
                "color": style["color"],
                "intensity": min(1.0, strength),
                "speed": style["speed"],
                "label": style["label"],
                "particles": max(2, int(strength * 5)),
            })
    except Exception as ex:
        log.debug("flow_renderer: graph flows failed: %s", ex)


def _add_attention_flows(
    nodes: dict[str, dict],
    flows: list[dict],
    days: int,
) -> None:
    """Add attention flows from view events."""
    try:
        from app.services import read_tracking_service

        trending = read_tracking_service.get_trending(limit=30, days=days)
        style = FLOW_STYLES["attention"]

        for t in trending:
            asset_id = t["asset_id"]
            view_count = t["view_count"]
            unique = t.get("unique_viewers", 0)

            # Ensure asset node exists
            if asset_id not in nodes:
                nodes[asset_id] = {
                    "id": asset_id,
                    "label": asset_id[:30],
                    "type": "asset" if not asset_id.startswith("lc-") else "concept",
                    "size": 0.4,
                    "color": _node_color("concept" if asset_id.startswith("lc-") else "asset"),
                }

            # Create an "attention" source node representing viewers
            viewer_id = f"__viewers_{asset_id}"
            if viewer_id not in nodes:
                nodes[viewer_id] = {
                    "id": viewer_id,
                    "label": f"{unique} viewers",
                    "type": "viewer_group",
                    "size": 0.2 + min(0.5, unique / 20),
                    "color": "#fbbf24",
                }

            intensity = min(1.0, view_count / 50)
            flows.append({
                "from": viewer_id,
                "to": asset_id,
                "type": "attention",
                "color": style["color"],
                "intensity": intensity,
                "speed": style["speed"] * (0.5 + intensity * 0.5),
                "label": f"{view_count} views",
                "particles": max(2, min(15, view_count // 5)),
            })

            # Discovery sub-flows (referrals)
            chain = read_tracking_service.get_discovery_chain(asset_id)
            if chain:
                disc_style = FLOW_STYLES["discovery"]
                for link in chain[:5]:  # top 5 referrers
                    ref_id = link.get("referrer", "")
                    if ref_id and ref_id not in nodes:
                        nodes[ref_id] = {
                            "id": ref_id,
                            "label": ref_id[:20],
                            "type": "contributor",
                            "size": 0.3,
                            "color": _node_color("contributor"),
                        }
                    if ref_id:
                        flows.append({
                            "from": ref_id,
                            "to": asset_id,
                            "type": "discovery",
                            "color": disc_style["color"],
                            "intensity": 0.6,
                            "speed": disc_style["speed"],
                            "label": "Discovery",
                            "particles": 3,
                        })
    except Exception as ex:
        log.debug("flow_renderer: attention flows failed: %s", ex)


def _add_treasury_flows(
    nodes: dict[str, dict],
    flows: list[dict],
    days: int,
) -> None:
    """Add treasury CC flows."""
    try:
        from app.services.cc_treasury_service import TreasuryLedgerEntry
        from app.services.unified_db import session
        from sqlalchemy import func

        since = datetime.now(timezone.utc) - timedelta(days=days)

        with session() as s:
            # Aggregate mints per user
            mints = (
                s.query(
                    TreasuryLedgerEntry.user_id,
                    func.sum(TreasuryLedgerEntry.amount_cc).label("total"),
                    func.count(TreasuryLedgerEntry.id).label("count"),
                )
                .filter(
                    TreasuryLedgerEntry.action == "mint",
                    TreasuryLedgerEntry.created_at >= since,
                )
                .group_by(TreasuryLedgerEntry.user_id)
                .all()
            )

            if mints:
                # Treasury node
                nodes["__treasury"] = {
                    "id": "__treasury",
                    "label": "Treasury",
                    "type": "treasury",
                    "size": 0.8,
                    "color": "#f59e0b",
                }

                style = FLOW_STYLES["treasury"]
                for row in mints:
                    uid = row.user_id
                    total = float(row.total or 0)
                    if uid not in nodes:
                        nodes[uid] = {
                            "id": uid,
                            "label": uid[:20],
                            "type": "contributor",
                            "size": 0.3,
                            "color": _node_color("contributor"),
                        }

                    flows.append({
                        "from": "__treasury",
                        "to": uid,
                        "type": "treasury",
                        "color": style["color"],
                        "intensity": min(1.0, total / 100),
                        "speed": style["speed"],
                        "label": f"{total:.1f} CC",
                        "particles": max(2, min(10, int(total / 10))),
                    })

            # Aggregate stakes per user→idea
            stakes = (
                s.query(
                    TreasuryLedgerEntry.user_id,
                    TreasuryLedgerEntry.idea_id,
                    func.sum(TreasuryLedgerEntry.amount_cc).label("total"),
                )
                .filter(
                    TreasuryLedgerEntry.action == "stake",
                    TreasuryLedgerEntry.created_at >= since,
                    TreasuryLedgerEntry.idea_id.isnot(None),
                )
                .group_by(TreasuryLedgerEntry.user_id, TreasuryLedgerEntry.idea_id)
                .all()
            )

            stake_style = FLOW_STYLES["staking"]
            for row in stakes:
                uid = row.user_id
                iid = row.idea_id
                total = float(row.total or 0)
                if iid and iid not in nodes:
                    nodes[iid] = {
                        "id": iid,
                        "label": iid[:20],
                        "type": "idea",
                        "size": 0.4,
                        "color": _node_color("idea"),
                    }
                if uid and iid:
                    flows.append({
                        "from": uid,
                        "to": iid,
                        "type": "staking",
                        "color": stake_style["color"],
                        "intensity": min(1.0, total / 50),
                        "speed": stake_style["speed"],
                        "label": f"{total:.0f} CC staked",
                        "particles": max(1, min(8, int(total / 20))),
                    })
    except Exception as ex:
        log.debug("flow_renderer: treasury flows failed: %s", ex)


# ---------------------------------------------------------------------------
# Layout and helpers
# ---------------------------------------------------------------------------

def _layout_nodes(nodes: dict[str, dict]) -> list[dict[str, Any]]:
    """Assign 2D positions to nodes. Simple radial layout by type."""
    type_groups: dict[str, list[str]] = {}
    for nid, n in nodes.items():
        ntype = n.get("type", "unknown")
        type_groups.setdefault(ntype, []).append(nid)

    result = []
    group_idx = 0
    total_groups = max(len(type_groups), 1)

    for ntype, ids in type_groups.items():
        base_angle = (group_idx / total_groups) * math.pi * 2
        radius = 5.0 if ntype not in ("treasury",) else 0.0

        for i, nid in enumerate(ids):
            n = nodes[nid]
            if ntype == "treasury":
                x, y = 0.0, 0.0
            else:
                spread = 0.4
                angle = base_angle + (i - len(ids) / 2) * spread
                r = radius + (i % 3) * 1.2
                x = math.cos(angle) * r
                y = math.sin(angle) * r

            result.append({
                **n,
                "x": round(x, 2),
                "y": round(y, 2),
            })

        group_idx += 1

    return result


def _node_size(ntype: str) -> float:
    return {
        "concept": 0.4,
        "idea": 0.5,
        "contributor": 0.3,
        "asset": 0.35,
        "treasury": 0.8,
        "spec": 0.3,
        "event": 0.2,
    }.get(ntype, 0.25)


def _node_color(ntype: str) -> str:
    return {
        "concept": "#a78bfa",
        "idea": "#60a5fa",
        "contributor": "#34d399",
        "asset": "#fbbf24",
        "treasury": "#f59e0b",
        "spec": "#6b7280",
        "event": "#f472b6",
        "viewer_group": "#fbbf24",
        "community": "#8b5cf6",
    }.get(ntype, "#9ca3af")
