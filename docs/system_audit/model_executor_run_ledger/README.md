# Model Executor Proof Ledger

This directory is the substrate-native home for model executor proof runs.

Each run lives in its own JSON record so parallel work does not contend on
`docs/system_audit/model_executor_runs.jsonl`. The JSONL file remains a legacy
export/cache shape for existing gates and readers.

Validate native records:

```bash
python3 scripts/model_executor_proof_ledger.py validate
```

Export native records as JSONL for legacy readers:

```bash
python3 scripts/model_executor_proof_ledger.py export-jsonl
```

Import legacy JSONL rows into native records, then refresh and check the cache:

```bash
python3 scripts/model_executor_proof_ledger.py import-jsonl
python3 scripts/model_executor_proof_ledger.py sync-jsonl --output docs/system_audit/model_executor_runs.jsonl
python3 scripts/model_executor_proof_ledger.py check-jsonl
```

`check-jsonl` compares projected rows as a multiset, so older cache ordering can
remain stable while the native records become the coordination source.

The Form-native record contract lives in
`docs/coherence-substrate/model-executor-proof-ledger.form`.
