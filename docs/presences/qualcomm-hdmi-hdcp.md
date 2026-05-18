---
name: Qualcomm — Linux HDMI / HDCP kernel module
canonical_url: null
type: contributor
contributor_type: HUMAN
claimed: false
create_if_missing: true
---

# Qualcomm — Linux HDMI / HDCP kernel module

*Work · Qualcomm · Boulder · within Oct 2009 – Jan 2022 · Linux kernel contributor*

While at Qualcomm, contributed a Linux kernel module supporting **HDMI output with hardware encryption** for MSM-family SoCs. HDMI carries the visible signal; [HDCP](https://en.wikipedia.org/wiki/High-bandwidth_Digital_Content_Protection) — High-bandwidth Digital Content Protection — encrypts it in hardware so a downstream display can prove it is licensed to receive it. The driver glues the chip's cipher engine, key ladder, cable-state machine, and the upstream DRM/KMS surface into one kernel module that exposes the secure display path to userspace cleanly. References live upstream in the Linux kernel git history with the contributor's name on them.

## Grounding

- **Era** — Within Qualcomm tenure · October 2009 – January 2022 · Senior Staff Engineer · Boulder
- **Substrate** — Linux kernel · C · in-kernel DRM/KMS subsystem · MSM display hardware · MDSS (Mobile Display Subsystem)
- **Display protocol** — [HDMI](https://en.wikipedia.org/wiki/HDMI) — High-Definition Multimedia Interface · TMDS lanes · E-DDC for sink discovery · CEC for control
- **Encryption layer** — [HDCP](https://en.wikipedia.org/wiki/High-bandwidth_Digital_Content_Protection) — hardware key ladder · authentication-with-revocation · link-integrity verification · cipher engine driving the TMDS lanes
- **Upstream** — References in the Linux kernel git history with the contributor's name. Find them by searching the kernel tree for `git log --author="Urs Muff"` — see the [mainline tree](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/) and the [kernel mailing-list archive](https://lore.kernel.org/).
- **Lineage forward** — The Linux kernel's discipline — every commit signed off, every patch reviewed publicly, every change addressable by a hash — is the same discipline now expressed in the [Coherence Network](/people/coherence-network) 's commit verbs (`tend` / `attune` / `compost` / `release`). Different naming, same posture.

## What Qualcomm — Linux HDMI / HDCP kernel module has given the Coherence Network

The kernel work is the only piece in the body of evidence with a *public, attributed, immutable* trace. Quark and MindTouch and Trimble source code lives behind corporate walls; the BML thesis archive is local to this repo. But Linux kernel commits are signed-off by author, reviewed in public on the kernel mailing list, and merged into a tree that is mirrored across thousands of machines worldwide. A contribution to that tree carries the engineer's name into a corner of the commons that won't be edited away.

---

Public attribution lives in the Linux kernel git history. To surface this body's commits, clone the kernel tree ( [torvalds/linux.git](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/) ) and run `git log --author="Urs Muff"`, or search the kernel mailing-list archive at [lore.kernel.org](https://lore.kernel.org/). If you have specific commit hashes or patch URLs to anchor this page, refine through the Refine doorway below.

*(This page is a writing-surface scaffold synced from the body's rendering surface — round-tripped from the graph the cell already lives in. `claimed: false` invites direct authorship to replace any part of it.)*
