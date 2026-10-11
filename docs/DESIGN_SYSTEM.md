# Design System

## 1. Design Direction

- **Style:** v1 uses the **stock Frappe Desk UI** unchanged. This is a deliberate
  decision, not a gap: v1 is an internal tool for a single-department pilot, and
  custom UI before product validation is wasted money.
- **Mood (when custom UI arrives):** calm, institutional, print-like — the product
  generates compliance paperwork, so the interface should feel like a well-kept
  register, not a startup dashboard.
- **Design Principles:**
  1. Zero custom UI before the pilot proves the workflow.
  2. When custom UI comes, it replaces Desk only for scholar/supervisor flows —
     admin/research office stays on Desk (they're power users of filters/exports).
  3. Read-only surfaces (committee, buyer) get PDFs, never logins.

## 2. Brand

- **Brand Name:** PhD Tracker
- **Logo:** none yet — do not invent one for Desk (Frappe app icon suffices in v1).
- **Brand Voice:** plain, official, zero marketing gloss inside the product.

## 3–14. Tokens, Typography, Components

**Deferred.** Colors, type scale, spacing, buttons, cards, navigation, states,
icons, breakpoints: all inherit from Frappe Desk defaults in v1. Defining custom
tokens now would be fabrication — no custom screen exists to apply them to.

**The rule while Desk is the UI:** change nothing. No custom CSS, no Desk
overrides, no theme app. Any visual change request gets routed through this
document first: we define the tokens (palette, type, spacing per the ECC web
design-quality rules — intentional palette, semantic color, real type pairing)
at the moment the first custom page is committed, not before.

## 15. Accessibility

Non-negotiable even on stock Desk:
- Keyboard navigation and visible focus states (Desk provides; don't break them).
- Do not rely on color alone to convey report states (state names are text).
- Print formats must be readable in grayscale — they are photocopied in committee
  meetings.