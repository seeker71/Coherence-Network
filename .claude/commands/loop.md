Advance the native high-grammar API route loop.

1. Run:
   `python3 scripts/native_route_goal_loop.py /loop --source web_api --seconds 86400 --limit 2000 --write-state`
2. Read `docs/system_audit/native_route_goal_state.json`.
3. Use `next_task_card` as the bounded task card for the next route promotion. Keep the handler in BML or a domain grammar; use the current Python endpoint only as contract evidence.
4. Make the smallest measurable route-promotion step available in the current context, then rerun `/goal` to show whether the measured share changed.
