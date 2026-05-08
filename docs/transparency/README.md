# Transparency · what we keep, where, and how to be removed

The Coherence Network is built on the conviction that everything traceable belongs in the open. This page is the operational version of that conviction — what kinds of data the network holds, where they live, what's public, and what to do if you arrived here and need to be removed.

## What the network holds, in plain terms

Three kinds of record accumulate as the network breathes:

| Record | Lives in | Visibility | Substrate |
|---|---|---|---|
| **Contributions** | `contribution_ledger` table | Public | Postgres on the VPS · nightly dumps to [coherence-network-archive](https://github.com/seeker71/coherence-network-archive) |
| **View events** | `asset_view_events` (last ~7 days) | Public | Postgres + cold-tier per-day archives at [Coherence-Network releases](https://github.com/seeker71/Coherence-Network/releases) tagged `archive-view-events-*` |
| **Graph state** | Neo4j (contributors, assets, concepts, edges) | Public | Same nightly postgres dump captures the relational mirror |

There is no separate private version. The dumps shipped to the public archive each night are byte-perfect mirrors of the live database. Anyone can verify their own contribution is preserved exactly as recorded, audit attribution chains across days, or stand up a fresh instance of the network from any past dump.

## What you implicitly agree to by participating

When you contribute (a commit, a presence, a refinement, a view event), the following becomes part of the public body of evidence:

1. **The action itself** — what changed, what was contributed, what frequency was emitted.
2. **Attribution** — your `contributor_id`, the timestamp, the asset/concept/edge that was touched, and the coherence-weighted attention reward (if any).
3. **Behavioural shape** — the daily rollup of which surfaces you visited (asset views, concept reads). Per-event detail (referrer, session fingerprint, page route) lives in the per-day cold-tier archive for as long as the archive is preserved, which is intended to be indefinitely.
4. **Lineage edges** — anyone you've referred, anyone you've credited as inspiration, anyone whose contribution your work cites.

Two things the network deliberately doesn't keep:

- **No tracking cookies, no third-party fingerprints, no cross-site tracking.** The session fingerprint is a per-tab UUID generated locally; it never leaves the network's first-party context.
- **No location, no device specifics, no IP-based geolocation.** The view events carry only the page route, not the visitor's environment.

## How to be removed (the opt-out path)

Public-by-default doesn't mean public-forever-no-matter-what. If your situation has changed since you started contributing — a privacy concern, a dispute, a right-to-be-forgotten request, anything we couldn't anticipate at arrival — the network honours the redaction request through this procedure:

### 1. Open a private channel

Email `umuff71@gmail.com` (network maintainer) with subject "opt-out request" and your `contributor_id`. We confirm the request before acting; nobody else gets to opt out on your behalf.

### 2. The redaction is run

[`scripts/opt_out_contributor.py`](../../scripts/opt_out_contributor.py) is the lever. It performs four passes:

- **Hot tier** — `UPDATE asset_view_events SET contributor_id=NULL, session_fingerprint=NULL, source_page=NULL, referrer_contributor_id=NULL` for every row tied to the contributor. The events stay (the network preserves the *shape* of attention) but the *who* is removed.
- **Contribution ledger** — `UPDATE contribution_ledger SET contributor_id='contributor:redacted'` for every row tied to the contributor. The ledger keeps WHAT happened; WHO is anonymised.
- **Cold-tier per-day archives** — for every archived day that contains the contributor, the gzipped JSONL is downloaded, the same anonymisation is applied to each event in-place, the file is re-gzipped, the SHA-256 is recomputed, and the asset is re-uploaded under the same tag + filename (the deterministic URL stays valid; only the SHA changes). The tombstone in the live DB is updated in lockstep so retrievers always verify against the current archive content.
- **Audit log** — a JSONL record of what was done is written to `/var/lib/coherence-network/opt-outs.log` for compliance review (kept private; never shipped to the public archive).

The same script supports `--dry-run` so you can see exactly what would change before any commit.

### 3. The honest scope

These are the limits of what an opt-out can guarantee, named directly:

- **Past third-party mirrors are out of reach.** Anyone who downloaded a cold-tier archive before the rewrite has the old SHA-256 on their disk. The network's surfaces (live DB, current cold-tier archives, future dumps) reflect the redaction; mirrors elsewhere don't.
- **Past postgres dumps in the public archive aren't rewritten.** Each nightly dump is a monolithic snapshot; rewriting them retroactively would invalidate every prior cryptographic verification. From the moment of opt-out, every new nightly dump reflects the redacted DB; older dumps in the archive are immutable.
- **GitHub's asset-CDN has a brief propagation window (~2 minutes observed)** after a cold-tier archive is rewritten. During that window the retrieval surface (`/api/views/archive/{day}`) returns an integrity error rather than serving stale content — fail-closed by design. The audit log and tombstone already record the new SHA, so the proof of rewrite is durable. Re-fetching after the window settles returns the redacted content cleanly.
- **Aggregate counts persist.** The sentinel `contributor:redacted` keeps the ledger's aggregate-counter behaviour intact (the network can still see "N contributions came from redacted cells") without exposing who. If you need stronger removal, say so in your request; we'll discuss what's possible at the substrate level.

The opt-out is **forward-looking and current-state effective**. It honours the request without pretending the substrate has powers it doesn't have.

## Verification

If you ever want to verify what the network holds about you:

- **Live state**: `GET /api/contributions?contributor_id=contributor:...` returns your contribution ledger.
- **View trail**: `GET /api/views/trail/contributor:...` returns the concepts and assets you've touched.
- **Cold-tier**: `GET /api/views/archive` lists every archived day with SHA-256; `GET /api/views/archive/{day}` retrieves and verifies a specific day.
- **Postgres dump**: any release on [coherence-network-archive](https://github.com/seeker71/coherence-network-archive) is downloadable and contains the full DB state at that snapshot time.

Each of these can be cross-referenced against the others. If any single substrate's view of you contradicts another, that's a signal worth raising — the network's posture is that all four should agree.

## Why this document exists

The first time someone asks for an opt-out, the network's response should be a well-rehearsed clean operation, not a credibility crisis. This page exists so the procedure is visible *before* it's needed, and so the conviction that backs it ("public-by-default with explicit, narrow opt-out paths") is on the record from the start rather than retrofitted later.

The opt-out lever has been built and exercised on a synthetic test contributor; the procedure is documented; the audit log path is set up. When the first real request lands, the body responds at the speed of the request, not at the speed of building.
