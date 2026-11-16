"""ESPN fallback for Understat: estimates of Understat's match numbers from ESPN alone, used only for matches that
Understat has not published (for example while understat.com is down).

Train and validate (run from the project root after src.process.build_history):
    python -m src.model.espn_fallback

What each Understat number becomes:
- shots, on target, box shots, shot locations, minutes: read directly from ESPN's play-by-play (every shot carries
  its pitch position, scorer, team and outcome);
- xG: a logistic-regression shot model (distance, angle, header, assist type, situation) trained on 2025/26
  league shots with Understat's own totals as the scale; penalties 0.76;
- deep completions and PPDA: regressions on ESPN's team box stats, trained on 2025/26 team-matches;
- fast-attack shots: ESPN's "fast break" shots, scaled to Understat's "Fast" attack-speed total on 2025/26.

Everything is trained on 2025/26 and tested on the 2026/27 matches that Understat did publish, so the report states
how close the estimates are. Writes models/espn_fallback.joblib and reports/espn_fallback.md.
"""
import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression, PoissonRegressor
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
CACHES = [ROOT / "data" / "raw" / "espn" / "json", ROOT / "data" / "raw" / "live" / "espn"]
HIST = ROOT / "data" / "processed" / "history"
RAW_HIST = ROOT / "data" / "raw" / "history"
REF = ROOT / "data" / "reference"
MODEL = ROOT / "models" / "espn_fallback.joblib"
REPORT = ROOT / "reports" / "espn_fallback.md"
CODES = {"ENG": "eng.1", "ESP": "esp.1", "ITA": "ita.1"}
PENALTY_XG = 0.76
LENGTH, WIDTH, GOAL = 105.0, 68.0, 7.32
TRAIN_SEASON, TEST_SEASON = 2526, 2627

SHOT = re.compile(r"^(Goal!|Attempt (saved|missed|blocked)\.|Penalty (saved|missed)!)")
ZONES = [("very close range", "very_close"), ("six yard box", "six_yard"), ("centre of the box", "box_centre"),
         ("left side of the box", "box_side"), ("right side of the box", "box_side"),
         ("difficult angle and long range", "long_angle"), ("difficult angle", "angle"),
         ("more than 35 yards", "long_range"), ("long range", "long_range"), ("outside the box", "outside")]
BOX_STATS = ["possessionPct", "accuratePasses", "totalPasses", "totalCrosses", "accurateCrosses", "totalLongBalls",
             "accurateLongBalls", "wonCorners", "effectiveTackles", "interceptions"]
DEEP_FEATURES = ["possessionPct", "accuratePasses", "totalPasses", "totalCrosses", "accurateCrosses",
                 "totalLongBalls", "wonCorners", "shots", "box_shots", "xg", "opp_def_actions"]
PPDA_FEATURES = ["opp_accuratePasses", "opp_totalPasses", "def_actions", "possessionPct"]


# ---------------------------------------------------------------- parsing
def summary_path(code: str, event_id) -> Path | None:
    for cache in CACHES:
        p = cache / code / f"summary_{int(event_id)}.json"
        if p.exists():
            return p
    return None


def _minute(clock) -> float:
    txt = clock.get("displayValue", "") if isinstance(clock, dict) else str(clock or "")
    nums = [int(x) for x in re.findall(r"\d+", txt)]
    return float(sum(nums[:2])) if nums else np.nan


def parse_shots(summary: dict) -> pd.DataFrame:
    """Every shot in ESPN's commentary, in Understat's shape: team (ESPN name), player, minute, location_x/y on a 0-1
    pitch attacking towards x = 1, result, and the pre-shot features the xG model uses. Own goals are left out."""
    rows = []
    for c in summary.get("commentary", []):
        text = c.get("text", "")
        if not SHOT.match(text) or "Own Goal" in text:
            continue
        play, lower = c.get("play") or {}, text.lower()
        who = re.search(r"(?:Goal! [^.]*\. |Attempt \w+\. |Penalty \w+! )([^(]+) \(([^)]+)\)", text)
        body = re.search(r"\) (right footed shot|left footed shot|header|shot)", text)
        penalty = "converts the penalty" in lower or lower.startswith("penalty")
        x, y = play.get("fieldPositionX"), play.get("fieldPositionY")
        ok = x is not None and y is not None and 1 < float(x) <= 100
        situation = ("corner" if "following a corner" in lower else "set_piece" if "set piece" in lower
                     else "fast_break" if "fast break" in lower
                     else "free_kick" if "free kick" in lower and "direct" in lower else "open_play")
        assist = ("cross" if "cross" in lower and "assisted by" in lower else "through_ball" if "through ball" in lower
                  else "headed_pass" if "headed pass" in lower else "pass" if "assisted by" in lower else "none")
        goal = text.startswith("Goal!")
        rows.append({
            "team": (play.get("team") or {}).get("displayName") or (who.group(2).strip() if who else ""),
            "player": who.group(1).strip() if who else "", "minute": _minute(c.get("time")),
            "location_x": float(x) / 100 if ok else np.nan, "location_y": float(y) / 100 if ok else np.nan,
            "zone": next((z for k, z in ZONES if k in lower), "box_centre" if penalty else "unknown"),
            "body": {"right footed shot": "foot", "left footed shot": "foot", "header": "head"}.get(
                body.group(1), "other") if body else "other",
            "assist": assist, "situation": "penalty" if penalty else situation, "penalty": penalty, "goal": goal,
            "result": "Goal" if goal else "Saved Shot" if "saved" in lower[:20] else
                      "Blocked Shot" if "blocked" in lower[:20] else "Missed Shot"})
    return pd.DataFrame(rows)


def geometry(shots: pd.DataFrame) -> pd.DataFrame:
    """Distance to goal (m) and the angle the goal mouth subtends (radians). Shots without a position fall back to a
    typical location for their zone."""
    typical = {"very_close": (0.97, 0.5), "six_yard": (0.95, 0.5), "box_centre": (0.89, 0.5), "box_side": (0.89, 0.3),
               "angle": (0.93, 0.15), "long_angle": (0.8, 0.15), "outside": (0.79, 0.5), "long_range": (0.68, 0.5),
               "unknown": (0.89, 0.5)}
    x = shots.location_x.fillna(shots.zone.map(lambda z: typical[z][0]))
    y = shots.location_y.fillna(shots.zone.map(lambda z: typical[z][1]))
    dx, dy = (1 - x).clip(lower=0.002) * LENGTH, (y - 0.5) * WIDTH
    angle = np.arctan2(GOAL * dx, dx ** 2 + dy ** 2 - (GOAL / 2) ** 2)
    return shots.assign(distance=np.hypot(dx, dy), angle=np.where(angle < 0, angle + np.pi, angle))


def design(shots: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    g = geometry(shots)
    X = pd.concat([pd.DataFrame({"log_distance": np.log(g.distance), "angle": g.angle,
                                 "head_distance": np.log(g.distance) * (g.body == "head")}, index=g.index),
                   pd.get_dummies(g[["body", "assist", "situation"]].astype(str), dtype=float)], axis=1)
    return X.reindex(columns=columns, fill_value=0.0) if columns is not None else X


def shot_xg(model: dict, shots: pd.DataFrame) -> np.ndarray:
    if shots.empty:
        return np.array([])
    p = model["xg"].predict_proba(design(shots, model["xg_columns"]))[:, 1] * model["xg_scale"]
    return np.where(shots.penalty, PENALTY_XG, np.clip(p, 0.003, 0.97))


def box_stats(summary: dict) -> dict[str, dict]:
    out = {}
    for team in summary.get("boxscore", {}).get("teams", []):
        stats = {s["name"]: s.get("displayValue") for s in team.get("statistics", [])}
        out[team["team"]["displayName"]] = {k: pd.to_numeric(stats.get(k), errors="coerce") for k in BOX_STATS}
    return out


def team_rows(shots: pd.DataFrame, box: dict[str, dict]) -> pd.DataFrame:
    """One row per side: box stats, the opponent's, and shot totals from the play-by-play."""
    sides = list(box)
    rows = []
    for team in sides:
        opp = next((o for o in sides if o != team), None)
        s = shots[shots.team == team] if len(shots) else shots
        row = {"espn_team": team, **box[team], **{f"opp_{k}": v for k, v in (box.get(opp) or {}).items()},
               "shots": len(s), "shots_on_target": int(s.result.isin(["Goal", "Saved Shot"]).sum()) if len(s) else 0,
               "box_shots": int(_in_box(s).sum()) if len(s) else 0,
               "fast_shots": int((s.situation == "fast_break").sum()) if len(s) else 0,
               "xg": float(s.xg.sum()) if "xg" in s and len(s) else 0.0,
               "np_xg": float(s.loc[~s.penalty, "xg"].sum()) if "xg" in s and len(s) else 0.0}
        row["def_actions"] = (row.get("effectiveTackles") or 0) + (row.get("interceptions") or 0)
        row["opp_def_actions"] = (row.get("opp_effectiveTackles") or 0) + (row.get("opp_interceptions") or 0)
        rows.append(row)
    return pd.DataFrame(rows)


def _in_box(s: pd.DataFrame) -> pd.Series:
    from src.process.features import in_box
    pos = in_box(s.location_x, s.location_y)
    text = s.zone.isin(["very_close", "six_yard", "box_centre", "box_side"]) | s.penalty
    return pos.where(s.location_x.notna(), text)


# ---------------------------------------------------------------- applying the model to one league-season
def estimate_season(code: str, events: pd.DataFrame, model: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Understat-shaped tables for ESPN `events` (columns event_id, date, espn_home, espn_away, home_score,
    away_score; ESPN team names) whose summaries are cached: matches (one row per match), shots, and per-team
    fast-attack shot estimates."""
    matches, shots_out, fast = [], [], []
    for ev in events.drop_duplicates("event_id").itertuples():
        path = summary_path(code, ev.event_id)
        if path is None:
            continue
        summary = json.loads(path.read_text(encoding="utf-8"))
        shots = parse_shots(summary)
        if len(shots):
            shots["xg"] = shot_xg(model, shots)
        tr = team_rows(shots, box_stats(summary)).set_index("espn_team")
        if not {ev.espn_home, ev.espn_away} <= set(tr.index):
            continue
        tr["deep_completions"] = np.round(model["deep"].predict(tr[DEEP_FEATURES].fillna(0)))
        tr["ppda"] = np.exp(model["ppda"].predict(np.log1p(tr[PPDA_FEATURES].fillna(0))))
        h, a = tr.loc[ev.espn_home], tr.loc[ev.espn_away]
        hs, as_ = int(ev.home_score), int(ev.away_score)
        pts = (3, 0) if hs > as_ else (0, 3) if hs < as_ else (1, 1)
        game_id = int(ev.event_id)
        matches.append({"game_id": game_id, "event_id": game_id, "date": ev.date, "home_espn": ev.espn_home,
                        "away_espn": ev.espn_away, "home_goals": hs, "away_goals": as_,
                        "home_points": pts[0], "away_points": pts[1],
                        **{f"{side}_{k}": r[k] for side, r in (("home", h), ("away", a))
                           for k in ("xg", "np_xg", "deep_completions", "ppda")}})
        if len(shots):
            shots_out.append(shots.assign(game_id=game_id, event_id=game_id, date=ev.date))
        fast += [{"espn_team": t, "fast_shots": r.fast_shots, "game_id": game_id} for t, r in tr.iterrows()]
    cols = ["team", "player", "minute", "location_x", "location_y", "result", "situation", "body", "xg", "game_id"]
    return (pd.DataFrame(matches), pd.concat(shots_out, ignore_index=True) if shots_out else pd.DataFrame(columns=cols),
            pd.DataFrame(fast))


# ---------------------------------------------------------------- training and validation
def espn_names() -> dict[str, str]:
    ref = pd.concat([pd.read_csv(REF / "teams.csv"), pd.read_csv(REF / "teams_promoted_2627.csv")])
    return dict(zip(ref.espn, ref.team))


def load_league(seasons: tuple[int, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parsed ESPN shots and per-side ESPN rows for every league match in team_match (Understat-sourced only)."""
    tm = pd.read_parquet(HIST / "team_match.parquet")
    if "source" in tm:
        tm = tm[tm.source == "understat"]
    tm = tm[tm.season.isin(seasons) & tm.event_id.notna()]
    names = espn_names()
    shots, sides = [], []
    for (season, league, event_id), _ in tm.groupby(["season", "league", "event_id"]):
        path = summary_path(CODES[league[:3]], event_id)
        if path is None:
            continue
        summary = json.loads(path.read_text(encoding="utf-8"))
        s = parse_shots(summary)
        s = s.assign(event_id=int(event_id), season=season, team=s.team.map(names).fillna(s.team)) if len(s) else s
        shots.append(s)
        box = {names.get(k, k): v for k, v in box_stats(summary).items()}
        sides.append(team_rows(s, box).rename(columns={"espn_team": "team"}).assign(event_id=int(event_id),
                                                                                   season=season, league=league))
    shots = pd.concat([s for s in shots if len(s)], ignore_index=True)
    sides = pd.concat(sides, ignore_index=True)
    truth = tm.assign(event_id=tm.event_id.astype(int))[["event_id", "team", "xg", "np_xg", "deep_completions", "ppda",
                                                         "shots", "box_shots", "game_id"]]
    truth = truth.rename(columns=lambda c: c if c in ("event_id", "team") else c + "_us")
    sides = sides.merge(truth, on=["event_id", "team"], how="inner")
    return shots, sides


def understat_fast(season: int) -> pd.DataFrame:
    """Understat 'Fast' attack-speed shots per club-season (canonical names)."""
    br = pd.read_csv(HIST / "breakdowns.csv")
    br = br[(br.season == season) & (br.block == "attackSpeed") & (br.category == "Fast")]
    return br.groupby("team").shots.sum().rename("fast_us").reset_index()


def main() -> None:
    shots, sides = load_league((TRAIN_SEASON, TEST_SEASON))
    train_s, test_s = shots[shots.season == TRAIN_SEASON], shots[shots.season == TEST_SEASON]
    open_train = train_s[~train_s.penalty]
    xg = LogisticRegression(max_iter=3000, C=1.0).fit(design(open_train), open_train.goal)
    model = {"xg": xg, "xg_columns": list(design(open_train).columns), "xg_scale": 1.0, "penalty_xg": PENALTY_XG}
    # Put team totals on Understat's scale, fitted on 2025/26 only.
    tr_sides = sides[sides.season == TRAIN_SEASON]
    raw = train_s.assign(xg=shot_xg(model, train_s)).groupby(["event_id", "team"]).xg.sum()
    model["xg_scale"] = float(tr_sides.set_index(["event_id", "team"]).xg_us.sum() / raw.sum())

    shots["xg"] = shot_xg(model, shots)
    est = shots.groupby(["event_id", "team"]).agg(xg_est=("xg", "sum")).reset_index()
    sides = sides.merge(est, on=["event_id", "team"], how="left").fillna({"xg_est": 0.0})
    sides["xg"] = sides.xg_est  # the regressions see estimated xG, as they will when Understat is missing

    tr, te = sides[sides.season == TRAIN_SEASON], sides[sides.season == TEST_SEASON]
    model["deep"] = make_pipeline(StandardScaler(), PoissonRegressor(alpha=1e-3, max_iter=1000)).fit(
        tr[DEEP_FEATURES].fillna(0), tr.deep_completions_us)
    ok = tr.ppda_us.between(1, 60)
    model["ppda"] = make_pipeline(StandardScaler(), LinearRegression()).fit(
        np.log1p(tr.loc[ok, PPDA_FEATURES].fillna(0)), np.log(tr.loc[ok, "ppda_us"]))

    # Fast attacks: ESPN fast-break shots scaled to Understat's Fast total, per club-season on 2025/26.
    fast = sides.groupby(["season", "team"]).fast_shots.sum().reset_index()
    f_tr = fast[fast.season == TRAIN_SEASON].merge(understat_fast(TRAIN_SEASON), on="team")
    model["fast_scale"] = float(f_tr.fast_us.sum() / max(f_tr.fast_shots.sum(), 1))
    MODEL.parent.mkdir(exist_ok=True)
    joblib.dump(model, MODEL)

    # ---- validation on 2026/27 (matches Understat did publish before the outage)
    te = te.assign(deep_est=model["deep"].predict(te[DEEP_FEATURES].fillna(0)),
                   ppda_est=np.exp(model["ppda"].predict(np.log1p(te[PPDA_FEATURES].fillna(0)))))
    f_te = fast[fast.season == TEST_SEASON].merge(understat_fast(TEST_SEASON), on="team")
    test_s = shots[shots.season == TEST_SEASON]
    t_open = test_s[~test_s.penalty]
    corr = lambda a, b: float(np.corrcoef(a, b)[0, 1])  # noqa: E731
    rows = [
        ("Shot-level ROC AUC (open play)", f"{roc_auc_score(t_open.goal, t_open.xg):.3f}"),
        ("Shot-level Brier score", f"{brier_score_loss(t_open.goal, t_open.xg):.4f}"),
        ("xG per team-match: correlation with Understat", f"r = {corr(te.xg_est, te.xg_us):.3f}"),
        ("xG per team-match: mean absolute difference", f"{(te.xg_est - te.xg_us).abs().mean():.2f}"),
        ("Shots per team-match: correlation with Understat", f"r = {corr(te.shots, te.shots_us):.3f}"),
        ("Box shots per team-match: correlation with Understat", f"r = {corr(te.box_shots, te.box_shots_us):.3f}"),
        ("Deep completions per team-match: correlation", f"r = {corr(te.deep_est, te.deep_completions_us):.3f}"),
        ("Deep completions per team-match: mean absolute difference",
         f"{(te.deep_est - te.deep_completions_us).abs().mean():.2f}"),
        ("PPDA per team-match: correlation", f"r = {corr(te.ppda_est, te.ppda_us):.3f}"),
        ("Fast-attack shots per club-season: correlation", f"r = {corr(f_te.fast_shots, f_te.fast_us):.3f}"),
    ]
    season_check = club_season_check(model)
    REPORT.write_text("\n".join([
        "# ESPN fallback for Understat", "",
        "Used only for league matches Understat has not published (understat.com has been down since about "
        "3 Nov 2026). Every estimate is trained on 2025/26 and tested on the 2026/27 matches Understat did publish "
        f"({te.event_id.nunique()} matches, {len(te)} team-matches, {len(test_s):,} shots).", "",
        "| Test (2026/27 league matches) | Value |", "|---|---|", *[f"| {k} | {v} |" for k, v in rows], "",
        f"xG scale factor {model['xg_scale']:.3f}; fast-break scale factor {model['fast_scale']:.2f} "
        "(Understat counts more attacks as 'Fast' than ESPN's commentary calls fast breaks).", "",
        "## Club-season level: the 13 clustering features and the style", "",
        "Each 2026/27 club is described twice, once with Understat's numbers and once with every match estimated from "
        "ESPN, then both are classified with the unchanged 2025/26 model.", "",
        season_check, ""]), encoding="utf-8")
    print("\n".join(f"{k}: {v}" for k, v in rows))
    print(season_check)


def club_season_check(model: dict) -> str:
    """Re-describe every 2026/27 club with all matches estimated from ESPN, and compare with the Understat version."""
    from src.process.build_history import project_styles
    from src.process.features import CLUSTER_FEATURES, aggregate

    tm = pd.read_parquet(HIST / "team_match.parquet")
    tm = tm[(tm.season == TEST_SEASON) & (tm.get("source", "understat") == "understat")]
    names = espn_names()
    est = []
    for league, g in tm.groupby("league"):
        code = CODES[league[:3]]
        inv = {v: k for k, v in names.items()}
        ev = g[g.is_home].assign(event_id=g.event_id.astype(int), espn_home=g.team.map(inv),
                                 espn_away=g.opponent.map(inv), home_score=g.goals, away_score=g.goals_against)
        m, _, fast = estimate_season(code, ev, model)
        est.append((league, m, fast))
    rows = []
    for league, m, fast in est:
        for side, other in (("home", "away"), ("away", "home")):
            rows.append(pd.DataFrame({"event_id": m.event_id, "team": m[f"{side}_espn"].map(names),
                                      "xg_e": m[f"{side}_xg"], "np_xg_e": m[f"{side}_np_xg"],
                                      "deep_e": m[f"{side}_deep_completions"], "ppda_e": m[f"{side}_ppda"]}))
    e = pd.concat(rows)
    shots, sides = load_league((TEST_SEASON,))
    sides = sides[["event_id", "team", "shots", "shots_on_target", "box_shots", "fast_shots"]].rename(
        columns=lambda c: c + "_e" if c not in ("event_id", "team") else c)
    alt = tm.assign(event_id=tm.event_id.astype(int)).merge(e, on=["event_id", "team"]).merge(sides, on=["event_id", "team"])
    for c in ("xg", "np_xg", "ppda", "shots", "shots_on_target", "box_shots"):
        alt[c] = alt[f"{c}_e"]
    alt["deep_completions"] = alt.deep_e
    real = aggregate(tm, ["league", "team"])
    fake = aggregate(alt, ["league", "team"])
    br = pd.read_csv(HIST / "breakdowns.csv")
    fast_us = br[(br.season == TEST_SEASON) & (br.block == "attackSpeed") & (br.category == "Fast")].groupby("team").shots.sum()
    real["fast_attack_shots"] = real.team.map(fast_us) / real.matches
    fake["fast_attack_shots"] = fake.team.map(alt.groupby("team").fast_shots_e.sum() * model["fast_scale"]) / fake.matches
    feats = list(CLUSTER_FEATURES)
    real, fake = project_styles(real.copy()), project_styles(fake.copy())
    lines = ["| Feature | r (Understat vs ESPN estimate) |", "|---|---|"]
    for f in feats:
        lines.append(f"| {f} | {np.corrcoef(real[f], fake.set_index('team').loc[real.team, f])[0, 1]:.3f} |")
    same = (real.set_index("team").cluster == fake.set_index("team").cluster).mean()
    lines += ["", f"**Same style for {same:.0%} of the {len(real)} clubs** "
              f"({int(round(same * len(real)))} of {len(real)}), using the estimates for every match. In the app only "
              "matches after Understat's last update are estimated, so the share of estimated data is smaller."]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
