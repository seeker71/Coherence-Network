# Idea: improvement-as-contribution

**Every improvement to hosting, rendering, or generation earns CC when tracked.**

## Problem

Infrastructure contributions are invisible. Someone writes a faster GLTF renderer, a lower-latency hosting node, or a higher-quality image generator — and there is no mechanism to register that work, let it compete alongside the original, and earn CC proportional to how much it gets used. Committee selection or manual promotion becomes the only path, which is slow and introduces politics. The improvement itself carries the proof of value; usage is the verdict.

## Desired Capabilities

- Any contributor can fork an existing provider (renderer, generator, hosting node) and register a new version with a `parent_id` link.
- Both the original and the fork remain active simultaneously. Neither is deprecated by the act of forking.
- When a render event, generation event, or hosting request resolves, CC flows to whichever version was actually used — at the standard share (15% renderer / 5% host node default).
- A comparison endpoint shows usage counts and CC earned per version, making competitive standing visible.
- The improvement registry is queryable: "which versions of renderer X exist, how much has each earned, which is winning?"

## Spec Links

- [improvement-as-contribution](../specs/improvement-as-contribution.md)

## Absorbed Ideas

_none_
