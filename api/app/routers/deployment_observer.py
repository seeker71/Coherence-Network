"""GitHub-OIDC-authenticated public deployment observation endpoints."""
from __future__ import annotations

import base64
import binascii
from typing import Annotated
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services import unified_db
from app.services.deployment_observer_service import (
    DeploymentObserverError,
    active_challenge_for_nonce,
    consume_observation,
    issue_challenge,
)


router = APIRouter()
_LOOPBACK_BASE = "http://127.0.0.1:8000"


class ChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_sha: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]


class ObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: Annotated[str, Field(pattern=r"^[0-9a-f-]{36}$")]
    nonce: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{43}$")]
    public_url: Annotated[str, Field(min_length=1, max_length=2048)]
    status_code: Annotated[int, Field(ge=100, le=599)]
    content_type: Annotated[str, Field(min_length=1, max_length=256)]
    public_body_base64: Annotated[str, Field(min_length=4, max_length=180000)]
    direct_probe_body_base64: Annotated[
        str, Field(min_length=4, max_length=180000)
    ]


def _bearer(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="observer OIDC bearer required")
    token = authorization.removeprefix("Bearer ")
    if not token or " " in token or len(token) > 32768:
        raise HTTPException(status_code=401, detail="observer OIDC bearer invalid")
    return token


def _decode_body(encoded: str) -> bytes:
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="public body base64 invalid") from exc
    if not 2 <= len(raw) <= 131072:
        raise HTTPException(status_code=422, detail="public body size invalid")
    return raw


def _observer_http_error(exc: Exception) -> HTTPException:
    message = str(exc)
    status = 503 if message in {"observer-disabled", "current-deployed-sha-unavailable"} else 403
    return HTTPException(status_code=status, detail=message)


@router.post("/challenge", summary="Issue a one-time native deployment challenge")
async def create_challenge(
    body: ChallengeRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    try:
        with unified_db.session() as session:
            return issue_challenge(
                session,
                target_sha=body.target_sha,
                oidc_token=_bearer(authorization),
            )
    except DeploymentObserverError as exc:
        raise _observer_http_error(exc) from exc


async def _loopback_health(nonce: str) -> bytes:
    url = f"{_LOOPBACK_BASE}/api/health?observation_nonce={quote(nonce, safe='')}"
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0),
            follow_redirects=False,
            trust_env=False,
            headers={"Accept": "application/json", "Cache-Control": "no-cache"},
        ) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="observer loopback failed") from exc
    if response.status_code != 200 or str(response.url) != url:
        raise HTTPException(status_code=503, detail="observer loopback status invalid")
    if response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(status_code=503, detail="observer loopback content type invalid")
    if not 2 <= len(response.content) <= 131072:
        raise HTTPException(status_code=503, detail="observer loopback body size invalid")
    return response.content


@router.post("/observation", summary="Consume a challenge and persist its WITNESS")
async def record_observation(
    body: ObservationRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    public_body = _decode_body(body.public_body_base64)
    direct_probe_body = _decode_body(body.direct_probe_body_base64)
    try:
        # Reject unresolved/expired/consumed nonces before making any network call.
        with unified_db.session() as session:
            active_challenge_for_nonce(session, nonce=body.nonce)
    except DeploymentObserverError as exc:
        raise _observer_http_error(exc) from exc
    loopback_body = await _loopback_health(body.nonce)
    try:
        with unified_db.session() as session:
            observation = consume_observation(
                session,
                challenge_id=body.challenge_id,
                nonce=body.nonce,
                public_url=body.public_url,
                status_code=body.status_code,
                content_type=body.content_type,
                public_body=public_body,
                loopback_body=loopback_body,
                direct_probe_body=direct_probe_body,
                oidc_token=_bearer(authorization),
            )
            # Imported here so disabled observer endpoints do not couple ordinary
            # API startup to the substrate WITNESS implementation.
            from app.services.deployment_observation import (
                record_authenticated_deployment_observation,
            )

            witness = record_authenticated_deployment_observation(
                session,
                observation=observation,
                host_health=public_body,
                recorder_health=loopback_body,
                host_health_status=body.status_code,
                recorder_health_status=200,
                health_route="/api/health",
            )
    except (DeploymentObserverError, ValueError) as exc:
        raise _observer_http_error(exc) from exc

    # The WITNESS is committed before index publication.  A heal failure leaves
    # no false OBSERVED answer; the deploy job remains red and a retry can heal.
    try:
        from scripts.form_cli_rag import INDEX, heal

        heal(INDEX, verbose=False)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="observer witness index heal failed") from exc
    return {
        "schema": "authenticated-deployment-observation-v1",
        "challenge_id": body.challenge_id,
        "target_sha": observation["challenge"].target_sha,
        "commitment_sha256": observation["commitment_sha256"],
        "stable_projection_sha256": observation["stable_projection_sha256"],
        "witness_node_id": witness["node_id"],
        "witness_content_node_id": witness["content_node_id"],
        "observed": True,
    }
