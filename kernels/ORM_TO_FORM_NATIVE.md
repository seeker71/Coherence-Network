# DB → Form-native: the data contract lives in Form blueprints

> Urs (2026-05-30): "we don't need full SQLAlchemy support. We need to read and
> write to the DB, represent the DB tables in Form blueprints, and update the
> schema when the data contract changes — or vice versa. Migrate / manage the
> tables."

That reframes the goal. The earlier plan here (wrap SQLAlchemy behind a
`SubstrateStore` interface and keep it as the backend) is **composted** — we are
not emulating an ORM. We own the schema. The **Blueprint is the schema**, DDL
and DML are **projections** of the blueprint into a dialect, and a migration is
a **blueprint diff** rendered to `ALTER`. Four small things, not an ORM:

1. **Represent** tables as Form blueprints. *(done — `db-schema.fk`)*
2. **Project** a blueprint → DDL (CREATE/INDEX) per dialect. *(done)*
3. **Migrate** via blueprint diff → ALTER, both directions. *(forward done;
   introspection — live schema → blueprint — is the open "vice versa")*
4. **Read/write** rows ↔ Records through a thin DB driver. *(open)*

## The model (NUMS-Go: cells are part of what the struct IS)

```
table   = (name, columns, uniques, indexes)     ← the Blueprint of a table
column  = (name, logical-type, nullable, default)
row     = a Record over that blueprint
dialect = (name, int-type, str-type, text-type, datetime-type, pk-clause)  ← DATA
```

`logical-type ∈ {pk int str text datetime}`. The substrate's whole live schema
(`substrate_nodes`, `substrate_cells`, `substrate_agents`,
`substrate_relationships`) is exactly these types — no ORM machinery needed to
express it.

**One engine, dialect as data** (core-abstraction-first). sqlite and postgres
are not parallel code paths; they are two `mk-dialect` values the same renderer
reads. The only cells that differ are the autoincrement PK
(`INTEGER PRIMARY KEY AUTOINCREMENT` vs `SERIAL PRIMARY KEY`) and `str`'s
physical type (`TEXT` vs `VARCHAR`). A third dialect is a new literal, not new
code.

## What's proven (`form/form-stdlib/db-schema.fk`, band 11111 three-way)

The real substrate tables, defined as Form blueprints in
[`db-schema-band.fk`](../form/form-stdlib/tests/db-schema-band.fk), project to:

- `create-ddl nodes SQLITE` / `... POSTGRES` → the correct `CREATE TABLE` for
  each dialect from **one** blueprint.
- `index-ddls nodes` → the `CREATE INDEX` statements.
- `migration-ddls nodes-v0 nodes SQLITE` → **regenerates orm.py's hand-written
  `_ensure_columns` patches verbatim**:
  `ALTER TABLE substrate_nodes ADD COLUMN domain INTEGER NOT NULL DEFAULT 0`
  and `ALTER TABLE substrate_cells ADD COLUMN access_recipe TEXT` now *fall out*
  of `(blueprint-without-col → blueprint-with-col)`. The migration that was
  maintained by hand is a projection of the contract.

This file is **pure** — it computes SQL strings, it does not run them — so it is
three-way parity-tested (Go/Rust/TS, 0 divergent) like every other engine here.

## What's open (the next breaths, in order)

1. **DB driver natives** — `sql_exec(dsn, ddl)` and `sql_query(dsn, sql) → rows`.
   This is the side-effecting leaf, so it does NOT get three-way value-parity
   (a side effect can't be diffed three ways); it gets one reference
   implementation per kernel and an integration test against a real **sqlite**
   file (dev/test dialect — no server, cheap). The **SQL strings** it runs are
   already three-way verified by the pure engine; only execution is per-kernel.
   sqlite first (dev/test), postgres via the same native signature for prod.
2. **Introspection — the "vice versa."** `introspect(dsn, table) → blueprint`
   by reading `PRAGMA table_info` (sqlite) / `information_schema.columns`
   (postgres). Then `schema-diff (introspect live) (contract blueprint)` names
   the drift in *either* direction: contract ahead of DB → forward ALTER; DB
   ahead of contract → the contract file needs the column. Same diff engine,
   both directions.
3. **Row ↔ Record read/write.** A row is a Record over the table blueprint;
   `insert table record`, `select table where`, `update`. Field types come from
   the blueprint, so serialization (datetime ↔ text, etc.) is contract-driven.
4. **Wire the contract into the body.** The substrate tables' blueprints live in
   a `.fk` (or interned substrate cells), and `init_db` / `_ensure_columns`
   become "render + apply the projections" instead of hand-maintained SQL. The
   data contract has one home, in Form, and the DB follows it.

## Why this is the right shape

- **Traceability**: every DDL/migration string has a recipe provenance — you can
  ask the substrate *why* a column exists (which blueprint, which diff).
- **No drift**: the hand-written `_ensure_columns` was a place the contract and
  the DB could silently disagree. A projection can't disagree with itself.
- **Dogfooding the center**: the substrate's own persistence shape is expressed
  in the substrate's own language, content-addressed like everything else.
- **Small**: four operations and a dialect table — not an ORM, not SQLAlchemy.

The pure engine (steps 1–2 of the model) is the spec made executable; the driver
and introspection (open items above) are the remaining I/O leaves.
