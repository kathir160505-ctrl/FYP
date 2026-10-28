import html

import numpy as np
import pandas as pd
import streamlit as st

import charts
import data
import ui

COMPETITION_SHORT = {"Premier League": "EPL", "La Liga": "LaLiga", "Serie A": "Serie A", "Champions League": "UCL"}


def pick_player(p: pd.DataFrame) -> pd.Series:
    seasons = sorted(p.season.unique(), reverse=True)
    q = st.query_params
    with ui.panel():
        c0, c1, c2, c3 = st.columns([0.8, 1, 1.4, 2])
        season = c0.selectbox("Season", seasons, format_func=data.season_label,
                              index=seasons.index(int(q["season"])) if q.get("season", "").isdigit()
                              and int(q["season"]) in seasons else 0)
        ps = p[p.season == season]
        league = c1.selectbox("League", ["All leagues", *data.LEAGUE_FLAGS])
        if league != "All leagues":
            ps = ps[ps.league_name == league]
        clubs = sorted(ps.team.unique())
        default_club = q.get("club", "Manchester United")
        team = c2.selectbox("Club", clubs, index=clubs.index(default_club) if default_club in clubs else 0)
        squad = ps[ps.team == team].sort_values("minutes", ascending=False)
        names = squad.name.tolist()
        default = q.get("player")
        name = c3.selectbox("Player", names, index=names.index(default) if default in names else 0,
                            format_func=lambda n: f"{n} · {squad.set_index('name').group.get(n, '')}")
    st.query_params.update({"season": str(season), "club": team, "player": name})
    return squad[squad.name == name].iloc[0]


def radar_series(p: pd.DataFrame, row: pd.Series) -> tuple[list, list]:
    metrics = data.PLAYER_RADAR["Goalkeeper" if row.group == "Goalkeeper" else "outfield"]
    metrics = [(c, l) for c, l in metrics if f"{c}_pct" in p.columns]
    return [l for _, l in metrics], [row.get(f"{c}_pct", np.nan) for c, _ in metrics]


def render() -> None:
    if not data.players_ready():
        ui.page_header("Players", "Player profiles", "Every player in the Premier League, La Liga and Serie A.")
        ui.callout("Player data is still being prepared. Run <code>python -m src.collect.players</code>, then "
                   "<code>python -m src.process.build_players</code>, and restart the app.", warn=True)
        return
    p = data.players()
    p["season_label"] = p.season.map(data.season_label)
    ui.page_header("Players", "Player profiles",
                   "Every player in the Premier League, La Liga and Serie A since 2025/26: attacking output from "
                   "Understat, defending and goalkeeping from FBref, and match-by-match line-ups from ESPN.")
    row = pick_player(p)
    meta = data.clubs().set_index("team")
    hist = data.history().drop_duplicates("team").set_index("team")
    color = hist.color.get(row.team, "#6B7280")
    crest = hist.logo.get(row.team) if row.team in hist.index else None
    crest = crest if isinstance(crest, str) else None
    ui.player_header(row, crest, color)

    gk = row.group == "Goalkeeper"
    per90 = lambda c: f"{row[c]:.2f} per 90" if pd.notna(row.get(c)) else ""  # noqa: E731
    if gk:
        ui.kpis([("Appearances", f"{int(row.matches)}", f"{int(row.starts) if pd.notna(row.starts) else '–'} starts", color),
                 ("Saves", f"{int(row.saves) if pd.notna(row.get('saves')) else '–'}", per90("saves_p90"), color),
                 ("Save %", f"{row.save_pct:.0f}%" if pd.notna(row.get("save_pct")) else "–", "of shots on target", color),
                 ("Clean sheets", f"{int(row.clean_sheets) if pd.notna(row.get('clean_sheets')) else '–'}", "FBref", color),
                 ("Goals conceded", f"{int(row.goals_conceded) if pd.notna(row.get('goals_conceded')) else '–'}", "", color)])
    else:
        ui.kpis([("Appearances", f"{int(row.matches)}", f"{int(row.starts) if pd.notna(row.starts) else '–'} starts", color),
                 ("Expected goals", f"{row.xg:.1f}", f"{row.goals - row.xg:+.1f} goals vs xG", color),
                 ("Expected assists", f"{row.xa:.1f}", f"{row.assists - row.xa:+.1f} assists vs xA", color),
                 ("Shots", f"{int(row.shots)}", per90("shots_p90"), color),
                 ("Key passes", f"{int(row.key_passes)}", per90("key_passes_p90"), color),
                 ("Tackles won", f"{int(row.tackles_won)}" if pd.notna(row.get("tackles_won")) else "–",
                  per90("tackles_won_p90"), color)])

    c1, c2 = st.columns([1, 1.15], gap="medium")
    with c1:
        labels, values = radar_series(p, row)
        with ui.panel("Percentile profile", f"Per 90 minutes, against {row.group.lower()}s in the three leagues "
                      f"({row.season_label}, regular players only)"):
            if row.in_pool and not all(pd.isna(v) for v in values):
                st.plotly_chart(charts.player_radar(labels, values, color), width="stretch",
                                key=f"pradar-{row.player_id}-{row.season}")
            else:
                ui.note("Not enough minutes yet for a fair comparison: percentiles need at least 30% of the club's "
                        "league minutes.")
    with c2:
        with ui.panel("Most similar players", f"Closest per-90 profile among {row.group.lower()}s, all three leagues"):
            sim = similar_players(p, row)
            if sim.empty:
                ui.note("Not enough minutes for a comparison.")
            else:
                st.dataframe(sim, hide_index=True, width="stretch", height=390, column_config={
                    "": st.column_config.ImageColumn(width="small"),
                    "Similarity": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100)})

    with ui.panel("Match log", "League and Champions League matches · from ESPN match sheets"):
        if pd.isna(row.athlete_id):
            ui.note("This player could not be linked to ESPN match sheets.")
        else:
            m = data.player_matches(row.athlete_id)
            m = m[m.season == row.season].sort_values("date", ascending=False)
            st.dataframe(pd.DataFrame({
                "Date": m.date.dt.strftime("%d %b %Y"), "Comp": m.competition_name.map(COMPETITION_SHORT),
                "Club": m.team, "Opponent": m.opponent, "": m.home_away.map({"home": "H", "away": "A"}),
                "Role": np.where(m.starter, "Started", np.where(m.subbed_in, "Sub", "Unused")),
                "Position": m.position.fillna(""), "Sub": m.sub_minute.fillna(""),
                "Goals": m.goals, "Assists": m.assists, "Shots": m.shots,
                "Cards": [("🟥" if r else "") + ("🟨" if y else "") for y, r in zip(m.yellow.fillna(0), m.red.fillna(0))]}),
                hide_index=True, width="stretch", height=min(420, 35 * (len(m) + 1) + 3))

    leaders(p[p.season == row.season])
    ui.note("Sources: Understat (attacking stats, xG model), FBref (tackles won, interceptions, crosses, goalkeeping), "
            "ESPN (line-ups, shirt numbers). Photos: Wikimedia Commons via Wikidata, where a freely licensed photo "
            "exists; other players are shown with their initials. Click a photo in a table to open it.")
    ui.footer()


def similar_players(p: pd.DataFrame, row: pd.Series, n: int = 8) -> pd.DataFrame:
    if not row.in_pool:
        return pd.DataFrame()
    cols = [c for c, _ in data.PLAYER_RADAR["Goalkeeper" if row.group == "Goalkeeper" else "outfield"]]
    cols = [f"{c}_pct" for c in cols if f"{c}_pct" in p.columns]
    pool = p[(p.season == row.season) & (p.group == row.group) & p.in_pool].dropna(subset=cols)
    if row.name not in pool.index:
        return pd.DataFrame()
    dist = np.sqrt(((pool[cols] - pool.loc[row.name, cols]) ** 2).mean(axis=1))
    near = pool.assign(dist=dist).drop(row.name).nsmallest(n, "dist")
    return pd.DataFrame({"": data.photos(near), "Player": near.name, "Club": near.team, "League": near.league_name,
                         "Minutes": near.minutes, "Similarity": (100 - near.dist).clip(0, 100)})


def leaders(p: pd.DataFrame) -> None:
    metrics = {"Goals": "goals", "Expected goals": "xg", "Assists": "assists", "Expected assists": "xa",
               "Key passes": "key_passes", "xG chain": "xg_chain", "Tackles won": "tackles_won",
               "Interceptions": "interceptions", "Saves": "saves"}
    with ui.panel("League leaders", f"{data.season_label(p.season.iloc[0])} · totals across the three leagues"):
        c1, c2, c3 = st.columns([1.2, 1, 1])
        label = c1.selectbox("Metric", list(metrics), key="leader_metric")
        league = c2.selectbox("League", ["All leagues", *data.LEAGUE_FLAGS], key="leader_league")
        group = c3.selectbox("Position", ["All positions", *data.POSITION_GROUPS], key="leader_group")
        col = metrics[label]
        d = p if league == "All leagues" else p[p.league_name == league]
        d = d if group == "All positions" else d[d.group == group]
        top = d.dropna(subset=[col]).nlargest(15, col)
        st.dataframe(pd.DataFrame({"": data.photos(top), "Player": top.name, "Club": top.team, "League": top.league_name,
                                   "Position": top.group, "Minutes": top.minutes, label: top[col]}),
                     hide_index=True, width="stretch", height=560, column_config={
                         "": st.column_config.ImageColumn(width="small"),
                         label: st.column_config.ProgressColumn(format="%.1f" if col in ("xg", "xa", "xg_chain") else "%d",
                                                                min_value=0, max_value=float(top[col].max() or 1))})
