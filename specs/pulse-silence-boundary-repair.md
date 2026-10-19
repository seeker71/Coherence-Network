---
idea_id: pipeline-reliability
status: done
source:
  - file: pulse/store.bml
    symbols: [ws-changes, ws-now, ws-history]
  - file: pulse/native-store.bml
    symbols: [nw-commit, nw-recover]
  - file: pulse/import-history.bml
    symbols: [whi-import, whi-resume]
  - file: pulse/probe.bml
    symbols: [wp-round, wp-sample]
  - file: pulse/http.bml
    symbols: [ph-handle]
  - file: pulse/observe.bml
    symbols: [po-fixture]
  - file: pulse/web.bml
    symbols: [pw-render, pw-document]
  - file: pulse/html.bml
    symbols: [fh-escape, fh-document]
  - file: pulse/index.bml
requirements:
  - "R1: Three consecutive observed failures open a silence; three observed successes close it."
  - "R2: Closure preserves the re_enter choice, evidence count and window in silences.note."
  - "R3: GET /pulse/now reconciles durable evidence before returning unresolved silences."
  - "R4: An unresolved silence keeps overall at least strained; a silent severity keeps it silent."
  - "R5: Existing sample history, silence IDs and notes persist through native deployment."
  - "R6: Native HTML carries the current snapshot, daily evidence and complete silence/repair disclosures without a host web renderer or hydration payload."
  - "R7: Durable daily cards and exact range summaries retain direct-history counts and nearest-rank percentiles through publication and recovery."
done_when:
  - "The focused native application observation witnesses opening, closure, exact percentile ranks and idempotent recovery on a separate native store."
  - "The running native HTTP boundary returns current organs, history and silence receipts with the existing public shapes."
test: "cd form && ./fkwu ../pulse/observe.bml < a-private-fixture-config.json"
constraints:
  - "Implementation stays in application-owned Form/BML on the unchanged pinned fkwu."
  - "No fabricated successes, shortened history windows or weakened repair thresholds."
  - "Public API remains read-only; reconciliation derives only from durable observations."
---

# Pulse silence repair

A silence is a durable stop receipt. The native witness re-enters only when its
stored observations supply three consecutive successes, closing at the first
closing success. Its existing note field holds:

```text
boundary_repair_protocol: choice=re_enter; closed after N consecutive breathing samples; evidence_window=FIRST..LAST
```

`WitnessStore` is the reusable BML template for this movement. It reads the last
twenty raw samples, excludes explicit non-observations, retains the latest five
observed samples and derives the trailing run. An unresolved silence escalates
after five minutes. The native scheduler and `GET /pulse/now` use the same template,
so a missed scheduler reconciliation does not leave a stale open receipt.

The public snapshot stays coherent with the ledger: an unresolved silence keeps
the whole witness at least strained, and an unresolved silent receipt keeps it
silent. Historical uptime and exact nearest-rank p50/p95 exclude unobserved
samples. Additive daily counts and histograms accelerate those reads while raw
samples and the original silence IDs remain authoritative.

The focused application observation uses a separate native store, witnesses opening
and closure with their receipt, reads 1/7/30/90/180-day histories, and observes
idempotent journal replay with a retained torn tail. Native file-format import keeps
every raw row, original ID and note; startup completes the final live delta before
archiving the legacy files. Native Recipe pages and transaction frames own ongoing
persistence. Deployment observes the real HTTP contract against the private archive
before switching onto the original volume. A changed application boundary does not
call for kernel or sibling-kernel suites.

The public web page is a Form/BML read over that same checkpoint. Native escaped
HTML templates carry navigation, current status, daily evidence links and latency
sparklines. Day disclosures retain complete repair notes; the archive view has no
thirty-silence display cap. Traefik gives `/pulse` to this native owner and the
Next.js Pulse family and its separate origin/configuration doors are retired.

Daily cards and aligned binary summaries are derived indexes, not expiring
response caches. A transaction publishes changed cards and ancestor histograms
before advancing its checkpoint. Startup observes raw-day sequence coordinates to
derive or reconcile those indexes. Queries read an exact range cover and the
sliding boundary day. Whole raw pages reuse their committed time bounds; only a
page crossing the cutoff parses each sample time. The native HTTP client reads
through the peer's close rather than accepting a header-only packet as a body.

See also: [pulse witness](../pulse/README.md),
[boundary repair protocol](../docs/vision-kb/concepts/lc-boundary-repair-protocol.md).
