import html

import streamlit as st

import charts
import data
import ui


def _crest_strip(members, limit: int = 8) -> str:
    imgs = "".join(f'<img src="{r.logo}" title="{html.escape(r.team)}" style="width:26px;height:26px;'
                   f'object-fit:contain;margin:0 4px 4px 0">' for r in members.head(limit).itertuples())
    more = f'<span class="note" style="vertical-align:top;line-height:26px">+{len(members) - limit}</span>' \
        if len(members) > limit else ""
    return imgs + more


def render() -> None:
    df = data.clubs()
    cm = data.cluster_model()
    ui.page_header("Overview", "How Europe's top three leagues attack",
                   "Unsupervised machine learning groups all 60 clubs by <b>how</b> they attack, using possession, "
                   "passing directness, chance creation, xG, counter-attacks and box presence, with no style labels "
                   "given in advance.",
                   meta="Season <b>2025/26</b><br>Premier League · La Liga · Serie A")
    ui.kpis([
        ("Clubs analysed", "60", "20 per league", "#38BDF8"),
        ("Matches", "1,140", "complete league season", "#6366F1"),
        ("Shots", f"{len(data.shots()):,}", "with location and xG", "#A78BFA"),
        ("Attacking styles", str(df.cluster.nunique()), "found by K-means clustering", "#F59E0B"),
        ("Variance captured", f"{cm['explained_variance'].sum():.0%}", f"by {cm['n_components']} principal components",
         "#22C55E"),
    ])

    c1, c2 = st.columns([3, 1], gap="medium")
    with c2:
        with ui.panel("Filters"):
            leagues = st.pills("Leagues", list(data.LEAGUE_FLAGS), selection_mode="multi",
                               default=list(data.LEAGUE_FLAGS)) or list(data.LEAGUE_FLAGS)
            highlight = st.multiselect("Highlight clubs", data.club_options(df), placeholder="Search clubs")
        with ui.panel("Reading the map"):
            ui.note("Each marker is a club; clubs close together attack in similar ways.<br><br>"
                    "<b>Horizontal:</b> attacking dominance (possession, xG, shots), the largest source of "
                    "difference.<br><b>Vertical:</b> crossing volume versus finishing efficiency.<br><br>"
                    "Markers: ● Premier League · ◆ La Liga · ■ Serie A")
    with c1:
        with ui.panel("Attacking style map", "All 60 clubs on the first two principal components, coloured by style"):
            st.plotly_chart(charts.style_map(df[df.league_name.isin(leagues)], highlight,
                                             tuple(cm["explained_variance"][:2])), width="stretch")

    st.markdown('<div class="panel-title" style="margin:0.6rem 0 0.6rem 0;font-size:1.1rem">The four attacking '
                'philosophies</div>', unsafe_allow_html=True)
    z = data.profiles()
    z = z[z.kind == "z"].set_index("cluster")
    cols = st.columns(4, gap="small")
    for col, cluster in zip(cols, data.CLUSTER_ORDER):
        members = df[df.cluster == cluster].sort_values("PC1", ascending=False)
        prof = z.loc[cluster, data.FEATURES].sort_values(ascending=False)
        chips = "".join(f'<span class="chip up">▲ {data.SHORT_LABELS[f]}</span>' for f in prof.index[:3] if prof[f] > 0.2)
        chips += "".join(f'<span class="chip down">▼ {data.SHORT_LABELS[f]}</span>' for f in prof.index[-2:] if prof[f] < -0.2)
        split = " · ".join(f"{(members.league_name == lg).sum()} {lg}" for lg in data.LEAGUE_FLAGS)
        col.markdown(
            f'''<div class="card style-card" style="--c:{data.CLUSTER_COLORS[cluster]}">
            <div class="count">{len(members)}<span>clubs</span></div>
            <h4 style="margin-top:0.55rem">{cluster}</h4>
            <div class="note" style="margin-bottom:0.55rem">{split}</div>
            <p>{cm["blurbs"][cluster]}</p><div style="margin-bottom:0.5rem">{chips}</div>
            <div>{_crest_strip(members)}</div></div>''',
            unsafe_allow_html=True)

    uniq = df[df.dbscan_outlier].sort_values("uniqueness", ascending=False)
    st.write("")
    with ui.panel("Statistically unique clubs",
                  "Flagged as density outliers by DBSCAN in most of 24 parameter settings: no close peers in any league"):
        cols = st.columns(len(uniq), gap="small")
        means, stds = df[data.FEATURES].mean(), df[data.FEATURES].std()
        for col, row in zip(cols, uniq.itertuples()):
            zr = (df.set_index("team").loc[row.team, data.FEATURES] - means) / stds
            extreme = zr.abs().sort_values(ascending=False).index[:2]
            chips = "".join(f'<span class="chip {"up" if zr[f] > 0 else "down"}">{data.SHORT_LABELS[f]} '
                            f'{zr[f]:+.1f} SD</span>' for f in extreme)
            col.markdown(f'''<div class="card" style="background:var(--surface-2)">
                <div class="mini-club"><img src="{row.logo}"><div><h4 style="margin:0">{html.escape(row.team)}</h4>
                <div class="note">{row.league_name}</div></div></div>
                <div style="margin:0.6rem 0 0.3rem 0">{ui.cluster_badge(row.cluster)}</div>
                <div>{chips}</div><div class="note">Outlier in {row.uniqueness:.0%} of settings</div></div>''',
                         unsafe_allow_html=True)
    ui.footer()
