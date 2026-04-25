# MVP External Validator Governance

Independent third-party validators can attest to acceptance claims so external entities can audit and trust the judge result. The system uses Ed25519 signature quorum over a canonical claim payload.

## Config (api/config/mvp_acceptance_policy.json)

Under `trust.public_validator`:

- **keys**: List of validator identities. Each entry:
  - `id` (required): Unique identifier matching attestations (e.g. `org-a-auditor`).
  - `public_key_base64` (required): Ed25519 public key, base64-encoded (32 bytes).
  - `source` (optional): Organisation or origin (e.g. `acme-audit`, `sigstore`). Shown in judge contract for audit.
  - `label` (optional): Human-readable label (e.g. `Acme Corp Auditor`).
- **attestations**: List of submitted attestations. Each entry:
  - `id` or `validator_id`: Must match a configured key `id`.
  - `signature_base64`: Ed25519 signature over the **canonical claim JSON bytes**, base64-encoded.
- **quorum**: Minimum number of valid signatures required (e.g. `2` for 2-of-3).
- **required**: If `true`, judge fails when valid_signatures < quorum.

Example: two independent orgs, require both to attest (quorum 2):

```json
"public_validator": {
  "required": true,
  "quorum": 2,
  "keys": [
    {
      "id": "org-a-auditor",
      "public_key_base64": "<base64-ed25519-public-key-1>",
      "source": "org-a",
      "label": "Org A Audit"
    },
    {
      "id": "org-b-auditor",
      "public_key_base64": "<base64-ed25519-public-key-2>",
      "source": "org-b",
      "label": "Org B Audit"
    }
  ],
  "attestations": [
    { "id": "org-a-auditor", "signature_base64": "<base64-signature-1>" },
    { "id": "org-b-auditor", "signature_base64": "<base64-signature-2>" }
  ]
}
```

## Running as a third-party validator

1. **Generate key pair** (Ed25519): e.g. Python `nacl.signing.SigningKey.generate()`, keep private key secret, publish only the public key (base64 of `verify_key.encode()`).
2. **Register**: Operator adds your public key to `trust.public_validator.keys` with a unique `id` and optional `source`/`label`.
3. **Claim payload**: Same payload the judge uses. Obtain it from the judge response: `GET /api/runtime/mvp/acceptance-judge` returns `contract.claim_payload` (same query params `seconds`/`limit` for the window). Canonical form for signing: JSON with sorted keys, no whitespace between tokens, UTF-8 bytes — i.e. `json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")`. The API hashes these bytes to produce `claim_sha256`.
4. **Sign**: Sign the **bytes** of the canonical JSON (not the hash). Ed25519: `signing_key.sign(claim_bytes)` then take `.signature` and base64-encode.
5. **Submit attestation**: Today, attestations are configured in the same policy file: operator adds `{ "id": "<your-key-id>", "signature_base64": "<base64-signature>" }` to `trust.public_validator.attestations`. A future API could accept attestations via POST so third parties do not need file access.

## Auditing

- **Judge response**: `GET /api/runtime/mvp/acceptance-judge` returns `contract.public_validator` with:
  - `required_quorum`, `configured_validators`, `valid_signatures`, `pass`
  - `claim_sha256`: hash of the canonical claim (for transparency anchoring)
  - `validators`: per-validator `id`, `source`, `label`, `verified`, `reason`
- An external entity can verify that at least `required_quorum` independent validators (by `source`) attested and that the claim_sha256 matches their own computation of the claim payload.

## See also

- Spec 114: MVP Cost and Acceptance Proof
- `api/config/mvp_acceptance_policy.json`
- Judge contract: `contract.implementation_evidence.public_validator_inputs`
