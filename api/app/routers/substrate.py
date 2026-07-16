"""Coherence-substrate REST API.

Read endpoints for agent reasoning + one write endpoint (POST /ingest)
so a visiting body can place markdown content into the lattice without
a repo clone. The substrate is also built by the ingestion frontends
(markdown_frontend, etc.) running on disk content; the consumed surfaces
include these endpoints + the Form notation parser (POST /form).

See docs/coherence-substrate/ for usage; see api/app/services/substrate/
for the implementation.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from sqlalchemy.exc import OperationalError

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.services.substrate import (
    DOMAIN_RECIPE_SHAPE,
    CellView,
    NamedCell,
    NodeID,
    annotate_path,
    canonical_shape_names,
    find_cells_compatible_with,
    find_equivalent_cells,
    ingest_markdown_text,
    lattice_stats,
    lookup_cell,
    lookup_node,
    view_cell_through_blueprint,
)
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.unified_db import session as session_scope
from app import config_loader


router = APIRouter()
_KERNEL_CORE_BML_RELATIVE = Path("form") / "form-stdlib" / "bml" / "kernel-core.bml"
_KERNEL_CORE_COUNTS = {
    "primitive_count": "RequiredPrimitiveCount",
    "dispatch_count": "RequiredDispatchCount",
    "proof_count": "RequiredProofCount",
}


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class NodeIDOut(BaseModel):
    package: int
    level: int
    type_: int = Field(alias="type")
    instance: int

    model_config = {"populate_by_name": True}

    @classmethod
    def from_node_id(cls, node_id: NodeID | None) -> "NodeIDOut | None":
        if node_id is None or node_id.is_undefined():
            return None
        return cls(
            package=node_id.package,
            level=node_id.level,
            type=node_id.type_,
            instance=node_id.instance,
        )


class CellOut(BaseModel):
    cell_id: int
    name: str
    domain: str
    blueprint: NodeIDOut
    base: NodeIDOut | None = None
    access: NodeIDOut | None = None
    ctor: NodeIDOut | None = None
    source_path: str | None = None

    @classmethod
    def from_cell(cls, cell: NamedCell) -> "CellOut":
        return cls(
            cell_id=cell.cell_id or 0,
            name=cell.name,
            domain=cell.domain,
            blueprint=NodeIDOut.from_node_id(cell.blueprint),
            base=NodeIDOut.from_node_id(cell.base),
            access=NodeIDOut.from_node_id(cell.access),
            ctor=NodeIDOut.from_node_id(cell.ctor),
            source_path=cell.source_path,
        )


class NodeOut(BaseModel):
    id: NodeIDOut
    serialized: str
    domain: str
    count: int

    @classmethod
    def from_orm(cls, orm_obj: SubstrateNodeORM) -> "NodeOut":
        return cls(
            id=NodeIDOut(
                package=orm_obj.package,
                level=orm_obj.level,
                type=orm_obj.type_,
                instance=orm_obj.instance,
            ),
            serialized=orm_obj.serialized,
            domain=orm_obj.domain,
            count=orm_obj.count or 0,
        )


class ResolvedNodeOut(BaseModel):
    id: NodeIDOut
    resolved: bool
    kind: str | None = None
    cell: CellOut | None = None
    node: NodeOut | None = None


class GroundedAskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)

    @field_validator("query")
    @classmethod
    def query_has_no_control_bytes(cls, value: str) -> str:
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("query contains a control character")
        return value


class GroundedAskResponse(BaseModel):
    query: str
    trust: str
    trust_fields: dict[str, str]
    grounded_node_id: str | None = None
    content_node_id: str | None = None
    source_path: str | None = None
    source_key: str | None = None
    answer_key: str | None = None
    answer: str
    payload: str
    native_challenge_digest: str
    form_cli_binary_sha256: str
    form_cli_table_sha256: str
    form_cli_wrapper_sha256: str
    form_cli_source_stamp: str
    form_cli_build_id: str
    kernel_runtime: str
    elapsed_ms: int


class EquivalentResponse(BaseModel):
    blueprint: NodeIDOut
    cells: list[CellOut]
    count: int


class LatticeStatsOut(BaseModel):
    blueprints_total: int
    recipes_total: int
    cells_total: int


class HistogramEntry(BaseModel):
    blueprint: NodeIDOut
    count: int
    sample_names: list[str]


class HistogramOut(BaseModel):
    domain: str
    entries: list[HistogramEntry]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/lattice/stats", response_model=LatticeStatsOut, tags=["substrate"])
def get_lattice_stats() -> LatticeStatsOut:
    """Return per-domain counts (blueprints, recipes, cells)."""
    with session_scope() as session:
        s = lattice_stats(session)
        return LatticeStatsOut(**s)


@router.get("/cell/{domain}/{name:path}", response_model=CellOut, tags=["substrate"])
def get_cell(domain: str, name: str) -> CellOut:
    """Look up a cell by (domain, name)."""
    with session_scope() as session:
        cell = lookup_cell(session, domain, name)
        if cell is None:
            raise HTTPException(status_code=404, detail=f"cell ({domain}, {name}) not found")
        return CellOut.from_cell(cell)


@router.get("/node/{package}/{level}/{type_}/{instance}", response_model=NodeOut, tags=["substrate"])
def get_node(package: int, level: int, type_: int, instance: int) -> NodeOut:
    """Look up a substrate_nodes row by NodeID."""
    nid = NodeID(package, level, type_, instance)
    with session_scope() as session:
        orm = lookup_node(session, nid)
        if orm is None:
            raise HTTPException(status_code=404, detail=f"node {nid} not found")
        return NodeOut.from_orm(orm)


@router.get(
    "/resolve/{package}/{level}/{type_}/{instance}",
    response_model=ResolvedNodeOut,
    tags=["substrate"],
)
def resolve_node(
    package: int, level: int, type_: int, instance: int
) -> ResolvedNodeOut:
    """Resolve a universal NodeID, including a NamedCell REF.

    NamedCell references live at ``@1.1.9.<cell_id>`` and intentionally do
    not require a duplicate ``substrate_nodes`` row. This door proves that a
    grounding identity still names a current cell; ordinary Blueprint/Recipe
    NodeIDs continue through the interned-node lookup.
    """
    node_id = NodeID(package, level, type_, instance)
    node_out = NodeIDOut.from_node_id(node_id)
    assert node_out is not None
    with session_scope() as session:
        if package == 1 and level == 1 and type_ == 9:
            row = (
                session.query(SubstrateNamedCellORM)
                .filter_by(cell_id=instance)
                .one_or_none()
            )
            if row is None:
                return ResolvedNodeOut(id=node_out, resolved=False)
            from app.services.substrate.kernel import _orm_to_cell

            return ResolvedNodeOut(
                id=node_out,
                resolved=True,
                kind="named_cell_ref",
                cell=CellOut.from_cell(_orm_to_cell(session, row)),
            )

        orm = lookup_node(session, node_id)
        if orm is None:
            return ResolvedNodeOut(id=node_out, resolved=False)
        return ResolvedNodeOut(
            id=node_out,
            resolved=True,
            kind=orm.domain,
            node=NodeOut.from_orm(orm),
        )


def _grounded_ask_root() -> Path:
    api_root = Path(__file__).resolve().parents[2]
    if (api_root / "bin" / "form-cli").is_file():
        return api_root
    return api_root.parent


_NODE_ID_RE = re.compile(r"^@[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TRUST_RE = re.compile(
    r"^trust  path:(native|rented)  grounded:(yes|no)  freq:(yes|no|unknown)  "
    r"freq-source:(certified-form|semantic-model|human-gold|unmeasured)  "
    r"suffic:(yes|no)  "
    r"observed:(yes|no)  -> (OBSERVED|native-partial|rented)  "
    r"decision:(accept|retry|escalate)  "
    r"reason:(ok|empty|bad-shape|weak-content|low-confidence|low-trust)$"
)


def _run_native_wrapper(
    command: list[str], *, cwd: Path, timeout: int
) -> subprocess.CompletedProcess[bytes]:
    """Run the wrapper in an isolated process group and reap the whole tree."""
    popen_kwargs: dict[str, Any] = {
        "cwd": cwd,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **popen_kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        if process.poll() is None:
            process.kill()
            process.communicate()
        raise exc
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _secure_native_query_directory(path: Path) -> None:
    """Create the API staging directory without following a hostile symlink."""
    try:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        metadata = path.lstat()
        if path.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
            raise OSError("query directory is not a real directory")
        if os.name != "nt":
            os.chmod(path, 0o700)
            metadata = path.lstat()
            if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
                raise OSError("query directory ownership/mode invalid")
    except OSError as exc:
        raise HTTPException(
            status_code=503, detail="native query staging directory is insecure"
        ) from exc


def _parse_native_grounded_payload(
    stdout: bytes,
    stderr: bytes,
) -> tuple[str, dict[str, str], dict[str, str], str, str]:
    """Validate the complete byte protocol before exposing any native claim."""
    try:
        stderr_text = stderr.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=502, detail="native trust trace is not UTF-8") from exc
    trust_lines = stderr_text.splitlines()
    if len(trust_lines) != 1:
        raise HTTPException(status_code=502, detail="native trust trace count invalid")
    trust = trust_lines[0]
    match = _TRUST_RE.fullmatch(trust)
    if match is None:
        raise HTTPException(status_code=502, detail="native trust trace schema invalid")
    (
        path,
        grounded,
        frequency,
        frequency_source,
        sufficient,
        observed,
        verdict,
        decision,
        reason,
    ) = match.groups()
    if path != "native":
        raise HTTPException(
            status_code=502,
            detail="grounded ask returned a non-native path",
        )
    computed_observed = (
        path == "native"
        and grounded == "yes"
        and frequency == "yes"
        and frequency_source == "certified-form"
        and sufficient == "yes"
    )
    if (observed == "yes") != computed_observed:
        raise HTTPException(status_code=502, detail="native observed claim inconsistent")
    expected_verdict = (
        "OBSERVED"
        if computed_observed
        else ("native-partial" if path == "native" else "rented")
    )
    if verdict != expected_verdict:
        raise HTTPException(status_code=502, detail="native verdict inconsistent")
    if frequency == "yes" and frequency_source != "certified-form":
        raise HTTPException(status_code=502, detail="native frequency source invalid")
    if frequency == "no" and frequency_source in {
        "certified-form",
        "unmeasured",
    }:
        raise HTTPException(status_code=502, detail="native frequency source inconsistent")

    if grounded == "no":
        try:
            miss_payload = stdout.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=502, detail="native miss payload is not UTF-8") from exc
        if miss_payload.strip() not in {
            "grounded:miss",
            "[ask: local fkwu RAG index has no grounded hit]",
        }:
            raise HTTPException(status_code=502, detail="native miss payload invalid")
        trust_fields = {
            "path": path,
            "grounded": grounded,
            "freq": frequency,
            "freq-source": frequency_source,
            "suffic": sufficient,
            "observed": observed,
            "verdict": verdict,
            "decision": decision,
            "reason": reason,
        }
        return trust, trust_fields, {}, "", miss_payload

    marker = b"\nanswer:"
    marker_at = stdout.find(marker)
    if marker_at < 0:
        raise HTTPException(status_code=502, detail="native answer marker missing")
    metadata_bytes = stdout[:marker_at]
    try:
        metadata_text = metadata_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="native grounded ask emitted non-UTF-8 protocol bytes",
        ) from exc
    allowed = {
        "grounded",
        "content-node",
        "source-path",
        "source-key",
        "answer-key",
        "retrieval-score",
        "retrieval-runner-score",
        "retrieval-query-total",
        "retrieval-threshold",
        "retrieval-confidence",
        "local-lane",
        "synthesis-lane",
        "answer-byte-length",
    }
    bindings: dict[str, str] = {}
    for line in metadata_text.splitlines():
        if ":" not in line:
            raise HTTPException(status_code=502, detail="native binding syntax invalid")
        key, value = line.split(":", 1)
        if key not in allowed or key in bindings or not value:
            raise HTTPException(status_code=502, detail="native binding schema invalid")
        bindings[key] = value
    if set(bindings) != allowed:
        raise HTTPException(status_code=502, detail="native binding set incomplete")
    if not _NODE_ID_RE.fullmatch(bindings["grounded"]):
        raise HTTPException(status_code=502, detail="native grounding REF invalid")
    if not _NODE_ID_RE.fullmatch(bindings["content-node"]):
        raise HTTPException(status_code=502, detail="native grounding CTOR invalid")
    if not _SHA256_RE.fullmatch(bindings["source-key"]):
        raise HTTPException(status_code=502, detail="native source key invalid")
    if not _SHA256_RE.fullmatch(bindings["answer-key"]):
        raise HTTPException(status_code=502, detail="native answer key invalid")
    if bindings["local-lane"] != "fkwu-rag-grounded" or bindings[
        "synthesis-lane"
    ] != "fkwu-rag-grounded":
        raise HTTPException(status_code=502, detail="native lane identity invalid")
    numeric: dict[str, int] = {}
    for key in (
        "retrieval-score",
        "retrieval-runner-score",
        "retrieval-query-total",
        "retrieval-threshold",
        "retrieval-confidence",
    ):
        value = bindings[key]
        if not value.isascii() or not value.isdecimal():
            raise HTTPException(status_code=502, detail=f"native {key} invalid")
        numeric[key] = int(value)
    if not (
        0 <= numeric["retrieval-runner-score"] <= numeric["retrieval-score"]
        <= numeric["retrieval-query-total"]
        and 0 < numeric["retrieval-threshold"]
        <= numeric["retrieval-score"]
        and 0 <= numeric["retrieval-confidence"] <= 100
    ):
        raise HTTPException(status_code=502, detail="native retrieval metrics inconsistent")
    try:
        answer_length = int(bindings["answer-byte-length"])
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="native answer length invalid") from exc
    if not 0 <= answer_length <= 1_000_000:
        raise HTTPException(status_code=502, detail="native answer length out of range")
    framed_answer = stdout[marker_at + len(marker):]
    answer_bytes = framed_answer[:answer_length]
    if len(answer_bytes) != answer_length or framed_answer[answer_length:] != b"\n":
        raise HTTPException(status_code=502, detail="native answer framing invalid")
    try:
        answer = answer_bytes.decode("utf-8", errors="strict")
        payload = (metadata_bytes + marker + answer_bytes).decode(
            "utf-8", errors="strict"
        )
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="native grounded ask emitted non-UTF-8 protocol bytes",
        ) from exc
    if hashlib.sha256(answer_bytes).hexdigest() != bindings["answer-key"]:
        raise HTTPException(status_code=502, detail="native answer digest mismatch")
    trust_fields = {
        "path": path,
        "grounded": grounded,
        "freq": frequency,
        "freq-source": frequency_source,
        "suffic": sufficient,
        "observed": observed,
        "verdict": verdict,
        "decision": decision,
        "reason": reason,
    }
    return trust, trust_fields, bindings, answer, payload


def _run_grounded_ask(query: str) -> GroundedAskResponse:
    from app.services.native_runtime_observation import observe_native_runtime

    timeout = config_loader.get_int("grounding", "native_ask_timeout_seconds", 20)
    max_chars = config_loader.get_int("grounding", "native_ask_max_query_chars", 2000)
    if len(query) > max_chars:
        raise HTTPException(
            status_code=413,
            detail=f"query exceeds configured native ask limit ({max_chars} chars)",
        )
    root = _grounded_ask_root()
    wrapper = root / "bin" / "form-cli"
    if not wrapper.is_file():
        raise HTTPException(status_code=503, detail="native form-cli wrapper unavailable")

    observation_before = observe_native_runtime(force=True)
    if observation_before.get("verified") is not True:
        raise HTTPException(status_code=503, detail="native carrier observation failed")
    if Path(str(observation_before.get("root") or "")).resolve() != root.resolve():
        raise HTTPException(status_code=503, detail="native carrier root mismatch")
    kernel_before = observation_before.get("kernel")
    form_cli_before = observation_before.get("form_cli")
    if (
        not isinstance(kernel_before, dict)
        or kernel_before.get("verified") is not True
        or kernel_before.get("runtime") not in {"inline", "subprocess"}
        or not isinstance(form_cli_before, dict)
        or form_cli_before.get("verified") is not True
    ):
        raise HTTPException(status_code=503, detail="native carrier observation incomplete")
    carrier_bindings_before = {
        "native_challenge_digest": observation_before.get("challenge_digest"),
        "form_cli_binary_sha256": form_cli_before.get("binary_sha256"),
        "form_cli_table_sha256": form_cli_before.get("table_sha256"),
        "form_cli_wrapper_sha256": form_cli_before.get("wrapper_sha256"),
        "form_cli_source_stamp": form_cli_before.get("source_stamp"),
        "form_cli_build_id": form_cli_before.get("build_id"),
        "kernel_runtime": kernel_before.get("runtime"),
        "kernel_binary_sha256": kernel_before.get("binary_sha256"),
        "kernel_inline_sha256": kernel_before.get("inline_sha256"),
    }
    for key in (
        "native_challenge_digest",
        "form_cli_binary_sha256",
        "form_cli_table_sha256",
        "form_cli_wrapper_sha256",
        "form_cli_source_stamp",
    ):
        if not _SHA256_RE.fullmatch(str(carrier_bindings_before[key] or "")):
            raise HTTPException(status_code=503, detail=f"native carrier {key} invalid")
    if any(
        not str(carrier_bindings_before[key] or "")
        for key in ("form_cli_source_stamp", "form_cli_build_id", "kernel_runtime")
    ):
        raise HTTPException(status_code=503, detail="native carrier identity invalid")

    started = time.monotonic()
    query_dir = Path.home() / ".coherence-network" / "api-queries"
    _secure_native_query_directory(query_dir)
    query_path = ""
    try:
        fd, query_path = tempfile.mkstemp(
            dir=query_dir,
            prefix="grounded-ask-",
            suffix=".query",
        )
        with os.fdopen(fd, "wb") as query_out:
            query_out.write(query.encode("utf-8"))
            query_out.flush()
            os.fsync(query_out.fileno())
        try:
            process = _run_native_wrapper(
                [str(wrapper), "ask-file", query_path],
                cwd=root,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(
                status_code=504,
                detail="native grounded ask timed out",
            ) from exc
        observation_after = observe_native_runtime(force=True)
    finally:
        if query_path:
            try:
                os.unlink(query_path)
            except FileNotFoundError:
                pass

    if observation_after.get("verified") is not True:
        raise HTTPException(status_code=503, detail="native carrier post-observation failed")
    if Path(str(observation_after.get("root") or "")).resolve() != root.resolve():
        raise HTTPException(status_code=503, detail="native carrier post-root mismatch")
    kernel_after = observation_after.get("kernel")
    form_cli_after = observation_after.get("form_cli")
    if (
        not isinstance(kernel_after, dict)
        or kernel_after.get("verified") is not True
        or not isinstance(form_cli_after, dict)
        or form_cli_after.get("verified") is not True
    ):
        raise HTTPException(status_code=503, detail="native carrier post-observation incomplete")
    carrier_bindings_after = {
        "native_challenge_digest": observation_after.get("challenge_digest"),
        "form_cli_binary_sha256": form_cli_after.get("binary_sha256"),
        "form_cli_table_sha256": form_cli_after.get("table_sha256"),
        "form_cli_wrapper_sha256": form_cli_after.get("wrapper_sha256"),
        "form_cli_source_stamp": form_cli_after.get("source_stamp"),
        "form_cli_build_id": form_cli_after.get("build_id"),
        "kernel_runtime": kernel_after.get("runtime"),
        "kernel_binary_sha256": kernel_after.get("binary_sha256"),
        "kernel_inline_sha256": kernel_after.get("inline_sha256"),
    }
    if carrier_bindings_after != carrier_bindings_before:
        raise HTTPException(status_code=503, detail="native carrier changed during ask")

    if process.returncode != 0:
        error_text = process.stderr.decode("utf-8", errors="replace")
        last_error = next(
            (line for line in reversed(error_text.splitlines()) if line.strip()),
            "native form-cli failed",
        )
        raise HTTPException(status_code=503, detail=last_error[:500])
    trust, trust_fields, bindings, answer, payload = _parse_native_grounded_payload(
        process.stdout,
        process.stderr,
    )
    return GroundedAskResponse(
        query=query,
        trust=trust,
        trust_fields=trust_fields,
        grounded_node_id=bindings.get("grounded"),
        content_node_id=bindings.get("content-node"),
        source_path=bindings.get("source-path"),
        source_key=bindings.get("source-key"),
        answer_key=bindings.get("answer-key"),
        answer=answer,
        payload=payload,
        native_challenge_digest=str(
            carrier_bindings_before["native_challenge_digest"]
        ),
        form_cli_binary_sha256=str(
            carrier_bindings_before["form_cli_binary_sha256"]
        ),
        form_cli_table_sha256=str(
            carrier_bindings_before["form_cli_table_sha256"]
        ),
        form_cli_wrapper_sha256=str(
            carrier_bindings_before["form_cli_wrapper_sha256"]
        ),
        form_cli_source_stamp=str(
            carrier_bindings_before["form_cli_source_stamp"]
        ),
        form_cli_build_id=str(carrier_bindings_before["form_cli_build_id"]),
        kernel_runtime=str(carrier_bindings_before["kernel_runtime"]),
        elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
    )


@router.post(
    "/grounded-ask",
    response_model=GroundedAskResponse,
    tags=["substrate"],
)
def grounded_ask(req: GroundedAskRequest) -> GroundedAskResponse:
    """Run the deployed c-bootstrapped Form ask lane and relay its native trace."""
    if not req.query.strip():
        raise HTTPException(status_code=422, detail="query must contain non-space text")
    return _run_grounded_ask(req.query)


@router.get("/equivalent/{domain}/{name:path}", response_model=EquivalentResponse, tags=["substrate"])
def get_equivalent(domain: str, name: str) -> EquivalentResponse:
    """Find structurally-equivalent cells to (domain, name).

    Returns all cells whose Blueprint NodeID matches that of the named cell.
    Two cells with the same Blueprint NodeID are structurally identical
    regardless of name or domain.
    """
    with session_scope() as session:
        cell = lookup_cell(session, domain, name)
        if cell is None:
            raise HTTPException(status_code=404, detail=f"cell ({domain}, {name}) not found")
        equivalents = find_equivalent_cells(session, cell.blueprint, exclude_name=cell.name)
        return EquivalentResponse(
            blueprint=NodeIDOut.from_node_id(cell.blueprint),
            cells=[CellOut.from_cell(c) for c in equivalents],
            count=len(equivalents),
        )


@router.get("/cells", tags=["substrate"])
def list_cells(
    domain: str | None = Query(None, description="Filter by domain"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> dict[str, Any]:
    """List cells (optionally filtered by domain)."""
    with session_scope() as session:
        base = session.query(SubstrateNamedCellORM)
        if domain is not None:
            base = base.filter_by(domain=domain)
        total = base.count()
        rows = base.offset(offset).limit(limit).all()
        from app.services.substrate.kernel import _orm_to_cell  # internal helper
        items = [CellOut.from_cell(_orm_to_cell(session, r)) for r in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# Cross-modal canonical shapes (recipe-shape domain)
# ---------------------------------------------------------------------------
#
# The cross-modal substrate proofs (PR #1956 +
# scripts/intern_modality_blueprints.py) intern canonical recipe shapes
# such as R_ObserverConditionedActualization, R_Recovery, R_Pointing,
# R_Re-coherence, R_Re-pattern, R_Re-anchor under domain="recipe-shape".
# Per-modality cells share their canonical's Blueprint NodeID, so the
# substrate-native query for "what cells across modalities share this
# shape?" is `find_equivalent_cells(canonical.blueprint)`.
#
# These endpoints expose that cross-modal unity directly, so any agent
# surface (MCP, web) can ask the substrate "what other modalities carry
# the shape I am thinking about?" without composing the Form query.
#
# The domain name and the list of canonical shape names live in
# `app.services.substrate.modality_shapes` so this router and the intern
# script share one source-of-truth. The router previously carried a
# hand-maintained list that fell out of sync when the canonical set grew
# from 7 to 13 entries — content-addressing keeps the cells aligned, but
# the human-readable name list needs the same discipline.


CANONICAL_RECIPE_SHAPE_DOMAIN = DOMAIN_RECIPE_SHAPE


class CrossModalTwinsOut(BaseModel):
    canonical_name: str
    blueprint: NodeIDOut | None = None
    twins: list[CellOut] = Field(default_factory=list)
    count: int = 0
    found: bool = False


@router.get(
    "/cross_modal_twins/{canonical_name}",
    response_model=CrossModalTwinsOut,
    tags=["substrate"],
)
def get_cross_modal_twins(canonical_name: str) -> CrossModalTwinsOut:
    """Return per-modality cells that share the canonical shape's Blueprint.

    Wrapper around `find_equivalent_cells` for the `recipe-shape` domain.
    The canonical cell itself is excluded from the twins list — callers
    receive the *other* modality expressions of the same structural shape.

    Returns `found=false` when the canonical name is not interned, so
    callers can render an honest empty result rather than treat a missing
    canonical as an error.
    """
    with session_scope() as session:
        cell = lookup_cell(session, CANONICAL_RECIPE_SHAPE_DOMAIN, canonical_name)
        if cell is None:
            return CrossModalTwinsOut(canonical_name=canonical_name)
        equivalents = find_equivalent_cells(
            session, cell.blueprint, exclude_name=cell.name
        )
        return CrossModalTwinsOut(
            canonical_name=canonical_name,
            blueprint=NodeIDOut.from_node_id(cell.blueprint),
            twins=[CellOut.from_cell(c) for c in equivalents],
            count=len(equivalents),
            found=True,
        )


class CanonicalFamilyOut(BaseModel):
    canonical_name: str
    blueprint: NodeIDOut
    members: list[CellOut] = Field(default_factory=list)
    member_count: int = 0


class CanonicalFamiliesOut(BaseModel):
    families: list[CanonicalFamilyOut] = Field(default_factory=list)
    count: int = 0


# The canonical cross-modal shapes interned by
# scripts/intern_modality_blueprints.py. Read from
# `app.services.substrate.modality_shapes.CANONICAL_SHAPES` so the
# endpoint returns a stable ordering with the keystone first AND stays
# in sync as the canonical set grows. The actual cells and Blueprint
# NodeIDs are read live from the substrate.


@router.get(
    "/canonical_families",
    response_model=CanonicalFamiliesOut,
    tags=["substrate"],
)
def get_canonical_families() -> CanonicalFamiliesOut:
    """List all interned cross-modal canonical shapes with their members.

    Returns one entry per canonical shape (R_ObserverConditionedActualization,
    R_Recovery, R_SustainedTension, R_ResolutionToSilence, R_MeetThenShift,
    R_SkipTheIntermediate, R_ReturnFromEdge), each carrying the full family
    of per-modality cells that share the canonical's Blueprint NodeID. The
    map of cross-modal unity.

    Shapes whose canonical cell is not interned (e.g. in a fresh test
    substrate) are omitted; callers see only the families that exist.
    """
    families: list[CanonicalFamilyOut] = []
    with session_scope() as session:
        for canonical_name in canonical_shape_names():
            cell = lookup_cell(
                session, CANONICAL_RECIPE_SHAPE_DOMAIN, canonical_name
            )
            if cell is None:
                continue
            # Members include the canonical itself, so callers see the
            # complete family without needing a second lookup.
            members = find_equivalent_cells(session, cell.blueprint)
            families.append(
                CanonicalFamilyOut(
                    canonical_name=canonical_name,
                    blueprint=NodeIDOut.from_node_id(cell.blueprint),
                    members=[CellOut.from_cell(c) for c in members],
                    member_count=len(members),
                )
            )
    return CanonicalFamiliesOut(families=families, count=len(families))


class ModalityForOut(BaseModel):
    per_modality_name: str
    canonical_name: str | None = None
    blueprint: NodeIDOut | None = None
    family: list[CellOut] = Field(default_factory=list)
    family_count: int = 0
    found: bool = False


@router.get(
    "/modality_for/{per_modality_name}",
    response_model=ModalityForOut,
    tags=["substrate"],
)
def get_modality_for(per_modality_name: str) -> ModalityForOut:
    """Inverse query: from a per-modality cell name, find its canonical family.

    Given a recipe-shape cell like `R_Re-coherence` (quantum) or
    `R_Pointing` (teaching), returns the cross-modal canonical shape it
    belongs to and the other modality twins that share its Blueprint.
    Lets a cell ask "what other domains carry the shape I am thinking
    about?" without knowing the canonical name in advance.

    The canonical is detected as the family member whose name matches one
    of the interned canonical shapes; the cell itself is included in the
    `family` list so callers see the full membership.
    """
    with session_scope() as session:
        cell = lookup_cell(
            session, CANONICAL_RECIPE_SHAPE_DOMAIN, per_modality_name
        )
        if cell is None:
            return ModalityForOut(per_modality_name=per_modality_name)
        family_cells = find_equivalent_cells(session, cell.blueprint)
        canonical_names = set(canonical_shape_names())
        canonical_name = next(
            (c.name for c in family_cells if c.name in canonical_names),
            None,
        )
        return ModalityForOut(
            per_modality_name=per_modality_name,
            canonical_name=canonical_name,
            blueprint=NodeIDOut.from_node_id(cell.blueprint),
            family=[CellOut.from_cell(c) for c in family_cells],
            family_count=len(family_cells),
            found=True,
        )


class PathAnnotationOut(BaseModel):
    path: str
    cell: CellOut | None = None
    blueprint: NodeIDOut | None = None
    domain: str | None = None
    equivalents: list[CellOut] = Field(default_factory=list)
    equivalents_count: int = 0
    in_substrate: bool


@router.get("/annotate", response_model=PathAnnotationOut, tags=["substrate"])
def get_annotation(path: str = Query(..., description="File path to annotate")) -> PathAnnotationOut:
    """Return substrate context for a file path.

    The agent-grounding endpoint: when an agent reads a file and wants to
    know what cell that path is in the substrate (NodeID, Blueprint shape,
    structural equivalents), it calls this. Returns in_substrate=False
    when the path isn't ingested.

    See docs/coherence-substrate/agents-using-substrate.md "Pattern 5:
    Auto-annotation on file reads" for usage.
    """
    with session_scope() as session:
        ann = annotate_path(session, path)
        return PathAnnotationOut(
            path=ann.path,
            cell=CellOut.from_cell(ann.cell) if ann.cell else None,
            blueprint=NodeIDOut.from_node_id(ann.blueprint) if ann.blueprint else None,
            domain=ann.domain,
            equivalents=[CellOut.from_cell(c) for c in ann.equivalents],
            equivalents_count=len(ann.equivalents),
            in_substrate=ann.cell is not None,
        )


class PageSubstrateOut(BaseModel):
    """Substrate footprint for a web route — what cells compose this page.

    Twins here are the *kind cohort*: artifacts that share this file's
    harmonic band (.tsx with .tsx, .py with .py). Blueprint-equivalence
    is not a useful discriminator across artifacts — every ARTIFACT cell
    today shares the same Blueprint shape `(path, kind, hash, size, mtime)`;
    the per-cell identity lives in the CTOR (which carries content_hash).
    The kind cohort is the meaningful structural neighborhood — a Recipe
    over surface form rather than over content.
    """

    route: str
    source_path: str | None = None
    in_substrate: bool = False
    source: CellOut | None = None
    twins: list[CellOut] = Field(default_factory=list)
    twins_count: int = 0
    twins_kind: str | None = None
    kind: str | None = None
    note: str | None = None


def _normalize_route(route: str) -> list[str]:
    """Strip query string + fragment + trailing slash; return path segments."""
    route = route.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    return [s for s in route.split("/") if s]


def _resolve_via_filesystem(segments: list[str], app_dir, repo_root) -> str | None:
    """Walk `web/app/` from the repo root. Used in dev where the repo is
    whole. Static segments match exactly; dynamic segments try `[*]` dirs."""
    current = app_dir
    for seg in segments:
        direct = current / seg
        if direct.is_dir():
            current = direct
            continue
        match = None
        if current.is_dir():
            for child in current.iterdir():
                if child.is_dir() and child.name.startswith("[") and child.name.endswith("]"):
                    match = child
                    break
        if match is None:
            return None
        current = match

    page_file = current / "page.tsx"
    if not page_file.is_file():
        return None
    try:
        rel = page_file.resolve().relative_to(repo_root)
    except ValueError:
        return None
    return str(rel).replace("\\", "/")


_ROUTE_MANIFEST_CACHE: dict[str, str] | None = None


def _load_route_manifest() -> dict[str, str]:
    """Read `api/app/data/web_routes.json` once and cache it.

    The manifest is generated by `scripts/generate_repo_indexes.py` and
    committed so the API container — which ships `api/` but not `web/` —
    can still resolve any page route. Keys are Next.js route patterns
    (e.g. `/ideas/[idea_id]`); values are repo-relative page paths.
    """
    global _ROUTE_MANIFEST_CACHE
    if _ROUTE_MANIFEST_CACHE is not None:
        return _ROUTE_MANIFEST_CACHE
    import json
    from pathlib import Path

    # __file__ = api/app/routers/substrate.py → parents[1] = api/app
    manifest_path = Path(__file__).resolve().parents[1] / "data" / "web_routes.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        routes = payload.get("routes", {})
        if isinstance(routes, dict):
            _ROUTE_MANIFEST_CACHE = {str(k): str(v) for k, v in routes.items()}
            return _ROUTE_MANIFEST_CACHE
    except (OSError, ValueError):
        pass
    _ROUTE_MANIFEST_CACHE = {}
    return _ROUTE_MANIFEST_CACHE


def _resolve_via_manifest(segments: list[str]) -> str | None:
    """Match the request segments against the committed route manifest.

    Builds a trie at first call (lazy) so static segments win over
    dynamic ones at every depth, matching Next.js routing semantics and
    the prior filesystem-walking behavior. Used in production where the
    `web/app/` tree isn't present in the API container.
    """
    routes = _load_route_manifest()
    if not routes:
        return None

    trie: dict = {}
    for pattern, source in routes.items():
        node = trie
        parts = [p for p in pattern.split("/") if p]
        for part in parts:
            node = node.setdefault("_children", {}).setdefault(part, {})
        node["_source"] = source

    node = trie
    for seg in segments:
        children = node.get("_children", {})
        if seg in children:
            node = children[seg]
            continue
        dyn_key = next(
            (k for k in children if k.startswith("[") and k.endswith("]")),
            None,
        )
        if dyn_key is None:
            return None
        node = children[dyn_key]

    return node.get("_source")


def _resolve_route_to_page_path(route: str) -> str | None:
    """Map a Next.js route like `/resonance` → `web/app/resonance/page.tsx`.

    Prefers filesystem walking when `web/app/` is on disk (dev), and
    falls back to the committed JSON manifest in `api/app/data/` when it
    isn't (the API container ships `api/` only). Returns the
    repo-relative path (POSIX separators) or None if no page matches.
    """
    from pathlib import Path

    segments = _normalize_route(route)
    repo_root = Path(__file__).resolve().parents[3]
    app_dir = repo_root / "web" / "app"
    if app_dir.is_dir():
        return _resolve_via_filesystem(segments, app_dir, repo_root)
    return _resolve_via_manifest(segments)


@router.get("/page", response_model=PageSubstrateOut, tags=["substrate"])
def get_page_substrate(
    route: str = Query(..., description="Web route, e.g. /resonance or /ideas/foo"),
) -> PageSubstrateOut:
    """Substrate footprint for a web route.

    Maps the route to its page.tsx, annotates it as an ARTIFACT cell, and
    returns structural twins — other pages whose Blueprint matches. The
    badge in the web layout calls this so any page can reveal what cells
    compose it and which other pages share its shape.

    Returns `in_substrate=False` with a `note` when the page file resolves
    but its ARTIFACT cell hasn't been ingested yet. Callers render the
    note quietly rather than treating it as an error.
    """
    path = _resolve_route_to_page_path(route)
    if path is None:
        return PageSubstrateOut(
            route=route,
            source_path=None,
            in_substrate=False,
            note="no page.tsx resolves for this route",
        )
    kind = path.rsplit(".", 1)[-1] if "." in path else None
    with session_scope() as session:
        ann = annotate_path(session, path)
        if ann.cell is None:
            return PageSubstrateOut(
                route=route,
                source_path=path,
                in_substrate=False,
                kind=kind,
                note="page found on disk but not yet ingested as an ARTIFACT cell",
            )
        twin_cells = _kind_cohort_for(session, path, kind, limit=24)
        return PageSubstrateOut(
            route=route,
            source_path=path,
            in_substrate=True,
            source=CellOut.from_cell(ann.cell),
            twins=[CellOut.from_cell(c) for c in twin_cells],
            twins_count=len(twin_cells),
            twins_kind=kind,
            kind=kind,
        )


def _kind_cohort_for(session, source_path: str, kind: str | None, *, limit: int):
    """Return up to `limit` other artifact cells sharing this kind.

    The kind cohort is the meaningful "structural neighborhood" for an
    artifact: cells whose file suffix matches. Excludes the source cell
    itself. Sorted by path for stability across calls.
    """
    from app.services.substrate.kernel import _orm_to_cell

    if not kind:
        return []
    suffix = f".{kind}"
    rows = (
        session.query(SubstrateNamedCellORM)
        .filter_by(domain="artifact")
        .filter(SubstrateNamedCellORM.name.endswith(suffix))
        .filter(SubstrateNamedCellORM.name != source_path)
        .order_by(SubstrateNamedCellORM.name)
        .limit(limit)
        .all()
    )
    return [_orm_to_cell(session, r) for r in rows]


class CellViewOut(BaseModel):
    cell: CellOut
    view_blueprint: NodeIDOut
    compatible: bool
    reason: str | None = None


@router.get("/view/{cell_domain}/{cell_name:path}", response_model=CellViewOut, tags=["substrate"])
def get_view(
    cell_domain: str,
    cell_name: str,
    blueprint_package: int = Query(..., alias="bp_package"),
    blueprint_level: int = Query(..., alias="bp_level"),
    blueprint_type: int = Query(..., alias="bp_type"),
    blueprint_instance: int = Query(..., alias="bp_instance"),
) -> CellViewOut:
    """Project a cell through a different Blueprint than its base.

    BML-style detached interface: the cell's data stays canonical; this
    endpoint returns a CellView that pairs the cell with a chosen view
    Blueprint, plus a compatibility flag indicating whether the projection
    is structurally sound.

    The substrate already has the dual-pointer shape implicitly in
    NamedCell{access Recipe, base Blueprint}. This endpoint exposes the
    Views explicitly so agents can reason about "this cell viewed as X"
    without committing the projection.
    """
    view_bp = NodeID(
        blueprint_package, blueprint_level, blueprint_type, blueprint_instance
    )
    with session_scope() as session:
        cell = lookup_cell(session, cell_domain, cell_name)
        if cell is None:
            raise HTTPException(
                status_code=404, detail=f"cell ({cell_domain}, {cell_name}) not found"
            )
        view = view_cell_through_blueprint(session, cell, view_bp)
        return CellViewOut(
            cell=CellOut.from_cell(view.cell),
            view_blueprint=NodeIDOut.from_node_id(view.view_blueprint),
            compatible=view.compatible,
            reason=view.reason,
        )


@router.get("/compatible_with/{package}/{level}/{type_}/{instance}", tags=["substrate"])
def get_compatible_cells(
    package: int,
    level: int,
    type_: int,
    instance: int,
    domain: str | None = Query(None),
) -> list[CellViewOut]:
    """Find all cells that can be viewed through this Blueprint.

    BML detached-interface query: given an interface (Blueprint), what
    cells in the body can be projected through it? Returns the set of
    compatible CellViews.
    """
    view_bp = NodeID(package, level, type_, instance)
    with session_scope() as session:
        views = find_cells_compatible_with(session, view_bp, domain=domain)
        return [
            CellViewOut(
                cell=CellOut.from_cell(v.cell),
                view_blueprint=NodeIDOut.from_node_id(v.view_blueprint),
                compatible=v.compatible,
                reason=v.reason,
            )
            for v in views
        ]


@router.get("/histogram/{domain}", response_model=HistogramOut, tags=["substrate"])
def get_histogram(domain: str) -> HistogramOut:
    """Vocabulary distribution for a domain — group cells by Blueprint NodeID.

    Returns: for this domain, how many cells share each Blueprint, with up to
    3 sample names per blueprint. The killer query: agents reasoning about
    "what shapes exist in this domain" call this and reason from the result.
    """
    with session_scope() as session:
        rows = (
            session.query(SubstrateNamedCellORM)
            .filter_by(domain=domain)
            .all()
        )
        by_blueprint: dict[int, dict[str, Any]] = {}
        for r in rows:
            bp_id = r.blueprint_node_id
            if bp_id not in by_blueprint:
                bp_orm = (
                    session.query(SubstrateNodeORM).filter_by(node_id=bp_id).one_or_none()
                )
                if bp_orm is None:
                    continue
                by_blueprint[bp_id] = {
                    "blueprint": NodeIDOut(
                        package=bp_orm.package,
                        level=bp_orm.level,
                        type=bp_orm.type_,
                        instance=bp_orm.instance,
                    ),
                    "count": 0,
                    "sample_names": [],
                }
            by_blueprint[bp_id]["count"] += 1
            if len(by_blueprint[bp_id]["sample_names"]) < 3:
                by_blueprint[bp_id]["sample_names"].append(r.name)

        entries = [HistogramEntry(**v) for v in by_blueprint.values()]
        entries.sort(key=lambda e: e.count, reverse=True)
        return HistogramOut(domain=domain, entries=entries)


# ---------------------------------------------------------------------------
# Shape-health — does each cell's CTOR carry structured composition or
# flat type-markers? Catches silent flatten regressions where aggregate
# counts look stable while cell CTORs point at flat encodings.
# ---------------------------------------------------------------------------


class DomainShapeOut(BaseModel):
    total: int
    structured: int
    flat: int
    no_ctor: int
    ratio: float  # structured / (structured + flat), 0..1


class ShapeHealthOut(BaseModel):
    overall: DomainShapeOut
    domains: dict[str, DomainShapeOut]
    flags: list[str]


# A CTOR's serialized representation looks like
#   "1.2.9.1+<child>+<child>+..."
# where each `<child>` is a NodeID in `package.level.type.instance` form.
# Structured CTORs have children at composite level (level >= 3, e.g.
# `1.3.X.Y`) — each child is itself a composed (key, value) recipe.
# Flat CTORs have children at trivial level (`1.1.X.Y`, level == 1) —
# each child is a leaf recipe carrying a type-marker string.
#
# The discriminator: a CTOR is structured iff at least one direct child
# is at level >= 2 (i.e. carries internal composition); flat iff every
# direct child is at level 1 (trivial leaves only).


@router.get("/shape_health", response_model=ShapeHealthOut, tags=["substrate"])
def get_shape_health() -> ShapeHealthOut:
    """Sense whether cells carry composed CTORs or flat type-markers.

    The structural-composition discipline (CLAUDE.md → "Structural
    composition discipline") promises every cell's CTOR is a tree of
    R_Block.LET (key, value) pairs all the way down. The earlier flat
    encoder produced CTORs whose children were trivial-string recipes
    holding type-marker strings like "name=str".

    Both shapes hash to NodeIDs that look superficially similar; the
    lattice/stats endpoint reports the same recipe count whether cells
    point at structured or flat CTORs. This endpoint distinguishes them
    by examining each CTOR's direct children: a `+1.2.9.3` token in the
    serialized representation means R_Block.LET is present (structured);
    children that are only `+1.1.5.*` (trivial strings) mean flat.

    Flags raised when ratio < 0.95 (5%+ of cells carry flat CTORs) so
    the wellness check surfaces silent flatten regressions before they
    compound.
    """
    with session_scope() as session:
        cells = session.query(SubstrateNamedCellORM).all()

        # Pre-fetch all CTOR node serialized strings in one batch.
        ctor_ids = {c.ctor_recipe_node_id for c in cells if c.ctor_recipe_node_id}
        ctor_nodes = (
            session.query(SubstrateNodeORM)
            .filter(SubstrateNodeORM.node_id.in_(ctor_ids))
            .all()
        ) if ctor_ids else []
        ctor_serialized: dict[int, str] = {n.node_id: n.serialized for n in ctor_nodes}

        def _classify(node_id: int | None) -> str:
            if not node_id:
                return "no_ctor"
            serialized = ctor_serialized.get(node_id, "")
            # Parse "category+child+child+..." into child NodeIDs and
            # read each child's level (second integer in p.l.t.i form).
            parts = serialized.split("+")
            if len(parts) <= 1:
                return "no_ctor"
            child_levels: list[int] = []
            for child in parts[1:]:
                segments = child.split(".")
                if len(segments) >= 2:
                    try:
                        child_levels.append(int(segments[1]))
                    except ValueError:
                        continue
            if not child_levels:
                return "no_ctor"
            # Structured iff any direct child has level >= 2 (i.e. is itself
            # a composed recipe). Flat iff every child is at level 1.
            return "structured" if any(lv >= 2 for lv in child_levels) else "flat"

        by_domain: dict[str, dict[str, int]] = {}
        overall_counts = {"structured": 0, "flat": 0, "no_ctor": 0, "total": 0}
        for cell in cells:
            kind = _classify(cell.ctor_recipe_node_id)
            bucket = by_domain.setdefault(
                cell.domain, {"structured": 0, "flat": 0, "no_ctor": 0, "total": 0}
            )
            bucket[kind] += 1
            bucket["total"] += 1
            overall_counts[kind] += 1
            overall_counts["total"] += 1

        def _to_out(counts: dict[str, int]) -> DomainShapeOut:
            denom = counts["structured"] + counts["flat"]
            ratio = (counts["structured"] / denom) if denom > 0 else 1.0
            return DomainShapeOut(
                total=counts["total"],
                structured=counts["structured"],
                flat=counts["flat"],
                no_ctor=counts["no_ctor"],
                ratio=round(ratio, 4),
            )

        domains = {d: _to_out(c) for d, c in by_domain.items()}
        overall = _to_out(overall_counts)

        flags: list[str] = []
        if overall.ratio < 0.95 and overall.flat > 0:
            flags.append(
                f"overall structured ratio {overall.ratio:.0%} — "
                f"{overall.flat} of {overall.flat + overall.structured} "
                f"cells carry flat CTORs; re-ingest with --structured"
            )
        for name, shape in domains.items():
            if shape.ratio < 0.95 and shape.flat > 0:
                flags.append(
                    f"{name}: structured ratio {shape.ratio:.0%} — "
                    f"{shape.flat} flat cells "
                    f"(of {shape.flat + shape.structured})"
                )

        return ShapeHealthOut(overall=overall, domains=domains, flags=flags)


# ---------------------------------------------------------------------------
# Form-language evaluation — the substrate-native query DSL
# ---------------------------------------------------------------------------


class FormRequest(BaseModel):
    expression: str = Field(
        ...,
        min_length=1,
        description=(
            "Form-notation expression. Examples: '?equivalent @spec(agent-pipeline)', "
            "'@memory(presences_of_the_field)', '?cells where domain == \"spec\"'. "
            "Grammar: docs/coherence-substrate/form-language.md."
        ),
    )
    mode: str = Field(
        default="ast",
        pattern="^(ast|streaming|run)$",
        description=(
            "Evaluation path. 'ast' uses the structural Form evaluator; 'streaming' "
            "uses the BMF-style direct Recipe emitter for its supported recipe subset; "
            "'run' executes Form through the runtime and returns the computed value."
        ),
    )


class FormResultOut(BaseModel):
    """Discriminated union of Form evaluation outcomes.

    `kind` names which field carries the result. Other fields are null.
    Kinds: node_id, recipe, cell, view, cells, views, lattice, keywords,
    vocabulary, value.
    """

    kind: str
    node_id: NodeIDOut | None = None
    cell: CellOut | None = None
    view: CellViewOut | None = None
    cells: list[CellOut] | None = None
    views: list[CellViewOut] | None = None
    lattice: dict[str, int] | None = None
    keywords: list[str] | None = None
    vocabulary: dict[str, dict[str, int]] | None = None
    value: Any | None = None


class KernelImageProposalRequest(BaseModel):
    expression: str = Field(
        ...,
        min_length=1,
        max_length=128 * 1024,
        description=(
            "BML source expression for a candidate kernel core image. This route "
            "previews and proves the proposal; it does not mutate production."
        ),
    )
    grammar: str = Field(
        default="bml",
        pattern="^bml$",
        description="Source grammar for this proposal. This first public gate accepts BML.",
    )
    requested_action: str = Field(
        default="preview",
        pattern="^(preview|apply)$",
        description=(
            "preview returns the candidate proof. apply is accepted as intent but "
            "still refuses live mutation in this public route."
        ),
    )
    source_label: str | None = Field(
        default=None,
        max_length=512,
        description="Optional caller-provided provenance label for the proposal source.",
    )


class KernelImageProofStepOut(BaseModel):
    name: str
    status: str
    detail: str
    observed: Any | None = None
    expected: Any | None = None


class KernelCoreImageCandidateOut(BaseModel):
    kind: str
    image_kind: str
    source_authority: str
    primitive_count: int
    dispatch_count: int
    proof_count: int
    witness_recipes: list[str]
    image_hash: str


class KernelImageMutationGateOut(BaseModel):
    requested: bool
    allowed: bool
    performed: bool
    reason: str
    next_gate: str


class KernelImageProposalOut(BaseModel):
    state: str
    proposal_id: str
    proposal_status: str
    grammar: str
    source_label: str | None = None
    source_hash: str
    canonical_source_hash: str | None = None
    proof_passed: bool
    candidate_image: KernelCoreImageCandidateOut | None = None
    diff: dict[str, Any]
    proof_trace: list[KernelImageProofStepOut]
    trust_envelope: dict[str, Any]
    mutation: KernelImageMutationGateOut


def _cell_view_out(v: CellView) -> CellViewOut:
    return CellViewOut(
        cell=CellOut.from_cell(v.cell),
        view_blueprint=NodeIDOut.from_node_id(v.view_blueprint),
        compatible=v.compatible,
        reason=v.reason,
    )


def _runtime_value_out(value: Any) -> Any:
    """Render Form runtime values into JSON-safe response payloads."""
    if isinstance(value, NodeID):
        node = NodeIDOut.from_node_id(value)
        return node.model_dump(by_alias=True) if node else None
    if isinstance(value, NamedCell):
        return CellOut.from_cell(value).model_dump(by_alias=True)
    if isinstance(value, CellView):
        return _cell_view_out(value).model_dump(by_alias=True)
    if isinstance(value, list):
        return [_runtime_value_out(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _runtime_value_out(item) for key, item in value.items()}
    return value


def _form_result_from_runtime_value(value: Any) -> FormResultOut:
    """Render runtime fallback values with the same shape as AST results."""
    if isinstance(value, NodeID):
        return FormResultOut(kind="node_id", node_id=NodeIDOut.from_node_id(value))
    if isinstance(value, NamedCell):
        return FormResultOut(kind="cell", cell=CellOut.from_cell(value))
    if isinstance(value, CellView):
        return FormResultOut(kind="view", view=_cell_view_out(value))
    if isinstance(value, list):
        if value and all(isinstance(item, NamedCell) for item in value):
            return FormResultOut(kind="cells", cells=[CellOut.from_cell(item) for item in value])
        if value and all(isinstance(item, CellView) for item in value):
            return FormResultOut(kind="views", views=[_cell_view_out(item) for item in value])
    return FormResultOut(kind="value", value=_runtime_value_out(value))


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_kernel_core_source() -> str | None:
    here = Path(__file__).resolve()
    for root in (*here.parents, Path.cwd()):
        candidate = root / _KERNEL_CORE_BML_RELATIVE
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return None


def _count_method_value(source: str, method_name: str) -> int | None:
    pattern = re.compile(
        rf"\bint\s+{re.escape(method_name)}\s*\(\s*\)\s*"
        r"(?:\[[^\]]*\]\s*)?\{\s*return\s+([0-9]+)\s*;\s*\}",
        re.DOTALL,
    )
    match = pattern.search(source)
    if not match:
        return None
    return int(match.group(1))


def _kernel_count_values(source: str) -> dict[str, int | None]:
    return {
        field: _count_method_value(source, method)
        for field, method in _KERNEL_CORE_COUNTS.items()
    }


def _proof_step(
    name: str,
    passed: bool,
    detail: str,
    *,
    observed: Any | None = None,
    expected: Any | None = None,
) -> KernelImageProofStepOut:
    return KernelImageProofStepOut(
        name=name,
        status="pass" if passed else "fail",
        detail=detail,
        observed=observed,
        expected=expected,
    )


def _kernel_image_proof_trace(
    source: str,
    counts: dict[str, int | None],
) -> list[KernelImageProofStepOut]:
    witness_methods = ["Minimal", "Observable", "Executable", "Trustable"]
    return [
        _proof_step(
            "source-present",
            bool(source.strip()),
            "Submitted source is non-empty.",
            observed=len(source),
            expected=">0 bytes",
        ),
        _proof_step(
            "grammar-bml",
            True,
            "This first proposal gate accepts BML source only.",
            observed="bml",
            expected="bml",
        ),
        _proof_step(
            "kernel-core-self-class",
            "class KernelCoreSelf" in source,
            "Source declares the kernel self class.",
            observed="class KernelCoreSelf" in source,
            expected=True,
        ),
        _proof_step(
            "kernel-core-image-class",
            "class KernelCoreImage" in source,
            "Source declares the kernel image class.",
            observed="class KernelCoreImage" in source,
            expected=True,
        ),
        _proof_step(
            "required-counts-present",
            all(value is not None for value in counts.values()),
            "Source declares primitive, dispatch, and proof counts.",
            observed=counts,
            expected={key: "int return" for key in counts},
        ),
        _proof_step(
            "witness-methods-present",
            all(f"bool {name}()" in source for name in witness_methods),
            "Source names the minimal observable executable trust witnesses.",
            observed=[name for name in witness_methods if f"bool {name}()" in source],
            expected=witness_methods,
        ),
    ]


def _proof_passed(trace: list[KernelImageProofStepOut]) -> bool:
    return all(step.status == "pass" for step in trace)


def _kernel_image_candidate(
    source_hash: str,
    counts: dict[str, int | None],
) -> KernelCoreImageCandidateOut | None:
    if not all(isinstance(value, int) for value in counts.values()):
        return None
    payload = {
        "kind": "KERNEL-CORE-IMAGE",
        "image_kind": "kernel-core-self",
        "source_hash": source_hash,
        "source_authority": "submitted BML source plus public proposal proof",
        "primitive_count": counts["primitive_count"],
        "dispatch_count": counts["dispatch_count"],
        "proof_count": counts["proof_count"],
        "witness_recipes": ["add", "if", "do"],
    }
    image_hash = _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return KernelCoreImageCandidateOut(
        kind="KERNEL-CORE-IMAGE",
        image_kind="kernel-core-self",
        source_authority="submitted BML source plus public proposal proof",
        primitive_count=int(counts["primitive_count"] or 0),
        dispatch_count=int(counts["dispatch_count"] or 0),
        proof_count=int(counts["proof_count"] or 0),
        witness_recipes=["add", "if", "do"],
        image_hash=image_hash,
    )


def _kernel_image_diff(
    source_hash: str,
    canonical_source: str | None,
    counts: dict[str, int | None],
) -> dict[str, Any]:
    canonical_hash = _sha256_text(canonical_source) if canonical_source is not None else None
    canonical_counts = (
        _kernel_count_values(canonical_source)
        if canonical_source is not None
        else {key: None for key in _KERNEL_CORE_COUNTS}
    )
    return {
        "same_as_current_source": source_hash == canonical_hash,
        "count_delta": {
            key: (
                None
                if counts[key] is None or canonical_counts[key] is None
                else counts[key] - canonical_counts[key]  # type: ignore[operator]
            )
            for key in _KERNEL_CORE_COUNTS
        },
        "canonical_counts": canonical_counts,
        "proposed_counts": counts,
    }


def _kernel_image_trust_envelope(
    *,
    proof_passed: bool,
    requested_action: str,
    candidate_image: KernelCoreImageCandidateOut | None,
) -> dict[str, Any]:
    return {
        "state": "kernel-image-proposal-preview",
        "choice_success": 1 if proof_passed else 0,
        "protocol": "POST /api/substrate/kernel-image/proposals",
        "default_route": "proposal-preview",
        "native_route": "Form kernel-image-proposal envelope",
        "bma": "kernel-image-proposal",
        "prediction_error": "carried_as_residual",
        "residual": (
            "Public source can propose a kernel image; live mutation remains "
            "behind commit, proof, review, deploy, and public SHA verification."
        ),
        "requested_action": requested_action,
        "mutation_allowed": False,
        "mutation_performed": False,
        "candidate_image_hash": candidate_image.image_hash if candidate_image else None,
        "rollback": "no production state changed by this route",
    }


def _is_access_bootstrap_gap(exc: TypeError) -> bool:
    text = str(exc)
    return (
        "Form: cannot evaluate Access" in text
        or "Form: cannot evaluate MethodCall" in text
    )


def _guard_public_form_expression(expression: str) -> None:
    """The retired Python evaluator never receives public expressions."""
    del expression
    raise HTTPException(
        status_code=410,
        detail=(
            "the consumer-side Python Form evaluator was removed; use "
            "POST /api/substrate/grounded-ask or the native form-cli carrier"
        ),
    )


@router.get("/form", response_model=FormResultOut, tags=["substrate"])
def evaluate_form_get(
    expression: str = Query(
        ...,
        min_length=1,
        max_length=2000,
        description=(
            "Form-notation expression, URL-encoded. Examples: "
            "'@concept(living-axioms)', '?equivalent @concept(lc-trust-over-fear)', "
            "'?lattice'. Grammar: docs/coherence-substrate/form-language.md."
        ),
    ),
    mode: str = Query(
        "ast",
        pattern="^(ast|run)$",
        description=(
            "'ast' (default) answers structural queries — @cell, ?lattice, "
            "?equivalent. 'run' executes Form and returns the computed value, "
            "so a guest can run any code they know the grammar for "
            "(e.g. 'defn fib (n) = ...; fib 10' -> 55). 'streaming' (Recipe "
            "emission) stays POST-only. Host-effect verbs are refused on "
            "either mode."
        ),
    ),
) -> FormResultOut:
    """GET lane of the Form door — form-cli for guests who cannot POST.

    Chat assistants (Grok, ChatGPT browsing, Gemini) can usually only fetch
    URLs, so the POST-only Form door was structurally invisible to them — a
    guest could read every cell's metadata but never speak, or run, the
    substrate's own language. This lane evaluates the same expressions through
    the same evaluators. 'ast' and 'run' are both offered (compute is the
    point); only 'streaming' Recipe emission is held to POST. Every expression
    passes the host-effect guard first (enforced in the shared handler below).
    """
    return evaluate_form(FormRequest(expression=expression, mode=mode))


@router.post("/form", response_model=FormResultOut, tags=["substrate"])
def evaluate_form(req: FormRequest) -> FormResultOut:
    """Evaluate a Form-notation expression against the substrate.

    The substrate's native query language. Lets an outside caller ask
    structural questions the body knows how to answer — without composing
    multiple lookup calls.

    Returns a discriminated result: the `kind` field names which payload
    field carries the value (node_id / recipe / cell / view / cells /
    views). `mode="streaming"` routes supported recipe expressions through
    the direct-emission parser and returns the emitted Recipe NodeID.
    `mode="run"` executes Form and returns the runtime value. Host-machine
    verbs (`pytest_passes`, `file_*`, `symbol_in_file`) are refused on this
    public door — they run only in in-process spec-proving. Parse and
    evaluation errors return HTTP 400 with the failure reason.

    Grammar lives in docs/coherence-substrate/form-language.md.
    """
    _guard_public_form_expression(req.expression)
    raise AssertionError("unreachable")


@router.post(
    "/kernel-image/proposals",
    response_model=KernelImageProposalOut,
    tags=["substrate"],
)
def propose_kernel_image(req: KernelImageProposalRequest) -> KernelImageProposalOut:
    """Preview a public kernel-image proposal without mutating production.

    The public interface can now receive BML source for the kernel core,
    derive a candidate image summary, return source/image hashes and a
    trust envelope, and explicitly stop before live mutation. Applying an
    accepted proposal still belongs to the source-control proof/deploy path.
    """
    source = req.expression
    source_hash = _sha256_text(source)
    canonical_source = _read_kernel_core_source()
    canonical_source_hash = (
        _sha256_text(canonical_source) if canonical_source is not None else None
    )
    counts = _kernel_count_values(source)
    proof_trace = _kernel_image_proof_trace(source, counts)
    proof_passed = _proof_passed(proof_trace)
    candidate_image = _kernel_image_candidate(source_hash, counts) if proof_passed else None
    proposal_id = "kernel-proposal-" + source_hash.removeprefix("sha256:")[:16]
    mutation_requested = req.requested_action == "apply"
    trust_envelope = _kernel_image_trust_envelope(
        proof_passed=proof_passed,
        requested_action=req.requested_action,
        candidate_image=candidate_image,
    )

    return KernelImageProposalOut(
        state="kernel-image-proposal-preview",
        proposal_id=proposal_id,
        proposal_status="accepted-preview" if proof_passed else "rejected-preview",
        grammar=req.grammar,
        source_label=req.source_label,
        source_hash=source_hash,
        canonical_source_hash=canonical_source_hash,
        proof_passed=proof_passed,
        candidate_image=candidate_image,
        diff=_kernel_image_diff(source_hash, canonical_source, counts),
        proof_trace=proof_trace,
        trust_envelope=trust_envelope,
        mutation=KernelImageMutationGateOut(
            requested=mutation_requested,
            allowed=False,
            performed=False,
            reason=(
                "This public route previews and proves the candidate image; it "
                "does not write files, open deploys, or mutate production."
            ),
            next_gate="commit evidence -> PR -> CI -> deploy -> public SHA verification",
        ),
    )


# ---------------------------------------------------------------------------
# Ingest — let a visiting body place markdown content into the lattice
# ---------------------------------------------------------------------------


_INGEST_DOMAINS = {"memory", "spec", "idea", "concept", "presence"}
_MAX_INGEST_CHARS = 64 * 1024  # 64KB — generous for memory/spec/idea/concept content

# Retry an ingest that the DB canceled due to lock_timeout (transient
# contention). Interning is idempotent, so a fresh-session retry is safe.
_INGEST_LOCK_RETRIES = 3
_INGEST_LOCK_BACKOFF_S = 0.1


def _is_lock_timeout(exc: Exception) -> bool:
    """True when a DB error is a lock_timeout cancellation (psycopg
    LockNotAvailable, surfaced as sqlalchemy OperationalError) — the fast-fail
    the 2026-07-02 DB timeouts produce for a lock-waiter."""
    orig = getattr(exc, "orig", None)
    if orig is not None and "LockNotAvailable" in type(orig).__name__:
        return True
    return "lock timeout" in str(exc).lower()


class IngestRequest(BaseModel):
    domain: str = Field(
        ...,
        description=(
            "Domain blueprint to ingest under. One of: memory, spec, idea, "
            "concept, presence."
        ),
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_INGEST_CHARS,
        description=(
            "Raw markdown content. If a frontmatter block is present, the "
            "domain's expected name field (e.g. 'name' for memory, 'id' for "
            "concept) is preferred; otherwise the body is hashed for identity."
        ),
    )
    source_label: str | None = Field(
        default=None,
        max_length=512,
        description=(
            "Provenance hint stored on the cell. Honest description of where "
            "this content came from (e.g. 'web:contributor:abc123')."
        ),
    )


class IngestResponse(BaseModel):
    cell: CellOut
    blueprint: NodeIDOut
    ctor: NodeIDOut | None = None


@router.post("/ingest", response_model=IngestResponse, tags=["substrate"])
def ingest_content(req: IngestRequest) -> IngestResponse:
    """Place markdown content into the lattice from outside the repo.

    The body-reads-itself practice still holds: this endpoint creates or
    updates a NamedCell keyed by the frontmatter name field (or body hash
    when no name is present). Cross-references in the content do *not*
    auto-bind to existing cells — equivalence in the substrate is
    structural, not lexical. Two ingested cells with the same shape
    converge automatically; two with different shapes stay distinct.
    """
    if req.domain not in _INGEST_DOMAINS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"unknown domain '{req.domain}'; expected one of "
                f"{sorted(_INGEST_DOMAINS)}"
            ),
        )
    # Retry on lock-timeout. Since 2026-07-02 the DB cancels a lock-waiter fast
    # (lock_timeout=5s) instead of letting it hang for hours — good, but the
    # canceled waiter surfaced to the client as a 500. Content-addressed
    # interning is IDEMPOTENT (same content -> same NodeID, no duplication), so
    # a fresh-session retry is safe: it absorbs transient contention into a
    # transparent success rather than a user-facing error. Bounded so a genuine
    # long-holder still fails fast (that case is the separate txn-shortening
    # fix, task_6a93acdd), never an unbounded spin.
    last_exc: Exception | None = None
    for attempt in range(_INGEST_LOCK_RETRIES):
        try:
            with session_scope() as session:
                try:
                    cell, blueprint_id, ctor_id = ingest_markdown_text(
                        session,
                        req.domain,
                        req.content,
                        source_label=req.source_label,
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                return IngestResponse(
                    cell=CellOut.from_cell(cell),
                    blueprint=NodeIDOut.from_node_id(blueprint_id),
                    ctor=NodeIDOut.from_node_id(ctor_id) if ctor_id else None,
                )
        except OperationalError as exc:
            if not _is_lock_timeout(exc):
                raise
            last_exc = exc
            if attempt < _INGEST_LOCK_RETRIES - 1:
                time.sleep(_INGEST_LOCK_BACKOFF_S * (attempt + 1))
    # Exhausted retries against sustained contention — a long holder, not a
    # transient. Fail honestly (503, retryable) rather than a bare 500.
    raise HTTPException(
        status_code=503,
        detail="write lane busy (lock contention); please retry",
    ) from last_exc
