# Anveshan logo package

The Anveshan symbol, themed for research.vivekjindal.in. Open `preview.html` in a browser to see it in the site's light
and dark header styles, with the animation and a Replay button.

## The idea

A spiral that starts heavy and grounded, then narrows toward an open frontier: a researcher's path. The amber dot is the
seeker (the student), released from the end of the path into the opening, where the next question waits.

## Folder map

| Folder | Contents | Use for |
|---|---|---|
| `static/` | SVG masters: `light`, `dark`, `flat`, `flat-black`, `flat-white`, `flat-mono-6d4bc3`, `app-icon` | Web, product UI, print, one-colour uses |
| `png/` | The same logos as transparent PNG at 512 and 1024 px | Slides, documents, social, email |
| `animated/` | `anveshan-animated-light.svg`, `anveshan-animated-dark.svg` | The website (plays once, then a soft ripple) |
| `video/` | 6-second MP4 and GIF, light (cream background) and dark | Presentations, social, video editors |
| `source/gen.py` | Generator for all SVGs (`python3 source/gen.py`) | Changing a colour or the taper |
| `preview.html` | Live preview on the site palette | Reviewing, showing others |

## Which file to use

- Light page (cream `#F6EFE6` or white): `static/anveshan-symbol-light.svg`
- Dark page (`#221A2E`): `static/anveshan-symbol-dark.svg`
- Print, stamps, embroidery or one colour: `static/anveshan-symbol-flat*.svg` (the flat set has no gradient)
- App icon or favicon source: `static/anveshan-app-icon.svg`
- Website animation: the matching `animated/` SVG, loaded with an `<img>` tag

## Colours

| Role | Light | Dark |
|---|---|---|
| Spiral, thick start (foundation) | Violet `#6D4BC3` (rgb 109, 75, 195) | Dusk `#9F88D6` (rgb 159, 136, 214) |
| Spiral, thin tip (frontier) | Lilac `#9570D6` (rgb 149, 112, 214) | Mist `#D9CCF2` (rgb 217, 204, 242) |
| Seeker dot | Amber `#E3922A` (rgb 227, 146, 42) | Butter `#F2CC8F` (rgb 242, 204, 143) |

Violet is the site's own primary (`--accent-strong`). The gradient runs from the tip (top left) to the base (bottom right).

## Notes and limits

- The animated SVGs work on screens only. They use a mask and a style block, so they are not suitable for print or
  cutting. They show the static logo for visitors who prefer reduced motion.
- The site switches theme with a `data-theme` attribute, which a logo loaded as an image cannot see. Swap between the
  light and dark files when the theme changes, or inline the SVG and bind its colours to CSS variables.
- The amber dot is about 2.2:1 against cream. That is fine as a large decorative shape; do not use it for text.
- There is no custom wordmark yet. The "Anveshan" text in `preview.html` is the site's existing Fraunces.
- The favicon on the site is still the owl; `static/anveshan-app-icon.svg` is the source for a replacement.
- Trademark: run a trademark and reverse-image search before launch. This package is not legal clearance.
