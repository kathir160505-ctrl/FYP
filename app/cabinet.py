"""The trophy cabinet: an SVG drawing of a club's trophies, one figure per title, one shelf per competition type.

Drawn, not photographed, so every club gets its own cabinet without image rights. Each trophy shape loosely
follows its competition (big-eared European Cup, tall UEFA Cup vase, lidded league trophy, globe for world titles).
Trophies rise in one after another when the club changes; hover one for its season.
"""
import html

import pandas as pd

ICON_W, ICON_H, GAP = 34, 52, 6
PER_ROW = 26
LEFT = 205  # width of the shelf labels
WIDTH = LEFT + PER_ROW * (ICON_W + GAP) + 24

GOLD = ("#FBE7A1", "#E3B341", "#9A6B12")
SILVER = ("#F3F4F6", "#C3C8CF", "#6B7280")
BRONZE = ("#F5D0B0", "#C8834B", "#7C4A21")

# category -> (shape, metal)
STYLE = {"League title": ("league", GOLD), "Domestic cup": ("cup", GOLD), "League Cup": ("cup", SILVER),
         "European Cup": ("bigears", SILVER), "UEFA Cup": ("vase", SILVER), "Cup Winners' Cup": ("cup", SILVER),
         "Conference League": ("vase", BRONZE), "UEFA Super Cup": ("cup", GOLD), "World club title": ("globe", GOLD),
         "Second-tier title": ("cup", BRONZE)}

# Shapes drawn in a 40 x 60 box; "m" is the metal gradient id, "d" its dark edge colour.
SHAPES = {
    "cup": """<path d="M11 8h18v9a9 9 0 0 1-18 0z" fill="url(#{m})" stroke="{d}" stroke-width=".8"/>
<path d="M11 10H6v3a6 6 0 0 0 6 6M29 10h5v3a6 6 0 0 1-6 6" fill="none" stroke="url(#{m})" stroke-width="2.4"/>
<rect x="18" y="26" width="4" height="10" fill="url(#{m})"/><rect x="13" y="36" width="14" height="4" rx="1" fill="url(#{m})"/>""",
    "bigears": """<path d="M10 7h20v10a10 10 0 0 1-20 0z" fill="url(#{m})" stroke="{d}" stroke-width=".8"/>
<path d="M11 9C1 7-1 25 14 25M29 9c10-2 12 16-3 16" fill="none" stroke="url(#{m})" stroke-width="3"/>
<rect x="18" y="27" width="4" height="9" fill="url(#{m})"/><path d="M12 36h16l2 5H10z" fill="url(#{m})"/>""",
    "league": """<circle cx="20" cy="4" r="2" fill="url(#{m})"/><path d="M14 6h12l-1 3H15z" fill="url(#{m})"/>
<path d="M12 9h16l-2 14a6 6 0 0 1-12 0z" fill="url(#{m})" stroke="{d}" stroke-width=".8"/>
<path d="M13 12H8v2a5 5 0 0 0 5 5M27 12h5v2a5 5 0 0 1-5 5" fill="none" stroke="url(#{m})" stroke-width="2"/>
<rect x="18" y="29" width="4" height="7" fill="url(#{m})"/><path d="M13 36h14l1 5H12z" fill="url(#{m})"/>""",
    "vase": """<path d="M15 3h10l-1 6 3 14-4 6h-6l-4-6 3-14z" fill="url(#{m})" stroke="{d}" stroke-width=".8"/>
<path d="M16 9c-5 1-5 9 0 10M24 9c5 1 5 9 0 10" fill="none" stroke="url(#{m})" stroke-width="1.6"/>
<rect x="17" y="29" width="6" height="7" fill="url(#{m})"/><path d="M13 36h14l1 5H12z" fill="url(#{m})"/>""",
    "globe": """<circle cx="20" cy="14" r="10" fill="url(#{m})" stroke="{d}" stroke-width=".8"/>
<path d="M10 14h20M20 4c-6 6-6 14 0 20M20 4c6 6 6 14 0 20" fill="none" stroke="{d}" stroke-width=".7" opacity=".7"/>
<path d="M16 24h8l-1 12h-6z" fill="url(#{m})"/><path d="M12 36h16l1 5H11z" fill="url(#{m})"/>""",
}


def _gradients(uid: str) -> str:
    out = []
    for name, (hi, mid, lo) in (("gold", GOLD), ("silver", SILVER), ("bronze", BRONZE)):
        out.append(f'<linearGradient id="{uid}-{name}" x1="0" x2="1" y1="0" y2="1">'
                   f'<stop offset="0" stop-color="{hi}"/><stop offset=".5" stop-color="{mid}"/>'
                   f'<stop offset="1" stop-color="{lo}"/></linearGradient>')
    return "".join(out)


def _metal(colors: tuple) -> str:
    return {GOLD: "gold", SILVER: "silver", BRONZE: "bronze"}[colors]


def cabinet_html(honours: pd.DataFrame, labels: dict, order: list, team: str, crest: str | None, color: str) -> str:
    """honours: one row per trophy (category, competition, season) for one club."""
    uid = "tc" + str(abs(hash(team)) % 10**8)
    shelves = [(cat, honours[honours.category == cat]) for cat in order if (honours.category == cat).any()]
    rows = []  # (category, trophies on this row, is first row of the category)
    for cat, h in shelves:
        items = h.sort_values("end_year").to_dict("records")
        for i in range(0, len(items), PER_ROW):
            rows.append((cat, items[i:i + PER_ROW], i == 0))
    row_h = ICON_H + 20
    top = 70
    height = top + max(len(rows), 1) * row_h + 24
    parts, n = [], 0
    for r, (cat, items, first) in enumerate(rows):
        y = top + r * row_h
        shape, metal = STYLE.get(cat, ("cup", GOLD))
        if first:
            total = int((honours.category == cat).sum())
            parts.append(f'<text x="24" y="{y + ICON_H - 18}" class="lbl">{html.escape(labels.get(cat, cat))}</text>'
                         f'<text x="24" y="{y + ICON_H}" class="cnt">× {total}</text>')
        for i, t in enumerate(items):
            x = LEFT + i * (ICON_W + GAP)
            body = SHAPES[shape].format(m=f"{uid}-{_metal(metal)}", d=metal[2])
            tip = html.escape(f"{t['competition']} · {t['season']}")
            parts.append(f'<g class="tr" style="animation-delay:{min(n, 60) * 35}ms" '
                         f'transform="translate({x},{y}) scale({ICON_W / 40:.3f})"><title>{tip}</title>{body}</g>')
            n += 1
        # glass shelf with a soft highlight
        parts.append(f'<rect x="{LEFT - 14}" y="{y + ICON_H + 2}" width="{WIDTH - LEFT - 2}" height="5" rx="2" '
                     f'fill="url(#{uid}-shelf)"/>')
    if not rows:
        parts.append(f'<text x="{WIDTH / 2}" y="{top + 40}" text-anchor="middle" class="empty">'
                     'The cabinet is waiting for its first major trophy</text>')
    crest_img = (f'<image href="{html.escape(crest)}" x="22" y="14" width="40" height="40"/>' if crest else "")
    total = len(honours)
    return f'''<div class="cabinet"><style>
.cabinet svg {{ width: 100%; height: auto; display: block; border-radius: 10px; }}
.cabinet .lbl {{ font: 700 15px 'Barlow Condensed', 'Arial Narrow', sans-serif; fill: #E5E7EB; letter-spacing: .4px; text-transform: uppercase; }}
.cabinet .cnt {{ font: 800 20px 'Barlow Condensed', 'Arial Narrow', sans-serif; fill: #FBE7A1; }}
.cabinet .ttl {{ font: 800 24px 'Barlow Condensed', 'Arial Narrow', sans-serif; fill: #FFFFFF; text-transform: uppercase; }}
.cabinet .sub {{ font: 500 12px Inter, sans-serif; fill: #9CA3AF; }}
.cabinet .empty {{ font: 600 15px Inter, sans-serif; fill: #9CA3AF; }}
.cabinet .tr {{ animation: {uid}-rise .55s ease-out both; }}
.cabinet .tr:hover {{ filter: brightness(1.25) drop-shadow(0 0 6px rgba(251,231,161,.9)); cursor: default; }}
@keyframes {uid}-rise {{ from {{ opacity: 0; translate: 0 14px; }} to {{ opacity: 1; translate: 0 0; }} }}
@media (prefers-reduced-motion: reduce) {{ .cabinet .tr {{ animation: none; }} }}
</style>
<svg viewBox="0 0 {WIDTH} {height}" xmlns="http://www.w3.org/2000/svg" role="img"
 aria-label="{html.escape(team)} trophy cabinet: {total} trophies">
<defs>{_gradients(uid)}
<radialGradient id="{uid}-glow" cx=".5" cy="0" r="1"><stop offset="0" stop-color="#2B3442"/><stop offset="1" stop-color="#0B0F16"/></radialGradient>
<linearGradient id="{uid}-shelf" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#E5F0FF" stop-opacity=".55"/><stop offset="1" stop-color="#93A4BA" stop-opacity=".15"/></linearGradient>
</defs>
<rect width="{WIDTH}" height="{height}" rx="10" fill="#3A2A1C"/>
<rect x="8" y="8" width="{WIDTH - 16}" height="{height - 16}" rx="6" fill="url(#{uid}-glow)"/>
<rect x="8" y="8" width="{WIDTH - 16}" height="4" fill="{color}"/>
{crest_img}<text x="72" y="36" class="ttl">{html.escape(team)} trophy cabinet</text>
<text x="72" y="54" class="sub">{total} major honours · hover a trophy for its season</text>
{"".join(parts)}
</svg></div>'''
