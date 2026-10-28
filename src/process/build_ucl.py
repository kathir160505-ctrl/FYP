"""Phase B: Champions League tables, and how our clubs play in Europe compared with their league.

Run from the project root after src.collect.ucl and src.process.build_history:  python -m src.process.build_ucl

Outputs (data/processed/ucl/):
- ucl_match.csv     one row per team per completed UCL match (all 36 clubs), with ESPN box stats
- ucl_season.csv    one row per club-season: record, stage reached, per-match style stats; for our clubs also
                    the same stats in their league season and the projected 2025/26-model style
- ucl_vs_league.csv our clubs only: per-match ESPN stats in the UCL vs the league, side by side (long format)

UCL stats come from ESPN only (no xG; Understat does not cover the competition). The league comparison uses the
ESPN figures in the league data too, so both sides come from the same source and definitions.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW, REF = ROOT / "data" / "raw" / "ucl", ROOT / "data" / "reference"
HIST, OUT = ROOT / "data" / "processed" / "history", ROOT / "data" / "processed" / "ucl"
STAGES = ["league-phase", "knockout-round-playoffs", "round-of-16", "quarterfinals", "semifinals", "final"]
STAGE_NAMES = {"league-phase": "League phase", "knockout-round-playoffs": "Knockout play-off",
               "round-of-16": "Round of 16", "quarterfinals": "Quarter-final", "semifinals": "Semi-final",
               "final": "Final", "winner": "Winner"}
# Per-match style stats shared by the UCL and the league data (ESPN definitions on both sides).
COMPARE = {"possession": "Possession %", "pass_accuracy": "Pass accuracy %", "passes_completed": "Passes completed",
           "long_ball_share": "Long-ball share %", "crosses": "Crosses", "shots": "Shots", "shots_on_target": "Shots on target",
           "goals": "Goals", "goals_against": "Goals against", "points_per_match": "Points per match"}


def canonical_names() -> dict[str, str]:
    ref = pd.concat([pd.read_csv(REF / "teams.csv"), pd.read_csv(REF / "teams_promoted_2627.csv")])
    return dict(zip(ref.espn, ref.team))


def team_rows(raw: pd.DataFrame, names: dict) -> pd.DataFrame:
    d = raw.copy()
    home = d.home_away == "home"
    d["team"] = d.espn_team.map(names).fillna(d.espn_team)
    d["ours"] = d.espn_team.isin(names)
    d["opponent_espn"] = np.where(home, d.espn_away, d.espn_home)
    d["opponent"] = d.opponent_espn.map(names).fillna(d.opponent_espn)
    d["is_home"] = home
    d["goals"] = np.where(home, d.home_score, d.away_score)
    d["goals_against"] = np.where(home, d.away_score, d.home_score)
    d["points"] = np.select([d.goals > d.goals_against, d.goals == d.goals_against], [3, 1], 0)
    d["result"] = d.points.map({3: "W", 1: "D", 0: "L"})
    # A drawn final is decided on penalties: ESPN's winner flag says who lifted the trophy.
    d["won_final"] = (d.stage == "final") & np.where(home, d.home_winner, d.away_winner).astype(bool)
    d["date"] = pd.to_datetime(d.date, utc=True).dt.tz_localize(None)
    return d


def per_match(g: pd.DataFrame) -> pd.Series:
    n = len(g)
    return pd.Series({
        "possession": g.possessionPct.mean(),
        "pass_accuracy": g.accuratePasses.sum() / g.totalPasses.sum() * 100,
        "passes_completed": g.accuratePasses.sum() / n,
        "long_ball_share": g.totalLongBalls.sum() / g.totalPasses.sum() * 100,
        "crosses": g.totalCrosses.sum() / n,
        "shots": g.totalShots.sum() / n,
        "shots_on_target": g.shotsOnTarget.sum() / n,
        "goals": g.goals.sum() / n,
        "goals_against": g.goals_against.sum() / n,
        "points_per_match": g.points.sum() / n})


def ucl_season(m: pd.DataFrame) -> pd.DataFrame:
    rec = m.groupby(["season", "team"]).agg(
        ours=("ours", "first"), logo=("logo", "first"), played=("event_id", "size"),
        wins=("result", lambda r: (r == "W").sum()), draws=("result", lambda r: (r == "D").sum()),
        losses=("result", lambda r: (r == "L").sum()), gf=("goals", "sum"), ga=("goals_against", "sum"),
        stage_idx=("stage", lambda s: max(STAGES.index(x) for x in s)), champion=("won_final", "any"))
    style = m.groupby(["season", "team"]).apply(per_match, include_groups=False)
    out = rec.join(style).reset_index()
    out["stage_reached"] = [("winner" if c else STAGES[i]) for i, c in zip(out.stage_idx, out.champion)]
    out["stage_name"] = out.stage_reached.map(STAGE_NAMES)
    # League-phase table position: points, then goal difference, then goals scored (UEFA's first tie-breakers).
    lp = m[m.stage == "league-phase"].groupby(["season", "team"]).agg(
        lp_pts=("points", "sum"), lp_gd=("goals", "sum"), lp_ga=("goals_against", "sum"), lp_gf=("goals", "sum"))
    lp["lp_gd"] -= lp.pop("lp_ga")
    lp = lp.sort_values(["season", "lp_pts", "lp_gd", "lp_gf"], ascending=[True, False, False, False])
    lp["league_phase_position"] = lp.groupby("season").cumcount() + 1
    out = out.merge(lp.reset_index(), on=["season", "team"], how="left")
    return out.drop(columns="stage_idx")


def league_espn(names: set) -> pd.DataFrame:
    """The same per-match ESPN stats for our UCL clubs' league seasons."""
    tm = pd.read_parquet(HIST / "team_match.parquet")
    tm = tm[tm.team.isin(names) & ~tm.espn_missing]
    tm = tm.rename(columns={"goals": "goals", "goals_against": "goals_against"})
    return tm.groupby(["season", "team"]).apply(per_match, include_groups=False).reset_index()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    names = canonical_names()
    raw = pd.concat([pd.read_csv(p).assign(season=int(p.parent.name)) for p in sorted(RAW.glob("*/ucl_stats.csv"))],
                    ignore_index=True)
    m = team_rows(raw, names)
    s = ucl_season(m)
    ours = s[s.ours]
    lg = league_espn(set(ours.team))
    ts = pd.read_csv(HIST / "team_season.csv")[["season", "team", "league", "cluster", "position"]]
    s = s.merge(ts, on=["season", "team"], how="left")
    long = (ours[["season", "team", *COMPARE]].melt(["season", "team"], var_name="stat", value_name="ucl")
            .merge(lg.melt(["season", "team"], var_name="stat", value_name="league"), on=["season", "team", "stat"]))
    long["label"] = long.stat.map(COMPARE)
    long["diff"] = long.ucl - long.league
    cols = ["season", "date", "stage", "event_id", "team", "ours", "opponent", "is_home", "goals", "goals_against",
            "points", "result", "won_final", "possessionPct", "accuratePasses", "totalPasses", "totalLongBalls",
            "totalCrosses", "totalShots", "shotsOnTarget", "wonCorners", "saves", "logo"]
    m[cols].sort_values(["season", "date", "team"]).to_csv(OUT / "ucl_match.csv", index=False, encoding="utf-8")
    s.to_csv(OUT / "ucl_season.csv", index=False, encoding="utf-8")
    long.to_csv(OUT / "ucl_vs_league.csv", index=False, encoding="utf-8")
    for season, g in s.groupby("season"):
        champ = g[g.champion].team.tolist()
        print(f"UCL {season}: {g.played.sum() // 2} matches, {len(g)} clubs ({int(g.ours.sum())} ours), "
              f"winner: {champ[0] if champ else 'in progress'}")


if __name__ == "__main__":
    main()
