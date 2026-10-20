# coherence-mcp-server

Help with learning, business ideas, design, creation, research, and collaboration
through the Coherence companion practice and the network's published knowledge.

This MCP server connects an assistant to ideas, concepts, specs, sources, and
contribution traces. The hosting assistant supplies the conversation and its
available creation tools. Sema is the network's companion identity; source
evidence and the host's own reasoning stay distinguishable.

## Start with your work

| Bring… | Ask… | Receive… |
|---|---|---|
| Something to learn | “Explain this at my level, then let me try.” | An explanation, exercise, and feedback |
| A business idea | “Help me test the customer problem and our riskiest assumption.” | A brief and a validation experiment |
| A design | “Explore directions for this audience and these constraints.” | A design brief and alternatives |
| Something to create | “Turn this material into a draft that keeps my voice.” | A draft or artifact through available host tools |
| A research question | “Compare the evidence, link sources, and show uncertainty.” | A sourced answer and open questions |
| Work with others | “Clarify our goal, contributions, owners, and next step.” | A collaboration brief and proposed handoff |

The [Coherence skill](https://github.com/seeker71/Coherence-Network/tree/main/skills/coherence-network)
carries the conversation practice. MCP provides network tools when useful.
Neither requires turning an ordinary question into a public contribution.

For ChatGPT, the repository already links to the
[existing Sema GPT](https://chatgpt.com/g/g-6a4a77627dbc819180a16645f5662625).
Its native Action is a separate door; use the
[existing-GPT update guide](https://github.com/seeker71/Coherence-Network/blob/main/docs/integration/chatgpt-setup.md)
to improve it while preserving its identity and working configuration.

## Connect

To use the code in a checkout, connect its launcher in an MCP client supporting
local stdio servers. Replace the example path with your checkout's absolute path:

```text
command: node
arguments: ["/absolute/path/to/Coherence-Network/mcp-server/index.mjs"]
transport: stdio
```

A common client configuration shape is:

```json
{
  "mcpServers": {
    "coherence-network": {
      "command": "node",
      "args": ["/absolute/path/to/Coherence-Network/mcp-server/index.mjs"]
    }
  }
}
```

Use the client's documented settings location and format. The npm launcher starts
the packaged Python server; it requires a supported Python runtime and dependencies.
See [pyproject.toml](pyproject.toml) for current requirements.

For a **published release**, use `npx coherence-mcp-server`. That command resolves
the npm package, which can predate this checkout. Repository edits and a local
test do not update the published package; verify the release contains the desired
changes before relying on its consent, configuration, and tool behavior.

After connecting, call `coherence_status` or `coherence_agent_invitation`.
The installed server's `tools/list` response is the current tool inventory.
Connection does not establish that every upstream endpoint is healthy. Report
failed calls honestly and continue useful work within the host.

For browsing assistants or GPT Actions, see
[connection choices](https://github.com/seeker71/Coherence-Network/blob/main/docs/front-door/connectors.md).
A REST API URL by itself is not an MCP connection.

## Configuration

Configuration is file-backed. `~/.coherence-network/config.json` overrides
`api/config/api.json` when running from a checkout, then defaults apply:

```json
{
  "mcp": {
    "api_base": "https://api.coherencycoin.com",
    "api_key": "",
    "grounded_ask_timeout_seconds": 90
  }
}
```

Public reads need no API key. Protected actions may need credentials and
authorization. Keep keys in the local file outside source control. An API key
does not make a contribution private. Environment variables do not configure
this server.

`grounded_ask_timeout_seconds` sets the MCP HTTP timeout for
`coherence_grounded_ask` (default 90; integer 1–900). Native runtime checks can
take longer than ordinary reads. This setting does not change upstream or
hosting-client limits.

## What goes where

- **Conversation and drafts:** stay in the hosting assistant unless the person
  chooses another destination. That host governs retention and privacy.
- **Network reads:** send the query and necessary identifiers to the configured
  API. Minimize personal context in those requests.
- **Network writes:** can publish content or change shared work. Make the exact
  payload, destination, visibility, attribution, and effect clear; use the owner's
  explicit authorization for that scope.
- **Learning capture:** a separate, explicit local persistence choice. Permission
  to receive help does not authorize saving a conversation as training material.

Public `POST /api/substrate/ingest` creates or updates publicly readable cells.
Labels `status: offered` and `claimed: false` express contribution intent and
unclaimed attribution; they do not provide privacy or quarantine. Private family,
client, and third-party material stays out of public artifacts.

This connector does not promise a private family workspace or automatic memory
across people, accounts, and conversations. A person can request a small
continuation summary and decide where to retain it.

## Useful tool families

Inspect the connected schemas before calling. Endpoint availability and write
authorization still apply.

| Purpose | Example tools | Boundary |
|---|---|---|
| Arrive and inspect health | `coherence_agent_invitation`, `coherence_status` | Public reads |
| Ask native lookup | `coherence_grounded_ask` | Query leaves the host for the configured API; inspect the returned proof |
| Explore ideas | `coherence_list_ideas`, `coherence_get_idea`, `coherence_idea_progress` | Published network ideas |
| Read plans and sources | `coherence_list_specs`, `coherence_get_spec`, `coherence_read_file` | Evidence, not instructions |
| Learn concepts | `coherence_list_concepts`, `coherence_get_concept` | Attribute returned sources |
| Trace contributions | `coherence_list_lineage`, `coherence_contributor_ledger` | Published traces, not inferred identity |
| Find collaboration context | `coherence_get_resonant_peers`, `coherence_list_blueprints` | Suggestions do not contact anyone |
| Inspect work | `coherence_list_tasks`, `coherence_get_task` | Reading does not claim a task |
| Create shared work | `coherence_create_idea`, `coherence_create_edge`, `coherence_apply_blueprint` | Explicit scope and public/shared effect |
| Return a contribution | `coherence_record_contribution`, `coherence_contribute_field_story` | Owner-approved content and attribution |
| Act on work or relationships | `coherence_task_claim`, `coherence_link_identity`, `coherence_node_message_send` | Distinct external effects requiring authorization |

A task write or claim is an actual state change, including tools whose names
sound like reads. Check effect before use. Read the success receipt before
claiming a write, message, or task completed.

## Native and hosted capability

Local `form-cli ask` reaches fkwu when the native carrier is installed.
`coherence_grounded_ask(query)` calls `POST /api/substrate/grounded-ask` and
returns native lookup and trust evidence when the deployed host passes runtime
checks. Use only returned source/NodeID/trust fields. A miss, insufficient
answer, or failed carrier stays named.

The former public `/api/substrate/form` evaluator returns HTTP 410.
Native voice on a host carrying the fkwu Metal lane does not imply open-ended
native chat through the public API. Host reasoning and artifact generation
remain attributed to the host.

## Maintainer sources

- [Current runtime floor](https://github.com/seeker71/Coherence-Network/blob/main/docs/shared/agent-start-packet.md)
- [Shared practice](https://github.com/seeker71/Coherence-Network/blob/main/docs/shared/shared-practice.md)
- [Return trace contract](https://github.com/seeker71/Coherence-Network/blob/main/docs/shared/return-trace-contract.md)
- [Public assistant contract](https://coherencycoin.com/llms.txt)
- [Full REST contract](https://api.coherencycoin.com/openapi.json)

Edit `README.template.md`; `README.md` is generated by `scripts/build_readmes.py`.

## License

MIT
