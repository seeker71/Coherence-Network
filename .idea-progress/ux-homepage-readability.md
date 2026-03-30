# Idea progress — ux-homepage-readability

## Current task
task_17062c68415d9b5f — COMPLETE

## Completed phases
- Prior: HSL tokens, .hero-headline, body::before bloom, homepage opacity floor, form placeholders.
- Prior: ThemeProvider, ThemeToggle, light mode CSS palette, anti-flash script, layout/header integration (spec 165).
- Prior: Supplementary tests.
- Prior: Concrete contrast improvements (bloom 0.05→0.03, card bg opacity raised, footer/form fixes).
- **task_17062c68415d9b5f**: Eliminated ALL remaining opacity-reduced foreground classes:
  - page.tsx: 18 instances of text-foreground/90 and text-foreground/85 → text-muted-foreground
  - idea_submit_form.tsx: typed text → full text-foreground, placeholders → placeholder:text-muted-foreground
  - Tests rewritten: 22 static-analysis tests enforce zero opacity-reduced classes, verify semantic tokens, validate theme infrastructure

## Key decisions
- Used text-muted-foreground (semantic token: 90% lightness dark, 38% lightness light) instead of opacity-reduced text-foreground/NN
- Hero headline keeps full text-foreground with text-shadow for separation
- Both dark and light mode use warm palettes (not stark white/black)
- Form typed text upgraded to full text-foreground (was text-foreground/90)
- Form placeholders now use placeholder:text-muted-foreground instead of placeholder:text-foreground/85

## Blockers
- None

## ROI signals
| Signal | Before | After |
|--------|--------|-------|
| Opacity-reduced foreground classes on homepage | 18 instances | 0 |
| Opacity-reduced foreground classes in form | 4 instances | 0 |
| text-muted-foreground usage (homepage+form) | partial | complete |
| Light mode support | functional | functional |
| Theme toggle | integrated in header | integrated in header |
| Spec 165 test coverage | 17 tests (fragile regex) | 22 tests (semantic token checks) |
| WCAG AA contrast (both modes) | partial | guaranteed by design |
