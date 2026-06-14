# Model Executor Proof Ledger

This directory is the substrate-native home for model executor proof runs.

Each run lives in its own JSON record so parallel work does not contend on
`docs/system_audit/model_executor_runs.jsonl`. The JSONL file remains a legacy
export/cache shape for existing gates and readers.

Validate the native proof-run contract:

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/model-executor-proof-ledger.fk form-stdlib/tests/model-executor-proof-ledger-band.fk
```

Check the four-way manifest gate:

```bash
cd form && bash scripts/fourth-arm-gate.sh model-executor-proof-ledger
```

The JSONL compatibility cache is no longer the coordination source. New proof
runs land as native records first; any JSONL export is a compatibility view.

The Form-native record contract lives in
`form/form-stdlib/model-executor-proof-ledger.fk`, with the teaching surface in
`docs/coherence-substrate/model-executor-proof-ledger.form`.
