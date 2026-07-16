"""Verify GitHub Actions OIDC identity for the public deployment observer.

This is the independent identity boundary for deployment observation.  The
deploy host cannot mint these tokens: GitHub signs them, and this verifier
accepts only the pinned repository, protected main ref, Production environment,
caller workflow, and immutable reusable-observer workflow commit.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import json
import re
import threading
import time
from typing import Any, Callable, Mapping

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature


ISSUER = "https://token.actions.githubusercontent.com"
JWKS_URL = f"{ISSUER}/.well-known/jwks"
CHALLENGE_AUDIENCE_PREFIX = "urn:coherence:deployment-challenge:v1:"
OBSERVATION_AUDIENCE_PREFIX = "urn:coherence:deployment-observation:v1:"
_B64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_JTI_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,512}$")


class ObserverOIDCError(ValueError):
    """A GitHub token or its pinned identity claims failed closed."""


@dataclass(frozen=True)
class ObserverOIDCPolicy:
    repository: str
    repository_id: str
    repository_owner: str
    repository_owner_id: str
    ref: str
    environment: str
    caller_workflow_path: str
    observer_workflow_path: str
    observer_workflow_sha: str
    event_names: tuple[str, ...] = ("push", "schedule")
    max_token_age_seconds: int = 300
    clock_skew_seconds: int = 30

    def __post_init__(self) -> None:
        if not self.repository or "/" not in self.repository:
            raise ObserverOIDCError("observer-policy-repository")
        if not self.repository_id.isdigit() or not self.repository_owner_id.isdigit():
            raise ObserverOIDCError("observer-policy-numeric-identity")
        if not self.ref.startswith("refs/heads/"):
            raise ObserverOIDCError("observer-policy-ref")
        if not _FULL_SHA_RE.fullmatch(self.observer_workflow_sha):
            raise ObserverOIDCError("observer-policy-workflow-sha")
        if self.event_names != ("push", "schedule"):
            raise ObserverOIDCError("observer-policy-event-names")
        if not 30 <= self.max_token_age_seconds <= 600:
            raise ObserverOIDCError("observer-policy-token-age")
        if not 0 <= self.clock_skew_seconds <= 60:
            raise ObserverOIDCError("observer-policy-clock-skew")

    @property
    def subject(self) -> str:
        return f"repo:{self.repository}:environment:{self.environment}"

    @property
    def caller_workflow_ref(self) -> str:
        return f"{self.repository}/{self.caller_workflow_path}@{self.ref}"

    @property
    def observer_workflow_ref(self) -> str:
        return (
            f"{self.repository}/{self.observer_workflow_path}"
            f"@{self.observer_workflow_sha}"
        )


@dataclass(frozen=True)
class VerifiedObserverIdentity:
    jti: str
    target_sha: str
    issued_at: int
    expires_at: int
    run_id: str
    run_attempt: str
    actor_id: str
    workflow_sha: str
    job_workflow_sha: str
    claims_sha256: str


def challenge_audience(target_sha: str) -> str:
    if not _FULL_SHA_RE.fullmatch(target_sha):
        raise ObserverOIDCError("observer-target-sha")
    return f"{CHALLENGE_AUDIENCE_PREFIX}{target_sha}"


def observation_audience(commitment_sha256: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", commitment_sha256):
        raise ObserverOIDCError("observer-commitment-sha")
    digest = bytes.fromhex(commitment_sha256)
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"{OBSERVATION_AUDIENCE_PREFIX}{encoded}"


def _decode_segment(segment: str, label: str) -> bytes:
    if not segment or len(segment) > 65536 or not _B64URL_RE.fullmatch(segment):
        raise ObserverOIDCError(f"oidc-{label}-encoding")
    try:
        return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except (ValueError, TypeError) as exc:
        raise ObserverOIDCError(f"oidc-{label}-encoding") from exc


def _json_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ObserverOIDCError(f"oidc-{label}-json") from exc
    if not isinstance(value, dict):
        raise ObserverOIDCError(f"oidc-{label}-object")
    return value


def _numeric_claim(claims: Mapping[str, Any], name: str) -> int:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObserverOIDCError(f"oidc-{name}")
    if int(value) != value:
        raise ObserverOIDCError(f"oidc-{name}")
    return int(value)


def _text_claim(claims: Mapping[str, Any], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise ObserverOIDCError(f"oidc-{name}")
    return value


def _select_rsa_key(jwks: Mapping[str, Any], kid: str) -> rsa.RSAPublicKey:
    keys = jwks.get("keys")
    if not isinstance(keys, list) or not 1 <= len(keys) <= 32:
        raise ObserverOIDCError("oidc-jwks-keys")
    matches = [key for key in keys if isinstance(key, dict) and key.get("kid") == kid]
    if len(matches) != 1:
        raise ObserverOIDCError("oidc-jwks-kid")
    key = matches[0]
    if key.get("kty") != "RSA" or key.get("use") not in (None, "sig"):
        raise ObserverOIDCError("oidc-jwk-type")
    if key.get("alg") not in (None, "RS256"):
        raise ObserverOIDCError("oidc-jwk-alg")
    try:
        modulus = int.from_bytes(_decode_segment(str(key["n"]), "jwk-n"), "big")
        exponent = int.from_bytes(_decode_segment(str(key["e"]), "jwk-e"), "big")
        if modulus.bit_length() < 2048 or exponent < 3:
            raise ObserverOIDCError("oidc-jwk-strength")
        return rsa.RSAPublicNumbers(exponent, modulus).public_key()
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ObserverOIDCError):
            raise
        raise ObserverOIDCError("oidc-jwk-material") from exc


def _verified_token_claims(
    token: str, jwks: Mapping[str, Any]
) -> dict[str, Any]:
    if not isinstance(token, str) or not 100 <= len(token) <= 32768:
        raise ObserverOIDCError("oidc-token-size")
    parts = token.split(".")
    if len(parts) != 3:
        raise ObserverOIDCError("oidc-token-shape")
    header = _json_object(_decode_segment(parts[0], "header"), "header")
    claims = _json_object(_decode_segment(parts[1], "claims"), "claims")
    signature = _decode_segment(parts[2], "signature")
    if header.get("alg") != "RS256" or header.get("typ") not in (None, "JWT"):
        raise ObserverOIDCError("oidc-header-alg")
    if "jku" in header or "x5u" in header:
        raise ObserverOIDCError("oidc-header-remote-key")
    kid = header.get("kid")
    if not isinstance(kid, str) or not 1 <= len(kid) <= 256:
        raise ObserverOIDCError("oidc-header-kid")
    public_key = _select_rsa_key(jwks, kid)
    try:
        public_key.verify(
            signature,
            f"{parts[0]}.{parts[1]}".encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature as exc:
        raise ObserverOIDCError("oidc-signature") from exc
    return claims


def _validated_token_times(
    claims: Mapping[str, Any],
    policy: ObserverOIDCPolicy,
    now_epoch: int | None,
) -> tuple[int, int]:
    now = int(time.time()) if now_epoch is None else int(now_epoch)
    issued = _numeric_claim(claims, "iat")
    expires = _numeric_claim(claims, "exp")
    not_before = _numeric_claim(claims, "nbf")
    skew = policy.clock_skew_seconds
    if issued > now + skew or not_before > now + skew:
        raise ObserverOIDCError("oidc-not-yet-valid")
    if expires < now - skew:
        raise ObserverOIDCError("oidc-expired")
    if now - issued > policy.max_token_age_seconds + skew:
        raise ObserverOIDCError("oidc-too-old")
    if expires <= issued or expires - issued > 900:
        raise ObserverOIDCError("oidc-lifetime")
    return issued, expires


def _validated_identity_claims(
    claims: Mapping[str, Any],
    *,
    audience: str,
    target_sha: str,
    policy: ObserverOIDCPolicy,
) -> tuple[str, str, str, str]:
    if not _FULL_SHA_RE.fullmatch(target_sha):
        raise ObserverOIDCError("observer-target-sha")
    exact = {
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
        "runner_environment": "github-hosted",
        "workflow_ref": policy.caller_workflow_ref,
        "workflow_sha": target_sha,
        "sha": target_sha,
        "job_workflow_ref": policy.observer_workflow_ref,
        "job_workflow_sha": policy.observer_workflow_sha,
    }
    for name, expected in exact.items():
        if claims.get(name) != expected:
            raise ObserverOIDCError(f"oidc-claim-{name}")
    if claims.get("event_name") not in policy.event_names:
        raise ObserverOIDCError("oidc-claim-event_name")
    jti = _text_claim(claims, "jti")
    if not _JTI_RE.fullmatch(jti):
        raise ObserverOIDCError("oidc-jti")
    run_id = _text_claim(claims, "run_id")
    run_attempt = _text_claim(claims, "run_attempt")
    actor_id = _text_claim(claims, "actor_id")
    if not run_id.isdigit() or not run_attempt.isdigit() or not actor_id.isdigit():
        raise ObserverOIDCError("oidc-run-identity")
    return jti, run_id, run_attempt, actor_id


def verify_observer_token(
    token: str,
    *,
    audience: str,
    target_sha: str,
    policy: ObserverOIDCPolicy,
    jwks: Mapping[str, Any],
    now_epoch: int | None = None,
) -> VerifiedObserverIdentity:
    """Cryptographically verify a token and every deployment identity pin."""
    claims = _verified_token_claims(token, jwks)
    issued, expires = _validated_token_times(claims, policy, now_epoch)
    jti, run_id, run_attempt, actor_id = _validated_identity_claims(
        claims,
        audience=audience,
        target_sha=target_sha,
        policy=policy,
    )
    canonical_claims = json.dumps(claims, sort_keys=True, separators=(",", ":"))
    return VerifiedObserverIdentity(
        jti=jti,
        target_sha=target_sha,
        issued_at=issued,
        expires_at=expires,
        run_id=run_id,
        run_attempt=run_attempt,
        actor_id=actor_id,
        workflow_sha=_text_claim(claims, "workflow_sha"),
        job_workflow_sha=_text_claim(claims, "job_workflow_sha"),
        claims_sha256=hashlib.sha256(canonical_claims.encode("utf-8")).hexdigest(),
    )


class GitHubJWKS:
    """Small fail-closed cache for GitHub's fixed issuer JWKS endpoint."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 3600,
        fetch: Callable[[], Mapping[str, Any]] | None = None,
    ) -> None:
        if not 60 <= ttl_seconds <= 86400:
            raise ObserverOIDCError("oidc-jwks-cache-ttl")
        self._ttl = ttl_seconds
        self._fetch_override = fetch
        self._lock = threading.Lock()
        self._value: Mapping[str, Any] | None = None
        self._expires = 0.0

    def _fetch(self) -> Mapping[str, Any]:
        if self._fetch_override is not None:
            return self._fetch_override()
        with httpx.Client(
            timeout=httpx.Timeout(5.0),
            follow_redirects=False,
            headers={"Accept": "application/json"},
        ) as client:
            response = client.get(JWKS_URL)
        if response.status_code != 200 or str(response.url) != JWKS_URL:
            raise ObserverOIDCError("oidc-jwks-http")
        if len(response.content) > 262144:
            raise ObserverOIDCError("oidc-jwks-size")
        try:
            value = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise ObserverOIDCError("oidc-jwks-json") from exc
        if not isinstance(value, dict):
            raise ObserverOIDCError("oidc-jwks-object")
        return value

    def get(self, *, force: bool = False) -> Mapping[str, Any]:
        now = time.monotonic()
        with self._lock:
            if not force and self._value is not None and now < self._expires:
                return self._value
            value = self._fetch()
            # Validate the shape before caching attacker-controlled network data.
            keys = value.get("keys")
            if not isinstance(keys, list) or not 1 <= len(keys) <= 32:
                raise ObserverOIDCError("oidc-jwks-keys")
            self._value = value
            self._expires = now + self._ttl
            return value

    def verify(
        self,
        token: str,
        *,
        audience: str,
        target_sha: str,
        policy: ObserverOIDCPolicy,
        now_epoch: int | None = None,
    ) -> VerifiedObserverIdentity:
        try:
            return verify_observer_token(
                token,
                audience=audience,
                target_sha=target_sha,
                policy=policy,
                jwks=self.get(),
                now_epoch=now_epoch,
            )
        except ObserverOIDCError as first:
            # A previously unseen kid can be legitimate rotation.  Refresh once;
            # every other claim/signature failure remains just as strict.
            if str(first) != "oidc-jwks-kid":
                raise
            return verify_observer_token(
                token,
                audience=audience,
                target_sha=target_sha,
                policy=policy,
                jwks=self.get(force=True),
                now_epoch=now_epoch,
            )
