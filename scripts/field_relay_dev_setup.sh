#!/usr/bin/env bash
# field_relay_dev_setup.sh — provision a session to BUILD + PROVE the field relay's breath-4 carriers.
#
# Point a cloud environment's SETUP SCRIPT at this (Claude Code: Environment -> setup script; Codex:
# the setup phase, which has network while the agent phase does not). The relay's DECISION bodies are
# already proven four-way + native and merged:
#   field-relay.fk   (fr-route, 127)    — open, content-blind routing + consent
#   field-identity.fk(fiv-verdict, 511) — trust verdict at the edge (breath 3 keystone)
#   field-queue.fk   (fq-drain, 127)    — reconnect backlog drain (breath 2)
# What is NOT yet built is the CARRIERS + CLIENTS (breath 4): the ed25519 sign/verify carrier, the
# sha256 NodeID-derivation wiring, the TOFU pin store, the append-only board I/O, and a dial-out client.
# Those need deps the bare sandbox lacks. This script installs exactly those deps so the next session
# can build them AND prove them end-to-end against the live relay or a local one.
#
# The deps are already declared in api/requirements.txt:
#   fastapi + uvicorn[standard] (brings the websockets lib) — the relay transport + a WS client
#   cryptography>=41 / PyNaCl>=1.5 — ed25519 keygen/sign/verify, the identity carrier
# So provisioning is mostly `pip install -e api`. Idempotent: a satisfied env is a fast no-op.
#
# Optional (FIELD_RELAY_BUILD_KERNELS=1): also build the Go/Rust/TS form kernels so `form/validate.sh`
# can re-prove the four-way decision bands here. The carriers themselves are Python and do not need it;
# it is only for re-running the Form proofs.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 0

ok=0
need_install=0
# already provisioned? (the three carrier deps import) -> fast no-op
if python3 -c "import fastapi, websockets; from nacl import signing; from cryptography.hazmat.primitives.asymmetric import ed25519" >/dev/null 2>&1; then
  echo "⟐ breath-4 carrier deps already present (fastapi + websockets + ed25519) — ready to build + prove."
  ok=1
else
  need_install=1
fi

if [[ "$need_install" == 1 ]]; then
  echo "⟐ installing breath-4 carrier deps (api/requirements.txt: fastapi, uvicorn[standard]->websockets, cryptography, PyNaCl)…"
  if python3 -m pip install -e api -q >/dev/null 2>&1 || python3 -m pip install -r api/requirements.txt -q >/dev/null 2>&1; then
    if python3 -c "import fastapi, websockets; from nacl import signing; from cryptography.hazmat.primitives.asymmetric import ed25519" >/dev/null 2>&1; then
      echo "⟐ done — fastapi + websockets + ed25519 importable. Breath-4 carriers can be built and proven."
      ok=1
    else
      echo "⟐ install ran but a carrier dep is still missing — check pip output; breath-4 build will be partial."
    fi
  else
    echo "⟐ pip install failed (no network in agent phase? run this in the SETUP phase). Breath-4 build blocked until deps land."
  fi
fi

# Optional: build the form kernels so validate.sh can re-prove the decision bands locally.
if [[ "${FIELD_RELAY_BUILD_KERNELS:-0}" == 1 ]]; then
  echo "⟐ FIELD_RELAY_BUILD_KERNELS=1 — building Go/Rust/TS kernels for form/validate.sh (best-effort)…"
  ( cd form/form-kernel-go && go build -o bin-go . ) >/dev/null 2>&1 && echo "  go kernel built" || echo "  go kernel build skipped/failed"
  ( cd form/form-kernel-rust && cargo build --release ) >/dev/null 2>&1 && echo "  rust kernel built" || echo "  rust kernel build skipped/failed"
fi

if [[ "$ok" == 1 ]]; then
  cat <<'NEXT'
⟐ ready. Next session can now build + prove breath 4:
   - ed25519 identity carrier:  keygen -> NodeID=sha256(pubkey); sign/verify -> feed fiv-verdict (field-identity.fk)
   - dial-out client (Python, runs Mac/Windows/Linux): connect wss://…/api/field/relay/{nodeid}, hello+interface, sign envelopes
   - reconnect drain: read the append-only board -> fq-drain (field-queue.fk) -> replay the gap, advance the cursor
   - e2e proof: start the relay locally (uvicorn app.main:app) OR use the live endpoint; two clients exchange a signed
     envelope; impersonation (wrong key) is rejected by fiv-verdict; an offline cell drains its backlog on reconnect.
   Keep the proof discipline: the decision stays the proven Form recipe; the carrier is the thin shell around it.
NEXT
fi
exit 0
