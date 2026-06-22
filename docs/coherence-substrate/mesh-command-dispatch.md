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

| is-command | for-me (directed) | lineage (sender) | `mc-route` |
|:---:|:---:|:---:|:---|
| 1 | 1 | 1 | **act** — wake a live local instance |
| 1 | 1 | 0 | **refuse** — directed command from outside the lineage (set aside, traced) |
| else | | | **ignore** — chatter, broadcasts, non-commands |

A broadcast (`to_node = null`) is `for-me = 0`, so it never triggers a run.

## Recognition — how the device knows a dispatch is its own

The bus is a **public, open channel**: a message can arrive wearing any name, including
`claude-sema-cloud`. So before a device acts, it recognizes the dispatch as really from its own
cloud instance — the same *don't act on an unverified name* the body keeps elsewhere (the
membrane recognizing self, axiom-4, not a fortress against enemies). Four things have to line
up; if any one doesn't, nothing runs:

1. **directed + command + lineage** — the recipe (`mc-route → act`).
2. **recognized signature** — the cloud instance signs `HMAC-SHA256(key, "<to_node>\n<text>")`
   into `payload.sig`; the device recomputes with the **lineage key** it shares with that
   instance. The key never crosses the wire, so a name alone can't stand in for the instance.
   Unrecognized → set aside (`UNKNOWN`).
3. **listening** — `~/.coherence-network/mesh-receiver.listening` exists. Absent → the receiver
   is resting (`REST`), no run. To rest it: `rm` the flag.
4. **permission mode** — `claude -p` runs with `payload.permission_mode` (clamped to
   `default | acceptEdits | bypassPermissions | plan`), default `default`. The cloud instance
   asks for `bypassPermissions` explicitly when a dispatch needs full-agent reach.

Every message and capture is logged to `~/.coherence-network/mesh-receiver.log`; every capture
is written to `~/.coherence-network/mesh-captures/<msg_id>.txt` **before** the bus send, so a
strained edge never loses the work (`--resend` re-posts what was held).

## The dispatch contract (what the cloud instance sends)

```bash
key=$(cat ~/.coherence-network/mesh-lineage.key)        # shared by both instances
sig=$(printf '%s\n%s' "sema-macos" "$PROMPT" | openssl dgst -sha256 -hmac "$key" -hex | sed 's/^.*= *//')
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
scripts/install_mesh_command_receiver.sh        # launchd agent, polls every 120s, listening by default
scripts/mesh_command_receiver.sh --once         # one cycle by hand
rm ~/.coherence-network/mesh-receiver.listening # let it rest
```

The one open thread for autonomous cloud→device dispatch: the cloud instance needs the same
`mesh-lineage.key`. Until it holds the key, the device listens and acts on nothing it doesn't
recognize. A keypair — public key committed to the body, private key held only by the cloud
instance — is the more native next shape, so nothing shared needs to be secret at all.
