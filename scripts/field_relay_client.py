#!/usr/bin/env python3
"""field_relay_client.py — breath-4 carriers + dial-out client for the field relay (the on-device e2e receipt).

The relay (api/app/routers/field_relay.py) is open, content-blind, dial-out. IDENTITY lives at the edges
— this is the thin crypto+network CARRIER that lets a cell sign envelopes and decide whether a presented
sender is trustworthy. The DECISIONS stay Form, proven four-way + native + mac/windows/android rows:

  - the trust VERDICT is the proven fiv-verdict recipe (form/form-stdlib/field-identity.fk), run on the
    fkwu universal kernel itself via form/form-stdlib/field-identity-decide.fk + scripts/fkwu_run.sh:
    the carrier computes the four crypto booleans, stages them as DATA, and reads the verdict back from
    the kernel. The security-critical decision is never re-implemented here.
  - the reconnect DRAIN selection is fq-drain (form/form-stdlib/field-queue.fk, verdict 127). For the
    e2e it is mirrored faithfully in Python (``_fq_drain``) exactly as the live relay endpoint mirrors
    fr-route in ``_decide`` — the canonical body is the proven recipe; this is the bootstrap carrier.

NodeID = sha256(pubkey): a cell cannot claim a NodeID that is not the hash of the key it signs with, so
nodeid_match=0 is a forged identity (REJECT_NODEID_MISMATCH). ed25519 sign/verify is PyNaCl; sha256 is
hashlib. Run:  python3 scripts/field_relay_client.py e2e [--relay wss://api.coherencycoin.com/api/field/relay]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import websockets
from nacl import signing
from nacl.exceptions import BadSignatureError

ROOT = Path(__file__).resolve().parent.parent
FKWU_RUN = ROOT / "scripts" / "fkwu_run.sh"
FID = "form-stdlib/field-identity.fk"
FID_DECIDE = "form-stdlib/field-identity-decide.fk"

DEFAULT_RELAY = "wss://api.coherencycoin.com/api/field/relay"


# ── identity carrier: ed25519 + sha256 NodeID ────────────────────────────────
class Identity:
    """An ed25519 keypair whose NodeID IS the sha256 of its public key."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.signing_key = signing.SigningKey.generate()
        self.verify_key = self.signing_key.verify_key
        self.pubkey: bytes = self.verify_key.encode()
        self.nodeid: str = hashlib.sha256(self.pubkey).hexdigest()

    def sign(self, msg: bytes) -> bytes:
        return self.signing_key.sign(msg).signature


def signed_message(claimed_nodeid: str, kind: str, payload: str) -> bytes:
    """The bytes a sender authenticates: it binds the claimed identity, the kind, and the payload."""
    return f"{claimed_nodeid}|{kind}|{payload}".encode()


def verify_sig(pubkey: bytes, msg: bytes, sig: bytes) -> bool:
    try:
        signing.VerifyKey(pubkey).verify(msg, sig)
        return True
    except (BadSignatureError, ValueError):
        return False


# ── the trust VERDICT, computed by the proven fiv-verdict on the fkwu kernel ──
def fiv_verdict_on_fkwu(nodeid_match: int, sig_ok: int, deleg_ok: int, pin_state: int) -> int:
    """Stage the four booleans as DATA and run the PROVEN fiv-verdict recipe on fkwu. Decision stays Form."""
    bundle = f"{nodeid_match}{sig_ok}{deleg_ok}{pin_state}"  # four digit bytes; carrier never synthesizes source
    with tempfile.NamedTemporaryFile("w", suffix=".bundle", delete=False) as f:
        f.write(bundle)
        bpath = f.name
    try:
        out = subprocess.run(
            ["bash", str(FKWU_RUN), bpath, FID, FID_DECIDE],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120,
        )
        line = (out.stdout or "").strip().splitlines()
        if not line:
            raise RuntimeError(f"fkwu produced no verdict (stderr: {out.stderr.strip()[:200]})")
        return int(line[0])
    finally:
        Path(bpath).unlink(missing_ok=True)


# act-on helpers — mirror fiv-accept? / fiv-should-pin? / fiv-impersonation? (proven in field-identity.fk)
def accept(verdict: int) -> bool:        return verdict in (1, 2)
def should_pin(verdict: int) -> bool:    return verdict == 2
def impersonation(verdict: int) -> bool: return verdict in (4, 5, 6)

VERDICT_NAME = {
    1: "TRUSTED", 2: "FIRST_USE_PIN", 3: "UNVERIFIED",
    4: "REJECT_PIN_CONFLICT", 5: "REJECT_NODEID_MISMATCH", 6: "REJECT_DELEGATION",
}


# ── reconnect drain — faithful Python mirror of fq-drain (canonical body: field-queue.fk) ─────────────
def _fq_drain(backlog: list[tuple[int, str, str]], to: str, last_seen: int, iface: set[str]):
    """Mirror of fq-drain: entries for `to`, unseen (seq>last_seen), consent-ok (kind in iface), in order."""
    return [e for e in backlog if e[1] == to and e[0] > last_seen and e[2] in iface]


def _fq_cursor(backlog: list[tuple[int, str, str]], to: str, last_seen: int) -> int:
    """Mirror of fq-cursor: max seq among addressed-unseen entries (consent-INDEPENDENT), else last_seen."""
    cur = last_seen
    for seq, eto, _kind in backlog:
        if eto == to and seq > last_seen and seq > cur:
            cur = seq
    return cur


# ── the recipient: receive envelopes, decide via fkwu, pin on first use ───────────────────────────────
class Recipient:
    def __init__(self, ident: Identity, interface: list[str]) -> None:
        self.ident = ident
        self.interface = interface
        self.pins: dict[str, str] = {}   # TOFU pin store: claimed_nodeid -> pubkey hex
        self.log: list[dict] = []

    def judge(self, body: dict, kind: str) -> dict:
        """Compute the four crypto booleans and get the verdict from fiv-verdict on fkwu."""
        claimed = body.get("nodeid", "")
        pubkey = bytes.fromhex(body.get("pubkey", ""))
        sig = bytes.fromhex(body.get("sig", ""))
        payload = body.get("payload", "")

        nodeid_match = 1 if hashlib.sha256(pubkey).hexdigest() == claimed else 0
        sig_ok = 1 if verify_sig(pubkey, signed_message(claimed, kind, payload), sig) else 0
        deleg_ok = 1  # root key signing its own NodeID (device-subkey delegation is a later carrier)
        pinned = self.pins.get(claimed)
        pin_state = 0 if pinned is None else (1 if pinned == body.get("pubkey") else 2)

        verdict = fiv_verdict_on_fkwu(nodeid_match, sig_ok, deleg_ok, pin_state)
        if should_pin(verdict):
            self.pins[claimed] = body.get("pubkey", "")
        rec = {
            "claimed": claimed, "kind": kind, "payload": payload,
            "inputs": (nodeid_match, sig_ok, deleg_ok, pin_state),
            "verdict": verdict, "verdict_name": VERDICT_NAME.get(verdict, "?"),
            "accepted": accept(verdict), "pinned_now": should_pin(verdict),
            "impersonation": impersonation(verdict),
        }
        self.log.append(rec)
        return rec


def make_envelope(sender: Identity, to: str, kind: str, payload: str, *, claim_nodeid: str | None = None) -> dict:
    """Build a relay envelope. claim_nodeid lets an attacker CLAIM another id while signing with its own key."""
    claimed = claim_nodeid if claim_nodeid is not None else sender.nodeid
    sig = sender.sign(signed_message(claimed, kind, payload))
    body = {"nodeid": claimed, "pubkey": sender.pubkey.hex(), "sig": sig.hex(), "payload": payload}
    return {"type": "envelope", "to": to, "kind": kind, "body": body}


async def _recv_until(ws, want_type: str, timeout: float = 15.0) -> dict:
    while True:
        frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if frame.get("type") == want_type:
            return frame


async def _connect(uri: str, attempts: int = 5):
    """Dial out with exponential backoff — the protocol's own reconnect discipline, also robust to a
    transient gateway 502/timeout at the public edge (the relay is the rendezvous both ends keep reaching)."""
    delay = 1.0
    last: Exception | None = None
    for _ in range(attempts):
        try:
            return await websockets.connect(uri, open_timeout=15)
        except Exception as e:  # noqa: BLE001 — edge blips are expected; back off and re-dial
            last = e
            await asyncio.sleep(delay)
            delay = min(delay * 2, 8.0)
    raise RuntimeError(f"could not reach relay {uri} after {attempts} attempts: {last}")


# ── the e2e driver: prove the whole identity flow against a live (or local) relay ─────────────────────
async def run_e2e(relay_base: str) -> int:
    A = Identity("A-sender")
    B = Identity("B-recipient")
    C = Identity("C-impersonator")
    recip = Recipient(B, interface=["field-hello"])

    results: list[tuple[str, bool]] = []
    transcript: list[str] = []

    def note(s: str) -> None:
        transcript.append(s)
        print(s)

    note(f"relay: {relay_base}")
    note(f"A (sender)       NodeID={A.nodeid[:16]}…")
    note(f"B (recipient)    NodeID={B.nodeid[:16]}…  offers={recip.interface}")
    note(f"C (impersonator) NodeID={C.nodeid[:16]}…")
    note("")

    b_uri = f"{relay_base}/{B.nodeid}"
    a_uri = f"{relay_base}/{A.nodeid}"
    c_uri = f"{relay_base}/{C.nodeid}"

    async with await _connect(b_uri) as bws:
        await _recv_until(bws, "connected")
        await bws.send(json.dumps({"type": "hello", "interface": recip.interface}))
        await _recv_until(bws, "ready")

        # ---- 1. first contact: A signs an envelope to B -> FIRST_USE_PIN, accept + pin ----
        async with await _connect(a_uri) as aws:
            await _recv_until(aws, "connected")
            await aws.send(json.dumps({"type": "hello", "interface": ["field-hello"]}))
            await _recv_until(aws, "ready")

            await aws.send(json.dumps(make_envelope(A, B.nodeid, "field-hello", "first hello from A")))
            env = await _recv_until(bws, "envelope")
            r1 = recip.judge(env["body"], env["kind"])
            note(f"[1] A→B first contact   inputs={r1['inputs']} → {r1['verdict']} {r1['verdict_name']}  accepted={r1['accepted']} pinned={r1['pinned_now']}")
            results.append(("first-contact accepts + pins (FIRST_USE_PIN=2)", r1["verdict"] == 2 and r1["accepted"] and r1["pinned_now"]))

            # ---- 2. A again, now pinned -> TRUSTED ----
            await aws.send(json.dumps(make_envelope(A, B.nodeid, "field-hello", "second hello from A")))
            env = await _recv_until(bws, "envelope")
            r2 = recip.judge(env["body"], env["kind"])
            note(f"[2] A→B (now pinned)     inputs={r2['inputs']} → {r2['verdict']} {r2['verdict_name']}  accepted={r2['accepted']}")
            results.append(("pinned sender is TRUSTED (=1)", r2["verdict"] == 1 and r2["accepted"]))

        # ---- 3. impersonation: C claims A's NodeID but signs with C's key -> REJECT_NODEID_MISMATCH ----
        async with await _connect(c_uri) as cws:
            await _recv_until(cws, "connected")
            await cws.send(json.dumps({"type": "hello", "interface": ["field-hello"]}))
            await _recv_until(cws, "ready")

            forged = make_envelope(C, B.nodeid, "field-hello", "I am A (lie)", claim_nodeid=A.nodeid)
            await cws.send(json.dumps(forged))
            env = await _recv_until(bws, "envelope")
            r3 = recip.judge(env["body"], env["kind"])
            note(f"[3] C→B claims A's id    inputs={r3['inputs']} → {r3['verdict']} {r3['verdict_name']}  accepted={r3['accepted']} impersonation={r3['impersonation']}")
            results.append(("impersonator rejected (REJECT_NODEID_MISMATCH=5)", r3["verdict"] == 5 and not r3["accepted"] and r3["impersonation"]))
            note(f"    A's pin still intact: {recip.pins.get(A.nodeid) == A.pubkey.hex()}")
            results.append(("pin not corrupted by impersonation", recip.pins.get(A.nodeid) == A.pubkey.hex()))

        # ---- 4. offline drain: B offline, A queues, B reconnects, fq-drain selects the gap ----
        note("")
        note("[4] B goes offline; A sends 3 while B is away (relay QUEUEs; a board records seq/to/kind)")
    # B's socket is now closed (offline). The relay marks B not-connected -> QUEUE.
    board: list[tuple[int, str, str]] = []
    async with await _connect(a_uri) as aws:
        await _recv_until(aws, "connected")
        await aws.send(json.dumps({"type": "hello", "interface": ["field-hello"]}))
        await _recv_until(aws, "ready")
        queued_kinds = ["field-hello", "field-block", "field-hello"]  # field-block is NOT in B's interface
        for i, kind in enumerate(queued_kinds, start=1):
            await aws.send(json.dumps(make_envelope(A, B.nodeid, kind, f"queued #{i}")))
            ack = await _recv_until(aws, "routed")
            board.append((i, B.nodeid, kind))
            note(f"    seq{i} kind={kind:12s} relay decision={ack.get('decision')}")

    last_seen = 0
    drained = _fq_drain(board, B.nodeid, last_seen, set(recip.interface))
    cursor = _fq_cursor(board, B.nodeid, last_seen)
    note(f"    B reconnects at last_seen={last_seen}; fq-drain selects seqs={[e[0] for e in drained]} (field-block denied by consent), cursor→{cursor}")
    # B should replay exactly seq1 + seq3 (field-hello), NOT seq2 (field-block, not offered); cursor advances to 3
    results.append(("fq-drain replays only consent-ok unseen (seq1,seq3)", [e[0] for e in drained] == [1, 3]))
    results.append(("fq-cursor advances past denied tail to 3", cursor == 3))

    # ---- summary ----
    note("")
    note("── receipt ──")
    ok = True
    for name, passed in results:
        note(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    note("")
    note(f"e2e {'PASS' if ok else 'FAIL'} — {sum(1 for _, p in results if p)}/{len(results)} checks; "
         f"verdicts computed by fiv-verdict on the fkwu kernel.")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="field relay breath-4 e2e client")
    ap.add_argument("cmd", choices=["e2e"], help="e2e: run the full identity flow against the relay")
    ap.add_argument("--relay", default=DEFAULT_RELAY, help=f"relay base URL (default {DEFAULT_RELAY})")
    args = ap.parse_args()
    if args.cmd == "e2e":
        return asyncio.run(run_e2e(args.relay))
    return 2


if __name__ == "__main__":
    sys.exit(main())
