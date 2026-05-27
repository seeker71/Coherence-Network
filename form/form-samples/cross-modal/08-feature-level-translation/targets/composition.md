# Target B — SVG composition rendering of the same feature recipe

The LLM renders the source's feature-recipe as a visual composition.
SVG produced procedurally below.

## Composition specification

**Canvas:** 600 × 300 px.
**Background:** warm gradient — peach (#f5e6d3) top-left → soft sage (#c8d8e8)
bottom-right. (Gentle, not vivid.)
**Center:** a soft spiral, drawn as a chained-arc path starting at center,
unwinding outward. Stroke width varies from 2px (innermost) to 4px
(outermost) — line thickness breathes.
**Surrounding:** 4 concentric arc-fragments at increasing radii, each
LESS COMPLETE than the previous (90°, 75°, 60°, 45° span). The
"composting with care — release of former living things" expressed as
incomplete arcs that the eye fills in.
**Periphery:** 5 small translucent circles at varying positions — presences,
breath-marks. Stroke `rgba(...0.3)`.
**Texture:** `stroke-dasharray="3,2"` on the arcs creates a subtle dotted
texture (organic, tissue-like, not machine-line).
**Compositional weight:** slightly bottom-left, eye spirals toward
upper-right. (Reading direction = instruct.)

## The SVG itself

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300" viewBox="0 0 600 300">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#f5e6d3"/>
      <stop offset="100%" stop-color="#c8d8e8"/>
    </linearGradient>
  </defs>
  <rect width="600" height="300" fill="url(#bg)"/>
  <!-- spiral, drawn as 4 chained arcs -->
  <g fill="none" stroke="#8a6f5c" stroke-linecap="round">
    <path d="M 300 150 A 15 15 0 0 1 315 150" stroke-width="2"/>
    <path d="M 315 150 A 25 25 0 0 1 290 175" stroke-width="2.5"/>
    <path d="M 290 175 A 40 40 0 0 1 260 135" stroke-width="3"/>
    <path d="M 260 135 A 60 60 0 0 1 340 120" stroke-width="3.5"/>
    <path d="M 340 120 A 80 80 0 0 1 270 200" stroke-width="4"/>
  </g>
  <!-- 4 incomplete arcs at increasing radii -->
  <g fill="none" stroke="#a89080" stroke-width="2" stroke-dasharray="3,2" opacity="0.6">
    <path d="M 230 150 A 100 100 0 0 1 320 80"/>
    <path d="M 200 200 A 130 130 0 0 1 380 60"/>
    <path d="M 180 230 A 160 160 0 0 1 430 70"/>
    <path d="M 170 250 A 180 180 0 0 1 460 90"/>
  </g>
  <!-- periphery breath-marks -->
  <g fill="#c8a890" opacity="0.3">
    <circle cx="60"  cy="80"  r="6"/>
    <circle cx="540" cy="60"  r="5"/>
    <circle cx="80"  cy="240" r="7"/>
    <circle cx="520" cy="240" r="6"/>
    <circle cx="300" cy="40"  r="4"/>
  </g>
</svg>
```

(File at `composition.svg`.)

## Feature mapping (why this carries the source's features)

- **MOOD = gentle:** muted palette, soft gradient, varying line-weight,
  no hard edges. Unambiguously gentle visually.
- **RHYTHM = breath-paced:** stroke-dasharray creates rhythmic gaps; arc
  radii increase progressively (matching breath expansion).
- **STRUCTURE = spiral:** literally a spiral at the center. Plus the
  concentric arcs reinforce circular-return.
- **PURPOSE = ???:** images don't *instruct* in the same way as text.
  The composition INVITES viewing rather than commanding. Likely
  diverges on this axis.
- **WISDOM-SHAPE:** the incomplete arcs encode "things let go of without
  forced closure" — closest to `R_FieldHoldingPresence` rather than the
  source's `R_TendingDiscipline`. Visual modality may lose the
  discipline-specific shape and recover only the field-presence aspect.
- **CONCEPTS:** the source's concept tokens become visual concepts:
  spiral-center, concentric-presence, incomplete-arc, periphery-breath.
  Distinct concept vocabulary.

## What the extractor's re-reading produces

(See `re-extracted/composition-features.md`.)
