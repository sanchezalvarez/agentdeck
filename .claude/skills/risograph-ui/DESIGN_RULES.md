# Risograph Design Rules

Hard rules for UI dimensions, spacing, and component styling. When editing any
component with visual/class changes or touching `riso.css`, follow these. The
values are the baseline that makes the look cohesive — if you change one, change
it in one place (the token / `riso.css`) and update this file too.

All colours, classes, and tokens referenced below ship in `riso.css` (in this
skill). Examples use React + Tailwind v4 + Radix as a reference stack, but the
rules are stack-agnostic — map the class names to your own components if you
don't use Tailwind.

## Colours (CSS variables in `riso.css`)

| Purpose                | Token                | Light     | Dark      |
|------------------------|----------------------|-----------|-----------|
| Background (base)      | `--background`       | `#F0E8DC` | `#2C2418` |
| Background (raised)    | `--background-2`     | `#E6DDD0` | `#362D1F` |
| Background (sunken)    | `--background-3`     | `#D8CFC0` | `#403626` |
| Border (subtle)        | `--border`           | rgba 10%  | rgba 12%  |
| Border (strong)        | `--border-strong`    | rgba 20%  | rgba 22%  |
| Accent — primary       | `--accent-orange`    | `#E04E0E` | `#FF5A1A` |
| Accent — secondary     | `--accent-teal`      | `#0B7268` | `#14B8A6` |
| Accent — info          | `--accent-violet`    | `#5C3A9C` | `#8B62D4` |
| Accent — warning       | `--accent-gold`      | `#C8902A` | `#E8A830` |
| Offset shadow — orange | `--riso-orange`      | rgba 22%  | rgba 18%  |
| Offset shadow — teal   | `--riso-teal`        | rgba 22%  | rgba 18%  |
| Offset shadow — violet | `--riso-violet`      | rgba 18%  | rgba 15%  |

**Semantics:**
- **Orange** = primary action, selection highlight, active row tint.
- **Teal** = confirmed/selected toggle state, date picker.
- **Violet** = information / neutral markers.
- **Gold** = warning / pending status.
- **Destructive** = `var(--destructive)` only, never raw red.

Never use `#fff`, `#000`, or raw hex colours in components — always reference
tokens.

## Control heights

| Size | Height    | Use                                     |
|------|-----------|-----------------------------------------|
| `sm` | **22 px** | Table/row inline controls, row selects  |
| `md` | **26 px** | Toolbar buttons, bulk bar, filter bar   |
| `lg` | **32 px** | Form fields in dialogs, main CTA        |

Every control in the same horizontal row MUST share the same size bucket. If one
is `md`, all are `md`. Mixing `md` + `lg` in one row is a bug.

## Buttons — `.btn-tactile`

Base: `padding: 3px 8px`, `font-size: 11px`, `border: 1.5px solid
var(--btn-neutral-border)`, `border-radius: 4px`, soft drop shadow. Active state
translates `+1px` and flattens the shadow (press-in feel).

Variants defined in `riso.css`:
- `.btn-tactile` — neutral (default)
- `.btn-tactile-orange` — primary action
- `.btn-tactile-teal` — selected / toggle-on
- `.btn-tactile-violet` — info action
- `.btn-tactile-outline` — bordered neutral (dialog Cancel, destructive outline)

**Rules:**
- Never build a button from raw utility classes. Always start from `btn-tactile`.
- Icon + text: use `gap: 4px` (default) or `6px` for extra breathing room.
- Icon-only button: square, `width === height` of the bucket (22 / 26 / 32).
- Icon size = **11 px** at `sm`/`md`, **13 px** at `lg`.
- Destructive button: `background: var(--destructive)`, `color: #fff`.
  Destructive ghost: `btn-tactile-outline` + `color: var(--destructive)`.

## Selects / Dropdowns

If you use a headless primitive (e.g. Radix `Select`) that bakes in a default
height (`h-10`, `text-sm`), you MUST override it to the riso control height.

**Min widths (hard rule):**

| Content                               | Min width  |
|---------------------------------------|------------|
| Short enum (≤8 char labels)           | **120 px** |
| Medium (status, severity, category)   | **160 px** |
| Names / long labels (up to ~25 chars) | **200 px** |
| Wide (full member rosters, email)     | **240 px** |

Default when unsure: **200 px**. Never use `w-auto` / `fit-content` for a select
whose options contain variable user-entered strings — the trigger label ends up
narrower than the popover and layout jitters on selection change.

**Trigger template** (Radix + Tailwind reference — adapt to your stack):

```tsx
<SelectTrigger
  className="btn-tactile gap-1 !w-[200px] !h-auto !rounded !border-[1.5px]
             !border-[color:var(--btn-neutral-border)]
             !bg-[color:var(--btn-neutral-bg)]
             !px-[10px] !py-[3px] !text-[11px] !justify-between font-mono-ui"
>
  <div className="inline-flex items-center gap-1.5">
    <Icon size={12} /> Label…
  </div>
</SelectTrigger>
```

**Important:** wrap icon + text in a `<div>`, NOT `<span>`. Radix's
`SelectTrigger` applies `[&>span]:line-clamp-1`, which sets `display:
-webkit-box` on span children and stacks the icon above the text. Use `div` and
it renders inline-flex correctly.

Never manually place a second chevron inside the trigger — Radix renders one
automatically via `SelectPrimitive.Icon`.

## Inputs

- **Text input**: base `.btn-tactile` style — 1.5 px border, 4 px radius, 4×8 px
  padding, 11 px font.
- **Date input**: use `.input-riso-date`. If you build a custom date popover,
  portal it to `document.body` with fixed positioning — never wrap it in an
  `overflow: hidden` container expecting it to clip, and never fall back to the
  native `<input type="date">` chrome.
- **Checkbox**: `.riso-checkbox`. 14×14 px, 1.5 px border, 1.5×1.5 offset orange
  shadow, orange fill + white tick when checked. Use on every checkbox — no
  exceptions.
- **Radio**: no riso style shipped — if you need one, add it to `riso.css` and
  document it here.

## Cards & surfaces

`.card-riso` + variants in `riso.css`:
- `.card-riso` — teal offset shadow (default)
- `.card-riso-orange` — orange offset shadow
- `.card-riso-violet` — violet offset shadow
- `.card-riso-press` — interactive card (lift on hover, press on active)

Card body padding: **16 px (1 rem)** minimum. Header + body + footer stacked with
**12 px (0.75 rem)** gaps.

Always keep one step of contrast between a container and the card on it: a card
on a `--background-2` surface uses `--background` as its fill, and vice versa.

## Dialogs

Flexbox-centered, `max-height: 85vh` with internal scroll. Content padding:
**20 px**. Footer always right-aligned with **8 px** gap between buttons. Cancel
is `btn-tactile-outline`, confirm is `btn-tactile-orange` (or destructive
variant).

Popovers inside dialogs (date pickers, colour pickers, selects) MUST be portalled
to `document.body` with fixed positioning computed from the trigger's
`getBoundingClientRect()`. Never rely on an `absolute` popover inside a clipping
container.

## Spacing scale

Use these and only these:
- **2 / 4 / 6 / 8 px** — within a single component (icon-text gap, cell padding)
- **12 / 16 px** — between elements in a group (form rows, toolbar clusters)
- **20 / 24 px** — section padding (toolbars, card padding)
- **32 / 40 px** — page-level padding and major section gaps

Never use 2 px gaps for anything except icon+label in tight buttons.

## Typography

- **Display**: Syne Variable (`.font-display`) — page titles, dialog titles.
- **Mono UI**: IBM Plex Mono (`.font-mono-ui`) — all toolbar labels, buttons,
  badges, status chips, table headers, section labels, any small UPPERCASE label.
- **Body**: default system sans — long-form content and descriptions.

**Sizes:**
- 10 px — section labels, meta text, timestamps
- 11 px — buttons, toolbar labels, chips
- 12 px — table cells, form labels
- 13 / 14 px — body
- 16 px+ — card/section titles
- 24 px+ — page titles

Letter-spacing: `0.04em`–`0.08em` on UPPERCASE mono labels. Never squash headings
below tracking 0.

## Animations

Use the classes in `riso.css`, respect `prefers-reduced-motion`:
- `.animate-ink-in` — page sections / headers (0.6 s)
- `.animate-column-in` — toolbars, sidebars, columns (0.25 s)
- `.animate-card-in` — grid cards, stagger with `animation-delay: calc(N * 40ms)`
- `.animate-row-in` — table rows, stagger with `animation-delay: calc(N * 15ms)`
- `.animate-msg-in` — chat messages

All riso animations use `cubic-bezier(0.22, 1, 0.36, 1)`. Don't invent new
keyframes for one-off effects — reuse these.

## Anti-patterns (things that break the look)

- Raw `<select>`, `<input type="checkbox">`, `<input type="date">` without a riso
  class.
- Buttons with a default framework height (`h-10` / `h-9`) instead of a riso
  control height.
- `w-full` on a trigger/button inside a horizontal bar — it stretches and breaks
  alignment.
- Mixing button sizes in one row (a `md` button next to a select stuck at the
  primitive's default height).
- Native browser focus ring instead of the riso focus glow: `box-shadow: X X 0
  accent, 0 0 0 2px color-mix(... 18%)`.
- Pure palette colour classes (`bg-red-500`, `text-gray-600`) — always via tokens.
- Popovers rendered inline inside a clipping container (always portal).
- Filter values persisted in storage without validating they still exist on
  mount (stale IDs → silent empty state).
- A manually-placed second chevron inside a Radix `SelectTrigger`.
