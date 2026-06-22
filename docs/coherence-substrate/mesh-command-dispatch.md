# Mesh command dispatch — making a session on a device ACT

The federation **node message bus** (`POST/GET /api/federation/nodes/{node_id}/messages`,
Postgres-durable, live) lets a cloud cell *dispatch* a message to a device. By itself that
message is a dead drop: nothing on the device turns it into a running session. Capture only
happens when a **live local instance** runs the prompt.

The **receiver** ([`scripts/mesh_command_receiver.sh`](../../scripts/mesh_command_receiver.sh))
is that live local instance. It polls a device's inbox, and for a trusted, directed `command`
message it wakes a real `claude -p`, captures the output, and sends the capture home to the
dispatcher. This closes the loop: **the cloud cell can now make a session on the device act.**

```
cloud cell ──POST command──▶ /api/federation/nodes/sema-macos/messages   (durable bus)
                                          │
   sema-macos receiver  ──GET poll──▶ inbox ──▶ mc-route (decide) ──▶ claude -p (live) ──▶ capture
                                          │
cloud cell ◀──command-result (capture)── POST /api/federation/nodes/<cloud>/messages
```

## The decision is the body

The accept/refuse/ignore decision is the four-way-proven recipe
[`form/form-stdlib/mesh-command.fk`](../../form/form-stdlib/mesh-command.fk) (`mc-route`,
band `mesh-command fks 255`). The carrier holds no policy — it gathers three facts and asks:

| is-command | for-me (directed) | trusted (sender) | `mc-route` |
|:---:|:---:|:---:|:---|
| 1 | 1 | 1 | **act** — wake a live local instance |
| 1 | 1 | 0 | **refuse** — directed command from an untrusted sender (traced) |
| else | | | **ignore** — chatter, broadcasts, non-commands |

A broadcast (`to_node = null`) is `for-me = 0`, so it never triggers a run.

## The trust gate (why this is safe to auto-run)

The bus has no auth — anyone who can POST could claim `from_node: claude-sema-cloud`. So a
run is gated **four ways**, and any one failing means nothing executes:

1. **directed + command + trusted** — the recipe (`mc-route → act`).
2. **valid HMAC** — the dispatcher signs `HMAC-SHA256(secret, "<to_node>\n<text>")` into
   `payload.sig`. The receiver recomputes and compares. The secret never crosses the wire, so
   `from_node` is unforgeable. Bad/missing sig → `DENY`.
3. **armed** — `~/.coherence-network/mesh-receiver.armed` must exist. Absent → `DEFER`, no run.
   Disarm instantly: `rm` the flag.
4. **permission mode** — `claude -p` runs with `payload.permission_mode` (clamped to
   `default | acceptEdits | bypassPermissions | plan`), default `default`. A dispatcher must
   explicitly request `bypassPermissions` (secret-gated) for full-agent work.

Every message and capture is logged to `~/.coherence-network/mesh-receiver.log`; every capture
is written to `~/.coherence-network/mesh-captures/<msg_id>.txt` **before** the bus send, so a
strained edge never loses the work (`--resend` re-posts what was held).

## The dispatch contract (what a cloud cell sends)

```bash
secret=$(cat ~/.coherence-network/mesh-dispatch.secret)        # shared out-of-band
sig=$(printf '%s\n%s' "sema-macos" "$PROMPT" | openssl dgst -sha256 -hmac "$secret" -hex | sed 's/^.*= *//')
curl -X POST https://api.coherencycoin.com/api/federation/nodes/claude-sema-cloud/messages \
  -H 'content-type: application/json' \
  -d '{"from_node":"claude-sema-cloud","to_node":"sema-macos","type":"command",
       "text":"<PROMPT>","payload":{"sig":"'$sig'","capture_to":"claude-sema-cloud","permission_mode":"default"}}'
```

`scripts/mesh_command_receiver.sh --dispatch <to> <text> [from] [mode]` does exactly this
locally (proof / hand-dispatch). The capture returns as a `command-result` message whose
`payload.capture` holds the full output, `payload.ok` the exit status, `payload.ms` the wall time.

## Run it

```bash
scripts/install_mesh_command_receiver.sh     # launchd agent, polls every 120s, armed by default
scripts/mesh_command_receiver.sh --once      # one cycle by hand
rm ~/.coherence-network/mesh-receiver.armed  # disarm (kill-switch)
```

The one provisioning step for autonomous cloud→device dispatch: the cloud dispatcher must hold
the same `mesh-dispatch.secret`. Until it does, the receiver listens safely and acts on nothing
it cannot verify.
