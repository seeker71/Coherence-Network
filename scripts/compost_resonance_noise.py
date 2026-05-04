"""One-shot data cleanup — compost dead-tissue presences and re-attune.

Run after deploying the resonance service tightening (PR #1298). This:

1. Deletes confirmed dead-tissue nodes whose only edges are auto-noise:
   - contributor:decomposition-verify (test artifact)
   - 5 CI/build asset nodes (Documentation bundle, OpenClaw skill,
     GitHub repo description, Worker service, Cursor Pro Agent)

2. Patches contributor:seeker71 — sets `name` to "Urs Muff" so
   Connected Frequencies surfaces the human, not the handle.

3. Calls attune() on every real presence so the new prune_stale=True
   path sheds the 73 noise edges in one pass. Real presences keep
   their meaningful edges; only single-generic-token resonance falls
   away.

Idempotent — safe to re-run.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse

API = "https://api.coherencycoin.com"

DEAD_TISSUE_NODES = [
    "contributor:decomposition-verify",
    "asset:88d8c870-c915-426f-954a-80e34a0ea7ae",  # Documentation — SKILL.md, CLI README, RUNBOOK
    "asset:b69ac689-10b9-421d-9fda-fcad0c322589",  # OpenClaw skill (coherence-network) — v1.6.0
    "asset:6f541a13-c0b6-4a66-888a-915e10f426ef",  # GitHub repo seeker71/Coherence-Network
    "asset:22c3d9e4-335d-4055-a2d0-37b516a70ed1",  # Worker service — Windows/macOS, self-update
    "asset:c8150c8a-085e-41b2-829a-c9a98fc2dee6",  # Cursor Pro Agent — auto model selection
    # Second pass — platform implementation descriptors. The vision
    # space holds what the network IS, not how it's wired. The fact
    # that the web frontend has 35 pages is a deploy detail, not a
    # resonance with Living Collective concepts.
    "asset:f3946091-5d2c-4e6e-8cdf-00e77455e5bc",  # Coherence Network API — FastAPI 224 endpoints
    "asset:fd9b6956-5b2a-4444-bb43-733a86e758fb",  # Coherence Network web frontend — Next.js 15, 35 pages
    "asset:3ce356f1-b5a4-472b-811e-c8f939010bf9",  # Coherence Network Web — Next.js 15, 16 pages (older)
    "asset:0fa68f2e-4e28-4ca5-a165-fa2b223a19ee",  # Coherence Network API — 195 endpoints (older)
    "asset:0d81b5a7-8cff-421b-afbb-32d2ccc50041",  # Production PostgreSQL — ideas, specs, tasks, ...
    "asset:36d576e4-8e98-4886-befd-592258bd920e",  # Local runner — Thompson Sampling
    "asset:60e0962a-7764-4d47-8556-1fc7c51ce559",  # Coherence CLI (cc) — Node.js
    "asset:a06a8f69-19a0-45fa-9fe8-c08d115969a5",  # coherencycoin.com domain + Cloudflare CDN + TLS
    "asset:ba2b6101-bb9f-4d2c-b29c-8f1e83f35577",  # Coinbase Base wallet — treasury 0x...
    "asset:bd05c936-58a3-4a71-ad39-3457bae4bb20",  # 179 ideas, 175+ specs, 1952 tasks, 10 news sources
]

RENAMES = [
    ("contributor:seeker71", {
        "name": "Urs Muff",
        "description": (
            "Tender of the Coherence Network. Born Ebikon LU, met "
            "Ramtha at 18, moved to Colorado on intuition in 1998, "
            "CU Boulder MS/CS. Frequency carrier, not platform owner."
        ),
    }),
]

# Real presences whose edges to LC concepts should be re-attuned with
# the new (tighter) logic — the prune_stale path drops anything that
# no longer makes threshold.
REATTUNE = [
    "contributor:seeker71",
    "contributor:codex-agent",
    "contributor:cursor-agent",
    "contributor:coherence-runner",
    "contributor:claude-opus-mac-node",
    "contributor:external-proof-bot",
    "event:retreat-with-anne-tucker-sept-2024-1ffefd92d6cd",
]


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict | list | None]:
    """Hit the prod API via curl. urllib's default User-Agent gets a 403
    from Cloudflare in front of api.coherencycoin.com; curl's UA is fine.
    """
    url = f"{API}{path}"
    args = ["curl", "-sS", "-X", method, url, "-w", "\n%{http_code}"]
    if body is not None:
        args += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    raw = r.stdout
    # last line is the http code
    if "\n" in raw:
        body_text, code_str = raw.rsplit("\n", 1)
    else:
        body_text, code_str = "", raw
    try:
        status = int(code_str.strip() or "0")
    except ValueError:
        status = 0
    payload: dict | list | None = None
    if body_text:
        try:
            payload = json.loads(body_text)
        except Exception:
            payload = None
    return status, payload


def main() -> int:
    print("=== Step 1: rename + enrich seeker71 ===")
    for nid, patch in RENAMES:
        enc = urllib.parse.quote(nid, safe="")
        status, body = _request("PATCH", f"/api/graph/nodes/{enc}", patch)
        print(f"  PATCH {nid} -> status={status}")
        if status >= 400:
            print(f"    body: {body}")

    print()
    print("=== Step 2: delete dead-tissue nodes ===")
    for nid in DEAD_TISSUE_NODES:
        enc = urllib.parse.quote(nid, safe="")
        # Confirm only auto-noise edges first (defensive)
        status, edges = _request("GET", f"/api/graph/nodes/{enc}/edges")
        if status == 404:
            print(f"  {nid} already gone")
            continue
        if status >= 400:
            print(f"  {nid} edge fetch failed status={status}")
            continue
        types = {e.get("type") for e in (edges or [])}
        if types and types != {"resonates-with"}:
            print(f"  SKIP {nid} — has non-resonance edges {types}")
            continue
        status, body = _request("DELETE", f"/api/graph/nodes/{enc}")
        print(f"  DELETE {nid} -> status={status}")
        if status >= 400:
            print(f"    body: {body}")

    print()
    print("=== Step 3: re-attune real presences (prunes stale resonance) ===")
    for pid in REATTUNE:
        enc = urllib.parse.quote(pid, safe="")
        status, body = _request(
            "POST", f"/api/presences/{enc}/resonances/attune", None,
        )
        print(f"  attune {pid} -> status={status}")
        if isinstance(body, dict):
            written = body.get("written") or []
            existed = body.get("existed") or []
            pruned = body.get("pruned") or []
            print(
                f"    written={len(written)}  "
                f"existed={len(existed)}  "
                f"pruned={len(pruned)}"
            )
            if pruned:
                for p in pruned:
                    print(f"    pruned: {p}")
        elif status >= 400:
            print(f"    body: {body}")

    print()
    print("=== Step 4: verify lc-rhythm Connected Frequencies ===")
    status, edges = _request("GET", "/api/concepts/lc-rhythm/edges")
    if isinstance(edges, list):
        relevant = [
            e for e in edges
            if not (e.get("from", "").startswith(("visual-lc-", "renderer-")) or
                    e.get("to", "").startswith(("visual-lc-", "renderer-")))
        ]
        targets = sorted({(e.get("from"), e.get("to"))
                          for e in relevant})
        print(f"  total edges: {len(edges)}, after visual/renderer filter: {len(relevant)}")
        for f, t in targets:
            print(f"    {f}  ->  {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
