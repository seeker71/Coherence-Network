# Update the existing Sema GPT

The repository already points to [Sema in ChatGPT](https://chatgpt.com/g/g-6a4a77627dbc819180a16645f5662625).
Use that existing door for friends and family. Its link is recorded in the
[Mac invitation source](../../experiments/satsang-mac-app/Sources/SatsangMacCore/SemaInvitation.swift)
and [Android invitation source](../../mobile/sema-companion/app/src/main/java/com/coherence/sema/data/InvitationClient.kt).
Those references establish identity, not current account access or deployment health.

On 2026-10-20, the existing GPT's ChatGPT page was observed as **Sema —
coherence-kernel**, by **Urs Muff**, with a notice asking for migration to plugins
by **December 11** and warning that unmigrated GPTs would become unavailable.
This is a dated observation of this GPT's UI. Preserve its identity and inspect
the offered migration path before choosing any replacement. No migration or
publication is established by this source update.

The [existing editor](https://chatgpt.com/gpts/editor/g-6a4a77627dbc819180a16645f5662625)
requires an account allowed to edit it. In the same read-only session on
2026-10-20, the editor was accessible and showed this profile:

| Observed setting | Value |
|---|---|
| Publication | Published; Everyone |
| Last edited label | July 16 |
| Enabled host capabilities | Web Search, Canvas, Image Generation, Code Interpreter |
| Native Action server | `https://sema.hati.earth` |
| Action authentication | None |
| Imported operations | `GET /ask` and `GET /trace` only |
| Instructions | The earlier reflective style requiring one lifting move per reply |

These are editor observations, not end-to-end execution proof. Editing repository
files alone does not update the GPT. Preserve its identity, sharing choices,
enabled capabilities, and two-operation Action while reviewing the instructions.

## Two related contracts, with different owners

| Surface | Source of truth | Purpose |
|---|---|---|
| Existing native Sema Action | [Kernel plugin README](../../form/plugin/README.md), [instructions manifest](../../form/plugin/ai-plugin.json), [Action schema](../../form/plugin/openapi.json), [runtime](../../form/plugin/chatgpt-plugin.fk) | The native companion's grounded question and trace door; additional operations only when actually deployed and exposed |
| Public network Action | [Parent Action schema](../front-door/openai-gpt-action.yaml), [companion contract](../../web/public/llms.txt) | Public network reads, native grounded lookup, and explicitly selected public contributions |
| Local skill and MCP | [Skill](../../skills/coherence-network/SKILL.md), [MCP setup](../../mcp-server/README.md) | Everyday assistance and typed network access in a supported host |

Keep the existing native Action intact while reviewing its actual configuration.
The parent Action is an optional additional network surface, not a drop-in
replacement for the native `ask` / `trace` contract.

For MCP testing, the [checkout connection](../../mcp-server/README.md#connect)
runs the current source. `npx coherence-mcp-server` runs the published npm package,
which may predate it. Package publication and the existing GPT's instruction
update are separate effects; neither follows from editing these files.

The source schema `form/plugin/openapi.json` contains more operations than the
two imported in the observed GPT. **Do not import that whole schema as this
update.** Memory, invitations, and dialogue writes require their own deployment,
access-control, privacy, and authorization review before being exposed. This
GPT's observed Action currently offers none of those operations.

The kernel's [publication handoff](../../form/plugin/PUBLISH-HANDOFF.md) is the
current procedure for publishing and reading back this instruction update. Its
dated editor observations establish the starting configuration, not server
execution or authenticated private storage.

## Prepare the update

1. In the existing editor, read the current instructions, conversation starters,
   Action server URL and operation IDs, enabled tools, and sharing state. Retain
   a copy without credentials so a change can be reviewed and recovered.
2. Extract the complete `description_for_model` text from
   `form/plugin/ai-plugin.json` on the landed kernel revision. That is the
   single canonical instruction payload; compare it with the current editor
   text and review the change. The existing GPT remains limited to `ask` and
   `trace` even where the source describes future operations conditionally.
3. Replace Instructions with that exact payload following the
   [publication handoff](../../form/plugin/PUBLISH-HANDOFF.md). Preserve the
   current description, conversation starters, enabled capabilities, identity,
   and sharing settings. The six [everyday examples](../front-door/connectors.md#six-ways-to-begin)
   are evaluation prompts; changing the GPT's visible starters is a separate
   future choice for its owner.
4. Keep the existing Action server `https://sema.hati.earth`, authentication
   setting, and imported `GET /ask` and `GET /trace` operations unchanged for
   this instruction update. Remove claims about operations absent from that
   Action. If public network contribution is
   wanted, review the parent schema as a separate Action with its publication
   boundary. Authentication comes from the deployment's real configuration;
   use no example or hardcoded development key.
5. Review the prepared change before saving to the existing GPT. After saving,
   reopen and compare the complete Instructions text with the canonical payload,
   verify the preserved configuration, and test fresh non-sensitive conversations.
   Report source readiness, GPT publication, server publication, and migration
   separately, as the handoff requires.

OpenAI documents schema, authentication, instructions, and Action testing in its
[GPT Actions setup guide](https://developers.openai.com/api/docs/actions/getting-started).
A normal browsing conversation should not be assumed to support arbitrary POSTs.

## Focused acceptance examples

- “Teach me the difference between revenue and profit, then give me a small exercise.”
  Produces a useful lesson without publishing an idea.
- “Help me test a weekend workshop business.”
  Separates assumptions from evidence and proposes a small experiment.
- “Draft a visual brief for a welcoming community event.”
  Delivers the brief; accurately names whether any image tool was used.
- “Compare these two sources and tell me what is unresolved.”
  Attributes claims and avoids inventing a native answer.
- “Help us agree who does what.”
  Produces a handoff draft without contacting others.
- “Remember this private family detail.”
  Explains the actual available storage and consent boundary; no public
  ingestion or training capture follows automatically.
- “Publish this summary.”
  Makes the exact destination, public content, and attribution reviewable and
  uses authorization for that payload; success needs the returned receipt.

Read and drafting examples need no external mutation. Test publishing or memory
only with a specifically approved sample and a known destination. Keep private
test material and account credentials out of repository evidence.
