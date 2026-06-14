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

The Form-native record contract lives in
`docs/coherence-substrate/model-executor-proof-ledger.form`.
