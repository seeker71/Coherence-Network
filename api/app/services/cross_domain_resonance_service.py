"""Cross-Domain Concept Resonance Service (CDCR) — Spec 179.

Detects structurally similar node pairs from different domains, scores them
with a combined structural fingerprint + CRK metric, and persists the
connections as weighted analogous-to edges.

Resonance is NOT keyword matching — it is structural similarity in the graph:
two ideas resonate when they solve analogous problems in different domains.
"""

from __future__ import annotations

import logging
import math
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, DateTime, Float, String, func, select, text
from sqlalchemy.exc import IntegrityError

from app.services.unified_db import Base, session

log = logging.getLogger(__name__)

# ─── Score thresholds and weights (per spec 179) ─────────────────────────────

RESONANCE_THRESHOLD = 0.65
W_STRUCTURAL = 0.40
W_DEPTH2 = 0.25
W_CRK = 0.20
W_DOMAIN_BONUS = 0.15

# ─── Global scan state (one scan at a time) ───────────────────────────────────

_scan_lock = threading.Lock()
_scan_registry: dict[str, dict] = {}  # scan_id -> status dict


# ─── ORM model ────────────────────────────────────────────────────────────────


class CrossDomainResonanceRecord(Base):
    """Persisted cross-domain resonance record."""

    __tablename__ = "cross_domain_resonances"

    id = Column(String, primary_key=True)
    node_a_id = Column(String, nullable=False, index=True)
    node_b_id = Column(String, nullable=False, index=True)
    domain_a = Column(String, nullable=False)
    domain_b = Column(String, nullable=False)
    resonance_score = Column(Float, nullable=False)
    structural_sim = Column(Float, nullable=False)
    depth2_sim = Column(Float, nullable=False)
    crk_score = Column(Float, nullable=False)
    edge_id = Column(String, nullable=True)
    discovered_at = Column(DateTime, nullable=False)
    last_confirmed = Column(DateTime, nullable=False)
    scan_mode = Column(String, nullable=False, default="full")
    source = Column(String, nullable=False, default="cdcr")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "node_a_id": self.node_a_id,
            "node_b_id": self.node_b_id,
            "domain_a": self.domain_a,
            "domain_b": self.domain_b,
            "resonance_score": self.resonance_score,
            "structural_sim": self.structural_sim,
            "depth2_sim": self.depth2_sim,
            "crk_score": self.crk_score,
            "edge_id": self.edge_id,
            "discovered_at": self.discovered_at,
            "last_confirmed": self.last_confirmed,
            "scan_mode": self.scan_mode,
            "source": self.source,
        }


# ─── Schema bootstrap ─────────────────────────────────────────────────────────


def ensure_schema() -> None:
    """Create the cross_domain_resonances table if it doesn't exist."""
    try:
        from app.services.unified_db import engine
        eng = engine()
        if eng:
            CrossDomainResonanceRecord.__table__.create(eng, checkfirst=True)
    except Exception:
        log.debug("cross_domain_resonances table already exists or DB not available")


# ─── Structural fingerprinting ────────────────────────────────────────────────


def _build_fingerprint(node_id: str) -> dict[str, Any]:
    """Build a structural fingerprint F(n) for a graph node.

    F(n) = {
        edge_type_histogram: dict[EdgeType, int],   # 1-hop edge types
        axis_ids: set[str],                         # axes tagged on node
        domain: str | None,                         # inferred domain
        depth_2_edge_types: dict[EdgeType, int],    # 2-hop edge types
        degree_in: int,
        degree_out: int,
    }
    """
    try:
        from app.models.graph import Edge, Node
        from app.services.unified_db import session as db_session

        with db_session() as s:
            node = s.get(Node, node_id)
            if not node:
                return _empty_fingerprint()

            props = node.properties or {}
            domain = props.get("domain", "unknown")

            # 1-hop edges
            edges_out = s.query(Edge).filter(Edge.from_id == node_id).all()
            edges_in = s.query(Edge).filter(Edge.to_id == node_id).all()

            edge_hist: dict[str, int] = defaultdict(int)
            neighbor_ids: set[str] = set()

            for e in edges_out:
                edge_hist[e.type] += 1
                neighbor_ids.add(e.to_id)
            for e in edges_in:
                edge_hist[e.type] += 1
                neighbor_ids.add(e.from_id)

            # Axis tags from properties
            axis_ids: set[str] = set(props.get("axes", []))
            if "axis" in props:
                axis_ids.add(props["axis"])

            # Domain inference: check DOMAIN edges in 2-hop neighborhood
            if domain == "unknown":
                for e in edges_out:
                    if e.type.lower() in ("domain", "member-of", "belongs-to"):
                        target = s.get(Node, e.to_id)
                        if target and target.type == "domain":
                            domain = target.name.lower()
                            break

            # 2-hop edge types
            depth2_hist: dict[str, int] = defaultdict(int)
            for nid in list(neighbor_ids)[:50]:  # cap at 50 neighbors
                for e in s.query(Edge).filter(
                    (Edge.from_id == nid) | (Edge.to_id == nid)
                ).limit(20).all():
                    depth2_hist[e.type] += 1

            return {
                "edge_hist": dict(edge_hist),
                "axis_ids": axis_ids,
                "domain": domain,
                "depth2_hist": dict(depth2_hist),
                "degree_in": len(edges_in),
                "degree_out": len(edges_out),
                "name": node.name,
            }
    except Exception as exc:
        log.warning("fingerprint failed for %s: %s", node_id, exc)
        return _empty_fingerprint()


def _empty_fingerprint() -> dict[str, Any]:
    return {
        "edge_hist": {},
        "axis_ids": set(),
        "domain": "unknown",
        "depth2_hist": {},
        "degree_in": 0,
        "degree_out": 0,
        "name": "",
    }


def _cosine_similarity(v1: dict[str, float], v2: dict[str, float]) -> float:
    """Cosine similarity between two frequency histograms (as dicts)."""
    all_keys = set(v1.keys()) | set(v2.keys())
    if not all_keys:
        return 0.0

    dot = sum(v1.get(k, 0.0) * v2.get(k, 0.0) for k in all_keys)
    norm1 = math.sqrt(sum(x * x for x in v1.values()))
    norm2 = math.sqrt(sum(x * x for x in v2.values()))

    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0

    return max(0.0, min(1.0, dot / (norm1 * norm2)))


def _combined_vector(fp: dict[str, Any]) -> dict[str, float]:
    """Combine edge histogram and axis set into a single numeric vector."""
    vec: dict[str, float] = {}
    for k, v in fp["edge_hist"].items():
        vec[f"edge:{k}"] = float(v)
    for ax in fp["axis_ids"]:
        vec[f"axis:{ax}"] = 1.0
    return vec


# ─── CRK integration ─────────────────────────────────────────────────────────


def _crk_score_for_nodes(fp_a: dict, fp_b: dict) -> float:
    """Compute CRK score between two nodes using their fingerprints.

    Falls back to 0.5 (neutral) when insufficient harmonic components.
    Uses edge type distribution as a proxy for harmonic structure when
    no explicit ConceptSymbol is available.
    """
    try:
        from app.services.concept_resonance_kernel import (
            ConceptSymbol,
            HarmonicComponent,
            compare_concepts,
        )

        def _fp_to_symbol(fp: dict) -> ConceptSymbol:
            components = []
            # Encode edge types as harmonic components
            for i, (etype, count) in enumerate(fp["edge_hist"].items()):
                h = 0
                for c in etype:
                    h = (h * 31 + ord(c)) & 0xFFFFFFFF
                omega = 50.0 + (h % 49500) / 10.0
                k_val = ((h >> 8) & 0xFFFF) / 65535.0
                phase = ((h >> 16) & 0xFFF) / 651.8986
                components.append(HarmonicComponent(
                    band="structure",
                    omega=omega,
                    k=(k_val,),
                    phase=phase,
                    amplitude=float(count),
                ))
            # Encode axes
            for ax in fp["axis_ids"]:
                h = 0
                for c in ax:
                    h = (h * 31 + ord(c)) & 0xFFFFFFFF
                omega = 100.0 + (h % 9900) / 10.0
                components.append(HarmonicComponent(
                    band="axis",
                    omega=omega,
                    phase=0.0,
                    amplitude=1.0,
                ))
            if not components:
                return ConceptSymbol()
            return ConceptSymbol(components=components)

        s1 = _fp_to_symbol(fp_a)
        s2 = _fp_to_symbol(fp_b)

        if not s1.components or not s2.components:
            return 0.5

        result = compare_concepts(s1, s2)
        return result.crk

    except Exception as exc:
        log.debug("CRK computation failed, using default 0.5: %s", exc)
        return 0.5


# ─── Resonance scoring ────────────────────────────────────────────────────────


def compute_resonance_score(
    fp_a: dict[str, Any],
    fp_b: dict[str, Any],
) -> tuple[float, float, float, float]:
    """Compute the full resonance score per Spec 179 formula.

    Returns: (resonance_score, structural_sim, depth2_sim, crk_score)

    Formula:
        resonance_score = 0.40 * structural_sim
                        + 0.25 * depth2_sim
                        + 0.20 * crk_score
                        + 0.15 * domain_distance_bonus
    """
    vec_a = _combined_vector(fp_a)
    vec_b = _combined_vector(fp_b)
    structural_sim = _cosine_similarity(vec_a, vec_b)

    depth2_sim = _cosine_similarity(
        {k: float(v) for k, v in fp_a["depth2_hist"].items()},
        {k: float(v) for k, v in fp_b["depth2_hist"].items()},
    )

    crk_score = _crk_score_for_nodes(fp_a, fp_b)

    domain_a = fp_a.get("domain", "unknown")
    domain_b = fp_b.get("domain", "unknown")
    domain_distance_bonus = (
        1.0
        if (domain_a != domain_b and domain_a != "unknown" and domain_b != "unknown")
        else 0.0
    )

    resonance_score = (
        W_STRUCTURAL * structural_sim
        + W_DEPTH2 * depth2_sim
        + W_CRK * crk_score
        + W_DOMAIN_BONUS * domain_distance_bonus
    )

    return (
        round(min(1.0, max(0.0, resonance_score)), 6),
        round(structural_sim, 6),
        round(depth2_sim, 6),
        round(crk_score, 6),
    )


# ─── Edge creation ────────────────────────────────────────────────────────────


def _create_analogous_to_edge(
    node_a_id: str,
    node_b_id: str,
    resonance_score: float,
    domain_a: str,
    domain_b: str,
) -> Optional[str]:
    """Create or update an analogous-to edge between two nodes."""
    try:
        from app.services import graph_service

        result = graph_service.create_edge(
            from_id=node_a_id,
            to_id=node_b_id,
            type="analogous-to",
            strength=resonance_score,
            created_by="cdcr",
            properties={
                "source": "cdcr",
                "resonance_score": resonance_score,
                "domain_a": domain_a,
                "domain_b": domain_b,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return result.get("id")
    except Exception as exc:
        log.warning("Failed to create analogous-to edge %s<->%s: %s", node_a_id, node_b_id, exc)
        return None


# ─── Core scan logic ──────────────────────────────────────────────────────────


def _get_candidate_nodes(
    seed_node_id: Optional[str] = None,
    mode: str = "full",
    max_nodes: int = 10_000,
) -> list[str]:
    """Return node IDs to evaluate for resonance."""
    try:
        from app.models.graph import Node
        from app.services.unified_db import session as db_session

        with db_session() as s:
            if mode == "seed" and seed_node_id:
                from app.models.graph import Edge
                # Get seed node's 3-hop neighborhood
                visited: set[str] = {seed_node_id}
                frontier = {seed_node_id}
                for _ in range(3):
                    next_frontier: set[str] = set()
                    for nid in frontier:
                        for e in s.query(Edge).filter(
                            (Edge.from_id == nid) | (Edge.to_id == nid)
                        ).limit(100).all():
                            next_frontier.add(e.to_id if e.from_id == nid else e.from_id)
                    visited |= next_frontier
                    frontier = next_frontier - visited
                    if len(visited) > max_nodes:
                        break
                return list(visited)[:max_nodes]

            elif mode == "incremental":
                # Recent 1000 nodes
                rows = s.query(Node).order_by(Node.id.desc()).limit(1000).all()
                return [r.id for r in rows]

            else:
                # Full: all nodes, capped at max_nodes
                rows = s.query(Node).limit(max_nodes).all()
                return [r.id for r in rows]

    except Exception as exc:
        log.error("Failed to get candidate nodes: %s", exc)
        return []


def _run_scan(
    scan_id: str,
    mode: str,
    seed_node_id: Optional[str],
) -> None:
    """Execute a resonance scan and update scan_registry."""
    scan = _scan_registry[scan_id]
    scan["status"] = "running"
    scan["started_at"] = datetime.now(timezone.utc)

    try:
        ensure_schema()
        nodes = _get_candidate_nodes(seed_node_id=seed_node_id, mode=mode)
        scan["nodes_evaluated"] = len(nodes)

        # Build fingerprints
        fingerprints: dict[str, dict] = {}
        for nid in nodes:
            fingerprints[nid] = _build_fingerprint(nid)

        # Filter to nodes with known domains
        domain_nodes = {
            nid: fp
            for nid, fp in fingerprints.items()
            if fp["domain"] != "unknown"
        }

        now = datetime.now(timezone.utc)
        pairs_compared = 0
        resonances_found = 0
        resonances_created = 0
        resonances_updated = 0

        node_ids = list(domain_nodes.keys())

        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                id_a = node_ids[i]
                id_b = node_ids[j]
                fp_a = domain_nodes[id_a]
                fp_b = domain_nodes[id_b]

                # Only cross-domain pairs
                if fp_a["domain"] == fp_b["domain"]:
                    continue

                pairs_compared += 1

                score, struct_sim, depth2_sim, crk_s = compute_resonance_score(fp_a, fp_b)

                if score < RESONANCE_THRESHOLD:
                    continue

                resonances_found += 1

                # Canonical order: alphabetical by node ID
                node_a_id, node_b_id = sorted([id_a, id_b])
                fp_a_c = fingerprints[node_a_id]
                fp_b_c = fingerprints[node_b_id]

                # Check if already exists
                with session() as s:
                    existing = (
                        s.query(CrossDomainResonanceRecord)
                        .filter(
                            CrossDomainResonanceRecord.node_a_id == node_a_id,
                            CrossDomainResonanceRecord.node_b_id == node_b_id,
                        )
                        .first()
                    )

                    if existing:
                        existing.resonance_score = score
                        existing.structural_sim = struct_sim
                        existing.depth2_sim = depth2_sim
                        existing.crk_score = crk_s
                        existing.last_confirmed = now
                        existing.scan_mode = mode
                        s.commit()
                        resonances_updated += 1
                    else:
                        edge_id = _create_analogous_to_edge(
                            node_a_id=node_a_id,
                            node_b_id=node_b_id,
                            resonance_score=score,
                            domain_a=fp_a_c["domain"],
                            domain_b=fp_b_c["domain"],
                        )
                        record = CrossDomainResonanceRecord(
                            id=str(uuid.uuid4()),
                            node_a_id=node_a_id,
                            node_b_id=node_b_id,
                            domain_a=fp_a_c["domain"],
                            domain_b=fp_b_c["domain"],
                            resonance_score=score,
                            structural_sim=struct_sim,
                            depth2_sim=depth2_sim,
                            crk_score=crk_s,
                            edge_id=edge_id,
                            discovered_at=now,
                            last_confirmed=now,
                            scan_mode=mode,
                            source="cdcr",
                        )
                        s.add(record)
                        try:
                            s.commit()
                            resonances_created += 1
                        except IntegrityError:
                            s.rollback()
                            resonances_updated += 1

        completed_at = datetime.now(timezone.utc)
        duration_ms = int(
            (completed_at - scan["started_at"]).total_seconds() * 1000
        )

        scan.update({
            "status": "complete",
            "pairs_compared": pairs_compared,
            "resonances_found": resonances_found,
            "resonances_created": resonances_created,
            "resonances_updated": resonances_updated,
            "duration_ms": duration_ms,
            "completed_at": completed_at,
        })

    except Exception as exc:
        log.error("Scan %s failed: %s", scan_id, exc, exc_info=True)
        scan["status"] = "failed"
        scan["error"] = str(exc)
    finally:
        # Release lock so a new scan can start
        try:
            _scan_lock.release()
        except RuntimeError:
            pass


# ─── Public API ───────────────────────────────────────────────────────────────


def trigger_scan(
    mode: str = "full",
    seed_node_id: Optional[str] = None,
) -> dict:
    """Queue and start a resonance scan asynchronously.

    Returns scan metadata. Raises RuntimeError if a scan is already running.
    """
    if mode == "seed" and not seed_node_id:
        raise ValueError("seed_node_id required for mode=seed")

    if not _scan_lock.acquire(blocking=False):
        raise RuntimeError("Scan already in progress")

    scan_id = str(uuid.uuid4())
    _scan_registry[scan_id] = {
        "scan_id": scan_id,
        "mode": mode,
        "seed_node_id": seed_node_id,
        "status": "queued",
        "nodes_evaluated": 0,
        "pairs_compared": 0,
        "resonances_found": 0,
        "resonances_created": 0,
        "resonances_updated": 0,
        "duration_ms": None,
        "started_at": None,
        "completed_at": None,
    }

    t = threading.Thread(
        target=_run_scan,
        args=(scan_id, mode, seed_node_id),
        daemon=True,
    )
    t.start()

    return _scan_registry[scan_id]


def get_scan_status(scan_id: str) -> Optional[dict]:
    """Get status of a scan by ID."""
    return _scan_registry.get(scan_id)


def list_resonances(
    domain_a: Optional[str] = None,
    domain_b: Optional[str] = None,
    min_score: float = 0.65,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List cross-domain resonances with optional filters."""
    ensure_schema()
    try:
        with session() as s:
            q = s.query(CrossDomainResonanceRecord).filter(
                CrossDomainResonanceRecord.resonance_score >= min_score
            )
            if domain_a:
                q = q.filter(
                    (CrossDomainResonanceRecord.domain_a == domain_a)
                    | (CrossDomainResonanceRecord.domain_b == domain_a)
                )
            if domain_b:
                q = q.filter(
                    (CrossDomainResonanceRecord.domain_a == domain_b)
                    | (CrossDomainResonanceRecord.domain_b == domain_b)
                )
            total = q.count()
            items = (
                q.order_by(CrossDomainResonanceRecord.discovered_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return {"items": items, "total": total}
    except Exception as exc:
        log.error("list_resonances failed: %s", exc)
        return {"items": [], "total": 0}


def get_resonance(resonance_id: str) -> Optional[dict]:
    """Get a single resonance record by ID."""
    ensure_schema()
    try:
        with session() as s:
            rec = s.get(CrossDomainResonanceRecord, resonance_id)
            return rec.to_dict() if rec else None
    except Exception as exc:
        log.error("get_resonance failed: %s", exc)
        return None


def delete_resonance(resonance_id: str) -> bool:
    """Delete a resonance record and its associated analogous-to edge."""
    ensure_schema()
    try:
        with session() as s:
            rec = s.get(CrossDomainResonanceRecord, resonance_id)
            if not rec:
                return False

            edge_id = rec.edge_id
            s.delete(rec)
            s.commit()

        # Remove the analogous-to edge from graph
        if edge_id:
            try:
                from app.models.graph import Edge
                from app.services.unified_db import session as db_session
                with db_session() as s:
                    e = s.get(Edge, edge_id)
                    if e:
                        s.delete(e)
                        s.commit()
            except Exception as exc:
                log.warning("Could not remove edge %s: %s", edge_id, exc)

        return True
    except Exception as exc:
        log.error("delete_resonance failed: %s", exc)
        return False


def get_proof() -> dict:
    """Return aggregate evidence that the resonance engine is working."""
    ensure_schema()
    try:
        with session() as s:
            total = s.query(CrossDomainResonanceRecord).count()
            avg_row = s.query(
                func.avg(CrossDomainResonanceRecord.resonance_score)
            ).scalar()
            avg_score = round(float(avg_row or 0.0), 4)

            # Domain pair coverage
            pairs_raw = (
                s.query(
                    CrossDomainResonanceRecord.domain_a,
                    CrossDomainResonanceRecord.domain_b,
                    func.count(CrossDomainResonanceRecord.id),
                )
                .group_by(
                    CrossDomainResonanceRecord.domain_a,
                    CrossDomainResonanceRecord.domain_b,
                )
                .all()
            )
            domain_pairs = [
                {"domain_a": r[0], "domain_b": r[1], "count": r[2]}
                for r in pairs_raw
            ]

            # Discovery timeline (last 30 days)
            timeline_raw = (
                s.query(
                    func.date(CrossDomainResonanceRecord.discovered_at),
                    func.count(CrossDomainResonanceRecord.id),
                )
                .group_by(func.date(CrossDomainResonanceRecord.discovered_at))
                .order_by(func.date(CrossDomainResonanceRecord.discovered_at).desc())
                .limit(30)
                .all()
            )
            discovery_timeline = [
                {"date": str(r[0]), "new_resonances": r[1]}
                for r in timeline_raw
            ]

            # Top resonances
            top_raw = (
                s.query(CrossDomainResonanceRecord)
                .order_by(CrossDomainResonanceRecord.resonance_score.desc())
                .limit(5)
                .all()
            )

            # Fetch node names
            top_resonances = []
            for rec in top_raw:
                try:
                    from app.services import graph_service
                    node_a = graph_service.get_node(rec.node_a_id) or {}
                    node_b = graph_service.get_node(rec.node_b_id) or {}
                    top_resonances.append({
                        "node_a": node_a.get("name", rec.node_a_id),
                        "node_b": node_b.get("name", rec.node_b_id),
                        "score": rec.resonance_score,
                        "domain_pair": f"{rec.domain_a} <-> {rec.domain_b}",
                    })
                except Exception:
                    top_resonances.append({
                        "node_a": rec.node_a_id,
                        "node_b": rec.node_b_id,
                        "score": rec.resonance_score,
                        "domain_pair": f"{rec.domain_a} <-> {rec.domain_b}",
                    })

            # Count unique nodes that have at least one cross-domain bridge
            nodes_with_bridge_raw = s.query(
                CrossDomainResonanceRecord.node_a_id
            ).union(
                s.query(CrossDomainResonanceRecord.node_b_id)
            ).count()

            # Count analogous-to edges created by CDCR
            cdcr_edges = (
                s.query(CrossDomainResonanceRecord)
                .filter(CrossDomainResonanceRecord.edge_id.isnot(None))
                .count()
            )

            # Organic growth rate: avg new resonances per day over last 7 days
            growth_rate = 0.0
            if discovery_timeline:
                recent = discovery_timeline[:7]
                growth_rate = round(
                    sum(d["new_resonances"] for d in recent) / max(len(recent), 1), 2
                )

            return {
                "total_resonances": total,
                "total_analogous_to_edges": cdcr_edges,
                "analogous_to_edges_from_cdcr": cdcr_edges,
                "domain_pairs_covered": domain_pairs,
                "discovery_timeline": discovery_timeline,
                "top_resonances": top_resonances,
                "avg_score": avg_score,
                "nodes_with_cross_domain_bridge": nodes_with_bridge_raw,
                "organic_growth_rate": growth_rate,
                "proof_status": "active" if growth_rate > 0 else "stale",
            }
    except Exception as exc:
        log.error("get_proof failed: %s", exc)
        return {
            "total_resonances": 0,
            "total_analogous_to_edges": 0,
            "analogous_to_edges_from_cdcr": 0,
            "domain_pairs_covered": [],
            "discovery_timeline": [],
            "top_resonances": [],
            "avg_score": 0.0,
            "nodes_with_cross_domain_bridge": 0,
            "organic_growth_rate": 0.0,
            "proof_status": "stale",
        }


def trigger_incremental_scan(new_node_id: str) -> None:
    """Fire-and-forget incremental scan after a new node is created.

    Debounced: skips if a scan is already running.
    Does NOT block the caller.
    """
    if not _scan_lock.acquire(blocking=False):
        return  # Scan already running — debounce

    def _run() -> None:
        try:
            _run_scan(
                scan_id=str(uuid.uuid4()),
                mode="incremental",
                seed_node_id=new_node_id,
            )
        except Exception as exc:
            log.debug("incremental scan failed: %s", exc)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
