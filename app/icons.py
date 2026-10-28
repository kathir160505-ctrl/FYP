"""Small inline SVG icons for the match centre (goal, assist, cards, substitutions), drawn to read at 12-16 px.

Inline SVG instead of emoji, so they look the same on every system and match the site's flat style."""

_BALL = ('<circle cx="8" cy="8" r="7" fill="#fff" stroke="#111827" stroke-width="1.2"/>'
         '<path d="M8 4.6 10.6 6.5 9.6 9.6H6.4L5.4 6.5Z" fill="#111827"/>'
         '<path d="M8 1v3.6M10.6 6.5l3.6-1.1M9.6 9.6l2.2 3.2M6.4 9.6l-2.2 3.2M5.4 6.5 1.8 5.4" stroke="#111827" stroke-width="1"/>')
_SHAPES = {
    "goal": _BALL,
    "own_goal": _BALL.replace('fill="#fff"', 'fill="#FCA5A5"', 1),
    "assist": ('<path d="M1.5 9.5V4.2h4.2l1.1 2.3 4.9 1.2c1.6.4 2.8 1.6 2.8 3v.8H1.5z" fill="#111827"/>'
               '<path d="M3 12v1.6M6 12v1.6M9 12v1.6M12 12v1.6" stroke="#111827" stroke-width="1.3"/>'),
    "yellow": '<rect x="4" y="1.5" width="8.5" height="12" rx="1.2" fill="#FACC15" transform="rotate(8 8 8)"/>',
    "red": '<rect x="4" y="1.5" width="8.5" height="12" rx="1.2" fill="#DC2626" transform="rotate(8 8 8)"/>',
    "second_yellow": ('<rect x="2.5" y="1.5" width="7.5" height="11" rx="1.1" fill="#FACC15"/>'
                      '<rect x="6" y="3.5" width="7.5" height="11" rx="1.1" fill="#DC2626"/>'),
    "sub_in": '<path d="M8 2 13.5 8.5H10V14H6V8.5H2.5Z" fill="#16A34A"/>',
    "sub_out": '<path d="M8 14 2.5 7.5H6V2h4v5.5h3.5Z" fill="#DC2626"/>',
    "penalty_miss": _BALL + '<path d="M3 3l10 10M13 3 3 13" stroke="#DC2626" stroke-width="1.8"/>',
    "injury": ('<rect x="1" y="1" width="14" height="14" rx="3" fill="#fff" stroke="#DC2626" stroke-width="1.4"/>'
               '<path d="M6.5 4h3v2.5H12v3H9.5V12h-3V9.5H4v-3h2.5z" fill="#DC2626"/>'),
    "doubt": ('<circle cx="8" cy="8" r="7" fill="#F59E0B"/><text x="8" y="11.6" font-size="10" font-family="Arial" '
              'font-weight="700" fill="#fff" text-anchor="middle">?</text>'),
    "unavailable": '<circle cx="8" cy="8" r="7" fill="#6B7280"/><path d="M4.5 8h7" stroke="#fff" stroke-width="2"/>',
    "var": '<rect x="1" y="3" width="14" height="10" rx="2" fill="#111827"/><text x="8" y="10.6" font-size="6.5" '
           'font-family="Arial" font-weight="700" fill="#fff" text-anchor="middle">VAR</text>',
}


def icon(name: str, size: int = 14, title: str = "") -> str:
    tip = f"<title>{title}</title>" if title else ""
    return (f'<svg class="ico" width="{size}" height="{size}" viewBox="0 0 16 16" role="img" aria-label="{title or name}">'
            f'{tip}{_SHAPES[name]}</svg>')


def repeat(name: str, n: int, size: int = 14, title: str = "") -> str:
    return "".join(icon(name, size, title) for _ in range(int(n)))
