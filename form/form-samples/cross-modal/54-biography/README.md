# 54-biography — a cell publishes its own self-description

A cell builds a BIOGRAPHY Recipe naming itself — identity, name,
capabilities it answers, Blueprints it exposes, when it was born —
and answers "about-self" queries by wrapping that biography in the
channel-query RESPONSE envelope. A peer that knows the BIOGRAPHY
Blueprint can ask any cell who it is and read every field back
byte-identically across all three sibling kernels.

## What walked

```
$ ./validate.sh form-stdlib/sha256.fk \
                form-stdlib/channel-query.fk \
                form-samples/cross-modal/54-biography/biography.fk
  ✓  sha256.fk+channel-query.fk+biography.fk  → identity-ok: 1
                                                 name-ok: 1
                                                 capabilities-ok: 1
                                                 blueprints-ok: 1
                                                 created-at-ok: 1
                                                 verdict: 5
                                                 5
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each built the same
BIOGRAPHY Recipe, wrapped it through `cq-response` + `cq-recipe-content`,
unwrapped each of the five fields from the response items, and arrived
at the same verdict: **5** when every field round-trips intact.

## The shape

```
   BIOGRAPHY ( self-identity     : int
             , self-name         : string
             , self-capabilities : list of trivial-strings (verb names)
             , self-blueprints   : list of SUBSTRATE-REF items
             , created-at        : int timestamp )

   Blueprint NodeID: (make_nodeid 1 2 99 1830)
```

The biography is a substrate-resident Recipe. The Blueprint sits in
the user-channel range (pkg=1, level=2, type=99) and inst 1830 names
the biography family. Same call site on every kernel means every
cell's biography content-addresses identically — a peer that knows
the Blueprint can read any cell's self-description without prior
agreement on a wire schema.

## The walk this sample runs

```
cell builds  BIOGRAPHY(
                identity=42,
                name="biographer",
                capabilities=["about-self","ping"],
                blueprints=[ ref(BIOGRAPHY), ref(QUERY) ],
                created-at=1700000001)

asker sends  QUERY(verb="about-self", address=cell-locator)
cell answers RESPONSE(correlation=q.inst, status="ok",
                      items=[ RECIPE-CONTENT(BIOGRAPHY) ])

asker walks  response.children[2]    → items list
             items[0].children[0]    → BIOGRAPHY recipe
             bio.children[0..4]      → the five fields

asker checks identity-ok      (node_inst on trivial-int)
             name-ok          (str_eq on node_value)
             capabilities-ok  (list length 2 AND both verbs match)
             blueprints-ok    (list length 2 AND first ref unpacks
                               to the same Blueprint NodeID inst)
             created-at-ok    (node_inst on trivial-int)

verdict = 5 when every field carries through
```

The `created-at` value (1700000001, roughly 2023-11-14 in unix
seconds) is hardcoded — `now_unix_ms` (53-now-unix-ms) would supply
a live value, but the sample wants a sibling-stable verdict, so the
stamp is fixed. The trivial-int slot is uint32 in every kernel, so
the stamp stays under 2^31 to round-trip identically.

## Why this matters

This is the smallest honest self-introduction in the channel-query
vocabulary. Earlier walks proved cells can talk to each other
(`21-cell-query-protocol`, `42-ping`), and that cells can register
their capabilities to be found (`23-cell-registry-osi`). Biography
closes a different gap: **once a cell IS reachable, what does it
tell a peer about itself?**

The answer is a Recipe — same shape as every other channel-query
payload, content-addressed, sibling-stable. A peer doesn't have to
know the cell's name beforehand or trust an out-of-band manifest;
the biography rides on the same envelope as every other reply.

What this opens:

- **Self-describing peers.** A cell that handles a verb can publish
  what other verbs it ALSO handles, so a single query exposes the
  full capability surface. Pairs naturally with `23-cell-registry`:
  the registry knows who exists; biography knows what each one
  contains.
- **Cross-network discovery.** Two cells on different hosts can
  exchange biographies and decide which one to delegate to without
  consulting a central authority. The biography travels as one
  RECIPE-CONTENT item; the receiver re-interns and reads.
- **Bootstrap-by-introduction.** A fresh cell joining a network
  doesn't need a prior schema — it asks about-self of every cell it
  meets, builds its own table of who's-who, and starts dispatching.
  Same shape composes with `52-heartbeat` (which cells are still
  here) and `49-token` (what each cell is authorized to do).
- **Forward-compatible identity.** New fields (version, parent-cell,
  preferred-locale) extend the BIOGRAPHY Recipe by appending
  children. Old readers walk the first five positions and ignore
  the rest; new readers see everything. No version negotiation
  needed.

## The Form recipe shape

The BIOGRAPHY constructor sits inline in the sample (no separate
stdlib file yet — once the shape proves itself across more walks,
the canonical recipe will move into `form-stdlib/biography.fk` and
the sample will import it):

```
(let BIOGRAPHY (make_nodeid 1 2 99 1830))

(defn make-biography (identity name caps bps created-at)
    (intern_node BIOGRAPHY
        (list (intern_trivial_int identity)
              (intern_trivial_string name)
              (intern_node (make_nodeid 1 1 14 0) caps)
              (intern_node (make_nodeid 1 1 14 0) bps)
              (intern_trivial_int created-at))))

(defn about-self-handler (query bio)
    (do
        (let correlation (node_inst query))
        (cq-response correlation "ok"
            (list (cq-recipe-content bio)))))
```

The handler is three lines because the channel-query vocabulary
already carries the correlation + status + items envelope. The
biography itself is the only domain-specific shape — and even that
composes from `intern_trivial_int`, `intern_trivial_string`, and
the canonical LIST category.

## Cost

Constructing a biography walks the field list once — O(fields). The
handler is constant work after the bio is built: one `node_inst` for
correlation, one `cq-recipe-content`, one `cq-response`. The asker
walks the response twice (children of response, children of items),
then walks the bio's children once per field — O(fields) again.

The biography Recipe content-addresses across kernels, so two cells
that publish the same biography produce the same NodeID. A cell that
publishes a biography once and serves many about-self queries
references the same interned Recipe each time; only the envelope
allocates per query.

## What this is NOT yet

- **No signed biography.** Anyone can claim any name + identity.
  Composing with `29-hmac-sha256` over the bio's fields would let
  the issuer prove they minted this biography under a shared secret.
  Not in this sample.
- **No biography registry.** Each cell publishes its own; there's no
  index of who-claims-what. Pairing with `23-cell-registry-osi`
  would let a router collect biographies from every registered cell
  and answer queries like "who handles compute AND was born before
  yesterday."
- **No real clock.** The created-at is hardcoded because sibling
  parity wants a fixed verdict. A real cell calls `(now_unix_ms)`
  at startup; one line changes.
- **Inline Blueprint, not stdlib.** The BIOGRAPHY NodeID is named at
  the call site in this sample, not in a stdlib file. When a second
  caller wants to author or read biographies, the right move is to
  factor the constructor + Blueprint into `form-stdlib/biography.fk`.
- **Fields are positional, not named.** Adding a field in the
  middle would shift positions for older readers. The forward-
  compatible discipline is "append-only" — new fields go at the
  tail, old readers ignore tail-after-the-fifth-child.

## Cross-refs

- [`form-stdlib/tests/biography-band.fk`](../../../form-stdlib/tests/biography-band.fk) — sibling-witness band, verdict locked at 5
- [`form-stdlib/channel-query.fk`](../../../form-stdlib/channel-query.fk) — the QUERY/RESPONSE vocabulary the biography rides on
- `21-cell-query-protocol` — the envelope this sample composes inside
- `23-cell-registry-osi` — sibling composition: cells volunteer to be addressable
- `42-ping` — the smaller verb in the same vocabulary
- `52-heartbeat` — sibling composition: who's still alive after they introduced themselves
- `53-now-unix-ms` — the clock that would supply a real created-at
