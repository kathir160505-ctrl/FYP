import html

import pandas as pd
import streamlit as st

import charts
import data
import ui

SPEED_ORDER = ["Fast", "Normal", "Standard", "Slow"]
SITUATION_ORDER = ["OpenPlay", "FromCorner", "SetPiece", "DirectFreekick", "Penalty"]
ZONE_ORDER = ["shotSixYardBox", "shotPenaltyArea", "shotOboxTotal"]
ZONE_NAMES = {"shotSixYardBox": "Six-yard box", "shotPenaltyArea": "Penalty area", "shotOboxTotal": "Outside box"}


def style_fit(silhouette: float) -> str:
    if silhouette >= 0.3:
        return "Clear fit"
    if silhouette >= 0.1:
        return "Typical"
    if silhouette >= 0:
        return "Borderline"
    return "Between styles"


def pick_club(df: pd.DataFrame) -> str:
    teams = data.club_options(df)
    default = st.query_params.get("club", "Manchester United")
    with ui.panel():
        c1, c2 = st.columns([1, 3])
        league = c1.selectbox("League", ["All leagues", *data.LEAGUE_FLAGS])
        pool = teams if league == "All leagues" else df[df.league_name == league].sort_values("team").team.tolist()
        team = c2.selectbox("Club", pool, index=pool.index(default) if default in pool else 0)
    st.query_params["club"] = team
    return team


def render() -> None:
    df = data.clubs()
    ui.page_header("Club profile", "Season attacking report",
                   "How a club attacked across the 2025/26 season: its style, fingerprint, chance creation, shot "
                   "locations and closest stylistic peers in all three leagues.")
    team = pick_club(df)
    row = df.set_index("team").loc[team]
    ui.club_header(df[df.team == team].iloc[0])

    league_df = df[df.league_name == row.league_name]
    accent = row.color
    ui.kpis([
        ("xG per match", f"{row.xg:.2f}", f"#{row.xg_lrank} of 20 in {row.league_name}", accent),
        ("Goals per match", f"{row.goals:.2f}", f"#{row.goals_lrank} of 20 in {row.league_name}", accent),
        ("Possession", f"{row.possession:.1f}%", f"#{row.possession_lrank} of 20 in {row.league_name}", accent),
        ("Shots per match", f"{row.shots:.1f}", f"#{row.shots_lrank} of 20 in {row.league_name}", accent),
        ("Long-ball share", f"{row.long_ball_share:.1f}%", f"#{row.long_ball_share_lrank} most direct of 20", accent),
        ("Style fit", style_fit(row.silhouette), f"silhouette {row.silhouette:.2f}", data.CLUSTER_COLORS[row.cluster]),
    ])

    c1, c2 = st.columns([1.1, 1], gap="medium")
    with c1:
        with ui.panel("Attacking fingerprint", "Percentile among all 60 clubs (100 = highest in the three leagues)"):
            cluster_avg = df[df.cluster == row.cluster][[f"{f}_pct" for f in data.FEATURES]].mean().to_numpy()
            st.plotly_chart(charts.radar([
                {"name": team, "values": [row[f"{f}_pct"] for f in data.FEATURES], "color": row.color},
                {"name": f"{row.cluster} average", "values": cluster_avg, "color": data.CLUSTER_COLORS[row.cluster],
                 "fill": False, "dash": "dot"},
            ], height=420), width="stretch")
    with c2:
        with ui.panel("Attacking identity", "What sets this club apart from the other 59"):
            cm = data.cluster_model()
            ui.callout(f"{ui.cluster_badge(row.cluster)}<div style='margin-top:0.5rem'>{cm['blurbs'][row.cluster]}</div>")
            z = ((row[data.FEATURES] - df[data.FEATURES].mean()) / df[data.FEATURES].std()).astype(float).sort_values()
            picks = list(z.index[::-1][:3]) + list(z.index[:2])
            ui.traits([(data.SHORT_LABELS[f], f"{data.fmt(f, row[f])} · #{row[f + '_lrank']} of 20 in {row.league_name}",
                        z[f]) for f in picks])
            if row.cluster_h1 != row.cluster_h2:
                ui.callout(f"Style shift during the season: <b>{row.cluster_h1}</b> in matchweeks 1–19, "
                           f"<b>{row.cluster_h2}</b> in matchweeks 20–38.", warn=True)
            else:
                ui.note(f"Consistent all season: {row.cluster_h1} in both halves.")

    tm = data.team_matches()
    club_tm = tm[tm.team == team]
    st.write("")
    tabs = st.tabs([":material/timeline: Season timeline", ":material/sports_soccer: Shot map",
                    ":material/bolt: How they attack", ":material/splitscreen: First vs second half",
                    ":material/hub: Similar clubs", ":material/history: 2025/26 vs 2026/27",
                    ":material/emoji_events: Honours & managers"])

    with tabs[0]:
        with ui.panel("Match Attacking Index", "Within-league z-score of xG, shots, deep completions, box shots and "
                      "possession · bars coloured by result · dashed line marks mid-season"):
            st.plotly_chart(charts.timeline(club_tm, row.color), width="stretch")
        with ui.panel("Chance creation vs concession", "Five-match rolling average"):
            st.plotly_chart(charts.xg_flow(club_tm, row.color), width="stretch")

    with tabs[1]:
        s = data.shots()
        s = s[s.team == team]
        with ui.panel():
            all_sit = sorted(s.situation.dropna().unique())
            situations = st.pills("Situation", all_sit, selection_mode="multi", default=all_sit) or all_sit
            c2, c3 = st.columns([1, 2])
            venue = c2.segmented_control("Venue", ["All", "Home", "Away"], default="All") or "All"
            mw = c3.slider("Matchweeks", 1, 38, (1, 38))
        f = s[s.situation.isin(situations) & s.matchweek.between(*mw)]
        if venue != "All":
            f = f[f.is_home == (venue == "Home")]
        ui.kpis([("Shots", f"{len(f)}", "in selection", row.color),
                 ("Goals", f"{int((f.result == 'Goal').sum())}", "own goals excluded", row.color),
                 ("Shot xG", f"{f.xg.sum():.1f}", "sum of individual shots", row.color),
                 ("xG per shot", f"{f.xg.mean():.3f}" if len(f) else "–", "average chance quality", row.color),
                 ("In the box", f"{f.in_box.mean():.0%}" if len(f) else "–",
                  f"all-club average {df.box_shot_share.mean():.0f}%", row.color)])
        c1, c2 = st.columns([1.35, 1], gap="medium")
        with c1:
            with ui.panel("Shot map", "Marker size = xG · gold stars are goals"):
                st.plotly_chart(charts.shot_map(f, row.color), width="stretch")
                ui.note("Shot data: Understat. Shot xG is the sum of individual shots. Match and season xG elsewhere use "
                        "Understat's match figure, which counts a rebound sequence as one chance (at most 1.0 xG), so "
                        "it can be slightly lower.")
        with c2:
            with ui.panel("Top shooters", "For the current selection"):
                if len(f):
                    top = (f.groupby("player").agg(Shots=("xg", "size"), Goals=("result", lambda r: (r == "Goal").sum()),
                                                   xG=("xg", "sum")).sort_values("xG", ascending=False).head(10)
                           .reset_index().rename(columns={"player": "Player"}))
                    top["G − xG"] = top.Goals - top.xG
                    st.dataframe(top, hide_index=True, width="stretch", height=410, column_config={
                        "xG": st.column_config.ProgressColumn("xG", format="%.1f", min_value=0,
                                                              max_value=float(top.xG.max())),
                        "G − xG": st.column_config.NumberColumn(format="%+.1f")})
                else:
                    ui.note("No shots match the current filters.")

    with tabs[2]:
        br = data.breakdowns()
        br = br[br.team == team]
        c1, c2, c3 = st.columns(3, gap="small")
        fast_rank = int(df.fast_attack_shots.rank(ascending=False, method="min")[df.team == team].iloc[0])
        with c1:
            with ui.panel("Attack speed", f"Fast attacks ≈ counter-attacks · #{fast_rank} of 60 for fast-attack shots"):
                st.plotly_chart(charts.breakdown_bars(br[br.block == "attackSpeed"], SPEED_ORDER, row.color), width="stretch")
        with c2:
            with ui.panel("Shot situation", "Where the chances came from"):
                sit = br[br.block == "situation"]
                st.plotly_chart(charts.breakdown_bars(sit, [c for c in SITUATION_ORDER if c in set(sit.category)], row.color),
                                width="stretch")
        with c3:
            with ui.panel("Shot zone", "Distance of attempts from goal"):
                zone = br[(br.block == "shotZone") & br.category.isin(ZONE_ORDER)].assign(
                    category=lambda d: d.category.map(ZONE_NAMES))
                st.plotly_chart(charts.breakdown_bars(zone, [ZONE_NAMES[z] for z in ZONE_ORDER], row.color), width="stretch")
        with ui.panel("Feature comparison", f"{team} against its league and its style group"):
            comp = pd.DataFrame({
                "Metric": [data.SHORT_LABELS[f] for f in data.FEATURES],
                team: [data.fmt(f, row[f]) for f in data.FEATURES],
                f"{row.league_name} avg": [data.fmt(f, league_df[f].mean()) for f in data.FEATURES],
                f"{row.cluster} avg": [data.fmt(f, df[df.cluster == row.cluster][f].mean()) for f in data.FEATURES],
                "League rank": [row[f + "_lrank"] for f in data.FEATURES],
                "Percentile (all 60)": [row[f + "_pct"] for f in data.FEATURES],
            })
            st.dataframe(comp, hide_index=True, width="stretch", column_config={
                "League rank": st.column_config.NumberColumn(format="#%d"),
                "Percentile (all 60)": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100)})

    with tabs[3]:
        h = data.halves()
        h = h[h.team == team].set_index("half")
        feats = [f for f in data.FEATURES if f in h.columns]
        c1, c2 = st.columns([1.1, 1], gap="medium")
        with c1:
            with ui.panel("First half vs second half", "Percentiles among all 60 clubs in the same half · counter-attacks "
                          "are season-level only (shown at 50)"):
                all_h = data.halves()
                pct = {half: [data.percent_rank(all_h[all_h.half == half][f], h.loc[half, f]) if f in feats else 50
                              for f in data.FEATURES] for half in ("H1", "H2")}
                st.plotly_chart(charts.radar([
                    {"name": "Matchweeks 1–19", "values": pct["H1"], "color": "#9CA3AF", "fill": False},
                    {"name": "Matchweeks 20–38", "values": pct["H2"], "color": row.color}], height=420), width="stretch")
        with c2:
            with ui.panel("Change by metric", f"Style: {row.cluster_h1} → {row.cluster_h2}"):
                tbl = pd.DataFrame({"Metric": [data.SHORT_LABELS[f] for f in feats],
                                    "MW 1–19": [data.fmt(f, h.loc["H1", f]) for f in feats],
                                    "MW 20–38": [data.fmt(f, h.loc["H2", f]) for f in feats],
                                    "Change": [h.loc["H2", f] - h.loc["H1", f] for f in feats]})
                st.dataframe(tbl, hide_index=True, width="stretch", height=455,
                             column_config={"Change": st.column_config.NumberColumn(format="%+.2f")})

    with tabs[4]:
        sim = data.similar()
        sim = sim[sim.team == team].merge(df[["team", "cluster", "logo", "color"]], left_on="similar_team", right_on="team",
                                          suffixes=("", "_s"))
        ui.note("Closest attacking profiles across all three leagues, by distance on the 13 standardised features. "
                "Useful for scouting comparable systems or likely-compatible opponents.")
        st.write("")
        cols = st.columns(5, gap="small")
        for col, r in zip(cols, sim.itertuples()):
            col.markdown(f'''<div class="card vs-card"><img src="{r.logo}">
                <h4 style="font-size:0.95rem">{html.escape(r.similar_team)}</h4>
                <div class="note" style="margin-bottom:0.4rem">{data.LEAGUES[r.similar_league]}</div>
                <div style="font-size:1.6rem;font-weight:800;color:var(--text-strong)">{r.similarity:.0f}<span class="note"> / 100</span></div>
                <div style="margin-top:0.4rem">{ui.cluster_badge(r.cluster)}</div></div>''', unsafe_allow_html=True)
        st.write("")
        with ui.panel("Fingerprint overlay"):
            pick = st.selectbox("Compare with", sim.similar_team.tolist())
            other = df.set_index("team").loc[pick]
            st.plotly_chart(charts.radar([
                {"name": team, "values": [row[f"{f}_pct"] for f in data.FEATURES], "color": row.color},
                {"name": pick, "values": [other[f"{f}_pct"] for f in data.FEATURES], "color": "#111418", "fill": False}],
                height=420), width="stretch")

    with tabs[5]:
        season_by_season(team, row.color)
    with tabs[6]:
        legacy(team, row.color)
    ui.footer()


def legacy(team: str, color: str) -> None:
    info = data.club_info().set_index("team")
    if team in info.index:
        i = info.loc[team]
        facts = [f"Founded <b>{int(i.founded)}</b>" if pd.notna(i.founded) else "",
                 f"<b>{html.escape(i.stadium)}</b>" + (f" ({int(i.capacity):,} seats)" if pd.notna(i.capacity) else "")
                 if pd.notna(i.stadium) else "",
                 html.escape(i.city) if pd.notna(i.city) else "",
                 f"Nicknames: {html.escape(i.nicknames)}" if isinstance(i.nicknames, str) and i.nicknames else ""]
        ui.callout(" · ".join(f for f in facts if f))

    h = data.honours()
    h = h[h.team == team]
    counts = h.category.value_counts()
    european = sum(counts.get(c, 0) for c in ("European Cup", "UEFA Cup", "Cup Winners' Cup", "Conference League"))
    ui.kpis([("League titles", f"{counts.get('League title', 0)}", last_won(h, "League title"), data.TROPHY_COLORS["League title"]),
             ("Domestic cups", f"{counts.get('Domestic cup', 0)}", last_won(h, "Domestic cup"), data.TROPHY_COLORS["Domestic cup"]),
             ("European Cups", f"{counts.get('European Cup', 0)}", last_won(h, "European Cup"), data.TROPHY_COLORS["European Cup"]),
             ("Major European", f"{european}", "European Cup, UEFA Cup/Europa, Cup Winners', Conference",
              data.TROPHY_COLORS["UEFA Cup"]),
             ("Second-tier titles", f"{counts.get('Second-tier title', 0)}", last_won(h, "Second-tier title"),
              data.TROPHY_COLORS["Second-tier title"])])

    c1, c2 = st.columns([1.3, 1], gap="medium")
    with c1:
        with ui.panel("Trophies by decade", "Hover a bar for the seasons"):
            if len(h):
                st.plotly_chart(charts.trophies_by_decade(h), width="stretch", key=f"trophies-{team}")
            else:
                ui.note("No major trophies recorded.")
    with c2:
        with ui.panel("Trophy cabinet"):
            if len(h):
                cab = (h.groupby("category").agg(Won=("season", "size"), First=("season", "first"),
                                                 Latest=("season", "last")).reindex(data.TROPHY_COLORS).dropna()
                       .reset_index())
                cab.insert(0, "Trophy", cab.pop("category").map(data.TROPHY_LABELS))
                st.dataframe(cab, hide_index=True, width="stretch", column_config={
                    "Won": st.column_config.NumberColumn(format="%d")})
            else:
                ui.note("No major trophies recorded.")

    m = data.managers()
    m = m[m.team == team]
    rec = data.manager_records()
    rec = rec[rec.team == team]
    c1, c2 = st.columns([1, 1.3], gap="medium")
    with c1:
        with ui.panel("Managers", "Head coaches, most recent first"):
            cur = m[m.current]
            if len(cur):
                c = cur.iloc[0]
                ui.callout(f"<b>Current manager: {html.escape(c.manager)}</b>"
                           + (f" ({html.escape(c.nationality)})" if isinstance(c.nationality, str) and c.nationality else "")
                           + f" · in charge since {c.start:%d %b %Y} ({tenure(c.days)})")
            else:
                ui.callout("No current head coach is recorded (the post may be vacant or held by a caretaker).", warn=True)
            tbl = m.head(15)
            st.dataframe(pd.DataFrame({"Manager": tbl.manager, "Nationality": tbl.nationality.fillna(""),
                                       "From": tbl.start.dt.strftime("%b %Y"),
                                       "To": tbl.end.dt.strftime("%b %Y").fillna("present"),
                                       "Tenure": tbl.days.map(tenure)}),
                         hide_index=True, width="stretch", height=420)
    with c2:
        with ui.panel("Manager records in our data", "League matches from 2025/26 onwards · Attacking Index is the "
                      "within-league match z-score used across the app"):
            if len(rec):
                st.dataframe(pd.DataFrame({
                    "Manager": rec.manager, "Matches": rec.matches,
                    "W-D-L": [f"{w}-{d}-{l}" for w, d, l in zip(rec.wins, rec.draws, rec.losses)],
                    "Points / match": rec.ppg, "xG": rec.xg, "xG against": rec.xg_against,
                    "Possession": rec.possession / 100, "Attacking Index": rec.attacking_index}),
                    hide_index=True, width="stretch", column_config={
                        "Points / match": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=3),
                        "xG": st.column_config.NumberColumn(format="%.2f"),
                        "xG against": st.column_config.NumberColumn(format="%.2f"),
                        "Possession": st.column_config.NumberColumn(format="percent"),
                        "Attacking Index": st.column_config.NumberColumn(format="%+.2f")})
                if len(rec) > 1:
                    best = rec.loc[rec.attacking_index.idxmax()]
                    ui.note(f"Most attacking spell in our data: <b>{html.escape(best.manager)}</b> "
                            f"(Attacking Index {best.attacking_index:+.2f} over {best.matches} matches). "
                            "Short spells are noisy; compare managers with at least 10 matches.")
            else:
                ui.note("No manager could be matched to this club's matches.")

    ui.note(f"Honours and managers: Wikidata (CC0), retrieved {data.legacy_retrieved()}. Super cups are not shown "
            "because Wikidata lists too few of them. Hand corrections (revoked titles, missing finals and spells) are "
            "listed in data/reference; league titles, domestic cups and European trophies match published totals for "
            "all 95 checked club counts (reports/phaseD_legacy_check.md).")


def last_won(h: pd.DataFrame, category: str) -> str:
    won = h[h.category == category]
    return f"latest {won.season.iloc[-1]}" if len(won) else "none recorded"


def tenure(days: int) -> str:
    years, months = divmod(round(days / 30.44), 12)
    if years:
        return f"{years} yr {months} mo" if months else f"{years} yr"
    return f"{months} mo" if months else f"{days} days"


def season_by_season(team: str, color: str) -> None:
    hist = data.history()
    h = hist[hist.team == team].sort_values("season")
    if h.empty:
        ui.note("No multi-season history for this club yet.")
        return
    last, now = h.iloc[0], h.iloc[-1]
    if len(h) > 1:
        same = last.cluster == now.cluster
        ui.callout(f"<b>{data.season_label(now.season)} so far ({int(now.played)} matches):</b> "
                   f"{ui.cluster_badge(now.cluster)} "
                   + ("the same attacking style as last season." if same else
                      f"a change from last season's {ui.cluster_badge(last.cluster)}.")
                   + " Both seasons are assigned with the 2025/26 model (same scaling, components and style centres), "
                     "so they are directly comparable.", warn=not same)
    c1, c2 = st.columns([1, 1.1], gap="medium")
    with c1:
        with ui.panel("Style by season", "Each square is a season; the number is the league position "
                      "(current position for a season in progress)"):
            st.plotly_chart(charts.style_timeline(h), width="stretch", config={"displayModeBar": False})
    with c2:
        with ui.panel("Last season vs this season", "Per-match averages"):
            rows = [("League position", "position", "%d"), ("Points per match", "points_per_match", "%.2f"),
                    ("xG", "xg", "%.2f"), ("Goals", "goals", "%.2f"), ("Shots", "shots", "%.1f"),
                    ("Possession %", "possession", "%.1f"), ("Long-ball share %", "long_ball_share", "%.1f"),
                    ("Deep completions", "deep_completions", "%.1f"), ("Box presence %", "box_shot_share", "%.1f")]
            cols = {data.season_label(s): [fmt % r[c] if pd.notna(r[c]) else "–" for _, c, fmt in rows]
                    for s, r in h.set_index("season").iterrows()}
            st.dataframe(pd.DataFrame({"Metric": [n for n, _, _ in rows], **cols}), hide_index=True, width="stretch")

    seasons = h.season.tolist()[::-1]
    pick = st.segmented_control("Week by week", seasons, default=seasons[0], format_func=data.season_label,
                                key="club_hist_season") or seasons[0]
    tm = data.history_matches(team)
    tm = tm[tm.season == pick]
    league = h.loc[h.season == pick, "league"].iloc[0]
    hist_all = data.history_league_season(league, pick)
    avg = hist_all.groupby("matchweek").points.mean().cumsum()
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        with ui.panel(f"Points race · {data.season_label(pick)}", "Cumulative points by matchweek against the league average"):
            st.plotly_chart(charts.points_race(tm, color, avg), width="stretch")
    with c2:
        with ui.panel(f"Attacking Index · {data.season_label(pick)}", "Match by match, bars coloured by result"):
            if tm.attacking_index.notna().any():
                st.plotly_chart(charts.timeline(tm.dropna(subset=["attacking_index"]), color), width="stretch",
                                key=f"hist-timeline-{pick}")
            else:
                ui.note("Possession data is missing for this season, so the Attacking Index is unavailable.")
