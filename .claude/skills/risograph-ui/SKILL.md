---
name: risograph-ui
description: Audit and apply a consistent Risograph-style UI — offset "misregistration" shadows, grain texture, tactile press-in buttons, registration-mark frames, and a fixed control-height / spacing / animation system. Use when building a new frontend with a risograph aesthetic, auditing an existing app for visual consistency, or fixing components that drift from the look. Ships a drop-in `riso.css` and a hard numeric ruleset (`DESIGN_RULES.md`).
---

# Risograph UI

A design-system skill for building and enforcing a **Risograph-print aesthetic**
in web UIs: layered offset "ink" shadows, grainy textures, a tight 4-colour
palette, bold mono labels, registration marks, and tactile micro-animations.

This skill bundles two companion files in its own directory — read them, don't
reinvent them:

- **`riso.css`** — drop-in design tokens + component classes (`btn-tactile`,
  `card-riso`, `surface-noise`, `riso-section-label`, `riso-frame`,
  `input-riso-date`, `riso-checkbox`, `animate-*`, …). Self-contained, plain CSS.
- **`DESIGN_RULES.md`** — the hard numeric rules: control heights (22/26/32 px),
  dropdown min-widths, spacing scale, typography sizes, anti-patterns. **Read it
  before making any visual change** — follow the numbers, don't improvise sizes
  from "what looks balanced."

## What is Risograph style?

Risograph style is characterized by:
- **Layered, slightly-offset colour printing** — shadow offsets in accent inks
  creating a "misregistration" look (e.g. `box-shadow: 3px 3px 0 var(--riso-teal)`).
- **Grainy / textured overlays** — subtle noise over surfaces and buttons.
- **A limited, bold palette** — 3–4 dominant inks (here: orange, teal, violet,
  gold) over warm paper, plus halftone dot accents.
- **Flat, bold typography** — strong weights, mono UPPERCASE labels, slight
  positive tracking.
- **Bold outlined components** — 1.5 px borders with offset shadows, not soft
  blurred elevation.
- **Registration marks & print motifs** — corner L-brackets, ◆ markers, ink strips.
- **An organic, slightly imperfect feel** — tactile, hand-printed, not corporate.
- **Punchy micro-animations** — button press offsets, ink-in entrances, hover shifts.

## Getting started (new project)

1. Copy `riso.css` into the project and import it once at the app root. (If you
   already have a token system, port the `:root` / `.dark` variables instead of
   the whole file.)
2. Add the class `dark` to `<html>`/`<body>` to switch to the dark palette.
3. Build components from the bundled classes — never from raw utility classes.
4. Follow `DESIGN_RULES.md` for every dimension decision.

## Auditing an existing app

When asked to audit or align an app to the risograph look, work in this order:

### 1. Map the surface area
Review, in this order:
- The design-token / global stylesheet (where CSS variables live).
- The app shell — top-level layout, sidebar, routing frame.
- Every page / route.
- Shared UI components (buttons, inputs, selects, dialogs, cards).
- Any repeating component family (list/grid cards, table rows, custom nodes).

### 2. Assess each area against the rules
For each file, check:
- Colour-token adherence (no raw hex, no framework palette classes).
- Button / input / card / select consistency with `DESIGN_RULES.md`.
- Control-height bucketing within each horizontal row.
- Typography hierarchy and mono-label usage.
- Spacing on the allowed scale only.
- Presence and quality of offset shadows + entrance animations.
- Anything that breaks the look (see the anti-patterns list in the rules).

### 3. Fix in priority order
1. **Design tokens** — make sure `riso.css` (or the project's equivalent) is the
   single source of truth.
2. **Shared components** — fix the button/input/select/dialog primitives once so
   every consumer inherits the look.
3. **Page-level fixes** — apply classes, correct heights, fix spacing.
4. **Animations** — add entrance + interaction animations last.

### 4. Apply, verifying as you go
- Change **only styling** (class names / CSS) — never logic or data flow.
- Preserve all `data-testid`, `aria-*`, and `role` attributes.
- Keep colour contrast at WCAG AA (4.5:1 for body text).
- Verify dark mode still reads coherently.
- When a design call is ambiguous, pick the more conservative option and note it.

## Component specs (summary)

Full numbers live in `DESIGN_RULES.md`; the essentials:

- **Buttons** — start from `.btn-tactile`; pick a variant (`-orange` primary,
  `-teal` toggle-on, `-violet` info, `-outline` cancel/ghost). Active state
  presses in (+1 px + flattened shadow). Icon 11 px (sm/md), 13 px (lg).
- **Cards** — `.card-riso` (+ `-orange` / `-violet` / `-press`). Offset ink shadow,
  noise fill, one contrast step from the surface beneath. 16 px body padding.
- **Selects** — min-width 200 px for name-bearing dropdowns; never `w-auto`.
  Override any primitive's default height to a riso bucket. Wrap icon+text in a
  `<div>`, not a `<span>`.
- **Inputs** — text inputs use the tactile look; `.riso-checkbox` on every
  checkbox; `.input-riso-date` for dates (portal any custom popover to body).
- **Labels** — `.riso-section-label` for uppercase mono section headers with the
  ◆ marker; `.tag-riso*` for pill tags; `.riso-stamp` for count/status badges.
- **Frames** — `.riso-frame` adds corner registration L-brackets; `.surface-noise`
  / `.riso-noise` add grain.

## Stack note

The rules (heights, colours, shadows, spacing, animations) are universal. The
code examples are React + Tailwind v4 + Radix because that's a common modern
stack and shows the tricky integration points (overriding a Radix `SelectTrigger`
height, portalling popovers out of clipping containers). If you don't use
Tailwind: apply the `riso.css` classes directly, and if you use Tailwind v4, map
the tokens into your theme with `@theme inline { --color-x: var(--x); }`. None of
the rules depend on a specific framework.

## Quality control

- Never break functionality — styling changes only.
- Re-check after each edit: stale colour values, mixed control heights in a row,
  missing hover/active states, native browser chrome leaking through.
- Respect `prefers-reduced-motion` (the bundled animations already do).
- If a CSS/visual approach fails twice, stop and propose a different architecture
  instead of iterating on the same broken one — especially for layout, text flow,
  and popover positioning.

## Output (after an audit)

Report concisely:
1. **Audit summary** — files reviewed and issues found.
2. **Changes made** — file-by-file list of what changed.
3. **Token reference** — any tokens added/modified.
4. **Pending** — items needing design review or assets (fonts, textures).
