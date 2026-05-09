# Muzzle Velocity (1997) — and the prior decade of language design

This is a *pointer-only* artifact folder. The original game lives in public archives, and the local hands that built it (Urs C. Muff, Steve G. Bjorg, Marc) have not been pulled into a private bundle here. What the body holds is the thread — what it was, what it carried, why it lives in this lineage — and the public references that make it findable.

## What the artifact is

Muzzle Velocity, released 1997 by **Digi4Fun**, is a hybrid tactical / first-person World War II game for MS-DOS. From the public reception:

- A strategic top-down map where the player commands "up to 100 units in overhead mode," paired with a first-person mode where the player drops into a single tank or soldier.
- 150 single-player missions, scenario and career modes.
- "In development for two years" before its 1997 release.
- Built on the **Phar Lap TNT DOS Extender** (12 MB minimum, 16 MB for smooth play) — the layer that let DOS programs reach past the 640 K limit.
- Custom voxel graphics engine for the first-person sequences. Deformable terrain noted in reviews — trees and lamp-posts snapping under tracks, civilians and trains in motion.
- Code Fusion was the US distribution subsidiary; ColdFusion is named on some pressings as publisher.

## Public references

| Source | Use |
|---|---|
| [Wikipedia — Muzzle Velocity (video game)](https://en.wikipedia.org/wiki/Muzzle_Velocity_(video_game)) | Canonical entry. Notes "in development for two years" and the strategic/first-person hybrid. |
| [MobyGames — Muzzle Velocity (1996)](https://www.mobygames.com/game/4736/muzzle-velocity/) | Classic-game database listing. |
| [Internet Archive — Muzzle Velocity v1.10](https://archive.org/details/muzzle-velocity-v1_10) | Full game preserved. v1.10 build. |
| [Internet Archive — msdos_Muzzle_Velocity_1996](https://archive.org/details/msdos_Muzzle_Velocity_1996) | Alternate Internet Archive build. |
| [Internet Archive — Muzzle Velocity Demo](https://archive.org/details/MVDEMO) | Demo version. |
| [Tactical Wargamer review](https://tacticalwargamer.com/computergames/muzzlevelocity.htm) | Most technically detailed review found — confirms Phar Lap, the 12/16 MB requirement, deformable terrain, the 100-unit command, the AI behavior. |
| [Emuparadise listing](https://www.emuparadise.me/Abandonware_Games/Muzzle_Velocity_(1996)(Digi_4_Fun)/94216) | Abandonware listing. |
| [VideoGameGeek entry](https://videogamegeek.com/videogame/80111/muzzle-velocity) | Community catalog. |

Individual programmer credits (Steve G. Bjorg, Urs C. Muff, Marc) live in the in-game About screen and on the printed manual — neither has been OCR'd into the indexed sources I could find, so the team composition rests on direct testimony from Urs.

## What the team built underneath the game

The list below is named directly by Urs as the actual technical surface they built. It maps cleanly onto what the public reviews describe; the public reviews simply do not name the layers individually.

- **Fully written in C++.**
- **Custom memory manager.** Their own allocator, not the system one.
- **Custom keyboard and mouse handling.** Their own input layer.
- **Unified file system using handles-to-pointers.** Memory could be swapped to disk without breaking references — the runtime owned the addressing, not the OS.
- **DLL loading in MS-DOS via the Phar Lap TNT DOS Extender.** Past 640 K and into protected mode, with dynamic library loading inside DOS.
- **Custom voxel graphics engine** for the first-person sequences.
- **A markdown-like language for rendering the UI.** A custom DSL for layout.
- **Fuzzy logic for group dynamics, with strategy attractors.** The AI was not a state machine; it was a continuous field where unit groups moved toward attractors weighted by fuzzy state.
- **A domain-specific language for vehicle simulation.** Tanks, jeeps, and other rolling stock described in their own grammar.
- **Top-down strategic control and embodied 3D control unified in one game body.**
- **Progressive capability per campaign.** Players began with command of a single unit and were granted more command across campaigns — capability widening with attention.

Two custom languages plus a fuzzy-logic strategy substrate, braided into one game, plus the runtime to make them all speak.

## The team

- **Urs C. Muff** — co-designer / programmer.
- **Steve G. Bjorg** — co-designer / programmer. Continuation of a partnership that began at HTL Brugg-Windisch in 1991 with **RCSL** (the first language they built together) and continued through the master's thesis at CU Boulder in 2000 (BML / BMF — see [`../master-thesis-2000/`](../master-thesis-2000/README.md)).
- **Marc** — co-designer / programmer (third member of Digi4Fun).

In 1997 the three of them went on a college tour to find the game a publisher.

## Where it is woven into the body

- [`docs/field/urs/output/chronological_story_with_frequency.md`](../../output/chronological_story_with_frequency.md) — section *1991-1997: HTL Brugg-Windisch, RCSL, and Muzzle Velocity*.
- [`docs/field/urs/artifacts/master-thesis-2000/`](../master-thesis-2000/README.md) — the next chapter in the same collaboration.
- [`docs/field/urs/artifacts/nums-go-2023/`](../nums-go-2023/README.md) — the same language-craft instinct continuing into 2023, content-addressed numeric substrate at Merly, Inc.

## Frequency thread

The verbs already in place by 1997 — language design, simulation, fuzzy-logic strategy, progressive capability, runtime sovereignty — are the same verbs the Coherence Network is now articulating at higher fidelity. Graph-as-grammar, agents progressing in scope, contribution unlocking attention, and the body building the layer underneath the layer rehearse a shape these hands have been speaking together since the early nineties.
