#!/usr/bin/env python3
"""Anveshan symbol: Frontier Taper + Spiral, rebuilt with few anchors and the research.vivekjindal.in palette.

Geometry (256 grid, centre 128,128): a clockwise spiral whose centre-line radius grows 70 -> 96 over 296 degrees while its
width tapers 40 -> 12 (foundation -> frontier). Round caps. The seeker (r24) sits at 46 deg, r111, in the opening.
"""
import math, pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent  # writes static/ and animated/ in the package root
C = (126.0, 133.0)  # shifted from (128,128) so the drawn mark is centred in the canvas
T0, SWEEP = 10.0, 296.0
R0, R1, WMAX, WMIN = 70.0, 96.0, 40.0, 12.0
SEEKER_R, SEEKER_AT = 24.0, (111.0, 46.0)
STEP = 20.0

LIGHT = dict(tip="#9570D6", deep="#6D4BC3", dot="#E3922A", ripple="#E3922A")
DARK = dict(tip="#D9CCF2", deep="#9F88D6", dot="#F2CC8F", ripple="#F2CC8F")


def f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def pol(r, deg):
    a = math.radians(deg)
    return (C[0] + r * math.cos(a), C[1] - r * math.sin(a))


def samples():
    n = round(SWEEP / STEP)
    out = []
    for i in range(n + 1):
        u = i / n
        ang = T0 - u * SWEEP
        r = R0 + (R1 - R0) * u
        w = WMAX + (WMIN - WMAX) * (u ** 1.25)
        out.append((ang, r, w))
    return out


def bezier(points):
    n = len(points)
    ext = [(2 * points[0][0] - points[1][0], 2 * points[0][1] - points[1][1])] + points + [
        (2 * points[-1][0] - points[-2][0], 2 * points[-1][1] - points[-2][1])
    ]
    segs = []
    for i in range(1, n):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        segs.append(f"C{f(c1[0])} {f(c1[1])} {f(c2[0])} {f(c2[1])} {f(p2[0])} {f(p2[1])}")
    return " ".join(segs)


def centre(u):
    return pol(R0 + (R1 - R0) * u, T0 - u * SWEEP)


def width(u):
    return WMAX + (WMIN - WMAX) * (u ** 1.25)


def normal(u, h=1e-5):
    ax, ay = centre(max(u - h, 0))
    bx, by = centre(min(u + h, 1))
    tx, ty = bx - ax, by - ay
    d = math.hypot(tx, ty)
    # clockwise travel on screen: the outward normal is the tangent rotated -90deg
    return (ty / d, -tx / d)


def edge(u, side):
    px, py = centre(u)
    nx, ny = normal(u)
    w = width(u) / 2 * side
    return (px + nx * w, py + ny * w)


def edge_segments(side, n, h=1e-5):
    """Cubic Hermite segments of one edge, using exact (numerical-derivative) tangents at every anchor."""
    segs = []
    for i in range(n):
        u0, u1 = i / n, (i + 1) / n
        p0, p1 = edge(u0, side), edge(u1, side)

        def d(u):
            a, b = edge(max(u - h, 0), side), edge(min(u + h, 1), side)
            span = min(u + h, 1) - max(u - h, 0)
            return ((b[0] - a[0]) / span, (b[1] - a[1]) / span)

        d0, d1 = d(u0), d(u1)
        k = (u1 - u0) / 3
        segs.append((p0, (p0[0] + d0[0] * k, p0[1] + d0[1] * k), (p1[0] - d1[0] * k, p1[1] - d1[1] * k), p1))
    return segs


def fmt(c1, c2, p):
    return f"C{f(c1[0])} {f(c1[1])} {f(c2[0])} {f(c2[1])} {f(p[0])} {f(p[1])}"


def spiral_path():
    n = round(SWEEP / STEP)
    out = edge_segments(1, n)
    inn = edge_segments(-1, n)
    start = out[0][0]
    path = [f"M{f(start[0])} {f(start[1])}"] + [fmt(c1, c2, p) for _, c1, c2, p in out]
    tip_in = inn[-1][3]
    path.append(f"A{f(WMIN / 2)} {f(WMIN / 2)} 0 0 1 {f(tip_in[0])} {f(tip_in[1])}")
    path += [fmt(c2, c1, p0) for p0, c1, c2, _ in reversed(inn)]
    path.append(f"A{f(WMAX / 2)} {f(WMAX / 2)} 0 0 1 {f(start[0])} {f(start[1])} Z")
    return " ".join(path)


def seeker():
    return pol(*SEEKER_AT)


def tip_centre():
    return centre(1.0)


def grad(c, gid="ring-grad"):
    return (
        f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{f(C[0]-68)}" y1="{f(C[1]-88)}" x2="{f(C[0]+77)}" y2="{f(C[1]+87)}">'
        f'<stop offset="0" stop-color="{c["tip"]}"/><stop offset="1" stop-color="{c["deep"]}"/></linearGradient>'
    )


def static(c, title, comment=""):
    sx, sy = seeker()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256" role="img" aria-labelledby="t">
  <title id="t">{title}</title>{comment}
  <defs>
    {grad(c)}
  </defs>
  <g id="symbol">
    <path id="spiral" fill="url(#ring-grad)" d="{spiral_path()}"/>
    <circle id="seeker" cx="{f(sx)}" cy="{f(sy)}" r="{f(SEEKER_R)}" fill="{c["dot"]}"/>
  </g>
</svg>
"""


def flat(ring, dot, title):
    sx, sy = seeker()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256" role="img" aria-labelledby="t">
  <title id="t">{title}</title>
  <g id="symbol">
    <path id="spiral" fill="{ring}" d="{spiral_path()}"/>
    <circle id="seeker" cx="{f(sx)}" cy="{f(sy)}" r="{f(SEEKER_R)}" fill="{dot}"/>
  </g>
</svg>
"""


def animated(c, title):
    sx, sy = seeker()
    tx, ty = tip_centre()
    dx, dy = tx - sx, ty - sy
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256" role="img" aria-labelledby="t">
  <title id="t">{title}</title>
  <!-- Entrance (plays once): the spiral is drawn clockwise from its thick foundation to its thin frontier; the seeker is released
       from the tip of the spiral and rolls to its place in the opening; then a soft ripple repeats.
       Final frame == the static master (the ripple is invisible at rest). -->
  <style>
    #seeker-move, #ripple {{ transform-box: fill-box; transform-origin: center; }}
    #sweep       {{ animation: sweep 1.6s cubic-bezier(.65,0,.25,1) both; }}
    #seeker-move {{ animation: release .9s cubic-bezier(.3,1.35,.5,1) 1.45s both; }}
    #ripple      {{ opacity: 0; animation: ripple 2.6s ease-out 3.2s infinite; }}
    @keyframes sweep   {{ from {{ stroke-dasharray: 1.02 3; stroke-dashoffset: 1.02; }} to {{ stroke-dasharray: 1.02 3; stroke-dashoffset: 0; }} }}
    @keyframes release {{ from {{ transform: translate({f(dx)}px, {f(dy)}px) scale(.25); opacity: 0; }} 15% {{ opacity: 1; }} to {{ transform: none; opacity: 1; }} }}
    @keyframes ripple  {{ from {{ transform: scale(1); opacity: .6; }} to {{ transform: scale(2.2); opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{ #sweep, #seeker-move, #ripple {{ animation: none !important; }} }}
  </style>
  <defs>
    {grad(c)}
    <mask id="reveal" maskUnits="userSpaceOnUse" x="0" y="0" width="256" height="256">
      <!-- Starts in the opening (48deg) so the mask seam never crosses the artwork. -->
      <circle id="sweep" cx="{f(C[0])}" cy="{f(C[1])}" r="75" pathLength="1" fill="none" stroke="#fff" stroke-width="150" transform="rotate(-48 {f(C[0])} {f(C[1])})"/>
    </mask>
  </defs>
  <g id="symbol">
    <path id="spiral" mask="url(#reveal)" fill="url(#ring-grad)" d="{spiral_path()}"/>
    <circle id="ripple" cx="{f(sx)}" cy="{f(sy)}" r="{f(SEEKER_R)}" fill="none" stroke="{c["ripple"]}" stroke-width="3"/>
    <g id="seeker-move"><circle id="seeker" cx="{f(sx)}" cy="{f(sy)}" r="{f(SEEKER_R)}" fill="{c["dot"]}"/></g>
  </g>
</svg>
"""


def app_icon(bg, c, title):
    sx, sy = seeker()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256" role="img" aria-labelledby="t">
  <title id="t">{title}</title>
  <defs>
    {grad(c)}
  </defs>
  <rect width="256" height="256" rx="56" fill="{bg}"/>
  <g id="symbol" transform="translate(128 126) scale(.7) translate(-128 -128)">
    <path id="spiral" fill="url(#ring-grad)" d="{spiral_path()}"/>
    <circle id="seeker" cx="{f(sx)}" cy="{f(sy)}" r="{f(SEEKER_R)}" fill="{c["dot"]}"/>
  </g>
</svg>
"""


if __name__ == "__main__":
    (OUT / "static").mkdir(exist_ok=True)
    (OUT / "animated").mkdir(exist_ok=True)
    (OUT / "static" / "anveshan-symbol-light.svg").write_text(static(LIGHT, "Anveshan logo symbol"))
    (OUT / "static" / "anveshan-symbol-dark.svg").write_text(static(DARK, "Anveshan logo symbol, for dark backgrounds"))
    (OUT / "static" / "anveshan-symbol-flat.svg").write_text(flat(LIGHT["deep"], LIGHT["dot"], "Anveshan logo symbol, flat"))
    (OUT / "static" / "anveshan-app-icon.svg").write_text(app_icon("#221A2E", DARK, "Anveshan app icon"))
    (OUT / "animated" / "anveshan-animated-light.svg").write_text(animated(LIGHT, "Anveshan logo symbol (animated)"))
    (OUT / "animated" / "anveshan-animated-dark.svg").write_text(animated(DARK, "Anveshan logo symbol (animated, dark)"))
    p = spiral_path()
    print("ok", len(p), "chars,", p.count("C") + p.count("A"), "segments")
