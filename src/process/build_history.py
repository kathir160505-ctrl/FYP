"""Phase A: build multi-season tables (2014/15 â†’ current) and project every club-season onto the
2025/26 attacking-style model.

Run from the project root after src.collect.history:  python -m src.process.build_history

Outputs (data/processed/history/):
- team_match.parquet   one row per club per match, every season (matchweek, half, attacking index)
- team_season.csv      one row per club-season: the 13 attacking features, context stats, projected style
- shots.parquet        every shot, every season (shot maps)
- breakdowns.csv       Understat attack-speed / shot-zone / situation splits per club-season
- clubs.csv            every club seen, with canonical name, ESPN name and the seasons/leagues it played
- name_map.csv         Understat â†” ESPN club-name matches per league-season, with match counts (audit)
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.predict.model import add_attacking_index
from src.process.features import aggregate, in_box, shot_summary, understat_long

ROOT = Path(__file__).resolve().parents[2]
RAW, REF = ROOT / "data" / "raw" / "history", ROOT / "data" / "reference"
OUT = ROOT / "data" / "processed" / "history"
LEAGUES = {"ENG": "ENG-Premier League", "ESP": "ESP-La Liga", "ITA": "ITA-Serie A"}
ESPN_STATS = ["possessionPct", "accuratePasses", "totalPasses", "totalCrosses", "accurateCrosses", "totalLongBalls",
              "accurateLongBalls", "totalShots", "shotsOnTarget", "wonCorners", "effectiveTackles", "interceptions"]
FIRST_SEASON = "2526"  # the thesis season; older seasons are out of scope
MIN_VOTES = 0.8  # a club's ESPN name must agree on at least 80% of its matched games


def season_label(season: str) -> str:
    return f"20{season[:2]}/{season[2:]}"


def canonical_names() -> dict[str, str]:
    ref = pd.concat([pd.read_csv(REF / "teams.csv"), pd.read_csv(REF / "teams_promoted_2627.csv")])
    return dict(zip(ref.espn, ref.team))


def match_names(us: pd.DataFrame, espn: pd.DataFrame) -> pd.DataFrame:
    """Map Understat club names to ESPN names by aligning matches on date (Â±1 day) and score."""
    ev = espn.drop_duplicates("event_id")[["date", "espn_home", "espn_away", "home_score", "away_score"]].copy()
    ev["day"] = pd.to_datetime(ev["date"], utc=True).dt.tz_localize(None).dt.normalize()
    m = us[["date", "home_team", "away_team", "home_goals", "away_goals"]].copy()
    m["day"] = pd.to_datetime(m["date"]).dt.normalize()
    cands = []
    for shift in (-1, 0, 1):
        j = m.assign(day=m["day"] + pd.Timedelta(days=shift)).merge(
            ev, left_on=["day", "home_goals", "away_goals"], right_on=["day", "home_score", "away_score"])
        cands.append(j)
    j = pd.concat(cands)
    votes = pd.concat([j[["home_team", "espn_home"]].set_axis(["understat", "espn"], axis=1),
                       j[["away_team", "espn_away"]].set_axis(["understat", "espn"], axis=1)])
    counts = votes.value_counts().rename("votes").reset_index()
    best = counts.sort_values("votes", ascending=False).drop_duplicates("understat")
    games = pd.concat([us.home_team, us.away_team]).value_counts()
    # Other games on the same day with the same score add noise votes, so measure against the club's own games.
    best["share"] = best["votes"] / best["understat"].map(games)
    return best


def build_league_season(key: str, season: str, names: dict) -> dict[str, pd.DataFrame] | None:
    d = RAW / season / key
    if not (d / "espn_stats.csv").exists():
        return None
    league = LEAGUES[key]
    us = pd.read_csv(d / "us_matches.csv")
    shots = pd.read_csv(d / "us_shots.csv")
    br = pd.read_csv(d / "us_breakdowns.csv")
    espn = pd.read_csv(d / "espn_stats.csv")

    nm = match_names(us, espn)
    clubs_us = set(us.home_team) | set(us.away_team)
    weak = nm[nm.share < MIN_VOTES]
    if set(nm.understat) != clubs_us or nm.espn.duplicated().any() or len(weak):
        raise SystemExit(f"{key} {season}: ambiguous club-name matching\n{nm.to_string()}")
    us_to_espn = dict(zip(nm.understat, nm.espn))
    to_team = {u: names.get(e, e) for u, e in us_to_espn.items()}
    espn_to_team = {e: names.get(e, e) for e in nm.espn}

    tm = understat_long(us).merge(shot_summary(shots), on=["game_id", "team"], how="left")
    tm[["shots", "shots_on_target", "box_shots"]] = tm[["shots", "shots_on_target", "box_shots"]].fillna(0)
    for col in ("team", "opponent", "home_team", "away_team"):
        tm[col] = tm[col].map(to_team)
    espn = espn.assign(home_team=espn.espn_home.map(espn_to_team), away_team=espn.espn_away.map(espn_to_team),
                       team=espn.espn_team.map(espn_to_team))
    tm = tm.merge(espn[["home_team", "away_team", "team", "event_id", *ESPN_STATS]],
                  on=["home_team", "away_team", "team"], how="left", validate="one_to_one")
    tm = tm.sort_values(["team", "date"]).reset_index(drop=True)
    tm["matchweek"] = tm.groupby("team").cumcount() + 1
    n_games = tm.groupby("team")["matchweek"].transform("max")
    tm["half"] = np.where(tm["matchweek"] > n_games / 2, "H2", "H1")
    tm["season"] = int(season)
    # "understat", or "espn_estimate" for matches Understat had not published (src/collect/history.py fallback).
    estimated = set(us.loc[us["source"] == "espn_estimate", "game_id"]) if "source" in us else set()
    tm["source"] = np.where(tm["game_id"].isin(estimated), "espn_estimate", "understat")
    tm["espn_missing"] = tm["event_id"].isna()
    # The attacking index needs ESPN possession; matches ESPN lacks keep NaN there.
    full = tm[~tm.espn_missing]
    idx = add_attacking_index(full)[["game_id", "team", "attacking_index", "index_conceded"]]
    tm = tm.merge(idx, on=["game_id", "team"], how="left")

    season_df = aggregate(tm[~tm.espn_missing], ["league", "team"])
    br = br.assign(team=br.team.map(to_team), league=league, season=int(season))
    speed = br[br.block == "attackSpeed"].pivot_table(index="team", columns="category", values="shots", aggfunc="sum")
    season_df["fast_attack_shots"] = season_df["team"].map(speed.get("Fast", pd.Series(dtype=float))) / season_df["matches"]
    season_df["season"] = int(season)
    est = tm[tm.source == "espn_estimate"].groupby("team").size()
    season_df["estimated_matches"] = season_df["team"].map(est).fillna(0).astype(int)
    shots = shots.assign(team=shots.team.map(to_team), season=int(season), league=league,
                         in_box=lambda s: in_box(s.location_x, s.location_y))
    return {"team_match": tm, "team_season": season_df, "shots": shots, "breakdowns": br,
            "name_map": nm.assign(league=league, season=int(season))}


def project_styles(ts: pd.DataFrame) -> pd.DataFrame:
    """Assign each club-season a style with the 2025/26 thesis model (same scaler, PCA and centroids)."""
    cm = joblib.load(ROOT / "models" / "cluster_model.joblib")
    pipe, feats, names = cm["pipeline"], cm["features"], cm["names"]
    ok = ts[feats].notna().all(axis=1)
    X = ts.loc[ok, feats]
    pcs = pipe[:-1].transform(X)
    dist = pipe[-1].transform(pcs)
    ts.loc[ok, "cluster"] = [names[int(c)] for c in dist.argmin(axis=1)]
    srt = np.sort(dist, axis=1)
    ts.loc[ok, "style_confidence"] = 1 - srt[:, 0] / srt[:, 1]  # 0 = between two styles, 1 = at a centroid
    for i in range(pcs.shape[1]):
        ts.loc[ok, f"PC{i + 1}"] = pcs[:, i]
    return ts


def add_standings(ts: pd.DataFrame, tm: pd.DataFrame) -> pd.DataFrame:
    """League table per league-season from all matches (points, then goal difference, then goals scored)."""
    t = tm.groupby(["league", "season", "team"]).agg(played=("game_id", "size"), pts=("points", "sum"),
                                                     gf=("goals", "sum"), ga=("goals_against", "sum")).reset_index()
    t["gd"] = t["gf"] - t["ga"]
    t = t.sort_values(["league", "season", "pts", "gd", "gf"], ascending=[True, True, False, False, False])
    t["position"] = t.groupby(["league", "season"]).cumcount() + 1
    return ts.merge(t, on=["league", "season", "team"], how="left")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    names = canonical_names()
    parts: dict[str, list] = {k: [] for k in ("team_match", "team_season", "shots", "breakdowns", "name_map")}
    for season_dir in sorted(p.name for p in RAW.iterdir() if p.is_dir() and p.name >= FIRST_SEASON):
        for key in LEAGUES:
            res = build_league_season(key, season_dir, names)
            if res is None:
                continue
            for k, v in res.items():
                parts[k].append(v)
            miss = int(res["team_match"]["espn_missing"].sum())
            print(f"{key} {season_label(season_dir)}: {res['team_match'].game_id.nunique()} matches, "
                  f"{len(res['team_season'])} clubs, {miss} team-rows without ESPN stats")
    tables = {k: pd.concat(v, ignore_index=True) for k, v in parts.items()}
    tables["team_season"] = add_standings(project_styles(tables["team_season"]), tables["team_match"])
    tables["team_season"]["season_label"] = tables["team_season"]["season"].map(lambda s: season_label(f"{s:04d}"))
    tm = tables["team_match"]
    clubs = (tm.groupby("team").agg(league=("league", "last"), first_season=("season", "min"),
                                    last_season=("season", "max"), seasons=("season", "nunique")).reset_index())
    tables["team_match"].to_parquet(OUT / "team_match.parquet", index=False)
    tables["shots"].to_parquet(OUT / "shots.parquet", index=False)
    tables["team_season"].to_csv(OUT / "team_season.csv", index=False)
    tables["breakdowns"].to_csv(OUT / "breakdowns.csv", index=False)
    tables["name_map"].to_csv(OUT / "name_map.csv", index=False)
    clubs.to_csv(OUT / "clubs.csv", index=False)
    print(f"Saved {len(tables['team_season'])} club-seasons, {len(clubs)} clubs, {len(tables['shots']):,} shots -> {OUT}")


if __name__ == "__main__":
    main()
