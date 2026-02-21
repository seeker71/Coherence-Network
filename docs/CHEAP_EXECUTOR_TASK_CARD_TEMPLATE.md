# Cheap Executor Task Card

goal: |
  <One sentence>

files_allowed:
  - /path/to/file1.py
  - /path/to/file2.ts

done_when:
  - "<Exact check command output phrase or command exit condition>"

commands:
  - "<exact command 1>"
  - "<exact command 2>"

constraints:
  - "No tests unless listed"
  - "No extra files"
  - "No extra edits"

proof_record:
  destination: docs/system_audit/model_executor_runs.jsonl
  fields:
    - model_used
    - input_tokens
    - output_tokens
    - attempts
    - commands_run
    - pass_fail
    - failure_reason
