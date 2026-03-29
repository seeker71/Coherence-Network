#!/usr/bin/env python3
"""
Demo: Idea Dual Identity — UUID + Slug
=======================================

Walks through the evolution of idea identity in Coherence Network:

  BEFORE  — slug IDs do double-duty as machine key and human label.
             Renaming breaks every cross-link. Runner grabs wrong idea.

  BRIDGE  — UUID auto-generation (PR #786): POST /api/ideas with no 'id'
             now returns a stable UUID4. This was the missing foundation.

  AFTER   — (spec 181 target) UUID as immutable FK + slug as mutable label.
             Renaming is free. FKs never break. Slugs grow structured over time.

Run:
    python3 scripts/demo_dual_identity.py

Requires:
    ~/.coherence-network/keys.json  with  { "coherence": { "api_key": "..." } }
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from typing import Any

BASE = "https://api.coherencycoin.com/api"
_KEYS_PATH = "~/.coherence-network/keys.json"

# ─── helpers ──────────────────────────────────────────────────────────────────

def _load_key() -> str:
    import os, json as _json
    path = os.path.expanduser(_KEYS_PATH)
    with open(path) as f:
        return _json.load(f)["coherence"]["api_key"]


API_KEY = _load_key()


def api(method: str, path: str, body: dict | None = None, retries: int = 3) -> tuple[int, Any]:
    cmd = [
        "curl", "-s", "-w", "\n%{http_code}",
        "-X", method.upper(),
        f"{BASE}{path}",
        "-H", f"X-API-Key: {API_KEY}",
        "-H", "Content-Type: application/json",
    ]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    for attempt in range(retries):
        result = subprocess.run(cmd, capture_output=True, text=True)
        raw, code = result.stdout.rsplit("\n", 1)
        http_code = int(code)
        if http_code == 429 and attempt < retries - 1:
            wait = 2 ** attempt
            print(f"  [rate-limited] waiting {wait}s before retry {attempt + 2}/{retries}…")
            time.sleep(wait)
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = raw
        return http_code, data
    return 429, {}


IS_UUID4 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def is_uuid4(s: str) -> bool:
    return bool(IS_UUID4.match(str(s or "")))


def hr(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def show(label: str, value: Any) -> None:
    print(f"  {label:<22} {value}")


def check(condition: bool, label: str) -> None:
    mark = "✓" if condition else "✗"
    print(f"  [{mark}] {label}")
    if not condition:
        sys.exit(f"\nFailed: {label}")


# ─── CHAPTER 1: The old world ─────────────────────────────────────────────────

hr("CHAPTER 1 — The old world: slug IDs doing double-duty")

print("""
  Before PR #786, every POST /api/ideas required a caller-supplied 'id'.
  That single field served two incompatible roles:

    Machine key  →  used in parent_idea_id, child_idea_ids, FK lookups
    Human label  →  used in URLs, CLI, runner direction text, spec globs

  The coupling caused real bugs:

  • Runner grabs wrong idea
      direction = "Implement edge-navigation"
      spec glob  = specs/*edge-navigation*
      → matches task_xxx_edge-navigation-fix.md instead of edge-navigation.md
      → provider works on the wrong spec

  • Rename = breaking change
      idea id: "cc-minting"
      parent_idea_id on 12 child ideas: "cc-minting"
      Rename to "treasury/cc-minting" → all 12 children become orphans

  • Collision risk
      Three spec files share the '169-' prefix (169-smart-reap.md,
      169-resonance-alive-empty-state.md, 169-fractal-node-edge-primitives.md)
      — same problem would hit idea IDs at scale
""")

# Show a real example of the old pattern still in the DB
code, data = api("GET", "/ideas?limit=5&lifecycle=active")
if code == 200:
    sample = [i for i in data.get("ideas", []) if not is_uuid4(i.get("id", ""))][:3]
    if sample:
        print("  Live examples of slug IDs still in the portfolio:")
        for idea in sample:
            show(idea["id"], idea.get("name", "")[:50])

# ─── CHAPTER 2: The bridge step ───────────────────────────────────────────────

hr("CHAPTER 2 — The bridge: UUID auto-generation (PR #786)")

print("""
  The key insight: the machine key must be stable and system-generated.
  Humans are bad at generating UUIDs; machines are bad at generating
  meaningful slugs. Split the job.

  PR #786 made 'id' optional in IdeaCreate. A Pydantic model_validator
  generates UUID4 when the caller omits it. Three files changed:

    api/app/models/idea.py          — model_validator + Optional[str] id
    api/app/models/spec_registry.py — same for spec_id
    api/app/services/idea_service.py — str | None, resolved = id or uuid4()

  This was the necessary foundation. Without it, the slug migration
  (spec 181) has nowhere to put the stable machine key.
""")

print("  Demonstrating now — POST with no 'id' field:\n")

code, created = api("POST", "/ideas", {
    "name": "Dual identity demo — auto UUID",
    "description": (
        "Created by demo_dual_identity.py to show UUID4 auto-generation. "
        "Will be retired at end of demo."
    ),
    "potential_value": 5.0,
    "estimated_cost": 0.5,
    "work_type": "exploration",
})

check(code == 201, f"POST /ideas returned 201 (got {code})")
demo_id = created.get("id", "")
check(is_uuid4(demo_id), f"Returned id is UUID4: {demo_id}")

show("HTTP status", code)
show("id (machine key)", demo_id)
show("name", created.get("name"))
show("lifecycle", created.get("lifecycle"))

print("""
  The API assigned a stable, collision-free UUID4 without the caller
  needing to invent one. This is the current production behaviour.
""")

time.sleep(0.4)

# ─── CHAPTER 3: What the full design looks like ───────────────────────────────

hr("CHAPTER 3 — Target design (spec 181): UUID + slug as distinct fields")

print("""
  Spec 181 adds a 'slug' field — mutable, human-readable, URL-safe —
  while 'id' (UUID4) becomes the immutable machine key that all FKs
  reference.

  The router resolves both:
    GET /api/ideas/3fa06e6c-...   → UUID lookup (exact, fast)
    GET /api/ideas/cc-minting      → slug index lookup
    GET /api/ideas/finance/cc-minting → namespaced slug lookup

  Renaming is free:
    PATCH /api/ideas/{uuid}/slug  { "slug": "finance/cc-minting" }
    → old slug kept in slug_history (permanent redirect)
    → all 12 child FKs pointing to uuid are unaffected

  Slug structure grows with the platform:

    Now:   cc-minting
    Q2:    finance/cc-minting
    Q4:    finance/treasury/cc-minting/testnet-deposit

  The namespace mirrors the super→child idea hierarchy, so the slug
  itself documents provenance — no separate lookup needed.
""")

# Simulate what the response WILL look like post-spec-181 implementation
simulated_response = {
    "id":           demo_id,                          # UUID4, immutable
    "slug":         "demo/dual-identity-auto-uuid",   # human key, mutable
    "slug_history": [],                               # grows on rename
    "name":         created.get("name"),
    "lifecycle":    "active",
}

print("  Simulated spec-181 response shape:")
for k, v in simulated_response.items():
    show(k, v)

print("""
  And a rename:
    PATCH /api/ideas/{uuid}/slug  { "slug": "explorations/dual-identity" }

  Response:
    { "id": "{uuid}",
      "slug": "explorations/dual-identity",
      "slug_history": ["demo/dual-identity-auto-uuid"] }

  GET /api/ideas/demo/dual-identity-auto-uuid  →  302 → same idea
  GET /api/ideas/explorations/dual-identity    →  200 same idea
  GET /api/ideas/{uuid}                        →  200 same idea — always
""")

# ─── CHAPTER 4: Why the order mattered ───────────────────────────────────────

hr("CHAPTER 4 — Why UUID auto-generation had to come first")

print("""
  The steps had to happen in this order:

  Step 1 — IdeaWorkType + lifecycle (IdeaCreate unchanged)
    Work type classification and lifecycle states are valuable on their own.
    No identity change needed yet.

  Step 2 — UUID auto-generation (PR #786, shipped)
    Make 'id' optional with UUID4 fallback. This is the hinge point.
    Without it:
      • spec 181's migration script has no stable key to promote to FK
      • slug rename can't be non-breaking (nothing else to hold the FK)
      • federation can't guarantee global uniqueness of imported ideas

    With it:
      • New ideas immediately get collision-free, rename-proof machine keys
      • The migration can backfill existing slugs into the 'slug' field
        and promote the existing id values to UUIDs safely
      • The runner can embed uuid in task context — spec glob becomes exact

  Step 3 — Full dual identity (spec 181, next)
    Now that the machine key is stable, we can:
    • Add 'slug' as a separate mutable field
    • Rewrite FKs to use uuid (one-time migration)
    • Enable slug rename without FK cascade

  Trying to do step 3 before step 2 would mean:
    • Migration has no stable target for FKs (slugs are mutable, so the
      'new id' field would itself need to be migrated again later)
    • Every rename during the transition window would corrupt cross-links

  This is why the auto-UUID PR was the right last step before the spec.
""")

# ─── CHAPTER 5: Live FK demonstration ────────────────────────────────────────

hr("CHAPTER 5 — Live: create a parent + child using UUIDs as FKs")

code, parent = api("POST", "/ideas", {
    "name": "Demo parent (spec 181 walkthrough)",
    "description": "Super idea to demonstrate UUID-based FK. Will be retired.",
    "potential_value": 10.0,
    "estimated_cost": 1.0,
    "idea_type": "super",
    "work_type": "exploration",
})
check(code == 201, f"Create parent: HTTP {code}")
parent_uuid = parent["id"]
check(is_uuid4(parent_uuid), f"Parent UUID: {parent_uuid}")
show("parent id", parent_uuid)

time.sleep(0.3)

code, child = api("POST", "/ideas", {
    "name": "Demo child (spec 181 walkthrough)",
    "description": "Child idea linked by UUID FK. Will be retired.",
    "potential_value": 3.0,
    "estimated_cost": 0.5,
    "idea_type": "child",
    "parent_idea_id": parent_uuid,    # ← UUID FK, not a slug
    "work_type": "feature",
})
check(code == 201, f"Create child: HTTP {code}")
child_uuid = child["id"]
check(is_uuid4(child_uuid), f"Child UUID: {child_uuid}")
show("child id", child_uuid)
show("child.parent_idea_id", child.get("parent_idea_id"))
check(child.get("parent_idea_id") == parent_uuid, "FK points to parent UUID")

print("""
  With slug as a separate field (spec 181):
  Renaming the parent from "demo/parent" to "walkthroughs/spec-181/parent"
  leaves parent_idea_id = "{uuid}" on the child completely unaffected.
  The slug is cosmetic. The UUID is load-bearing.
""")

# ─── Cleanup ──────────────────────────────────────────────────────────────────

hr("Cleanup — retiring demo ideas")

for uid, label in [(demo_id, "auto-uuid demo"), (child_uuid, "child"), (parent_uuid, "parent")]:
    code, _ = api("PATCH", f"/ideas/{uid}", {"lifecycle": "retired"})
    show(f"retire {label}", f"HTTP {code}")
    time.sleep(0.3)

# ─── Summary ──────────────────────────────────────────────────────────────────

hr("Summary")

print("""
  BEFORE        slug-as-ID        fragile FKs, rename = breaking change
  ─────────────────────────────────────────────────────────────────────
  PR #786       UUID auto-gen     stable machine key, no caller input needed
  Spec 181      UUID + slug       rename-proof FKs, human slugs grow structured

  Key properties of the target design:
    • id (UUID4)    — immutable, machine-generated, globally unique
    • slug          — mutable, human-writable, URL-safe, namespaced
    • slug_history  — permanent redirect list, old links never break
    • All FKs       — reference UUID only
    • All URLs      — accept UUID or slug (current or historical)
    • Slugs         — grow from flat → pillar/ → pillar/domain/ as taxonomy matures
    • Federation    — UUIDs survive import/export; slugs may be re-namespaced locally
""")
