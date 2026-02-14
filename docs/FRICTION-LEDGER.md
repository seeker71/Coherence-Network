# Friction Ledger

Track all justified blocking points as measurable friction events so we can reduce total energy loss over time.

## Principle

A block is valid only when it is explicit and measurable:

- reason
- risk avoided
- delay/cost impact
- owner
- unblock condition

## Machine Log

Append events to:

- `api/logs/friction_events.jsonl`

Each line is one JSON object.

## Event Schema

Required fields:

- `id` (string): stable event identifier
- `timestamp` (ISO8601 UTC): when the friction event was recorded
- `stage` (string): `idea|model|spec|acceptance|research|design|manifestation|validation|deploy`
- `block_type` (string): e.g. `missing_evidence`, `failing_test`, `unclear_intent`, `deploy_blocked`
- `severity` (string): `low|medium|high|critical`
- `owner` (string): responsible actor/team
- `unblock_condition` (string): concrete condition to clear block
- `energy_loss_estimate` (number): estimated value/energy loss for this event
- `cost_of_delay` (number): estimated delay cost
- `status` (string): `open|resolved`

Optional fields:

- `resolved_at` (ISO8601 UTC)
- `time_open_hours` (number)
- `resolution_action` (string)
- `notes` (string)

## Example Event

```json
{
  "id": "fric-2026-02-14-001",
  "timestamp": "2026-02-14T20:40:00Z",
  "stage": "validation",
  "block_type": "missing_e2e_proof",
  "severity": "high",
  "owner": "release-manager",
  "unblock_condition": "Public write/read flow passes against production API",
  "energy_loss_estimate": 18.0,
  "cost_of_delay": 6.0,
  "status": "open"
}
```

## Reporting

Generate ranked friction hotspots:

```bash
cd api && .venv/bin/python scripts/friction_report.py --window-days 7
```

JSON output for automation:

```bash
cd api && .venv/bin/python scripts/friction_report.py --window-days 7 --json
```

## Use In Gate Reviews

Before starting a new phase:

1. Review top `block_type` by `energy_loss_estimate`.
2. Resolve the highest-loss recurring source first.
3. Record resolution action and measure change in next window.
