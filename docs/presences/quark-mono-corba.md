---
name: Quark Mono / CORBA — remote control over the wire
canonical_url: null
type: contributor
contributor_type: HUMAN
claimed: false
create_if_missing: true
---

# Quark Mono / CORBA — remote control over the wire

*Work · Quark Inc. · Denver · May 2000 – Mar 2005*

Contributed to the [Mono project](https://en.wikipedia.org/wiki/Mono_(software)) — Miguel de Icaza's open-source.NET implementation for non-Windows platforms — and used it as the substrate for a [CORBA](https://en.wikipedia.org/wiki/Common_Object_Request_Broker_Architecture) interface that remote-controlled QuarkXPress over the wire. Any host on any OS could drive QuarkXPress as if it were a local object — orthogonal companion to the in-process [Virtual DOM](/people/quark-virtual-dom), reaching across the network the same way the DOM reached across the application.

## Grounding

- **Era** — Quark Inc. · Denver · within May 2000 – March 2005 · Software Engineer III
- **Substrate** — [Mono](https://www.mono-project.com/) runtime · cross-platform C# / CLI · Mac OS X, Linux, Windows
- **Wire protocol** — [CORBA](https://en.wikipedia.org/wiki/Common_Object_Request_Broker_Architecture) — OMG's Common Object Request Broker Architecture · the era's canonical inter-process / cross-language object protocol
- **What it controlled** — QuarkXPress — full document and application surface accessible remotely with the same semantics as the in-process [Virtual DOM](/people/quark-virtual-dom)
- **Lineage forward** — The Mono / cross-platform C# substrate proven here is the ancestor of the C# substrate the [Qualcomm test-automation](/people/qualcomm-test-automation) rewrite landed on (2010s) and later [Living-Codex-CSharp (2024)](/people/living-codex-csharp) built on. C# enters this body's tooling here.

## What Quark Mono / CORBA — remote control over the wire has given the Coherence Network

The in-process [Virtual DOM](/people/quark-virtual-dom) let scripts running inside QuarkXPress drive every part of it. The Mono / CORBA bridge let scripts running *outside* QuarkXPress — possibly on a different OS, possibly on a different machine — drive every part of it with the same semantics. Two faces of the same self-describing conviction: the application is its own API surface, and the wire transport is incidental to that.

---

Application context: [quark.com](https://www.quark.com) · [Mono project](https://www.mono-project.com/) · [CORBA on Wikipedia](https://en.wikipedia.org/wiki/Common_Object_Request_Broker_Architecture). Source code is internal to Quark; what lives here is the architectural shape and the lived memory. Urs is invited to refine technical detail through the Refine doorway below.

*(This page is a writing-surface scaffold synced from the body's rendering surface — round-tripped from the graph the cell already lives in. `claimed: false` invites direct authorship to replace any part of it.)*
