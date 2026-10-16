# Design System

> v2 rewrite: the "stock Frappe Desk" decision is superseded — the custom UI
> arrived with the Next.js web app. Direction unchanged: calm, institutional,
> print-like. The interface should feel like a well-kept register, not a
> startup dashboard.

## 1. Design Direction

- **Style:** "a well-kept register" — ink-on-paper palette, serif display over
  system sans body, 2px radius (registers don't have rounded corners), rules
  instead of shadows, state conveyed text-first (badge text) with color second.
- **Design Principles:**
  1. The API is the security enforcer; the UI only hides what the API already
     denies — visual gating is never the enforcement.
  2. Read-only surfaces (committee, buyer) get PDFs, never logins.
  3. Optimistic churn avoided: actions are explicit button → result; the user
     is never misled about whether their APR was submitted.

## 2. Brand

- **Brand Name:** PhD Tracker
- **Logo:** none — do not invent one; the wordmark suffices until a pilot asks.
- **Brand Voice:** plain, official, zero marketing gloss inside the product.

## 3. Tokens — the source is the CSS

Tokens live in `web/src/app/globals.css` (`:root` custom properties) and page
styles in `web/src/app/(app)/app.css`. **Change tokens there, not per-page.**

- **Palette:** ink `#1c1917` / ink-soft `#57534e` on paper `#faf9f7`, card
  `#ffffff`, rules `#d6d3d1`/`#a8a29e`; accent = register maroon `#7c2d12`
  (official, not startup); semantic `--danger` `#b91c1c`, `--ok` `#166534`.
- **Type:** `--font-display` Georgia/serif for headings (print pedigree, zero
  webfont bytes), system sans for body. Sizes `--text-sm` / `--text-base`.
- **Spacing/radius:** page rhythm via the layout grid; `--radius: 2px`.

## 4. Components — `web/src/lib/ui.tsx`

Button (`kind: primary/ghost/danger`), Field (label + control), Table
(head/rows/empty), PageHeader (title + optional `sub` ReactNode — a
StateBadge fits), StateBadge (workflow-state chip), ErrorText; `form-card`
and `.kv` layout classes in `app.css`. Real `<table>` for registers,
`<dl class="kv">` for key-value, `<label>`-wrapped controls — semantic HTML
first, no component library.

Rules for changes:
- New page composes the kit; no new button styles, no inline palettes.
- A new state value appears in StateBadge, fed by the API — never a client-side
  status guess.
- Hover/focus states exist and use the tokens; `:focus-visible` is the accent
  outline (accessibility floor, kept).

## 5. Accessibility (non-negotiable)

- Keyboard navigable; visible `:focus-visible` outline (tokens).
- Never color alone: every state badge carries its text (Draft/Submitted/…).
- Labels on every control (`aria-label` where visual text is absent).
- Export PDFs must stay readable in grayscale — they are photocopied in
  committee meetings.