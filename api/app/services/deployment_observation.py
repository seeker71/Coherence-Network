"""Persistent, content-bound deployment observations in the Form substrate.

The deploy host performs the independent HTTP observation.  This module admits
only a successful, SHA-matching ``/api/health`` response, preserves the exact
canonical response in a WITNESS CTOR, and can later re-derive every certificate
field from persisted substrate state.  A caller cannot turn an arbitrary RAG
answer into ``freq:yes`` by supplying a boolean.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app import config_loader
from app.services.substrate import NodeID, make_cell
from app.services.substrate.projection import ctor_field_lookup
from app.services.substrate.markdown_frontend import (
    BID_witness,
    body_to_access_recipe,
    frontmatter_to_blueprint,
    frontmatter_to_structured_ctor,
)
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM


SCHEMA = "deployment-witness-v3-oidc"
OBSERVER = "github-actions-oidc-public-loopback-and-direct-container-probes"
OBSERVER_AUTHENTICATION = "github-actions-oidc-v1"
SOURCE_PATH_PREFIX = "witness://deployment/"
_NAME_PREFIX = "deployment-observation-"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_NODE_RE = re.compile(r"^@[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$")
_FIELDS = (
    "schema",
    "observer",
    "observer_authentication",
    "observer_policy_sha256",
    "challenge_id",
    "observer_nonce",
    "nonce_sha256",
    "issued_jti",
    "observation_jti",
    "issued_claims_sha256",
    "observation_claims_sha256",
    "run_id",
    "run_attempt",
    "actor_id",
    "workflow_sha",
    "job_workflow_sha",
    "commitment_json",
    "commitment_sha256",
    "expected_sha",
    "actual_sha",
    "health_route",
    "host_health_status",
    "recorder_health_status",
    "health_result",
    "kernel_runtime",
    "kernel_binary_sha256",
    "kernel_result",
    "form_cli_binary_sha256",
    "form_cli_wrapper_sha256",
    "form_cli_table_sha256",
    "form_cli_stamp_sha256",
    "form_cli_source_sha256",
    "form_cli_result",
    "form_cli_protocol",
    "container_id",
    "image_id",
    "form_source_commit",
    "reproducible_builder_image",
    "reproduced_kernel_binary_sha256",
    "reproduced_form_cli_binary_sha256",
    "source_wrapper_sha256",
    "source_form_cli_source_sha256",
    "source_form_cli_table_sha256",
    "source_form_cli_stamp_sha256",
    "direct_probe_body_hex",
    "direct_probe_body_sha256",
    "host_health_body_hex",
    "host_health_body_sha256",
    "recorder_health_body_hex",
    "recorder_health_body_sha256",
    "stable_health_json",
    "stable_health_sha256",
    "evidence_key",
    "observed_at",
    "observed_epoch",
    "expires_at",
    "expires_epoch",
    "result",
)


class DeploymentObservationError(ValueError):
    """The proposed or persisted observation does not satisfy the contract."""


def _utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return _utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except (TypeError, ValueError) as exc:
        raise DeploymentObservationError("invalid-observation-time") from exc


def _max_clock_skew_seconds() -> int:
    skew = config_loader.get_int(
        "grounding", "deployment_witness_max_clock_skew_seconds", 120
    )
    if not 0 <= int(skew) <= 300:
        raise DeploymentObservationError("witness-clock-skew-config")
    return int(skew)


def _node_from_db_id(session: Session, db_id: int | None) -> NodeID | None:
    if db_id is None:
        return None
    row = session.query(SubstrateNodeORM).filter_by(node_id=db_id).one_or_none()
    if row is None:
        return None
    return NodeID(row.package, row.level, row.type_, row.instance)


def _decode_row(session: Session, row: SubstrateNamedCellORM) -> dict[str, Any]:
    ctor = _node_from_db_id(session, row.ctor_recipe_node_id)
    if ctor is None:
        raise DeploymentObservationError("witness-content-missing")
    payload = {field: ctor_field_lookup(session, ctor, field) for field in _FIELDS}
    payload.update(
        {
            "node_id": f"@1.1.9.{row.cell_id}",
            "content_node_id": f"@{ctor}",
            "source_path": row.source_path,
            "name": row.name,
        }
    )
    return payload


def _answer(payload: dict[str, Any]) -> str:
    """Exact answer bytes indexed and certified for this WITNESS."""
    answer = {
        "actual_sha": payload["actual_sha"],
        "actor_id": payload["actor_id"],
        "challenge_id": payload["challenge_id"],
        "commitment_sha256": payload["commitment_sha256"],
        "container_id": payload["container_id"],
        "content_node_id": payload["content_node_id"],
        "direct_probe_body_sha256": payload["direct_probe_body_sha256"],
        "evidence_key": payload["evidence_key"],
        "expected_sha": payload["expected_sha"],
        "expires_at": payload["expires_at"],
        "health_result": payload["health_result"],
        "health_route": payload["health_route"],
        "host_evidence_sha256": payload["host_health_body_sha256"],
        "host_health_status": payload["host_health_status"],
        "image_id": payload["image_id"],
        "issued_claims_sha256": payload["issued_claims_sha256"],
        "kernel_runtime": payload["kernel_runtime"],
        "kernel_binary_sha256": payload["kernel_binary_sha256"],
        "kernel_result": payload["kernel_result"],
        "form_cli_binary_sha256": payload["form_cli_binary_sha256"],
        "form_cli_wrapper_sha256": payload["form_cli_wrapper_sha256"],
        "form_cli_table_sha256": payload["form_cli_table_sha256"],
        "form_cli_stamp_sha256": payload["form_cli_stamp_sha256"],
        "form_cli_source_sha256": payload["form_cli_source_sha256"],
        "form_cli_result": payload["form_cli_result"],
        "form_cli_protocol": payload["form_cli_protocol"],
        "form_source_commit": payload["form_source_commit"],
        "reproducible_builder_image": payload["reproducible_builder_image"],
        "reproduced_kernel_binary_sha256": payload[
            "reproduced_kernel_binary_sha256"
        ],
        "reproduced_form_cli_binary_sha256": payload[
            "reproduced_form_cli_binary_sha256"
        ],
        "source_wrapper_sha256": payload["source_wrapper_sha256"],
        "source_form_cli_source_sha256": payload[
            "source_form_cli_source_sha256"
        ],
        "source_form_cli_table_sha256": payload[
            "source_form_cli_table_sha256"
        ],
        "source_form_cli_stamp_sha256": payload[
            "source_form_cli_stamp_sha256"
        ],
        "job_workflow_sha": payload["job_workflow_sha"],
        "node_id": payload["node_id"],
        "observer": payload["observer"],
        "observer_authentication": payload["observer_authentication"],
        "observer_policy_sha256": payload["observer_policy_sha256"],
        "observation_claims_sha256": payload[
            "observation_claims_sha256"
        ],
        "observed_at": payload["observed_at"],
        "recorder_evidence_sha256": payload[
            "recorder_health_body_sha256"
        ],
        "recorder_health_status": payload["recorder_health_status"],
        "result": payload["result"],
        "run_attempt": payload["run_attempt"],
        "run_id": payload["run_id"],
        "schema": payload["schema"],
        "stable_health_sha256": payload["stable_health_sha256"],
        "workflow_sha": payload["workflow_sha"],
    }
    return json.dumps(answer, sort_keys=True, separators=(",", ":"))


def frequency_receipt_key(
    cert_ref: str,
    subject_ctor: str,
    answer_key: str,
    expires_epoch: int,
    result: str,
) -> str:
    canonical = "\n".join(
        (
            "frequency-cert-v1",
            cert_ref,
            subject_ctor,
            answer_key,
            str(expires_epoch),
            result,
        )
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _authenticated_evidence_key(
    *,
    commitment_hash: str,
    host_hash: str,
    recorder_hash: str,
    direct_hash: str,
    stable_hash: str,
    issued_claims_hash: str,
    observation_claims_hash: str,
    policy_hash: str,
) -> str:
    return hashlib.sha256(
        "\n".join(
            (
                "authenticated-deployment-witness-v1",
                commitment_hash,
                host_hash,
                recorder_hash,
                direct_hash,
                stable_hash,
                issued_claims_hash,
                observation_claims_hash,
                policy_hash,
            )
        ).encode("utf-8")
    ).hexdigest()


def _strict_hex_bytes(payload: dict[str, Any], field: str) -> bytes:
    value = payload.get(field)
    if not isinstance(value, str) or not 4 <= len(value) <= 262144:
        raise DeploymentObservationError(f"witness-{field}-encoding")
    if len(value) % 2 or re.fullmatch(r"[0-9a-f]+", value) is None:
        raise DeploymentObservationError(f"witness-{field}-encoding")
    try:
        return bytes.fromhex(value)
    except ValueError as exc:  # defensive; the regex already excludes this
        raise DeploymentObservationError(f"witness-{field}-encoding") from exc


def _canonical_json_object(raw: str, label: str) -> tuple[dict[str, Any], str]:
    if not isinstance(raw, str) or not 2 <= len(raw) <= 131072:
        raise DeploymentObservationError(f"witness-{label}-json")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise DeploymentObservationError(f"witness-{label}-duplicate-key")
            value[key] = item
        return value

    try:
        parsed = json.loads(raw, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise DeploymentObservationError(f"witness-{label}-json") from exc
    if not isinstance(parsed, dict):
        raise DeploymentObservationError(f"witness-{label}-object")
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    if raw != canonical:
        raise DeploymentObservationError(f"witness-{label}-canonical")
    return parsed, canonical


def record_deployment_observation(
    session: Session,
    *,
    expected_sha: str,
    host_health: dict[str, Any] | str | bytes,
    recorder_health: dict[str, Any] | str | bytes,
    host_health_status: int = 200,
    recorder_health_status: int = 200,
    health_route: str = "/api/health",
    observed_at: datetime | None = None,
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    """Retired writer: unauthenticated health JSON can never mint a WITNESS."""
    raise DeploymentObservationError("authenticated-observer-required")


def record_authenticated_deployment_observation(
    session: Session,
    *,
    observation: dict[str, Any],
    host_health: bytes,
    recorder_health: bytes,
    host_health_status: int = 200,
    recorder_health_status: int = 200,
    health_route: str = "/api/health",
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    """Persist only a consumed, GitHub-OIDC-bound observer challenge."""
    from app.services.deployment_observer_service import (
        DeploymentObserverChallengeORM,
        bind_witness,
        canonical_json_bytes,
        health_url,
        nonce_sha256,
        observer_policy,
        observer_policy_sha256,
        stable_health_projection,
        validate_direct_probe,
    )

    challenge_value = observation.get("challenge")
    challenge_id = str(getattr(challenge_value, "challenge_id", ""))
    challenge = session.get(DeploymentObserverChallengeORM, challenge_id)
    if challenge is None:
        raise DeploymentObservationError("observer-challenge-unresolved")
    session.refresh(challenge)
    if challenge.consumed_epoch is None or challenge.witness_node_id is not None:
        raise DeploymentObservationError("observer-challenge-not-consumable")
    nonce = str(observation.get("nonce") or "")
    if challenge.nonce_sha256 != nonce_sha256(nonce):
        raise DeploymentObservationError("observer-nonce-binding")
    expected = challenge.target_sha
    if health_route != "/api/health" or host_health_status != 200:
        raise DeploymentObservationError("observer-health-transport")
    if recorder_health_status != 200:
        raise DeploymentObservationError("observer-loopback-transport")
    host_projection = stable_health_projection(
        host_health, nonce=nonce, target_sha=expected
    )
    recorder_projection = stable_health_projection(
        recorder_health, nonce=nonce, target_sha=expected
    )
    if canonical_json_bytes(host_projection) != canonical_json_bytes(
        recorder_projection
    ):
        raise DeploymentObservationError("observer-health-vantage-mismatch")
    stable_projection = observation.get("stable_projection")
    if stable_projection != host_projection:
        raise DeploymentObservationError("observer-stable-projection-binding")
    direct_bytes = observation.get("direct_probe_body")
    if not isinstance(direct_bytes, bytes):
        raise DeploymentObservationError("observer-direct-body-missing")
    direct_projection = validate_direct_probe(
        direct_bytes,
        challenge_input=str(host_projection["carrier_challenge_input_sha256"]),
        target_sha=expected,
        public_projection=host_projection,
    )
    if direct_projection != observation.get("direct_probe"):
        raise DeploymentObservationError("observer-direct-projection-binding")
    host_hash = hashlib.sha256(host_health).hexdigest()
    recorder_hash = hashlib.sha256(recorder_health).hexdigest()
    direct_hash = hashlib.sha256(direct_bytes).hexdigest()
    if (
        host_hash != observation.get("public_body_sha256")
        or recorder_hash != observation.get("loopback_body_sha256")
        or direct_hash != observation.get("direct_probe_body_sha256")
    ):
        raise DeploymentObservationError("observer-exact-body-binding")
    stable_json = canonical_json_bytes(host_projection).decode("utf-8")
    stable_hash = hashlib.sha256(stable_json.encode("utf-8")).hexdigest()
    if stable_hash != observation.get("stable_projection_sha256"):
        raise DeploymentObservationError("observer-stable-hash-binding")
    policy_hash = observer_policy_sha256(observer_policy())
    commitment = observation.get("commitment")
    if not isinstance(commitment, dict):
        raise DeploymentObservationError("observer-commitment-missing")
    commitment_json = canonical_json_bytes(commitment).decode("utf-8")
    commitment_hash = hashlib.sha256(commitment_json.encode("utf-8")).hexdigest()
    if commitment_hash != observation.get("commitment_sha256"):
        raise DeploymentObservationError("observer-commitment-binding")
    if commitment.get("observer_policy_sha256") != policy_hash:
        raise DeploymentObservationError("observer-policy-binding")
    if commitment.get("effective_url") != health_url(nonce):
        raise DeploymentObservationError("observer-health-url-binding")
    identity = observation.get("identity")
    if not isinstance(identity, dict):
        raise DeploymentObservationError("observer-identity-missing")
    if (
        challenge.observation_jti != identity.get("jti")
        or challenge.observation_claims_sha256 != identity.get("claims_sha256")
        or challenge.commitment_sha256 != commitment_hash
    ):
        raise DeploymentObservationError("observer-ledger-binding")

    current = _utc()
    observed = datetime.fromtimestamp(
        int(challenge.consumed_epoch), tz=timezone.utc
    ).replace(microsecond=0)
    if observed > current + timedelta(seconds=_max_clock_skew_seconds()):
        raise DeploymentObservationError("witness-observed-in-future")
    ttl = ttl_seconds
    if ttl is None:
        ttl = config_loader.get_int(
            "grounding", "deployment_witness_ttl_seconds", 86400
        )
    if not 60 <= int(ttl) <= 604800:
        raise DeploymentObservationError("witness-ttl-out-of-range")
    expires = observed + timedelta(seconds=int(ttl))
    evidence_key = _authenticated_evidence_key(
        commitment_hash=commitment_hash,
        host_hash=host_hash,
        recorder_hash=recorder_hash,
        direct_hash=direct_hash,
        stable_hash=stable_hash,
        issued_claims_hash=challenge.issued_claims_sha256,
        observation_claims_hash=str(challenge.observation_claims_sha256),
        policy_hash=policy_hash,
    )
    frontmatter: dict[str, Any] = {
        "schema": SCHEMA,
        "observer": OBSERVER,
        "observer_authentication": OBSERVER_AUTHENTICATION,
        "observer_policy_sha256": policy_hash,
        "challenge_id": challenge.challenge_id,
        "observer_nonce": nonce,
        "nonce_sha256": challenge.nonce_sha256,
        "issued_jti": challenge.issued_jti,
        "observation_jti": challenge.observation_jti,
        "issued_claims_sha256": challenge.issued_claims_sha256,
        "observation_claims_sha256": challenge.observation_claims_sha256,
        "run_id": challenge.run_id,
        "run_attempt": challenge.run_attempt,
        "actor_id": challenge.actor_id,
        "workflow_sha": challenge.workflow_sha,
        "job_workflow_sha": challenge.job_workflow_sha,
        "commitment_json": commitment_json,
        "commitment_sha256": commitment_hash,
        "expected_sha": expected,
        "actual_sha": expected,
        "health_route": health_route,
        "host_health_status": host_health_status,
        "recorder_health_status": recorder_health_status,
        "health_result": "ok",
        "kernel_runtime": host_projection["kernel_runtime"],
        "kernel_binary_sha256": host_projection["kernel_binary_sha256"],
        "kernel_result": host_projection["kernel_result"],
        "form_cli_binary_sha256": host_projection[
            "form_cli_binary_sha256"
        ],
        "form_cli_wrapper_sha256": host_projection[
            "form_cli_wrapper_sha256"
        ],
        "form_cli_table_sha256": host_projection[
            "form_cli_table_sha256"
        ],
        "form_cli_stamp_sha256": host_projection[
            "form_cli_stamp_sha256"
        ],
        "form_cli_source_sha256": host_projection[
            "form_cli_source_sha256"
        ],
        "form_cli_result": host_projection["form_cli_result"],
        "form_cli_protocol": host_projection["form_cli_protocol"],
        "container_id": direct_projection["container_id"],
        "image_id": direct_projection["image_id"],
        "form_source_commit": direct_projection["form_source_commit"],
        "reproducible_builder_image": direct_projection[
            "reproducible_builder_image"
        ],
        "reproduced_kernel_binary_sha256": direct_projection[
            "reproduced_kernel_binary_sha256"
        ],
        "reproduced_form_cli_binary_sha256": direct_projection[
            "reproduced_form_cli_binary_sha256"
        ],
        "source_wrapper_sha256": direct_projection["source_wrapper_sha256"],
        "source_form_cli_source_sha256": direct_projection[
            "source_form_cli_source_sha256"
        ],
        "source_form_cli_table_sha256": direct_projection[
            "source_form_cli_table_sha256"
        ],
        "source_form_cli_stamp_sha256": direct_projection[
            "source_form_cli_stamp_sha256"
        ],
        "direct_probe_body_hex": direct_bytes.hex(),
        "direct_probe_body_sha256": direct_hash,
        "host_health_body_hex": host_health.hex(),
        "host_health_body_sha256": host_hash,
        "recorder_health_body_hex": recorder_health.hex(),
        "recorder_health_body_sha256": recorder_hash,
        "stable_health_json": stable_json,
        "stable_health_sha256": stable_hash,
        "evidence_key": evidence_key,
        "observed_at": _iso(observed),
        "observed_epoch": int(observed.timestamp()),
        "expires_at": _iso(expires),
        "expires_epoch": int(expires.timestamp()),
        "result": "success",
    }
    name = (
        f"{_NAME_PREFIX}{expected[:12]}-{int(observed.timestamp())}-"
        f"{evidence_key[:12]}"
    )
    blueprint = frontmatter_to_blueprint(session, frontmatter, BID_witness())
    ctor = frontmatter_to_structured_ctor(session, frontmatter)
    if ctor is None:
        raise DeploymentObservationError("witness-content-missing")
    access = body_to_access_recipe(
        session,
        json.dumps(
            {
                "commitment": commitment,
                "direct": direct_projection,
                "stable": host_projection,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        blueprint,
    )
    cell = make_cell(
        session,
        name=name,
        domain="witness",
        blueprint=blueprint,
        access=access,
        ctor=ctor,
        source_path=f"{SOURCE_PATH_PREFIX}{name}",
    )
    bind_witness(
        session,
        challenge_id=challenge.challenge_id,
        witness_node_id=f"@1.1.9.{cell.cell_id}",
    )
    row = session.query(SubstrateNamedCellORM).filter_by(cell_id=cell.cell_id).one()
    return _verified_payload(
        session,
        _decode_row(session, row),
        now=current,
        allow_expired=False,
        require_current=False,
    )


def _verified_payload(
    session: Session,
    payload: dict[str, Any],
    *,
    now: datetime | None = None,
    allow_expired: bool = False,
    expected_answer_key: str | None = None,
    require_current: bool = True,
) -> dict[str, Any]:
    from app.services.deployment_observer_service import (
        SCHEMA as CHALLENGE_SCHEMA,
        DeploymentObserverChallengeORM,
        DeploymentObserverError as ExternalObserverError,
        DeploymentObserverTokenUseORM,
        canonical_json_bytes,
        carrier_challenge_input_sha256,
        health_url,
        nonce_sha256,
        observation_commitment,
        observer_policy,
        observer_policy_sha256,
        stable_health_projection,
        validate_direct_probe,
    )

    if payload.get("schema") != SCHEMA:
        raise DeploymentObservationError("witness-schema")
    if payload.get("observer") != OBSERVER:
        raise DeploymentObservationError("witness-observer")
    if payload.get("observer_authentication") != OBSERVER_AUTHENTICATION:
        raise DeploymentObservationError("witness-observer-authentication")
    if payload.get("health_route") != "/api/health":
        raise DeploymentObservationError("witness-health-route")
    expected = str(payload.get("expected_sha") or "")
    actual = str(payload.get("actual_sha") or "")
    if not _SHA_RE.fullmatch(expected) or actual != expected:
        raise DeploymentObservationError("witness-sha-mismatch")
    try:
        host_health_status = int(payload.get("host_health_status"))
        recorder_health_status = int(payload.get("recorder_health_status"))
        observed_epoch = int(payload.get("observed_epoch"))
        expires_epoch = int(payload.get("expires_epoch"))
    except (TypeError, ValueError) as exc:
        raise DeploymentObservationError("witness-numeric-field") from exc
    if host_health_status != 200 or recorder_health_status != 200:
        raise DeploymentObservationError("witness-health-status")
    observed = _parse_iso(str(payload.get("observed_at") or ""))
    expires = _parse_iso(str(payload.get("expires_at") or ""))
    if int(observed.timestamp()) != observed_epoch:
        raise DeploymentObservationError("witness-observed-binding")
    if int(expires.timestamp()) != expires_epoch or expires_epoch <= observed_epoch:
        raise DeploymentObservationError("witness-expiry-binding")
    current = _utc(now)
    if observed_epoch > int(current.timestamp()) + _max_clock_skew_seconds():
        raise DeploymentObservationError("witness-observed-in-future")
    if not 60 <= expires_epoch - observed_epoch <= 604800:
        raise DeploymentObservationError("witness-ttl-binding")
    if not allow_expired and int(current.timestamp()) > expires_epoch:
        raise DeploymentObservationError("witness-expired")
    if payload.get("result") != "success" or payload.get("health_result") != "ok":
        raise DeploymentObservationError("witness-result")
    if not _NODE_RE.fullmatch(str(payload.get("node_id") or "")):
        raise DeploymentObservationError("witness-ref")
    if not _NODE_RE.fullmatch(str(payload.get("content_node_id") or "")):
        raise DeploymentObservationError("witness-content-node")

    challenge_id = str(payload.get("challenge_id") or "")
    challenge = session.get(DeploymentObserverChallengeORM, challenge_id)
    if challenge is None or challenge.schema != CHALLENGE_SCHEMA:
        raise DeploymentObservationError("witness-challenge-ledger")
    session.refresh(challenge)
    if (
        challenge.consumed_epoch is None
        or challenge.witness_node_id != payload["node_id"]
        or challenge.target_sha != expected
        or int(challenge.consumed_epoch) != observed_epoch
    ):
        raise DeploymentObservationError("witness-challenge-binding")

    ledger_bindings = {
        "nonce_sha256": challenge.nonce_sha256,
        "issued_jti": challenge.issued_jti,
        "observation_jti": challenge.observation_jti,
        "issued_claims_sha256": challenge.issued_claims_sha256,
        "observation_claims_sha256": challenge.observation_claims_sha256,
        "run_id": challenge.run_id,
        "run_attempt": challenge.run_attempt,
        "actor_id": challenge.actor_id,
        "workflow_sha": challenge.workflow_sha,
        "job_workflow_sha": challenge.job_workflow_sha,
        "commitment_sha256": challenge.commitment_sha256,
        "host_health_body_sha256": challenge.public_body_sha256,
        "recorder_health_body_sha256": challenge.loopback_body_sha256,
        "direct_probe_body_sha256": challenge.direct_probe_body_sha256,
        "stable_health_sha256": challenge.stable_projection_sha256,
        "container_id": challenge.container_id,
        "image_id": challenge.image_id,
        "form_source_commit": challenge.form_source_commit,
    }
    if any(
        str(payload.get(field) or "") != str(value or "")
        for field, value in ledger_bindings.items()
    ):
        raise DeploymentObservationError("witness-ledger-field-binding")
    if payload.get("issued_jti") == payload.get("observation_jti"):
        raise DeploymentObservationError("witness-oidc-token-reuse")

    for phase, jti, claims_hash in (
        ("challenge", challenge.issued_jti, challenge.issued_claims_sha256),
        (
            "observation",
            challenge.observation_jti,
            challenge.observation_claims_sha256,
        ),
    ):
        token_use = session.get(DeploymentObserverTokenUseORM, str(jti or ""))
        if (
            token_use is None
            or token_use.phase != phase
            or token_use.challenge_id != challenge_id
            or token_use.target_sha != expected
            or token_use.claims_sha256 != claims_hash
        ):
            raise DeploymentObservationError("witness-oidc-token-ledger")

    nonce = str(payload.get("observer_nonce") or "")
    try:
        nonce_hash = nonce_sha256(nonce)
        policy = observer_policy()
        policy_hash = observer_policy_sha256(policy)
    except ExternalObserverError as exc:
        raise DeploymentObservationError(str(exc)) from exc
    if nonce_hash != payload.get("nonce_sha256"):
        raise DeploymentObservationError("witness-nonce-binding")
    if payload.get("observer_policy_sha256") != policy_hash:
        raise DeploymentObservationError("witness-policy-binding")
    if challenge.workflow_sha != expected:
        raise DeploymentObservationError("witness-caller-workflow-sha")
    if challenge.job_workflow_sha != policy.observer_workflow_sha:
        raise DeploymentObservationError("witness-observer-workflow-sha")

    host_bytes = _strict_hex_bytes(payload, "host_health_body_hex")
    recorder_bytes = _strict_hex_bytes(payload, "recorder_health_body_hex")
    direct_bytes = _strict_hex_bytes(payload, "direct_probe_body_hex")
    host_hash = hashlib.sha256(host_bytes).hexdigest()
    recorder_hash = hashlib.sha256(recorder_bytes).hexdigest()
    direct_hash = hashlib.sha256(direct_bytes).hexdigest()
    if (
        host_hash != payload.get("host_health_body_sha256")
        or recorder_hash != payload.get("recorder_health_body_sha256")
        or direct_hash != payload.get("direct_probe_body_sha256")
    ):
        raise DeploymentObservationError("witness-exact-body-hash")

    try:
        host_projection = stable_health_projection(
            host_bytes, nonce=nonce, target_sha=expected
        )
        recorder_projection = stable_health_projection(
            recorder_bytes, nonce=nonce, target_sha=expected
        )
        if canonical_json_bytes(host_projection) != canonical_json_bytes(
            recorder_projection
        ):
            raise DeploymentObservationError("witness-health-vantage-mismatch")
        stable_json = canonical_json_bytes(host_projection).decode("utf-8")
        stable_hash = hashlib.sha256(stable_json.encode("utf-8")).hexdigest()
        direct_projection = validate_direct_probe(
            direct_bytes,
            challenge_input=carrier_challenge_input_sha256(nonce),
            target_sha=expected,
            public_projection=host_projection,
        )
    except ExternalObserverError as exc:
        raise DeploymentObservationError(str(exc)) from exc
    if payload.get("stable_health_json") != stable_json:
        raise DeploymentObservationError("witness-stable-health-binding")
    if payload.get("stable_health_sha256") != stable_hash:
        raise DeploymentObservationError("witness-stable-health-hash")

    carrier_bindings = {
        "kernel_runtime": host_projection["kernel_runtime"],
        "kernel_binary_sha256": host_projection["kernel_binary_sha256"],
        "kernel_result": host_projection["kernel_result"],
        "form_cli_binary_sha256": host_projection["form_cli_binary_sha256"],
        "form_cli_wrapper_sha256": host_projection["form_cli_wrapper_sha256"],
        "form_cli_table_sha256": host_projection["form_cli_table_sha256"],
        "form_cli_stamp_sha256": host_projection["form_cli_stamp_sha256"],
        "form_cli_source_sha256": host_projection["form_cli_source_sha256"],
        "form_cli_result": host_projection["form_cli_result"],
        "form_cli_protocol": host_projection["form_cli_protocol"],
    }
    direct_bindings = {
        "container_id": direct_projection["container_id"],
        "image_id": direct_projection["image_id"],
        "form_source_commit": direct_projection["form_source_commit"],
        "reproducible_builder_image": direct_projection[
            "reproducible_builder_image"
        ],
        "reproduced_kernel_binary_sha256": direct_projection[
            "reproduced_kernel_binary_sha256"
        ],
        "reproduced_form_cli_binary_sha256": direct_projection[
            "reproduced_form_cli_binary_sha256"
        ],
        "source_wrapper_sha256": direct_projection["source_wrapper_sha256"],
        "source_form_cli_source_sha256": direct_projection[
            "source_form_cli_source_sha256"
        ],
        "source_form_cli_table_sha256": direct_projection[
            "source_form_cli_table_sha256"
        ],
        "source_form_cli_stamp_sha256": direct_projection[
            "source_form_cli_stamp_sha256"
        ],
    }
    if any(str(payload.get(key)) != str(value) for key, value in carrier_bindings.items()):
        raise DeploymentObservationError("witness-native-carrier-binding")
    if any(str(payload.get(key)) != str(value) for key, value in direct_bindings.items()):
        raise DeploymentObservationError("witness-direct-probe-binding")

    commitment, commitment_json = _canonical_json_object(
        str(payload.get("commitment_json") or ""), "commitment"
    )
    commitment_hash = hashlib.sha256(commitment_json.encode("utf-8")).hexdigest()
    try:
        effective_url = health_url(nonce)
        expected_commitment, expected_commitment_hash = observation_commitment(
            challenge=challenge,
            public_url=effective_url,
            expected_public_url=effective_url,
            status_code=host_health_status,
            content_type="application/json",
            public_body_sha256=host_hash,
            stable_sha256=stable_hash,
            direct_probe_body_sha256=direct_hash,
            container_id=str(direct_projection["container_id"]),
            image_id=str(direct_projection["image_id"]),
            form_source_commit=str(direct_projection["form_source_commit"]),
        )
    except ExternalObserverError as exc:
        raise DeploymentObservationError(str(exc)) from exc
    if (
        commitment != expected_commitment
        or commitment_hash != expected_commitment_hash
        or commitment_hash != payload.get("commitment_sha256")
    ):
        raise DeploymentObservationError("witness-commitment-binding")

    issued_claims_hash = str(payload.get("issued_claims_sha256") or "")
    observation_claims_hash = str(
        payload.get("observation_claims_sha256") or ""
    )
    for digest in (
        host_hash,
        recorder_hash,
        direct_hash,
        stable_hash,
        commitment_hash,
        issued_claims_hash,
        observation_claims_hash,
        policy_hash,
    ):
        if _HEX64_RE.fullmatch(digest) is None:
            raise DeploymentObservationError("witness-digest-field")
    evidence_key = _authenticated_evidence_key(
        commitment_hash=commitment_hash,
        host_hash=host_hash,
        recorder_hash=recorder_hash,
        direct_hash=direct_hash,
        stable_hash=stable_hash,
        issued_claims_hash=issued_claims_hash,
        observation_claims_hash=observation_claims_hash,
        policy_hash=policy_hash,
    )
    if payload.get("evidence_key") != evidence_key:
        raise DeploymentObservationError("witness-evidence-key-binding")

    if require_current:
        _require_current_deployment(payload, carrier_bindings)

    answer = _answer(payload)
    answer_key = hashlib.sha256(answer.encode("utf-8")).hexdigest()
    if expected_answer_key is not None and answer_key != expected_answer_key:
        raise DeploymentObservationError("witness-answer-binding")
    cert_key = frequency_receipt_key(
        str(payload["node_id"]),
        str(payload["content_node_id"]),
        answer_key,
        expires_epoch,
        "success",
    )
    return {
        **payload,
        "verified": True,
        "answer": answer,
        "answer_key": answer_key,
        "source_key": evidence_key,
        "certificate_node_id": payload["node_id"],
        "certificate_subject_content_node_id": payload["content_node_id"],
        "certificate_expires_epoch": expires_epoch,
        "certificate_result": "success",
        "certificate_receipt_key": cert_key,
    }


def _require_current_deployment(
    payload: dict[str, Any],
    carrier_bindings: dict[str, Any],
) -> None:
    """Re-execute the exact witnessed carrier challenge on the current image."""
    from app.services.deployment_observer_service import (
        DeploymentObserverError as ExternalObserverError,
        carrier_challenge_input_sha256,
        current_deployed_sha,
    )
    from app.services.native_runtime_observation import (
        observe_native_runtime_challenge,
    )

    try:
        current_sha = current_deployed_sha()
        challenge_input = carrier_challenge_input_sha256(
            str(payload.get("observer_nonce") or "")
        )
    except ExternalObserverError as exc:
        raise DeploymentObservationError(str(exc)) from exc
    if current_sha != payload.get("actual_sha"):
        raise DeploymentObservationError("witness-not-current-deployment")
    try:
        native = observe_native_runtime_challenge(challenge_input)
    except Exception as exc:
        raise DeploymentObservationError("witness-current-native-unverified") from exc
    if native.get("verified") is not True:
        raise DeploymentObservationError("witness-current-native-unverified")
    kernel = native.get("kernel")
    form_cli = native.get("form_cli")
    if not isinstance(kernel, dict) or not isinstance(form_cli, dict):
        raise DeploymentObservationError("witness-current-native-unverified")
    current_bindings = {
        "kernel_runtime": kernel.get("runtime"),
        "kernel_binary_sha256": kernel.get("binary_sha256"),
        "kernel_result": str(kernel.get("result")),
        "form_cli_binary_sha256": form_cli.get("binary_sha256"),
        "form_cli_wrapper_sha256": form_cli.get("wrapper_sha256"),
        "form_cli_table_sha256": form_cli.get("table_sha256"),
        "form_cli_stamp_sha256": form_cli.get("stamp_sha256"),
        "form_cli_source_sha256": form_cli.get("source_stamp"),
        "form_cli_result": form_cli.get("challenge_response_sha256"),
        "form_cli_protocol": "form-cli-v2",
    }
    if current_bindings != carrier_bindings:
        raise DeploymentObservationError("witness-not-current-native-carrier")
def verify_deployment_observation(
    session: Session,
    node_id: str,
    *,
    expected_answer_key: str | None = None,
    now: datetime | None = None,
    allow_expired: bool = False,
    require_current: bool = True,
) -> dict[str, Any]:
    match = re.fullmatch(r"@1\.1\.9\.([0-9]+)", node_id)
    if match is None:
        raise DeploymentObservationError("witness-ref")
    row = (
        session.query(SubstrateNamedCellORM)
        .filter_by(cell_id=int(match.group(1)), domain="witness")
        .one_or_none()
    )
    if row is None or not row.name.startswith(_NAME_PREFIX):
        raise DeploymentObservationError("witness-unresolved")
    return _verified_payload(
        session,
        _decode_row(session, row),
        now=now,
        allow_expired=allow_expired,
        expected_answer_key=expected_answer_key,
        require_current=require_current,
    )


def latest_deployment_observation(
    session: Session,
    *,
    now: datetime | None = None,
    allow_expired: bool = True,
    require_current: bool = True,
) -> dict[str, Any] | None:
    rows = (
        session.query(SubstrateNamedCellORM)
        .filter(SubstrateNamedCellORM.domain == "witness")
        .filter(SubstrateNamedCellORM.name.like(f"{_NAME_PREFIX}%"))
        .order_by(SubstrateNamedCellORM.created_at.desc(), SubstrateNamedCellORM.cell_id.desc())
        .all()
    )
    for row in rows:
        try:
            return _verified_payload(
                session,
                _decode_row(session, row),
                now=now,
                allow_expired=allow_expired,
                require_current=require_current,
            )
        except DeploymentObservationError:
            continue
    return None
