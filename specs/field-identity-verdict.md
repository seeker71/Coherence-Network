---
id: field-identity-verdict
idea_id: federation-and-nodes
status: active
decision: approved-2026-06-23-identity-at-the-edges
source:
  - file: form/form-stdlib/field-identity.fk
    symbols: [fiv-verdict, fiv-accept?, fiv-should-pin?, fiv-impersonation?]
  - file: form/form-stdlib/tests/field-identity-band.fk
  - file: specs/field-relay-always-open-connection.md
  - file: docs/coherence-substrate/channel-interface-consent.form
  - file: form/form-stdlib/sha256.fk
requirements:
  - "A four-way-proven identity-verdict recipe decides trust over crypto RESULTS (signature-ok, NodeID-match, delegation-ok, pin-state) — the decision is Form, the crypto is a carrier, exactly the fr-route pattern"
  - "The verdict distinguishes TRUSTED, FIRST_USE_PIN (TOFU), UNVERIFIED (unsigned, routed-not-trusted), and three rejects: pin-conflict, NodeID-mismatch, bad-delegation"
  - "The relay stays open + content-blind; this verdict runs at the recipient EDGE, never as a relay gate"
  - "NodeID derivation (NodeID = hash of public key) is Form-native-capable via sha256.fk, so a forged NodeID is provably rejectable, not a hand-wave"
done_when:
  - "field-identity-band.fk returns 511 identically on Go, Rust, TS (1 ok, 0 divergent) AND crosses the fourth arm (fkwu) — registered in fourth-arm-bands.txt"
  - "field-identity-band.fk verdict 511 also holds on the native binary lane (validate.sh --binary), bit-identical"
  - "fiv-verdict yields each of the six outcomes for its pinned input combination; fiv-accept?/should-pin?/impersonation? agree with the verdict"
constraints:
  - "The verdict is pure structural logic over booleans/enums — it performs no cryptography itself; sig_ok and deleg_ok are computed by the carrier (ed25519) and fed in"
  - "Identity is an EDGE concern: this never runs on the relay, which stays open and content-blind (field-relay spec, open-relay-consent-only decision)"
  - "TOFU, not a registry: FIRST_USE_PIN accepts + pins on first contact; a later key change for a pinned NodeID surfaces as REJECT_PIN_CONFLICT, never a silent overwrite"
  - "A NodeID IS the hash of its key (content-addressing) — a cell cannot claim a NodeID not derived from the key it signs with; nodeid_match==0 -> REJECT_NODEID_MISMATCH"
---

# Spec: Field identity verdict — who is trusted at the edge (breath 3 keystone)

## Purpose

The field relay is live, open, and content-blind: it routes by a presented NodeID and never polices
who anyone is (`field-relay-always-open-connection`). That leaves the real question — *who is this,
actually?* — to the **edges**, where it belongs. This spec delivers the keystone of that: the
**identity verdict**, the recipe a recipient runs to decide whether a presented sender identity is
trustworthy, impersonating, or merely unverified.

It is the `fr-route` pattern applied to identity: the **decision is Form** (proven four-way + native),
the **cryptography is a carrier**. The carrier computes booleans — does the signature verify (ed25519),
does the claimed NodeID equal the hash of the presented key (sha256), is the signing key delegated by
the person root — and the verdict recipe turns those into one of six outcomes plus the act-on helpers
(`accept?`, `should-pin?`, `impersonation?`). This is the precondition for a *second person*: with it,
the field can finally tell people apart by their keys, with no central registry and no relay gate.

## Requirements

- [x] **R1 — the verdict recipe, four-way + native.** `form/form-stdlib/field-identity.fk` defines
  `fiv-verdict(nodeid_match, sig_ok, deleg_ok, pin_state)` → one of 1 TRUSTED · 2 FIRST_USE_PIN ·
  3 UNVERIFIED · 4 REJECT_PIN_CONFLICT · 5 REJECT_NODEID_MISMATCH · 6 REJECT_DELEGATION, plus
  `fiv-accept?` / `fiv-should-pin?` / `fiv-impersonation?`. Proven 511 four-way + native binary.
- [ ] **R2 — NodeID derivation is Form-native.** Compute NodeID = sha256(pubkey) via `sha256.fk` so
  `nodeid_match` is a proven derivation, not a carrier hand-wave. (Follow-up.)
- [ ] **R3 — ed25519 carrier.** A bootstrap carrier computes `sig_ok` (envelope signature) and
  `deleg_ok` (root→device delegation chain) with a vetted library. (Follow-up, needs crypto deps.)
- [ ] **R4 — TOFU pin store.** Per-recipient pin store yields `pin_state`; a FIRST_USE_PIN verdict
  records the key; a conflict never overwrites. (Follow-up.)
- [ ] **R5 — client integration.** The relay client signs its envelopes and runs `fiv-verdict` on
  receipt; impersonation drops, first-use pins, trusted acts. (Breath 4 follow-up.)

## Files to Create/Modify

- `form/form-stdlib/field-identity.fk` — new: the identity-verdict decision recipe.
- `form/form-stdlib/tests/field-identity-band.fk` — new: four-way + native proof band (511).
- `form/fourth-arm-bands.txt` — modify: register the `field-identity` row.
- `specs/field-identity-verdict.md` — this contract.

## Acceptance Tests

- `cd form && ./validate.sh form-stdlib/field-identity.fk form-stdlib/tests/field-identity-band.fk` → `1 ok, 0 divergent` → 511, fourth arm four-way.
- `cd form && ./validate.sh --binary form-stdlib/field-identity.fk form-stdlib/tests/field-identity-band.fk` → 511, bit-identical.

## Verification

```bash
cd form && ./validate.sh form-stdlib/field-identity.fk form-stdlib/tests/field-identity-band.fk
cd form && ./validate.sh --binary form-stdlib/field-identity.fk form-stdlib/tests/field-identity-band.fk
python3 scripts/validate_spec_quality.py --file specs/field-identity-verdict.md
```

## Risks

- **The verdict is only as good as its inputs.** If the carrier's ed25519 verify is wrong, the verdict
  will TRUST a forgery — the logic can't catch what the crypto miscomputes. Mitigation: the carrier
  uses a vetted library; the seam is a tiny set of booleans, auditable; the verdict logic itself is
  proven four-way + native so it never adds error of its own.
- **NodeID binding must be real.** If `nodeid_match` is computed loosely, REJECT_NODEID_MISMATCH never
  fires and a NodeID is just a name again. Mitigation: R2 makes derivation Form-native via `sha256.fk`.
- **Pin-store integrity.** A poisoned pin store makes pin-match meaningless. Mitigation: pins are
  append-on-first-use; a key change surfaces as REJECT_PIN_CONFLICT (verdict 4), never silently
  overwritten — the conflict is loud by design.

## Gaps

- **ed25519 sign/verify carrier is not built** — `sig_ok` / `deleg_ok` are inputs today; a follow-up
  task builds the carrier (needs crypto deps absent from this environment).
- **NodeID = sha256(pubkey) derivation not yet wired** as a Form recipe — `sha256.fk` exists; a
  follow-up task makes `nodeid_match` a proven derivation.
- **TOFU pin store not built** — `pin_state` is an input today; a follow-up task adds the store.
- **Client integration is breath 4** — signing envelopes + running the verdict on receipt is a
  follow-up that lands with the device carriers.

## Out of Scope

- The cryptography itself (ed25519, sha256-over-key) — carriers, built where their deps live; this
  spec is the decision body, deliberately crypto-free and four-way provable.
- Per-device subkey delegation + revocation mechanics — designed in the field-relay Identity model
  (breath 3); the verdict consumes `deleg_ok`, it does not implement the chain.
- The relay itself — unchanged; it stays open and content-blind. This verdict is an edge concern.
```
