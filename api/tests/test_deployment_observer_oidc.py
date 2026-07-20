from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import time

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.services.deployment_observer_oidc import (
    ISSUER,
    ObserverOIDCError,
    ObserverOIDCPolicy,
    VerifiedObserverIdentity,
    challenge_audience,
    observation_audience,
    verify_observer_token,
)
from app.services.deployment_observer_service import (
    DeploymentObserverChallengeORM,
    DeploymentObserverError,
    DeploymentObserverTokenUseORM,
    HEALTH_SCHEMA,
    REPRODUCIBLE_BUILDER_IMAGE,
    carrier_challenge_input_sha256,
    consume_observation,
    form_cli_challenge_expected,
    health_url,
    issue_challenge,
    nonce_sha256,
    fkwu_challenge_expected,
    stable_health_projection,
)
from app.services import deployment_observer_service
from app.services.deployment_observation import (
    DeploymentObservationError,
    record_authenticated_deployment_observation,
    record_deployment_observation,
    verify_deployment_observation,
)
from app.services.unified_db import Base


TARGET = "a" * 40
OBSERVER_SHA = "b" * 40
REPO_ROOT = Path(__file__).resolve().parents[2]


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@pytest.fixture
def policy() -> ObserverOIDCPolicy:
    return ObserverOIDCPolicy(
        repository="seeker71/Coherence-Network",
        repository_id="1155981916",
        repository_owner="seeker71",
        repository_owner_id="743114",
        ref="refs/heads/main",
        environment="Production",
        caller_workflow_path=".github/workflows/hostinger-auto-deploy.yml",
        observer_workflow_path=".github/workflows/public-deployment-observer.yml",
        observer_workflow_sha=OBSERVER_SHA,
    )


@pytest.fixture
def signing_key() -> tuple[rsa.RSAPrivateKey, dict]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": "test-key",
        "n": _b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
        "e": _b64(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
    }
    return private, {"keys": [jwk]}


def _claims(policy: ObserverOIDCPolicy, audience: str, *, now: int = 1000) -> dict:
    return {
        "iss": ISSUER,
        "aud": audience,
        "sub": policy.subject,
        "repository": policy.repository,
        "repository_id": policy.repository_id,
        "repository_owner": policy.repository_owner,
        "repository_owner_id": policy.repository_owner_id,
        "ref": policy.ref,
        "ref_type": "branch",
        "ref_protected": "true",
        "environment": policy.environment,
        "event_name": "push",
        "runner_environment": "github-hosted",
        "workflow_ref": policy.caller_workflow_ref,
        "workflow_sha": TARGET,
        "sha": TARGET,
        "job_workflow_ref": policy.observer_workflow_ref,
        "job_workflow_sha": policy.observer_workflow_sha,
        "jti": "test-jti-12345678",
        "run_id": "12345",
        "run_attempt": "1",
        "actor_id": "743114",
        "iat": now - 5,
        "nbf": now - 5,
        "exp": now + 300,
    }


def _token(private: rsa.RSAPrivateKey, claims: dict, *, header: dict | None = None) -> str:
    protected = header or {"alg": "RS256", "typ": "JWT", "kid": "test-key"}
    head = _b64(json.dumps(protected, separators=(",", ":")).encode())
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = private.sign(
        f"{head}.{body}".encode("ascii"), padding.PKCS1v15(), hashes.SHA256()
    )
    return f"{head}.{body}.{_b64(signature)}"


def test_runtime_policy_pin_matches_the_reusable_workflow_call() -> None:
    workflow = (REPO_ROOT / ".github/workflows/hostinger-auto-deploy.yml").read_text(
        encoding="utf-8"
    )
    expected = (
        "uses: seeker71/Coherence-Network/"
        ".github/workflows/public-deployment-observer.yml@"
        f"{deployment_observer_service.PINNED_OBSERVER_WORKFLOW_SHA}"
    )
    assert expected in workflow
    assert len(deployment_observer_service.PINNED_OBSERVER_WORKFLOW_SHA) == 40


def test_manual_deploy_cannot_issue_a_witness_for_the_wrong_sha() -> None:
    workflow = (REPO_ROOT / ".github/workflows/hostinger-auto-deploy.yml").read_text(
        encoding="utf-8"
    )
    observer_job = workflow.split("  observe-public-deployment:\n", 1)[1]
    assert "if: github.event_name == 'push' || github.event_name == 'schedule'" in (
        observer_job
    )
    assert "workflow_dispatch" not in observer_job.split("    uses:", 1)[0]


def test_oidc_accepts_only_the_fully_pinned_reusable_workflow_identity(
    policy: ObserverOIDCPolicy,
    signing_key: tuple[rsa.RSAPrivateKey, dict],
) -> None:
    private, jwks = signing_key
    audience = challenge_audience(TARGET)
    identity = verify_observer_token(
        _token(private, _claims(policy, audience)),
        audience=audience,
        target_sha=TARGET,
        policy=policy,
        jwks=jwks,
        now_epoch=1000,
    )
    assert identity.target_sha == TARGET
    assert identity.workflow_sha == TARGET
    assert identity.job_workflow_sha == OBSERVER_SHA
    assert len(identity.claims_sha256) == 64


def test_oidc_accepts_scheduled_full_reobservation(
    policy: ObserverOIDCPolicy,
    signing_key: tuple[rsa.RSAPrivateKey, dict],
) -> None:
    private, jwks = signing_key
    audience = challenge_audience(TARGET)
    claims = _claims(policy, audience)
    claims["event_name"] = "schedule"
    identity = verify_observer_token(
        _token(private, claims),
        audience=audience,
        target_sha=TARGET,
        policy=policy,
        jwks=jwks,
        now_epoch=1000,
    )
    assert identity.target_sha == TARGET


@pytest.mark.parametrize(
    ("claim", "value", "error"),
    [
        ("aud", [challenge_audience(TARGET)], "oidc-claim-aud"),
        ("repository_id", "1", "oidc-claim-repository_id"),
        ("ref_protected", "false", "oidc-claim-ref_protected"),
        ("event_name", "workflow_dispatch", "oidc-claim-event_name"),
        ("runner_environment", "self-hosted", "oidc-claim-runner_environment"),
        ("workflow_sha", "c" * 40, "oidc-claim-workflow_sha"),
        ("job_workflow_sha", "c" * 40, "oidc-claim-job_workflow_sha"),
    ],
)
def test_oidc_rejects_each_unpinned_identity_axis(
    policy: ObserverOIDCPolicy,
    signing_key: tuple[rsa.RSAPrivateKey, dict],
    claim: str,
    value: object,
    error: str,
) -> None:
    private, jwks = signing_key
    audience = challenge_audience(TARGET)
    claims = _claims(policy, audience)
    claims[claim] = value
    with pytest.raises(ObserverOIDCError, match=error):
        verify_observer_token(
            _token(private, claims),
            audience=audience,
            target_sha=TARGET,
            policy=policy,
            jwks=jwks,
            now_epoch=1000,
        )


def test_oidc_rejects_remote_key_header_and_signature_mutation(
    policy: ObserverOIDCPolicy,
    signing_key: tuple[rsa.RSAPrivateKey, dict],
) -> None:
    private, jwks = signing_key
    audience = challenge_audience(TARGET)
    token = _token(private, _claims(policy, audience))
    with pytest.raises(ObserverOIDCError, match="oidc-signature"):
        verify_observer_token(
            token[:-2] + ("AA" if token[-2:] != "AA" else "BB"),
            audience=audience,
            target_sha=TARGET,
            policy=policy,
            jwks=jwks,
            now_epoch=1000,
        )
    header = {"alg": "RS256", "kid": "test-key", "jku": "https://evil.invalid/key"}
    with pytest.raises(ObserverOIDCError, match="oidc-header-remote-key"):
        verify_observer_token(
            _token(private, _claims(policy, audience), header=header),
            audience=audience,
            target_sha=TARGET,
            policy=policy,
            jwks=jwks,
            now_epoch=1000,
        )


def test_observation_audience_is_a_fixed_length_commitment() -> None:
    audience = observation_audience(hashlib.sha256(b"exact-response").hexdigest())
    assert audience.startswith("urn:coherence:deployment-observation:v1:")
    assert len(audience.rsplit(":", 1)[1]) == 43


def _health(nonce: str, *, timestamp: str = "2026-07-15T10:00:00Z") -> bytes:
    challenge_input = carrier_challenge_input_sha256(nonce)
    body = {
        "observation_schema": HEALTH_SCHEMA,
        "observation_nonce_sha256": nonce_sha256(nonce),
        "deployed_sha": TARGET,
        "status": "ok",
        "timestamp": timestamp,
        "integrity_verified": True,
        "integrity_compromised": False,
        "schema_ok": True,
        "kernel_runtime": "fkwu",
        "kernel_challenge": {
            "input_sha256": challenge_input,
            "result": fkwu_challenge_expected(challenge_input),
            "verified": True,
            "runtime": "fkwu",
            "binary_sha256": "1" * 64,
        },
        "form_cli_challenge": {
            "input_sha256": challenge_input,
            "result": form_cli_challenge_expected(challenge_input),
            "verified": True,
            "protocol": "form-cli-v2",
            "binary_sha256": "2" * 64,
            "wrapper_sha256": "6" * 64,
            "source_sha256": "3" * 64,
            "table_sha256": "4" * 64,
            "stamp_sha256": "5" * 64,
        },
    }
    return json.dumps(body, separators=(",", ":")).encode()


def _direct(nonce: str) -> bytes:
    challenge_input = carrier_challenge_input_sha256(nonce)
    return json.dumps(
        {
            "schema": "direct-native-carrier-probe-v1",
            "target_sha": TARGET,
            "api_build_context_sha": TARGET,
            "image_revision": TARGET,
            "form_source_commit": "c" * 40,
            "image_form_revision": "c" * 40,
            "challenge_input_sha256": challenge_input,
            "container_id": "8" * 64,
            "image_id": "sha256:" + "9" * 64,
            "kernel_result": fkwu_challenge_expected(challenge_input),
            "kernel_binary_sha256": "1" * 64,
            "form_cli_result": form_cli_challenge_expected(challenge_input),
            "form_cli_protocol": "form-cli-v2",
            "reproducible_builder_image": REPRODUCIBLE_BUILDER_IMAGE,
            "reproduced_kernel_binary_sha256": "1" * 64,
            "reproduced_form_cli_binary_sha256": "2" * 64,
            "source_wrapper_sha256": "6" * 64,
            "source_form_cli_source_sha256": "3" * 64,
            "source_form_cli_table_sha256": "4" * 64,
            "source_form_cli_stamp_sha256": "5" * 64,
            "form_cli_binary_sha256": "2" * 64,
            "form_cli_wrapper_sha256": "6" * 64,
            "form_cli_source_sha256": "3" * 64,
            "form_cli_table_sha256": "4" * 64,
            "form_cli_stamp_sha256": "5" * 64,
        },
        separators=(",", ":"),
    ).encode()


def test_health_projection_recomputes_both_native_challenges() -> None:
    nonce = _b64(b"n" * 32)
    projection = stable_health_projection(_health(nonce), nonce=nonce, target_sha=TARGET)
    assert projection["kernel_binary_sha256"] == "1" * 64
    assert projection["form_cli_binary_sha256"] == "2" * 64
    forged = json.loads(_health(nonce))
    forged["form_cli_challenge"]["result"] = "0" * 64
    with pytest.raises(DeploymentObserverError, match="form-cli-result"):
        stable_health_projection(
            json.dumps(forged).encode(), nonce=nonce, target_sha=TARGET
        )


class _FakeJWKS:
    def __init__(self) -> None:
        self.calls = 0

    def verify(self, token: str, **kwargs) -> VerifiedObserverIdentity:
        self.calls += 1
        phase = "challenge" if self.calls == 1 else "observation"
        return VerifiedObserverIdentity(
            jti=f"{phase}-jti-12345678",
            target_sha=TARGET,
            issued_at=995,
            expires_at=1300,
            run_id="12345",
            run_attempt="1",
            actor_id="743114",
            workflow_sha=TARGET,
            job_workflow_sha=OBSERVER_SHA,
            claims_sha256=("6" if phase == "challenge" else "7") * 64,
        )


def test_challenge_consumption_is_dual_vantage_and_one_time(
    monkeypatch: pytest.MonkeyPatch,
    policy: ObserverOIDCPolicy,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    DeploymentObserverChallengeORM.__table__.create(engine)
    DeploymentObserverTokenUseORM.__table__.create(engine)
    fake = _FakeJWKS()
    monkeypatch.setattr(
        "app.services.deployment_observer_service.current_deployed_sha",
        lambda: TARGET,
    )
    monkeypatch.setattr(
        "app.services.deployment_observer_service.observer_policy", lambda: policy
    )
    with Session(engine) as session:
        issued = issue_challenge(
            session,
            target_sha=TARGET,
            oidc_token="challenge-token",
            now_epoch=1000,
            jwks=fake,
        )
        public = _health(issued["nonce"], timestamp="external")
        loopback = _health(issued["nonce"], timestamp="loopback")
        result = consume_observation(
            session,
            challenge_id=issued["challenge_id"],
            nonce=issued["nonce"],
            public_url=health_url(issued["nonce"]),
            status_code=200,
            content_type="application/json",
            public_body=public,
            loopback_body=loopback,
            direct_probe_body=_direct(issued["nonce"]),
            oidc_token="observation-token",
            now_epoch=1010,
            jwks=fake,
        )
        assert result["public_body_sha256"] != result["loopback_body_sha256"]
        assert result["stable_projection_sha256"]
        assert session.query(DeploymentObserverTokenUseORM).count() == 2
        with pytest.raises(DeploymentObserverError, match="consumed"):
            consume_observation(
                session,
                challenge_id=issued["challenge_id"],
                nonce=issued["nonce"],
                public_url=health_url(issued["nonce"]),
                status_code=200,
                content_type="application/json",
                public_body=public,
                loopback_body=loopback,
                direct_probe_body=_direct(issued["nonce"]),
                oidc_token="observation-token",
                now_epoch=1011,
                jwks=fake,
            )


def test_authenticated_observation_persists_and_reverifies_the_complete_witness(
    monkeypatch: pytest.MonkeyPatch,
    policy: ObserverOIDCPolicy,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    fake = _FakeJWKS()
    monkeypatch.setattr(
        "app.services.deployment_observer_service.current_deployed_sha",
        lambda: TARGET,
    )
    monkeypatch.setattr(
        "app.services.deployment_observer_service.observer_policy", lambda: policy
    )
    now = int(time.time())
    with Session(engine) as session:
        issued = issue_challenge(
            session,
            target_sha=TARGET,
            oidc_token="challenge-token",
            now_epoch=now,
            jwks=fake,
        )
        public = _health(issued["nonce"], timestamp="external")
        loopback = _health(issued["nonce"], timestamp="loopback")
        consumed = consume_observation(
            session,
            challenge_id=issued["challenge_id"],
            nonce=issued["nonce"],
            public_url=health_url(issued["nonce"]),
            status_code=200,
            content_type="application/json",
            public_body=public,
            loopback_body=loopback,
            direct_probe_body=_direct(issued["nonce"]),
            oidc_token="observation-token",
            now_epoch=now + 1,
            jwks=fake,
        )
        witness = record_authenticated_deployment_observation(
            session,
            observation=consumed,
            host_health=public,
            recorder_health=loopback,
        )
        assert witness["verified"] is True
        assert witness["observer_authentication"] == "github-actions-oidc-v1"
        assert witness["reproduced_kernel_binary_sha256"] == "1" * 64
        assert witness["reproduced_form_cli_binary_sha256"] == "2" * 64

        challenge_input = carrier_challenge_input_sha256(issued["nonce"])
        monkeypatch.setattr(
            "app.services.native_runtime_observation.observe_native_runtime_challenge",
            lambda _challenge: {
                "verified": True,
                "kernel": {
                    "runtime": "fkwu",
                    "binary_sha256": "1" * 64,
                    "result": int(fkwu_challenge_expected(challenge_input)),
                },
                "form_cli": {
                    "binary_sha256": "2" * 64,
                    "wrapper_sha256": "6" * 64,
                    "source_stamp": "3" * 64,
                    "table_sha256": "4" * 64,
                    "stamp_sha256": "5" * 64,
                    "challenge_response_sha256": form_cli_challenge_expected(
                        challenge_input
                    ),
                },
            },
        )
        verified = verify_deployment_observation(
            session,
            witness["node_id"],
            expected_answer_key=witness["answer_key"],
        )
        assert verified["certificate_result"] == "success"

        challenge = session.get(
            DeploymentObserverChallengeORM, issued["challenge_id"]
        )
        assert challenge is not None
        challenge.image_id = "sha256:" + "0" * 64
        session.flush()
        with pytest.raises(
            DeploymentObservationError, match="witness-ledger-field-binding"
        ):
            verify_deployment_observation(
                session, witness["node_id"], require_current=False
            )


def test_retired_unauthenticated_writer_cannot_mint_a_witness() -> None:
    with pytest.raises(
        DeploymentObservationError, match="authenticated-observer-required"
    ):
        record_deployment_observation(
            None,  # type: ignore[arg-type]
            expected_sha=TARGET,
            host_health={},
            recorder_health={},
        )


def test_traefik_routes_public_nonce_health_and_observer_writes_to_api() -> None:
    compose = (
        Path(__file__).resolve().parents[2]
        / "deploy/kernel-router/docker-compose.kernel-router.yml"
    ).read_text(encoding="utf-8")
    native_rule = next(
        line
        for line in compose.splitlines()
        if "coherence-api-kernel-native-first.rule:" in line
    )
    bml_health_rule = next(
        line
        for line in compose.splitlines()
        if "coherence-api-bml-read-core-batch.rule:" in line
    )
    exclusion = "!QueryRegexp(`observation_nonce`,`^[A-Za-z0-9_-]{43}$`)"
    assert exclusion in native_rule
    assert "!PathPrefix(`/api/deployment-observer/`)" in native_rule
    assert f"(Path(`/api/health`) && {exclusion})" in bml_health_rule
