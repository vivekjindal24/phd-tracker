# Design System

> v3 rewrite: the "well-kept register" look (ink on paper, 2px radius, rules
> instead of shadows) is superseded by **warm academic claymorphism**. Goal:
> scholars and supervisors *enjoy* opening the app every week — adoption pulls
> itself (PRD §3). Compliance PDFs keep a print-like look (§7).

## 1. Design Direction

- **Style:** warm academic claymorphism — soft, puffy surfaces that look moulded
  from clay: large radii, pastel fills, a double inner shadow (light top-left,
  dark bottom-right) plus a soft outer drop shadow. Warm cream base with
  shades of purple as the main colour (academic violet), sage and butter
  accents.
- **Personality:** playful but trustworthy. Fun lives in shape, colour, motion
  and the mascot; wording stays plain and official (§2).
- **Design Principles:**
  1. The API is the security enforcer; the UI only hides what the API already
     denies — visual gating is never the enforcement.
  2. Everyone inside the university logs in and sees exactly their scope;
     only external committee members (examiners, RAC outsiders) get PDFs.
  3. Optimistic churn avoided: actions are explicit button → result; the user
     is never misled about whether their APR was submitted. Celebrations fire
     only after the API confirms.
  4. Delight never costs readability: long lists (registers, report lists)
     stay flat and scannable inside a clay container.

## 2. Brand

- **Brand Name:** Anveshan (Sanskrit: *exploration, inquiry*)
- **Mascot:** a round clay owl wearing a mortarboard. Inline SVG components in
  `web/src/components/brand/` — poses: `idle`, `reading` (loading),
  `sleeping` (server waking up), `cheering` (APR approved), `empty`
  (empty states). No raster images.
- **Icon:** the owl's face in a clay circle — the logo mark, the favicon
  (`web/src/app/icon.svg`) and the app icon.
- **Wordmark:** "Anveshan" in Fraunces SemiBold beside the icon, on a clay
  pill in the top bar.
- **Brand Voice:** plain, official, zero marketing gloss in labels and
  messages. The mascot may add one short friendly line on empty, loading and
  success states — never on errors that need action.

## 3. Tokens — the source is the CSS

Tokens live in `web/src/app/globals.css` (`:root` custom properties).
**Change tokens there, not per-page.** No Tailwind, no UI library.

### Palette — light (default)

| Token | Value | Use |
|---|---|---|
| `--bg` | `#F6EFE6` cream | page background |
| `--surface` | `#FFF8F0` warm white | clay cards, inputs |
| `--ink` | `#3D2C2E` cocoa | body text (12.5:1 on surface) |
| `--ink-soft` | `#6B5457` | secondary text (6.6:1) |
| `--lilac` | `#D9CCF2` | soft purple tint (selected rows, chips) |
| `--accent` | `#A78BDA` lavender | decoration, highlights, focus glow |
| `--accent-strong` | `#6D4BC3` deep violet | primary button fill (white text 6.1:1), links (5.8:1) |
| `--sage` | `#81B29A` | secondary accent; Approved |
| `--butter` | `#F2CC8F` | highlight; Draft |
| `--sky` | `#A8CCE8` | In review |
| `--coral` | `#F4A28C` | Rejected / sent back |
| `--danger` | `#B3261E` | destructive actions, error text |

State badges: cocoa text on the pastel fill (all ≥ 5.4:1).

### Palette — dark ("plum clay")

Follows `prefers-color-scheme`, overridable by a toggle that sets
`data-theme` on `<html>` (choice remembered in localStorage).

| Token | Value |
|---|---|
| `--bg` | `#221A2E` deep plum |
| `--surface` | `#30263F` |
| `--ink` | `#F1EAF7` (14.2:1 on bg) |
| `--ink-soft` | `#C4B8D4` (7.6:1 on surface) |
| `--lilac` | `#4A3D63` |
| `--accent` / `--accent-strong` | `#9F88D6` / `#B49DEB` (button text `#221A2E`, 7.1:1); links `#C7B4F3` (7.6:1) |
| pastels | same hues, 15% darker and desaturated; badge text `#221A2E` (≥ 5.3:1) |

Dark clay keeps the double inner shadow, with a cool lilac highlight
(`rgb(230 215 255 / .08)`) in place of white.

### Clay recipe

```css
--clay-shadow:
  8px 8px 18px rgb(61 44 46 / .16),          /* outer drop */
  inset -5px -5px 10px rgb(61 44 46 / .10),  /* inner shade, bottom-right */
  inset 5px 5px 10px rgb(255 255 255 / .85); /* inner light, top-left */
--clay-shadow-pressed:                       /* pressed / active */
  2px 2px 6px rgb(61 44 46 / .14),
  inset 4px 4px 8px rgb(61 44 46 / .14),
  inset -4px -4px 8px rgb(255 255 255 / .6);
```

- **Radius:** `--radius-sm 12px` (inputs, badges), `--radius 20px` (buttons,
  cards), `--radius-lg 32px` (panels, dialogs), `--radius-pill 999px`.
- **Spacing:** 4px base (`--space-1` … `--space-8`), generous padding inside
  clay (min 16px) — clay needs room to look puffy.
- **Page width:** content fills the window up to `max-width: 1600px`, side
  gutter `clamp(16px, 3vw, 48px)` — no narrow centred column. Dashboard tiles
  use an auto-fit grid (`minmax(220px, 1fr)`) so wide screens get more tiles.

### Type

- **Display:** Fraunces (soft, chunky serif — academic flavour) for headings
  and the wordmark, weights 600/700, `SOFT` axis turned up.
- **Body:** Nunito (rounded sans, highly readable) for everything else,
  weights 400/600/700.
- Self-hosted via `next/font` (no third-party request at runtime),
  `font-display: swap`, latin subset only.
- Sizes: `--text-sm` 0.875rem, `--text-base` 1rem, `--text-lg` 1.25rem,
  `--text-xl` 1.75rem, `--text-hero` clamp(2rem, 1.4rem + 2.5vw, 3rem).

## 4. Components — `web/src/components/ui/`

Button (`kind: primary/secondary/ghost/danger`), Field (label + control),
Card (clay surface), Table (head/rows/empty), PageHeader (title + optional
`sub`), StateBadge (workflow-state chip), ChainSteps (the item's approval
chain as a row of clay step chips — done / current / upcoming, with who
acted and when), QueueList (items waiting for the viewer, oldest first,
days-waiting chip), StatTile (dashboard number + label, links to the
filtered list), ErrorText, EmptyState (mascot + one line + optional action),
NotificationBell, ThemeToggle. Semantic HTML first: real `<table>`
for registers, `<dl class="kv">` for key-value, `<label>`-wrapped controls.

- **Buttons:** clay pills; hover lifts 2px, press swaps to
  `--clay-shadow-pressed` + `scale(.97)` (the "squish").
- **Inputs:** inset clay wells (pressed shadow at rest); focus adds the
  accent glow.
- **Cards & panels:** raised clay; dashboard tiles may break the grid
  (bento layout) for hierarchy.
- **Tables:** one clay card holds the table; rows inside are flat with soft
  zebra tint and a hover tint — never a clay shadow per row.
- **Badges:** small clay pills, pastel fill + text label (Draft,
  In review · <step>, Sent back, Approved).
- **Navigation:** clay pill top bar with grouped menus — My work, My unit,
  Office, Settings — showing only the groups the user's roles and enabled
  modules allow. On phones it collapses into a bottom sheet.
- **Home:** one page stacking a section per role the user holds (queue
  first, then scholars, then unit overview, then admin), bento tiles inside
  each section.

Rules for changes:
- A new page composes the kit; no new button styles, no inline palettes.
- A new state value appears in StateBadge, fed by the API — never a
  client-side status guess.
- Hover, focus and active states exist for every interactive element and
  use the tokens.

## 5. Motion — playful

- **Tactile base:** press squish (120ms), hover lift (180ms), badge pop on
  state change (spring-like `cubic-bezier(.34,1.56,.64,1)`, 300ms).
- **Celebration:** a short confetti burst in purple/palette colours.
  Hand-rolled (CSS/canvas, no dependency), ≤ 1.5s, fires once per event,
  only after the API confirms it:
  - any approver's **Approve** at a middle chain step → a small burst;
  - the final approval, and the scholar's first view of their approved item
    → the full burst plus the cheering owl ("Approved!");
  - the scholar's first view of their finalised seminar feedback;
  - a passed viva and the Shodhganga deposit — for the office recording it,
    and for the scholar on first view.
- **Empty states:** the owl idles (blink, gentle bob).
- **Cold start:** while the API wakes (Render free tier, 15–60s), the
  sleeping owl with "Waking up the server…" — intentional, not broken.
- Animate only `transform`, `opacity` and `box-shadow` on small elements.
- **`prefers-reduced-motion: reduce`** disables confetti, bobbing and
  springs; state changes become instant. Non-negotiable.

## 6. Accessibility (non-negotiable)

- WCAG AA contrast for all text in both themes (ratios in §3; recheck on any
  token change).
- Keyboard navigable; visible `:focus-visible` ring (2px `--accent-strong`
  outline + offset) — clay shadows never replace the focus ring.
- Never colour alone: every state badge carries its text.
- Labels on every control (`aria-label` where visual text is absent); the
  mascot is decorative (`aria-hidden`) unless it carries the only message.

## 7. Exports stay print-like

Compliance PDFs (APR, milestone register) do **not** use claymorphism: they
are photocopied in committee meetings. Black-on-white, Fraunces headings
optional, rules not shadows, readable in grayscale. The owl icon may appear
small in the header.
