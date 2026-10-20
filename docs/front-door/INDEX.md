# A companion for everyday work

Bring a question, an unfinished idea, or something you want to make. The Coherence
skill guides the conversation; MCP connects an assistant to published knowledge
and authorized actions. The person chooses the pace and what leaves the conversation.

| Start here | What it offers |
|---|---|
| [Existing Sema GPT](https://chatgpt.com/g/g-6a4a77627dbc819180a16645f5662625) | The existing ChatGPT door recorded by the Mac and Android invitation clients; [maintainer update guide](../integration/chatgpt-setup.md) |
| [Everyday starters and connection choices](connectors.md) | Mentorship, business ideas, design, creation, research, and collaboration |
| [Coherence skill](../../skills/coherence-network/SKILL.md) | Companion practice in a host that supports skills |
| [MCP setup](../../mcp-server/README.md) | Local stdio server and tool boundaries |
| [Public assistant contract](../../web/public/llms.txt) | Public reads, capability limits, and the boundary before publishing |
| [GPT Action schema](openai-gpt-action.yaml) | Supported REST reads, native lookup, and explicit public submission |

## What is available

The hosting assistant supplies its reasoning and available browsing, design, and
creation tools. Coherence adds practice and relevant network ideas, concepts,
sources, and contribution traces. An unavailable capability stays named; a useful
draft can still be completed in the conversation.

Public structural reads include cells, equivalent shapes, and lattice statistics.
`POST /api/substrate/grounded-ask` carries deployed native lookup when its host
passes runtime checks; a miss or unavailable carrier is an honest result.
Local `form-cli ask` enters the fkwu body.

## What sharing means

`POST /api/substrate/ingest` writes to the publicly readable lattice. A chosen
`status: offered` label does not create private storage or a moderation queue.
Before a write, show the destination, exact content, attribution, and visibility;
use the owner's explicit authorization for that content. Ordinary help, a pause,
and a request to remember something do not authorize publication.

Conversation retention and privacy are governed by the hosting assistant.
These public endpoints do not provide a private family workspace, cross-person
memory, or automatic continuity. Private source material stays out of public
artifacts; a person can choose a minimal, non-sensitive summary to share.

Maintainers start with [the current runtime floor](../shared/agent-start-packet.md).
