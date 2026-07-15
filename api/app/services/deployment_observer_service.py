"""One-time external deployment challenges and byte-bound observations."""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from dataclasses import asdict
from typing import Any, Mapping
from urllib.parse import quote
from uuid import uuid4

from sqlalchemy import Column, Integer, String, UniqueConstraint, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config_loader
from app.services.config_service import get_config
from app.services.unified_db import Base
from app.services.deployment_observer_oidc import (
    GitHubJWKS,
    ObserverOIDCError,
    ObserverOIDCPolicy,
    challenge_audience,
    observation_audience,
)


SCHEMA = "deployment-observer-challenge-v1"
HEALTH_SCHEMA = "native-carrier-observation-v1"
DIRECT_PROBE_SCHEMA = "direct-native-carrier-probe-v1"
COMMITMENT_SCHEMA = "deployment-observation-commitment-v1"
PUBLIC_API_BASE = "https://api.coherencycoin.com"
# Bootstrap invariant: the first PR lands the reusable workflow; the follow-up
# integration PR replaces this empty value with that merged commit's full SHA.
# Identity pins live in reviewed image code, never the host-mutable config.
PINNED_OBSERVER_WORKFLOW_SHA = ""
PINNED_REPOSITORY = "seeker71/Coherence-Network"
PINNED_REPOSITORY_ID = "1155981916"
PINNED_REPOSITORY_OWNER = "seeker71"
PINNED_REPOSITORY_OWNER_ID = "743114"
PINNED_REF = "refs/heads/main"
PINNED_ENVIRONMENT = "Production"
PINNED_CALLER_WORKFLOW = ".github/workflows/hostinger-auto-deploy.yml"
PINNED_OBSERVER_WORKFLOW = ".github/workflows/public-deployment-observer.yml"
REPRODUCIBLE_BUILDER_IMAGE = (
    "docker.io/library/rust:1.86-slim-bookworm@"
    "sha256:57d415bbd61ce11e2d5f73de068103c7bd9f3188dc132c97cef4a8f62989e944"
)
_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_JWKS = GitHubJWKS()


class DeploymentObserverError(ValueError):
    """The observer identity, challenge, or response failed closed."""


class DeploymentObserverChallengeORM(Base):
    __tablename__ = "deployment_observer_challenges"

    challenge_id = Column(String(36), primary_key=True)
    schema = Column(String(64), nullable=False)
    target_sha = Column(String(40), nullable=False, index=True)
    nonce_sha256 = Column(String(64), nullable=False, unique=True)
    issued_jti = Column(String(512), nullable=False, unique=True)
    issued_claims_sha256 = Column(String(64), nullable=False)
    issued_epoch = Column(Integer, nullable=False)
    expires_epoch = Column(Integer, nullable=False, index=True)
    run_id = Column(String(64), nullable=False)
    run_attempt = Column(String(32), nullable=False)
    actor_id = Column(String(64), nullable=False)
    workflow_sha = Column(String(40), nullable=False)
    job_workflow_sha = Column(String(40), nullable=False)
    consumed_epoch = Column(Integer, nullable=True)
    observation_jti = Column(String(512), nullable=True, unique=True)
    observation_claims_sha256 = Column(String(64), nullable=True)
    commitment_sha256 = Column(String(64), nullable=True)
    public_body_sha256 = Column(String(64), nullable=True)
    loopback_body_sha256 = Column(String(64), nullable=True)
    direct_probe_body_sha256 = Column(String(64), nullable=True)
    stable_projection_sha256 = Column(String(64), nullable=True)
    container_id = Column(String(64), nullable=True)
    image_id = Column(String(71), nullable=True)
    form_source_commit = Column(String(40), nullable=True)
    witness_node_id = Column(String(64), nullable=True)


class DeploymentObserverTokenUseORM(Base):
    __tablename__ = "deployment_observer_token_uses"

    jti = Column(String(512), primary_key=True)
    phase = Column(String(32), nullable=False)
    challenge_id = Column(String(36), nullable=False, index=True)
    target_sha = Column(String(40), nullable=False)
    claims_sha256 = Column(String(64), nullable=False)
    used_epoch = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("jti", name="uq_deployment_observer_token_jti"),
    )


def observer_enabled() -> bool:
    return bool(PINNED_OBSERVER_WORKFLOW_SHA) and config_loader.get_bool(
        "deployment_observer", "enabled", False
    )


def observer_policy() -> ObserverOIDCPolicy:
    if not observer_enabled():
        raise DeploymentObserverError("observer-disabled")
    return ObserverOIDCPolicy(
        repository=PINNED_REPOSITORY,
        repository_id=PINNED_REPOSITORY_ID,
        repository_owner=PINNED_REPOSITORY_OWNER,
        repository_owner_id=PINNED_REPOSITORY_OWNER_ID,
        ref=PINNED_REF,
        environment=PINNED_ENVIRONMENT,
        caller_workflow_path=PINNED_CALLER_WORKFLOW,
        observer_workflow_path=PINNED_OBSERVER_WORKFLOW,
        observer_workflow_sha=PINNED_OBSERVER_WORKFLOW_SHA,
        max_token_age_seconds=300,
        clock_skew_seconds=30,
    )


def observer_policy_sha256(policy: ObserverOIDCPolicy) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            {
                "repository": policy.repository,
                "repository_id": policy.repository_id,
                "repository_owner": policy.repository_owner,
                "repository_owner_id": policy.repository_owner_id,
                "ref": policy.ref,
                "environment": policy.environment,
                "caller_workflow_ref": policy.caller_workflow_ref,
                "observer_workflow_ref": policy.observer_workflow_ref,
                "event_names": list(policy.event_names),
                "max_token_age_seconds": policy.max_token_age_seconds,
                "clock_skew_seconds": policy.clock_skew_seconds,
            }
        )
    ).hexdigest()


def current_deployed_sha() -> str:
    value = str(get_config().get("deployed_sha") or "").strip().lower()
    if not _FULL_SHA_RE.fullmatch(value):
        raise DeploymentObserverError("current-deployed-sha-unavailable")
    return value


def nonce_sha256(nonce: str) -> str:
    if not isinstance(nonce, str) or not _NONCE_RE.fullmatch(nonce):
        raise DeploymentObserverError("observer-nonce")
    return hashlib.sha256(nonce.encode("ascii")).hexdigest()


def carrier_challenge_input_sha256(nonce: str) -> str:
    nonce_sha256(nonce)
    return hashlib.sha256(
        b"coherence-deployment-observer-v1\0" + nonce.encode("ascii")
    ).hexdigest()


def rust_challenge_expected(challenge_input: str) -> str:
    if not _HEX64_RE.fullmatch(challenge_input):
        raise DeploymentObserverError("carrier-challenge-input")
    first, second, third, fourth = (
        int(challenge_input[offset : offset + 4], 16)
        for offset in range(0, 16, 4)
    )
    return str((((first * 17 + second) * 19 + third) * 23) + fourth)


def rust_challenge_expression(challenge_input: str) -> str:
    if not _HEX64_RE.fullmatch(challenge_input):
        raise DeploymentObserverError("carrier-challenge-input")
    first, second, third, fourth = (
        int(challenge_input[offset : offset + 4], 16)
        for offset in range(0, 16, 4)
    )
    return (
        "(add (mul (add (mul (add (mul "
        f"{first} 17) {second}) 19) {third}) 23) {fourth})"
    )


def form_cli_challenge_expected(challenge_input: str) -> str:
    if not _HEX64_RE.fullmatch(challenge_input):
        raise DeploymentObserverError("carrier-challenge-input")
    return hashlib.sha256(
        b"form-cli-carrier-challenge-v1\n" + challenge_input.encode("ascii")
    ).hexdigest()


def health_url(nonce: str, *, base: str = PUBLIC_API_BASE) -> str:
    nonce_sha256(nonce)
    if base != PUBLIC_API_BASE:
        raise DeploymentObserverError("observer-public-base")
    return f"{base}/api/health?observation_nonce={quote(nonce, safe='')}"


def _loads_unique_json(raw: bytes) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not 2 <= len(raw) <= 131072:
        raise DeploymentObserverError("observer-health-body-size")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise DeploymentObserverError("observer-health-duplicate-key")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeploymentObserverError("observer-health-json") from exc
    if not isinstance(value, dict):
        raise DeploymentObserverError("observer-health-object")
    return value


def _hex_field(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _HEX64_RE.fullmatch(value):
        raise DeploymentObserverError(f"observer-health-{label}")
    return value


def stable_health_projection(
    raw: bytes,
    *,
    nonce: str,
    target_sha: str,
) -> dict[str, Any]:
    """Validate and select the externally reproducible native health facts."""
    body = _loads_unique_json(raw)
    nonce_digest = nonce_sha256(nonce)
    challenge_input = carrier_challenge_input_sha256(nonce)
    if body.get("observation_schema") != HEALTH_SCHEMA:
        raise DeploymentObserverError("observer-health-schema")
    if body.get("deployed_sha") != target_sha:
        raise DeploymentObserverError("observer-health-target-sha")
    if body.get("observation_nonce_sha256") != nonce_digest:
        raise DeploymentObserverError("observer-health-nonce-binding")
    if body.get("status") != "ok":
        raise DeploymentObserverError("observer-health-status")
    if body.get("integrity_verified") is not True:
        raise DeploymentObserverError("observer-health-integrity")
    if body.get("integrity_compromised") is not False:
        raise DeploymentObserverError("observer-health-integrity")
    if body.get("schema_ok") is not True:
        raise DeploymentObserverError("observer-health-db-schema")
    kernel = body.get("kernel_challenge")
    form_cli = body.get("form_cli_challenge")
    if not isinstance(kernel, dict) or not isinstance(form_cli, dict):
        raise DeploymentObserverError("observer-health-carriers")
    runtime = kernel.get("runtime")
    if runtime not in {"inline", "subprocess"} or body.get("kernel_runtime") != runtime:
        raise DeploymentObserverError("observer-health-kernel-runtime")
    if kernel.get("input_sha256") != challenge_input:
        raise DeploymentObserverError("observer-health-kernel-input")
    kernel_result = str(kernel.get("result") or "")
    if kernel_result != rust_challenge_expected(challenge_input):
        raise DeploymentObserverError("observer-health-kernel-result")
    if kernel.get("verified") is not True:
        raise DeploymentObserverError("observer-health-kernel-verification")
    if form_cli.get("input_sha256") != challenge_input:
        raise DeploymentObserverError("observer-health-form-cli-input")
    form_result = str(form_cli.get("result") or "")
    if form_result != form_cli_challenge_expected(challenge_input):
        raise DeploymentObserverError("observer-health-form-cli-result")
    if form_cli.get("verified") is not True or form_cli.get("protocol") != "form-cli-v2":
        raise DeploymentObserverError("observer-health-form-cli-verification")
    projection = {
        "schema": HEALTH_SCHEMA,
        "deployed_sha": target_sha,
        "observation_nonce_sha256": nonce_digest,
        "carrier_challenge_input_sha256": challenge_input,
        "status": "ok",
        "integrity_verified": True,
        "integrity_compromised": False,
        "schema_ok": True,
        "kernel_runtime": runtime,
        "kernel_result": kernel_result,
        "kernel_binary_sha256": _hex_field(
            kernel.get("binary_sha256"), "kernel-binary-sha256"
        ),
        "form_cli_result": form_result,
        "form_cli_protocol": "form-cli-v2",
        "form_cli_binary_sha256": _hex_field(
            form_cli.get("binary_sha256"), "form-cli-binary-sha256"
        ),
        "form_cli_wrapper_sha256": _hex_field(
            form_cli.get("wrapper_sha256"), "form-cli-wrapper-sha256"
        ),
        "form_cli_source_sha256": _hex_field(
            form_cli.get("source_sha256"), "form-cli-source-sha256"
        ),
        "form_cli_table_sha256": _hex_field(
            form_cli.get("table_sha256"), "form-cli-table-sha256"
        ),
        "form_cli_stamp_sha256": _hex_field(
            form_cli.get("stamp_sha256"), "form-cli-stamp-sha256"
        ),
    }
    return projection


def validate_direct_probe(
    raw: bytes,
    *,
    challenge_input: str,
    target_sha: str,
    public_projection: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the pinned observer's direct Docker-host carrier execution."""
    body = _loads_unique_json(raw)
    required = {
        "schema": DIRECT_PROBE_SCHEMA,
        "target_sha": target_sha,
        "api_build_context_sha": target_sha,
        "image_revision": target_sha,
        "challenge_input_sha256": challenge_input,
        "kernel_result": rust_challenge_expected(challenge_input),
        "form_cli_result": form_cli_challenge_expected(challenge_input),
        "form_cli_protocol": "form-cli-v2",
        "reproducible_builder_image": REPRODUCIBLE_BUILDER_IMAGE,
    }
    for name, expected in required.items():
        if body.get(name) != expected:
            raise DeploymentObserverError(f"observer-direct-{name}")
    container_id = str(body.get("container_id") or "")
    image_id = str(body.get("image_id") or "")
    if not _HEX64_RE.fullmatch(container_id):
        raise DeploymentObserverError("observer-direct-container-id")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise DeploymentObserverError("observer-direct-image-id")
    form_source_commit = str(body.get("form_source_commit") or "")
    if not _FULL_SHA_RE.fullmatch(form_source_commit):
        raise DeploymentObserverError("observer-direct-form-source-commit")
    if body.get("image_form_revision") != form_source_commit:
        raise DeploymentObserverError("observer-direct-form-image-revision")
    digest_fields = (
        "kernel_binary_sha256",
        "form_cli_binary_sha256",
        "form_cli_wrapper_sha256",
        "form_cli_source_sha256",
        "form_cli_table_sha256",
        "form_cli_stamp_sha256",
    )
    for field in digest_fields:
        value = _hex_field(body.get(field), f"direct-{field}")
        if value != public_projection.get(field):
            raise DeploymentObserverError(f"observer-direct-{field}-mismatch")
    reproduced = {
        "kernel_binary_sha256": _hex_field(
            body.get("reproduced_kernel_binary_sha256"),
            "reproduced-kernel-binary-sha256",
        ),
        "form_cli_binary_sha256": _hex_field(
            body.get("reproduced_form_cli_binary_sha256"),
            "reproduced-form-cli-binary-sha256",
        ),
        "form_cli_wrapper_sha256": _hex_field(
            body.get("source_wrapper_sha256"), "source-wrapper-sha256"
        ),
        "form_cli_source_sha256": _hex_field(
            body.get("source_form_cli_source_sha256"),
            "source-form-cli-source-sha256",
        ),
        "form_cli_table_sha256": _hex_field(
            body.get("source_form_cli_table_sha256"),
            "source-form-cli-table-sha256",
        ),
        "form_cli_stamp_sha256": _hex_field(
            body.get("source_form_cli_stamp_sha256"),
            "source-form-cli-stamp-sha256",
        ),
    }
    for field, expected in reproduced.items():
        if expected != body.get(field):
            raise DeploymentObserverError(f"observer-direct-reproducible-{field}")
    return {
        **required,
        "container_id": container_id,
        "image_id": image_id,
        "form_source_commit": form_source_commit,
        "image_form_revision": form_source_commit,
        "reproducible_builder_image": REPRODUCIBLE_BUILDER_IMAGE,
        **{
            "reproduced_kernel_binary_sha256": reproduced[
                "kernel_binary_sha256"
            ],
            "reproduced_form_cli_binary_sha256": reproduced[
                "form_cli_binary_sha256"
            ],
            "source_wrapper_sha256": reproduced["form_cli_wrapper_sha256"],
            "source_form_cli_source_sha256": reproduced[
                "form_cli_source_sha256"
            ],
            "source_form_cli_table_sha256": reproduced[
                "form_cli_table_sha256"
            ],
            "source_form_cli_stamp_sha256": reproduced[
                "form_cli_stamp_sha256"
            ],
        },
        **{field: body[field] for field in digest_fields},
    }


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def projection_sha256(projection: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(projection)).hexdigest()


def observation_commitment(
    *,
    challenge: DeploymentObserverChallengeORM,
    public_url: str,
    expected_public_url: str,
    status_code: int,
    content_type: str,
    public_body_sha256: str,
    stable_sha256: str,
    direct_probe_body_sha256: str,
    container_id: str,
    image_id: str,
    form_source_commit: str,
) -> tuple[dict[str, Any], str]:
    if public_url != expected_public_url:
        raise DeploymentObserverError("observer-effective-url")
    if status_code != 200:
        raise DeploymentObserverError("observer-http-status")
    if content_type.strip().lower() != "application/json":
        raise DeploymentObserverError("observer-content-type")
    if (
        not _HEX64_RE.fullmatch(public_body_sha256)
        or not _HEX64_RE.fullmatch(stable_sha256)
        or not _HEX64_RE.fullmatch(direct_probe_body_sha256)
        or not _HEX64_RE.fullmatch(container_id)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id)
        or not _FULL_SHA_RE.fullmatch(form_source_commit)
    ):
        raise DeploymentObserverError("observer-commitment-hash")
    payload = {
        "schema": COMMITMENT_SCHEMA,
        "challenge_id": challenge.challenge_id,
        "nonce_sha256": challenge.nonce_sha256,
        "target_sha": challenge.target_sha,
        "method": "GET",
        "effective_url": public_url,
        "status_code": status_code,
        "content_type": "application/json",
        "public_body_sha256": public_body_sha256,
        "stable_projection_sha256": stable_sha256,
        "direct_probe_body_sha256": direct_probe_body_sha256,
        "container_id": container_id,
        "image_id": image_id,
        "form_source_commit": form_source_commit,
        "issued_claims_sha256": challenge.issued_claims_sha256,
        "run_id": challenge.run_id,
        "run_attempt": challenge.run_attempt,
        "actor_id": challenge.actor_id,
        "workflow_sha": challenge.workflow_sha,
        "job_workflow_sha": challenge.job_workflow_sha,
        "observer_policy_sha256": observer_policy_sha256(observer_policy()),
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return payload, digest


def issue_challenge(
    session: Session,
    *,
    target_sha: str,
    oidc_token: str,
    now_epoch: int | None = None,
    jwks: GitHubJWKS = _JWKS,
) -> dict[str, Any]:
    now = int(time.time()) if now_epoch is None else int(now_epoch)
    target = target_sha.strip().lower()
    if target != current_deployed_sha():
        raise DeploymentObserverError("observer-target-not-current")
    policy = observer_policy()
    try:
        identity = jwks.verify(
            oidc_token,
            audience=challenge_audience(target),
            target_sha=target,
            policy=policy,
            now_epoch=now,
        )
    except ObserverOIDCError as exc:
        raise DeploymentObserverError(str(exc)) from exc
    ttl = config_loader.get_int("deployment_observer", "challenge_ttl_seconds", 300)
    if not 60 <= ttl <= 600:
        raise DeploymentObserverError("observer-challenge-ttl")
    nonce = base64_nonce()
    challenge_id = str(uuid4())
    row = DeploymentObserverChallengeORM(
        challenge_id=challenge_id,
        schema=SCHEMA,
        target_sha=target,
        nonce_sha256=nonce_sha256(nonce),
        issued_jti=identity.jti,
        issued_claims_sha256=identity.claims_sha256,
        issued_epoch=now,
        expires_epoch=now + ttl,
        run_id=identity.run_id,
        run_attempt=identity.run_attempt,
        actor_id=identity.actor_id,
        workflow_sha=identity.workflow_sha,
        job_workflow_sha=identity.job_workflow_sha,
    )
    session.add(
        DeploymentObserverTokenUseORM(
            jti=identity.jti,
            phase="challenge",
            challenge_id=challenge_id,
            target_sha=target,
            claims_sha256=identity.claims_sha256,
            used_epoch=now,
        )
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise DeploymentObserverError("observer-challenge-token-replay") from exc
    return {
        "schema": SCHEMA,
        "challenge_id": challenge_id,
        "nonce": nonce,
        "nonce_sha256": row.nonce_sha256,
        "target_sha": target,
        "health_url": health_url(nonce),
        "issued_claims_sha256": identity.claims_sha256,
        "run_id": identity.run_id,
        "run_attempt": identity.run_attempt,
        "actor_id": identity.actor_id,
        "workflow_sha": identity.workflow_sha,
        "job_workflow_sha": identity.job_workflow_sha,
        "observer_policy_sha256": observer_policy_sha256(policy),
        "expires_epoch": row.expires_epoch,
    }


def base64_nonce() -> str:
    nonce = secrets.token_urlsafe(32)
    if not _NONCE_RE.fullmatch(nonce):  # pragma: no cover - token_urlsafe contract
        raise DeploymentObserverError("observer-nonce-generation")
    return nonce


def active_challenge_for_nonce(
    session: Session,
    *,
    nonce: str,
    now_epoch: int | None = None,
) -> DeploymentObserverChallengeORM:
    now = int(time.time()) if now_epoch is None else int(now_epoch)
    digest = nonce_sha256(nonce)
    row = (
        session.query(DeploymentObserverChallengeORM)
        .filter_by(nonce_sha256=digest)
        .one_or_none()
    )
    if row is None or row.schema != SCHEMA:
        raise DeploymentObserverError("observer-challenge-unresolved")
    if row.expires_epoch < now or row.issued_epoch > now + 30:
        raise DeploymentObserverError("observer-challenge-expired")
    if row.consumed_epoch is not None:
        raise DeploymentObserverError("observer-challenge-consumed")
    if row.target_sha != current_deployed_sha():
        raise DeploymentObserverError("observer-challenge-stale-deploy")
    return row


def consume_observation(
    session: Session,
    *,
    challenge_id: str,
    nonce: str,
    public_url: str,
    status_code: int,
    content_type: str,
    public_body: bytes,
    loopback_body: bytes,
    direct_probe_body: bytes,
    oidc_token: str,
    now_epoch: int | None = None,
    jwks: GitHubJWKS = _JWKS,
) -> dict[str, Any]:
    """Verify both vantages and consume the one-time OIDC challenge atomically."""
    now = int(time.time()) if now_epoch is None else int(now_epoch)
    row = session.get(DeploymentObserverChallengeORM, challenge_id)
    if row is None or row.nonce_sha256 != nonce_sha256(nonce):
        raise DeploymentObserverError("observer-challenge-unresolved")
    active_challenge_for_nonce(session, nonce=nonce, now_epoch=now)
    public_projection = stable_health_projection(
        public_body, nonce=nonce, target_sha=row.target_sha
    )
    loopback_projection = stable_health_projection(
        loopback_body, nonce=nonce, target_sha=row.target_sha
    )
    if canonical_json_bytes(public_projection) != canonical_json_bytes(loopback_projection):
        raise DeploymentObserverError("observer-vantage-mismatch")
    public_hash = hashlib.sha256(public_body).hexdigest()
    loopback_hash = hashlib.sha256(loopback_body).hexdigest()
    stable_hash = projection_sha256(public_projection)
    direct_probe = validate_direct_probe(
        direct_probe_body,
        challenge_input=str(public_projection["carrier_challenge_input_sha256"]),
        target_sha=row.target_sha,
        public_projection=public_projection,
    )
    direct_probe_hash = hashlib.sha256(direct_probe_body).hexdigest()
    commitment, commitment_hash = observation_commitment(
        challenge=row,
        public_url=public_url,
        expected_public_url=health_url(nonce),
        status_code=status_code,
        content_type=content_type,
        public_body_sha256=public_hash,
        stable_sha256=stable_hash,
        direct_probe_body_sha256=direct_probe_hash,
        container_id=str(direct_probe["container_id"]),
        image_id=str(direct_probe["image_id"]),
        form_source_commit=str(direct_probe["form_source_commit"]),
    )
    policy = observer_policy()
    try:
        identity = jwks.verify(
            oidc_token,
            audience=observation_audience(commitment_hash),
            target_sha=row.target_sha,
            policy=policy,
            now_epoch=now,
        )
    except ObserverOIDCError as exc:
        raise DeploymentObserverError(str(exc)) from exc
    if (
        identity.run_id != row.run_id
        or identity.run_attempt != row.run_attempt
        or identity.actor_id != row.actor_id
        or identity.jti == row.issued_jti
    ):
        raise DeploymentObserverError("observer-run-identity-mismatch")
    session.add(
        DeploymentObserverTokenUseORM(
            jti=identity.jti,
            phase="observation",
            challenge_id=row.challenge_id,
            target_sha=row.target_sha,
            claims_sha256=identity.claims_sha256,
            used_epoch=now,
        )
    )
    updated = session.execute(
        update(DeploymentObserverChallengeORM)
        .where(
            DeploymentObserverChallengeORM.challenge_id == row.challenge_id,
            DeploymentObserverChallengeORM.consumed_epoch.is_(None),
            DeploymentObserverChallengeORM.expires_epoch >= now,
        )
        .values(
            consumed_epoch=now,
            observation_jti=identity.jti,
            observation_claims_sha256=identity.claims_sha256,
            commitment_sha256=commitment_hash,
            public_body_sha256=public_hash,
            loopback_body_sha256=loopback_hash,
            direct_probe_body_sha256=direct_probe_hash,
            stable_projection_sha256=stable_hash,
            container_id=str(direct_probe["container_id"]),
            image_id=str(direct_probe["image_id"]),
            form_source_commit=str(direct_probe["form_source_commit"]),
        )
    )
    try:
        session.flush()
    except IntegrityError as exc:
        raise DeploymentObserverError("observer-observation-token-replay") from exc
    if updated.rowcount != 1:
        raise DeploymentObserverError("observer-challenge-race")
    return {
        "challenge": row,
        "nonce": nonce,
        "direct_probe_body": bytes(direct_probe_body),
        "identity": asdict(identity),
        "commitment": commitment,
        "commitment_sha256": commitment_hash,
        "public_body_sha256": public_hash,
        "loopback_body_sha256": loopback_hash,
        "direct_probe_body_sha256": direct_probe_hash,
        "direct_probe": direct_probe,
        "stable_projection": public_projection,
        "stable_projection_sha256": stable_hash,
    }


def bind_witness(
    session: Session,
    *,
    challenge_id: str,
    witness_node_id: str,
) -> None:
    row = session.get(DeploymentObserverChallengeORM, challenge_id)
    if row is None or row.consumed_epoch is None:
        raise DeploymentObserverError("observer-challenge-not-consumed")
    if row.witness_node_id is not None:
        raise DeploymentObserverError("observer-witness-already-bound")
    row.witness_node_id = witness_node_id
    session.flush()
