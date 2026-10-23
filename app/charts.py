"""Plotly figures for the dashboard, sharing one dark theme."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from data import CLUSTER_COLORS, CLUSTER_ORDER, FEATURES, LEAGUE_SYMBOLS, SHORT_LABELS, fmt

BG = "rgba(0,0,0,0)"
GRID = "rgba(148,163,184,0.15)"
TEXT = "#cbd5e1"
MUTED = "#64748b"
PITCH_LINE = "rgba(226,232,240,0.55)"


def _layout(fig: go.Figure, height: int = 420, **kw) -> go.Figure:
    layout = dict(
        height=height, paper_bgcolor=BG, plot_bgcolor=BG, font=dict(color=TEXT, family="Inter, sans-serif", size=12),
        margin=dict(l=10, r=10, t=40, b=10), hoverlabel=dict(bgcolor="#0f172a", bordercolor="#334155",
                                                             font=dict(color="#e2e8f0")),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.12))
    fig.update_layout(**{**layout, **kw})
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def style_map(df: pd.DataFrame, highlight: list[str] | None = None, explained: tuple[float, float] = (0.58, 0.12)) -> go.Figure:
    fig = go.Figure()
    highlight = highlight or []
    for cluster in CLUSTER_ORDER:
        for league, symbol in LEAGUE_SYMBOLS.items():
            d = df[(df.cluster == cluster) & (df.league_name == league)]
            if d.empty:
                continue
            fig.add_trace(go.Scatter(
                x=d.PC1, y=d.PC2, mode="markers+text", text=d.abbr, textposition="top center",
                textfont=dict(size=9, color="#94a3b8"), name=cluster, legendgroup=cluster,
                showlegend=league == "Premier League",
                marker=dict(size=13, symbol=symbol, color=CLUSTER_COLORS[cluster],
                            line=dict(width=[3 if t in highlight else 0.5 for t in d.team],
                                      color=["#ffffff" if t in highlight else "#0b1020" for t in d.team]),
                            opacity=[1.0 if (not highlight or t in highlight) else 0.35 for t in d.team]),
                customdata=np.stack([d.team, d.league_name, d.cluster, d.possession, d.xg, d.shots, d.long_ball_share], axis=1),
                hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>%{customdata[2]}<br>"
                              "Possession %{customdata[3]:.1f}% · xG %{customdata[4]:.2f} · Shots %{customdata[5]:.1f}"
                              "<br>Long-ball share %{customdata[6]:.1f}%<extra></extra>"))
    fig.update_xaxes(title=f"← reactive · Attacking dominance (PC1, {explained[0]:.0%}) · dominant →")
    fig.update_yaxes(title=f"← efficient finishing · PC2 ({explained[1]:.0%}) · crossing volume →")
    return _layout(fig, height=560)


def radar(series: list[dict], height: int = 430) -> go.Figure:
    """series: [{"name", "values" (0-100 by FEATURES), "color", "fill"}]"""
    theta = [SHORT_LABELS[f] for f in FEATURES] + [SHORT_LABELS[FEATURES[0]]]
    fig = go.Figure()
    for s in series:
        r = list(s["values"]) + [s["values"][0]]
        fig.add_trace(go.Scatterpolar(
            r=r, theta=theta, name=s["name"], line=dict(color=s["color"], width=2.5, dash=s.get("dash", "solid")),
            fill="toself" if s.get("fill", True) else "none", fillcolor=_rgba(s["color"], 0.18),
            hovertemplate="%{theta}: %{r:.0f}th percentile<extra>" + s["name"] + "</extra>"))
    fig.update_layout(polar=dict(bgcolor=BG, radialaxis=dict(range=[0, 100], tickvals=[25, 50, 75], gridcolor=GRID,
                                                             tickfont=dict(size=9, color=MUTED), showline=False),
                                 angularaxis=dict(gridcolor=GRID, tickfont=dict(size=11, color=TEXT))))
    return _layout(fig, height=height, showlegend=len(series) > 1)


def _rgba(hex_color: str, alpha: float) -> str:
    c = hex_color.lstrip("#")
    return f"rgba({int(c[0:2], 16)},{int(c[2:4], 16)},{int(c[4:6], 16)},{alpha})"


def timeline(tm: pd.DataFrame, color: str) -> go.Figure:
    """Attacking Index per matchweek, bars coloured by result, with a 5-match rolling line."""
    tm = tm.sort_values("matchweek")
    res_color = {"W": "#22c55e", "D": "#94a3b8", "L": "#ef4444"}
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=tm.matchweek, y=tm.attacking_index, marker_color=[res_color[r] for r in tm.result], opacity=0.55,
        name="Match Attacking Index", customdata=np.stack([tm.opponent, tm.is_home.map({True: "H", False: "A"}),
                                                            tm.goals, tm.goals_against, tm.xg, tm.result], axis=1),
        hovertemplate="MW %{x} · %{customdata[1]} vs %{customdata[0]}<br>%{customdata[5]} %{customdata[2]}-%{customdata[3]}"
                      " · xG %{customdata[4]:.2f}<br>Attacking Index %{y:.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=tm.matchweek, y=tm.attacking_index.rolling(5, min_periods=1).mean(), mode="lines",
                             line=dict(color=color, width=3, shape="spline"), name="5-match rolling average"))
    fig.add_hline(y=0, line=dict(color=MUTED, dash="dot"), annotation_text="league average",
                  annotation_font_color=MUTED, annotation_position="bottom right")
    fig.add_vline(x=19.5, line=dict(color=GRID, dash="dash"))
    fig.update_xaxes(title="Matchweek", dtick=2)
    fig.update_yaxes(title="Attacking Index (z)")
    return _layout(fig, height=380, bargap=0.25)


def xg_flow(tm: pd.DataFrame, color: str) -> go.Figure:
    tm = tm.sort_values("matchweek")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tm.matchweek, y=tm.xg.rolling(5, min_periods=1).mean(), name="xG for (5-match avg)",
                             line=dict(color=color, width=3, shape="spline"), fill="tozeroy", fillcolor=_rgba(color, 0.12)))
    fig.add_trace(go.Scatter(x=tm.matchweek, y=tm.xg_against.rolling(5, min_periods=1).mean(),
                             name="xG against (5-match avg)", line=dict(color="#f87171", width=2, dash="dot", shape="spline")))
    fig.update_xaxes(title="Matchweek", dtick=2)
    fig.update_yaxes(title="xG per match")
    return _layout(fig, height=320)


def _half_pitch(fig: go.Figure) -> None:
    """Attacking half of a 105 x 68 m pitch, drawn vertically with the goal at the top.

    x = width (0-68 m), y = length (52.5-105 m).
    """
    line = dict(color=PITCH_LINE, width=1.5)
    shapes = [
        dict(type="rect", x0=0, y0=52.5, x1=68, y1=105, line=line),
        dict(type="rect", x0=34 - 20.16, y0=105 - 16.5, x1=34 + 20.16, y1=105, line=line),
        dict(type="rect", x0=34 - 9.16, y0=105 - 5.5, x1=34 + 9.16, y1=105, line=line),
        dict(type="rect", x0=34 - 3.66, y0=105, x1=34 + 3.66, y1=106.5, line=line),
        dict(type="circle", x0=34 - 9.15, y0=52.5 - 9.15, x1=34 + 9.15, y1=52.5 + 9.15, line=line),
    ]
    arc = np.linspace(-np.pi / 2 - 0.93, -np.pi / 2 + 0.93, 40)
    fig.add_trace(go.Scatter(x=34 + 9.15 * np.cos(arc), y=94 + 9.15 * np.sin(arc), mode="lines", line=line,
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=[34], y=[94], mode="markers", marker=dict(size=4, color=PITCH_LINE),
                             hoverinfo="skip", showlegend=False))
    fig.update_layout(shapes=shapes)
    fig.update_xaxes(range=[-1.5, 69.5], visible=False, constrain="domain")
    fig.update_yaxes(range=[51.5, 107.5], visible=False, scaleanchor="x", scaleratio=1, constrain="domain")


def shot_map(shots: pd.DataFrame, color: str) -> go.Figure:
    fig = go.Figure()
    _half_pitch(fig)
    for is_goal, name, c, sym in ((False, "No goal", _rgba(color, 0.35), "circle"), (True, "Goal", "#facc15", "star")):
        d = shots[(shots.result == "Goal") == is_goal]
        fig.add_trace(go.Scatter(
            x=d.location_y * 68, y=d.location_x * 105, mode="markers", name=name,
            marker=dict(size=5 + d.xg * 28, color=c, symbol=sym, line=dict(width=0.8, color="#0b1020")),
            customdata=np.stack([d.player, d.opponent, d.minute, d.xg, d.situation, d.result, d.matchweek], axis=1),
            hovertemplate="<b>%{customdata[0]}</b> vs %{customdata[1]} (MW %{customdata[6]}, %{customdata[2]}')<br>"
                          "%{customdata[5]} · xG %{customdata[3]:.2f} · %{customdata[4]}<extra></extra>"))
    return _layout(fig, height=470, plot_bgcolor="#0f3d2e", legend=dict(orientation="h", y=-0.04, x=0.5, xanchor="center"))


def stacked_share(df: pd.DataFrame, x: str, y: str, colors: dict, order: list, height: int = 300) -> go.Figure:
    fig = go.Figure()
    for cat in order:
        d = df[df[y] == cat]
        fig.add_trace(go.Bar(x=d[x], y=d["share"], name=cat, marker_color=colors.get(cat, "#64748b"),
                             text=[f"{v:.0f}%" if v >= 6 else "" for v in d["share"]], textposition="inside",
                             customdata=d["n"], hovertemplate="%{x}<br>" + cat + ": %{y:.1f}% (%{customdata})<extra></extra>"))
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title="share %", range=[0, 100])
    return _layout(fig, height=height)


def diverging_bars(a: pd.Series, b: pd.Series, name_a: str, name_b: str, color_a: str, color_b: str,
                   raw_a: pd.Series, raw_b: pd.Series) -> go.Figure:
    """Percentile comparison per feature: A to the left, B to the right."""
    labels = [SHORT_LABELS[f] for f in FEATURES][::-1]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=labels, x=-a[FEATURES][::-1], orientation="h", name=name_a, marker_color=color_a,
                         customdata=[fmt(f, raw_a[f]) for f in FEATURES][::-1],
                         hovertemplate="%{y}: %{customdata} (%{x:.0f})<extra>" + name_a + "</extra>"))
    fig.add_trace(go.Bar(y=labels, x=b[FEATURES][::-1], orientation="h", name=name_b, marker_color=color_b,
                         customdata=[fmt(f, raw_b[f]) for f in FEATURES][::-1],
                         hovertemplate="%{y}: %{customdata} (%{x:.0f})<extra>" + name_b + "</extra>"))
    fig.update_layout(barmode="relative")
    fig.update_xaxes(range=[-100, 100], tickvals=[-100, -50, 0, 50, 100], ticktext=["100", "50", "0", "50", "100"],
                     title="percentile among all 60 clubs")
    return _layout(fig, height=480)


def gauge_bar(prob: float, name_a: str, name_b: str, color_a: str, color_b: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[prob * 100], y=[""], orientation="h", marker_color=color_a, name=name_a,
                         text=f"{name_a}  {prob:.0%}", textposition="inside", insidetextanchor="start",
                         hovertemplate=f"{name_a}: {prob:.1%}<extra></extra>"))
    fig.add_trace(go.Bar(x=[(1 - prob) * 100], y=[""], orientation="h", marker_color=color_b, name=name_b,
                         text=f"{1 - prob:.0%}  {name_b}", textposition="inside", insidetextanchor="end",
                         hovertemplate=f"{name_b}: {1 - prob:.1%}<extra></extra>"))
    fig.add_vline(x=50, line=dict(color="#e2e8f0", width=1, dash="dot"))
    fig.update_layout(barmode="stack", showlegend=False, uniformtext=dict(minsize=12, mode="show"))
    fig.update_xaxes(range=[0, 100], visible=False)
    fig.update_yaxes(visible=False)
    fig.update_traces(textfont=dict(size=15, color="#0b1020"))
    return _layout(fig, height=90, margin=dict(l=0, r=0, t=0, b=0))


def contributions(themes: dict, name_a: str, name_b: str, color_a: str, color_b: str) -> go.Figure:
    items = sorted(themes.items(), key=lambda kv: abs(kv[1]))
    fig = go.Figure(go.Bar(
        y=[k for k, _ in items], x=[v for _, v in items], orientation="h",
        marker_color=[color_a if v > 0 else color_b for _, v in items],
        hovertemplate="%{y}: %{x:+.2f} log-odds<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=MUTED))
    fig.update_xaxes(title=f"← favours {name_b} · favours {name_a} →", zeroline=False)
    return _layout(fig, height=260, showlegend=False)


def breakdown_bars(df: pd.DataFrame, category_order: list, color: str, value: str = "shots") -> go.Figure:
    d = df.set_index("category").reindex(category_order).reset_index()
    total = d[value].sum()
    fig = go.Figure(go.Bar(x=d["category"], y=d[value], marker_color=color,
                           text=[f"{v / total:.0%}" for v in d[value]], textposition="outside",
                           customdata=np.stack([d["goals"], d["xg"]], axis=1),
                           hovertemplate="%{x}: %{y} shots · %{customdata[0]} goals · xG %{customdata[1]:.1f}<extra></extra>"))
    fig.update_yaxes(title=value)
    return _layout(fig, height=300, showlegend=False)


def league_box(df: pd.DataFrame, feature: str) -> go.Figure:
    """Box per league, with clubs overlaid as jittered points coloured by attacking philosophy."""
    leagues = ["Premier League", "La Liga", "Serie A"]
    rng = np.random.default_rng(0)
    fig = go.Figure()
    for i, league in enumerate(leagues):
        d = df[df.league_name == league]
        fig.add_trace(go.Box(x=[i] * len(d), y=d[feature], boxpoints=False, width=0.55, showlegend=False,
                             line=dict(color="#94a3b8"), fillcolor="rgba(148,163,184,0.08)", hoverinfo="skip"))
    for cluster in CLUSTER_ORDER:
        d = df[df.cluster == cluster]
        x = d.league_name.map({lg: i for i, lg in enumerate(leagues)}) + rng.uniform(-0.18, 0.18, len(d))
        fig.add_trace(go.Scatter(x=x, y=d[feature], mode="markers", name=cluster,
                                 marker=dict(size=9, color=CLUSTER_COLORS[cluster], line=dict(width=0.6, color="#0b1020")),
                                 text=d.team, hovertemplate="%{text}: %{y:.2f}<extra>" + cluster + "</extra>"))
    fig.update_xaxes(tickvals=list(range(3)), ticktext=leagues, range=[-0.6, 2.6])
    return _layout(fig, height=400)


def model_selection_chart(sel: pd.DataFrame, final_k: int) -> go.Figure:
    fig = go.Figure()
    for alg, g in sel.groupby("algorithm"):
        fig.add_trace(go.Scatter(x=g.k, y=g.silhouette, mode="lines+markers", name=f"{alg} silhouette"))
    km = sel[sel.algorithm == "KMeans"]
    fig.add_trace(go.Scatter(x=km.k, y=km.bootstrap_ari, mode="lines+markers", name="KMeans bootstrap stability (ARI)",
                             line=dict(dash="dot")))
    fig.add_vline(x=final_k, line=dict(color="#e2e8f0", dash="dash"), annotation_text=f"chosen k = {final_k}")
    fig.update_xaxes(title="number of clusters k", dtick=1)
    return _layout(fig, height=340)
