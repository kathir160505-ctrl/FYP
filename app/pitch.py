"""HTML/CSS line-up components for the match centre: a vertical pitch with both XIs, substitutes rows,
team stats rows and the key-event timeline. Plain HTML keeps names and icons crisp at any size."""
import html

import pandas as pd

from charts import formation_layout
from icons import icon, repeat


def short_name(name: str) -> str:
    """Surname for long names ('Bryan Mbeumo' -> 'Mbeumo'); keeps particles ('De Ligt', 'Van Dijk')."""
    parts = str(name).split()
    if len(name) <= 10 or len(parts) == 1:
        return name
    particles = {"de", "van", "der", "den", "da", "di", "dos", "del", "la", "le", "von", "ter", "el"}
    i = len(parts) - 1
    while i > 0 and parts[i - 1].lower() in particles:
        i -= 1
    return " ".join(p.capitalize() if p.lower() in particles and k == 0 else p
                    for k, p in enumerate(parts[i:]))


def player_icons(r) -> str:
    """Goals, own goals, assists and cards for one player row (from mc.lineups)."""
    n = lambda col: int(getattr(r, col, 0) or 0) if getattr(r, col, 0) == getattr(r, col, 0) else 0  # noqa: E731
    out = repeat("goal", n("goals"), 13, "Goal") + repeat("own_goal", n("own_goals"), 13, "Own goal")
    out += repeat("assist", n("assists"), 13, "Assist")
    if n("red") and n("yellow"):
        out += icon("second_yellow", 13, "Second yellow")
    elif n("red"):
        out += icon("red", 13, "Red card")
    elif n("yellow"):
        out += icon("yellow", 13, "Yellow card")
    return out


def _token(r, x: float, y: float, color: str, with_events: bool, links: dict | None = None) -> str:
    left, top = x / 68 * 100, (105 - y) / 105 * 100
    events = player_icons(r) if with_events else ""
    off = (f'<span class="pl-off">{icon("sub_out", 11, "Substituted")}{html.escape(str(r.sub_minute))}</span>'
           if with_events and getattr(r, "subbed_out", False) and getattr(r, "sub_minute", "") else "")
    tip = html.escape(f"{r.player} · {getattr(r, 'position', '') or ''}"
                      + (f" · {r.note}" if isinstance(getattr(r, "note", None), str) and r.note else ""))
    number = html.escape(str(r.jersey)) if isinstance(getattr(r, "jersey", None), str) and r.jersey else ""
    url = (links or {}).get(str(getattr(r, "athlete_id", "")))
    tag, attrs = ("a", f' href="{html.escape(url)}" target="_self"') if url else ("div", "")
    return (f'<{tag} class="pl{" link" if url else ""}" style="left:{left:.1f}%;top:{top:.1f}%" '
            f'title="{tip}{" · open profile" if url else ""}"{attrs}>'
            f'<div class="pl-num" style="background:{color}">{number}'
            f'{f"<span class=pl-ev>{events}</span>" if events else ""}{off}</div>'
            f'<div class="pl-name">{html.escape(short_name(r.player))}</div></{tag}>')


def pitch(home: pd.DataFrame | None, away: pd.DataFrame | None, home_color: str, away_color: str,
          with_events: bool = True, links: dict | None = None) -> str:
    """Home XI in the bottom half attacking up, away XI in the top half attacking down."""
    tokens = []
    for xi, color, side in ((home, home_color, "home"), (away, away_color, "away")):
        if xi is None or xi.empty:
            continue
        d = formation_layout(xi, xi.formation.iloc[0] if "formation" in xi else None)
        for r in d.itertuples():
            y = r.y * 0.46 + 2.5 if side == "home" else 102.5 - r.y * 0.46
            x = r.x if side == "home" else 68 - r.x
            tokens.append(_token(r, x, y, color, with_events, links))
    return ('<div class="pitch"><div class="pitch-lines"><i class="half"></i><i class="circle"></i><i class="spot"></i>'
            '<i class="box top"></i><i class="six top"></i><i class="box bottom"></i><i class="six bottom"></i></div>'
            + "".join(tokens) + "</div>")


def team_pitch(xi: pd.DataFrame, color: str, with_events: bool = True, links: dict | None = None) -> str:
    """One XI over the full pitch, attacking upwards (club pages)."""
    d = formation_layout(xi, xi.formation.iloc[0] if "formation" in xi else None)
    tokens = [_token(r, r.x, r.y * 0.92 + 4, color, with_events, links) for r in d.itertuples()]
    return ('<div class="pitch"><div class="pitch-lines"><i class="half"></i><i class="circle"></i><i class="spot"></i>'
            '<i class="box top"></i><i class="six top"></i><i class="box bottom"></i><i class="six bottom"></i></div>'
            + "".join(tokens) + "</div>")


def bench(df: pd.DataFrame, team: str, formation: str, crest: str | None, color: str,
          links: dict | None = None) -> str:
    """Substitutes used (green arrow, minute, their goals/assists/cards) in one row, then the unused names."""
    subs = df[~df.starter]
    used = subs[subs.subbed_in].copy()
    used["m"] = used.sub_minute.str.extract(r"(\d+)").astype(float)
    links = links or {}

    def name(r) -> str:
        url = links.get(str(r.athlete_id))
        return (f'<a href="{html.escape(url)}" target="_self">{html.escape(r.player)}</a>' if url
                else html.escape(r.player))
    chips = "".join(f'<span class="sub-chip">{icon("sub_in", 12, "Came on")}<b>{html.escape(str(r.sub_minute))}</b>'
                    f'{name(r)}{player_icons(r)}</span>'
                    for r in used.sort_values("m").itertuples())
    unused = ", ".join(name(r) for r in subs[~subs.subbed_in].itertuples())
    logo = f'<img src="{html.escape(crest)}" alt="">' if crest else ""
    return (f'<div class="bench"><div class="bench-head" style="--c:{color}">{logo}<b>{html.escape(team)}</b>'
            f'<span>{html.escape(str(formation or ""))}</span></div>'
            f'<div class="sub-row">{chips or "<span class=muted>No substitutions</span>"}</div>'
            + (f'<div class="unused"><span>Unused</span> {unused}</div>' if unused else "") + "</div>")


def stats_rows(stats: pd.DataFrame, home_color: str, away_color: str) -> str:
    """Home value | label | away value, a split bar underneath; the larger value in bold."""
    rows = []
    for r in stats.itertuples():
        pct = "%" in r.stat or r.stat == "Pass accuracy"
        f = (lambda v: f"{v:.0f}%") if pct else (lambda v: f"{v:.0f}")
        total = (r.home + r.away) or 1
        hb, ab = ("hi" if r.home > r.away else ""), ("hi" if r.away > r.home else "")
        label = r.stat.replace(" %", "")
        rows.append(f'<div class="st"><div class="st-top"><span class="{hb}">{f(r.home)}</span><span class="st-l">'
                    f'{html.escape(label)}</span><span class="{ab}">{f(r.away)}</span></div><div class="st-bar">'
                    f'<i style="width:{r.home / total * 100:.1f}%;background:{home_color}"></i>'
                    f'<i style="width:{r.away / total * 100:.1f}%;background:{away_color}"></i></div></div>')
    return '<div class="stats">' + "".join(rows) + "</div>"


EVENT_TITLES = {"goal": "Goal", "own_goal": "Own goal", "yellow": "Yellow card", "red": "Red card",
                "second_yellow": "Second yellow card", "penalty_miss": "Penalty missed"}


def timeline(ev: pd.DataFrame, home: dict, away: dict) -> str:
    """Key events in match order: home events on the left, away on the right, minute in the middle."""
    head = (f'<div class="tl-head"><span>{_crest(home)}{html.escape(home["team"])}</span>'
            f'<span>{html.escape(away["team"])}{_crest(away)}</span></div>')
    rows = []
    for r in ev.itertuples():
        if r.kind in ("ht", "ft"):
            label = "Half-time" if r.kind == "ht" else "Full-time"
            rows.append(f'<div class="tl-div">{label}</div>')
            continue
        if r.kind == "sub":
            body = (f'<div class="tl-main">{icon("sub_in", 13, "On")}{html.escape(r.player)}</div>'
                    f'<div class="tl-sub">{icon("sub_out", 13, "Off")}{html.escape(r.other)}'
                    f'{" · injury" if r.injury else ""}</div>')
        else:
            extra = ""
            if r.kind == "goal" and r.other:
                extra = f'<div class="tl-sub">{icon("assist", 12, "Assist")}{html.escape(r.other)}</div>'
            elif r.kind == "own_goal":
                extra = '<div class="tl-sub">Own goal</div>'
            score = f'<span class="tl-score">{r.score}</span>' if r.score else ""
            body = (f'<div class="tl-main">{icon(r.kind, 15, EVENT_TITLES.get(r.kind, ""))}'
                    f'{html.escape(r.player)}{score}</div>{extra}')
        cell = f'<div class="tl-cell {"goal" if r.kind in ("goal", "own_goal") else ""}">{body}</div>'
        left, right = (cell, "<div></div>") if r.side == "home" else ("<div></div>", cell)
        rows.append(f'<div class="tl-row">{left}<div class="tl-min">{html.escape(r.minute)}</div>{right}</div>')
    return f'<div class="tl">{head}{"".join(rows) or "<div class=muted>No events recorded.</div>"}</div>'


def _crest(t: dict) -> str:
    return f'<img src="{html.escape(t["logo"])}" alt="">' if t.get("logo") else ""


def scorers(ev: pd.DataFrame, side: str) -> str:
    """'Nico Paz 2', 57' · Douvikas 49'' style list under the scoreboard."""
    g = ev[(ev.side == side) & ev.kind.isin(["goal", "own_goal"])] if len(ev) else ev
    by = {}
    for r in g.itertuples():
        by.setdefault(r.player + (" (OG)" if r.kind == "own_goal" else ""), []).append(r.minute)
    return "<br>".join(f"{html.escape(p)} {', '.join(m)}" for p, m in by.items())


INJURY_ICON = {"injured": ("injury", "Injured"), "suspended": ("red", "Suspended"), "doubtful": ("doubt", "Doubtful"),
               "unavailable": ("unavailable", "Unavailable")}


def injury_list(df: pd.DataFrame, color: str, links: dict | None = None, avatar=None) -> str:
    """Injured, suspended and doubtful players: photo with a status badge, name, position and shirt number, then
    the status, reason and expected return (or chance of playing)."""
    if df is None or df.empty:
        return '<div class="muted">No injuries or suspensions reported.</div>'
    rows = []
    for r in df.itertuples():
        ico, label = INJURY_ICON.get(r.kind, ("injury", r.kind.title()))
        photo = r.photo if isinstance(r.photo, str) and r.photo else (avatar(r.player, color) if avatar else "")
        url = (links or {}).get(str(r.athlete_id)) if isinstance(r.athlete_id, str) else None
        name = html.escape(r.player)
        name = f'<a href="{html.escape(url)}" target="_self">{name}</a>' if url else name
        meta = " · ".join(x for x in (r.position, f"#{r.jersey}" if isinstance(r.jersey, str) and r.jersey else "") if x)
        detail = str(r.detail or "")
        status = label if not detail else f"{label} · {html.escape(detail)}"
        rows.append(f'<div class="inj"><div class="inj-face"><img src="{html.escape(photo)}" alt="">'
                    f'<span class="inj-badge">{icon(ico, 15, label)}</span></div>'
                    f'<div><div class="inj-name">{name}<span>{html.escape(" · " + meta) if meta else ""}</span></div>'
                    f'<div class="inj-status {r.kind}">{status}</div></div></div>')
    return '<div class="inj-list">' + "".join(rows) + "</div>"
