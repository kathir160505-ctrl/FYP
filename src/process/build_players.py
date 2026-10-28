"""Phase C: player profiles, match lineups and a probable XI per club.

Run from the project root after src.collect.players:  python -m src.process.build_players

Outputs (data/processed/players/):
- players.csv      one row per player, club and season: Understat attacking stats, FBref defensive and goalkeeper
                   stats, per-90 rates, percentiles among players of the same position group, nation, age,
                   ESPN id/shirt number and a Wikimedia Commons photo where one exists
- lineups.parquet  every player on every league and Champions League match sheet, with canonical club names
- probable_xi.csv  each club's most likely starting XI from its last five league starts (current season)
- match_report.csv how each source was matched (audit)

Players are matched within a club and season by normalised name; when the spelling differs between sources
(accents, nicknames, middle names) the closest name above a similarity threshold is used, and only if it is
unambiguous. Photos are matched to Wikidata by name and birth year.
"""
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW, REF = ROOT / "data" / "raw" / "players", ROOT / "data" / "reference"
OUT = ROOT / "data" / "processed" / "players"
MIN_SIMILARITY = 0.8
PERCENTILE_MINUTES = 0.3  # share of the club's league minutes a player needs to enter the percentile pool
GROUPS = {"GK": "Goalkeeper", "D": "Defender", "M": "Midfielder", "F": "Forward"}
COMPETITIONS = {"eng.1": "Premier League", "esp.1": "La Liga", "ita.1": "Serie A", "uefa.champions": "Champions League"}

# Per-90 stats and the position groups whose percentiles the app shows.
PER90 = ["goals", "np_xg", "assists", "xa", "shots", "key_passes", "xg_chain", "xg_buildup",
         "tackles_won", "interceptions", "crosses", "fouls", "saves"]
TOTALS = ["goals", "assists", "xg", "np_xg", "xa", "shots", "key_passes"]


# Letters that Unicode decomposition does not reduce to ASCII (they would otherwise be dropped).
FOLD = str.maketrans({"Ø": "O", "ø": "o", "Æ": "AE", "æ": "ae", "ß": "ss", "Ł": "L", "ł": "l", "Đ": "D", "đ": "d",
                      "ı": "i", "Þ": "Th", "þ": "th", "Œ": "OE", "œ": "oe"})


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name).translate(FOLD)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", s.replace("-", " ")).strip()


def similarity(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    ta, tb = set(a.split()), set(b.split())
    if ta <= tb or tb <= ta:  # "Vinicius Junior" vs "Vinicius Jose Paixao de Oliveira Junior"
        return 0.95
    return SequenceMatcher(None, a, b).ratio()


def match_within(left: pd.DataFrame, right: pd.DataFrame, keys: list[str], lname: str, rname: str) -> pd.Series:
    """For each row of `left`, the index of the matching `right` row (same keys), by name. NaN if none."""
    out = pd.Series(np.nan, index=left.index)
    rgroups = {k: g for k, g in right.groupby(keys)}
    for k, lg in left.groupby(keys):
        rg = rgroups.get(k)
        if rg is None:
            continue
        rnorm = rg[rname].map(norm)
        used = set()
        exact = {n: i for i, n in zip(rg.index, rnorm) if (rnorm == n).sum() == 1}
        pending = []
        for i, n in zip(lg.index, lg[lname].map(norm)):
            if n in exact and exact[n] not in used:
                out[i] = exact[n]
                used.add(exact[n])
            else:
                pending.append(i)
        for i in pending:
            scores = [(similarity(left.at[i, lname], rg.at[j, rname]), j) for j in rg.index if j not in used]
            scores.sort(reverse=True)
            if scores and scores[0][0] >= MIN_SIMILARITY and (len(scores) == 1 or scores[1][0] < scores[0][0]):
                out[i] = scores[0][1]
                used.add(scores[0][1])
    return out


def names(column: str) -> dict:
    ref = pd.concat([pd.read_csv(REF / "teams.csv"), pd.read_csv(REF / "teams_promoted_2627.csv")])
    return dict(zip(ref[column], ref.team))


def load(prefix: str) -> pd.DataFrame:
    frames = [pd.read_csv(p) for p in sorted(RAW.glob(f"{prefix}_*.csv"))]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def position_group(understat_pos: str, fbref_pos: str) -> str:
    """Understat lists positions like 'F M S' (most played first); FBref like 'DF,MF'."""
    us = str(understat_pos).split()
    if us and us[0] in GROUPS:
        return GROUPS[us[0]]
    fb = str(fbref_pos).split(",")[0]
    return {"GK": "Goalkeeper", "DF": "Defender", "MF": "Midfielder", "FW": "Forward"}.get(fb, "Midfielder")


def base_table() -> tuple[pd.DataFrame, dict]:
    us = load("understat")
    us["team"] = us.team.map(names("understat")).fillna(us.team)
    us["season"] = us.season.astype(int)
    us = us.rename(columns={"player": "name"})
    report = {"understat": len(us)}

    fb_std = load("fbref_standard")
    if len(fb_std):
        fb_std["team"] = fb_std.team.map(names("fbref")).fillna(fb_std.team)
        fb_std["season"] = fb_std.season.astype(int)
        fb = fb_std.rename(columns={"Playing Time_Min": "fb_minutes", "Playing Time_Starts": "fb_starts"})
        for table, cols in (("fbref_misc", {"Performance_TklW": "tackles_won", "Performance_Int": "interceptions",
                                            "Performance_Crs": "crosses", "Performance_Fls": "fouls",
                                            "Performance_Fld": "fouled"}),
                            ("fbref_keeper", {"Performance_Saves": "saves", "Performance_CS": "clean_sheets",
                                              "Performance_GA": "goals_conceded", "Performance_SoTA": "shots_faced"})):
            t = load(table)
            if len(t):
                t["team"] = t.team.map(names("fbref")).fillna(t.team)
                t["season"] = t.season.astype(int)
                t = t.rename(columns=cols)[["league", "season", "team", "player", *cols.values()]]
                fb = fb.merge(t.drop_duplicates(["league", "season", "team", "player"]),
                              on=["league", "season", "team", "player"], how="left")
        fb = fb.reset_index(drop=True)
        idx = match_within(us, fb, ["season", "team"], "name", "player")
        keep = ["nation", "pos", "born", "fb_minutes", "fb_starts", "tackles_won", "interceptions", "crosses",
                "fouls", "fouled", "saves", "clean_sheets", "goals_conceded", "shots_faced"]
        keep = [c for c in keep if c in fb.columns]
        joined = fb.loc[idx.dropna().astype(int), keep].set_axis(idx.dropna().index)
        us = us.join(joined)
        report["fbref_matched"] = int(idx.notna().sum())
    return us, report


def add_lineups(players: pd.DataFrame, report: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    lu = pd.read_csv(RAW / "lineups.csv", dtype={"athlete_id": str, "jersey": str, "formation_place": str})
    lu["team"] = lu.espn_team.map(names("espn")).fillna(lu.espn_team)
    lu["competition_name"] = lu.competition.map(COMPETITIONS)
    lu["date"] = pd.to_datetime(lu.date, utc=True).dt.tz_localize(None)
    opp = lu.groupby(["event_id", "home_away"]).team.first().unstack()
    lu["opponent"] = [opp.at[e, "away" if h == "home" else "home"] if e in opp.index else None
                      for e, h in zip(lu.event_id, lu.home_away)]
    league = lu[lu.competition != "uefa.champions"]
    apps = (league.groupby(["season", "team", "athlete_id"])
            .agg(espn_name=("player", "last"), jersey=("jersey", "last"), espn_position=("position", "last"),
                 starts=("starter", "sum"), apps=("event_id", "nunique")).reset_index())
    idx = match_within(players, apps, ["season", "team"], "name", "espn_name")
    m = apps.loc[idx.dropna().astype(int), ["athlete_id", "jersey", "espn_position", "starts"]].set_axis(idx.dropna().index)
    players = players.join(m)
    report["espn_matched"] = int(idx.notna().sum())
    # Link lineup rows back to the Understat player id where the club-season match succeeded.
    link = players.dropna(subset=["athlete_id"]).drop_duplicates(["athlete_id"])[["athlete_id", "player_id"]]
    lu = lu.merge(link, on="athlete_id", how="left")
    return players, lu


def add_photos(players: pd.DataFrame, report: dict) -> pd.DataFrame:
    wd = pd.read_csv(RAW / "wikidata_players.csv")
    clubs = pd.read_csv(REF / "clubs_wikidata.csv")
    wd["team"] = wd.club.map(dict(zip(clubs.wikidata, clubs.team)))
    wd["born_year"] = pd.to_datetime(wd.born, utc=True, errors="coerce").dt.year
    wd = (wd.sort_values("img").drop_duplicates(["team", "p"])
          .rename(columns={"pLabel": "wd_name", "p": "wikidata", "img": "photo"}).reset_index(drop=True))
    players["born_year"] = pd.to_numeric(players.get("born"), errors="coerce")
    # Same club and name; when FBref gives a birth year it must agree (namesakes are common).
    idx = match_within(players.assign(key=players.team), wd.assign(key=wd.team), ["key"], "name", "wd_name")
    ok = idx.dropna().astype(int)
    agree = (players.loc[ok.index, "born_year"].isna().to_numpy()
             | (players.loc[ok.index, "born_year"].to_numpy() == wd.loc[ok.to_numpy(), "born_year"].to_numpy()))
    ok = ok[agree]
    players = players.join(wd.loc[ok, ["wikidata", "photo"]].set_axis(ok.index))
    # Fallback: a footballer whose Wikidata label is exactly the player's name, with the same birth year
    # (or the only footballer of that name when the birth year is unknown).
    by_name = RAW / "wikidata_names.csv"
    if by_name.exists():
        bn = pd.read_csv(by_name)
        bn["born_year"] = pd.to_datetime(bn.born, utc=True, errors="coerce").dt.year
        bn = bn.sort_values("img").drop_duplicates("p")
        unique = bn.groupby("name").p.transform("size") == 1
        todo = players.wikidata.isna()
        for i in players.index[todo]:
            cand = bn[bn.name == players.at[i, "name"]]
            year = players.at[i, "born_year"]
            cand = cand[cand.born_year == year] if pd.notna(year) else cand[unique.loc[cand.index]]
            if len(cand) == 1:
                players.loc[i, ["wikidata", "photo"]] = [cand.p.iloc[0], cand.img.iloc[0]]
    # Commons "Special:FilePath" URLs redirect to the full file; ask for a 240px thumbnail instead.
    players["photo"] = players.photo.where(players.photo.isna(), players.photo.astype(str) + "?width=240")
    report["photos"] = int(players.photo.notna().sum())
    return players


def add_rates(p: pd.DataFrame) -> pd.DataFrame:
    p["group"] = [position_group(u, f) for u, f in zip(p.position, p.get("pos", pd.Series(index=p.index)))]
    nineties = p.minutes / 90
    for col in PER90:
        if col in p.columns:
            p[f"{col}_p90"] = np.where(nineties > 0, p[col] / nineties, np.nan)
    if {"saves", "shots_faced"} <= set(p.columns):
        p["save_pct"] = np.where(p.shots_faced > 0, p.saves / p.shots_faced * 100, np.nan)
    club_minutes = p.groupby(["season", "team"]).minutes.transform("max")
    p["in_pool"] = p.minutes >= PERCENTILE_MINUTES * club_minutes.clip(lower=1) * 1.0
    for col in [c for c in p.columns if c.endswith("_p90")] + (["save_pct"] if "save_pct" in p else []):
        pool = p[p.in_pool]
        pct = pool.groupby(["season", "group"])[col].rank(pct=True) * 100
        p.loc[pool.index, f"{col}_pct"] = pct
    return p


def probable_xi(lu: pd.DataFrame, last_n: int = 5) -> pd.DataFrame:
    """Most likely XI per club: the most-used recent formation, then the most frequent starter in each slot."""
    league = lu[(lu.competition != "uefa.champions") & lu.starter & (lu.season == lu.season.max())]
    rows = []
    for team, g in league.groupby("team"):
        recent_events = g.sort_values("date").event_id.unique()[-last_n:]
        r = g[g.event_id.isin(recent_events)]
        forms = r.drop_duplicates("event_id").sort_values("date").formation
        formation = forms.value_counts().index[0] if len(forms) else None
        # weight recent matches more: most recent = last_n, oldest = 1
        weight = {e: i + 1 for i, e in enumerate(recent_events)}
        r = r.assign(w=r.event_id.map(weight))
        taken = set()
        for place in sorted(r.formation_place.dropna().unique(), key=lambda x: int(x)):
            cands = (r[(r.formation_place == place) & (r.formation == formation)]
                     .groupby(["athlete_id", "player", "position_abbr", "position"]).w.sum()
                     .sort_values(ascending=False).reset_index())
            if cands.empty:
                cands = (r[r.formation_place == place].groupby(["athlete_id", "player", "position_abbr", "position"])
                         .w.sum().sort_values(ascending=False).reset_index())
            cands = cands[~cands.athlete_id.isin(taken)]
            if cands.empty:
                continue
            c = cands.iloc[0]
            taken.add(c.athlete_id)
            starts = int(r[(r.athlete_id == c.athlete_id)].event_id.nunique())
            rows.append({"team": team, "formation": formation, "formation_place": int(place),
                         "athlete_id": c.athlete_id, "player": c.player, "position_abbr": c.position_abbr,
                         "position": c.position, "recent_starts": starts, "of_matches": len(recent_events),
                         "last_match": r.date.max()})
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p, report = base_table()
    p, lu = add_lineups(p, report)
    p = add_photos(p, report)
    p = add_rates(p)
    p["age"] = np.where(p.born_year.notna(), 2000 + p.season // 100 - p.born_year, np.nan)
    p.to_csv(OUT / "players.csv", index=False, encoding="utf-8")
    lu.to_parquet(OUT / "lineups.parquet", index=False)
    xi = probable_xi(lu)
    xi.to_csv(OUT / "probable_xi.csv", index=False, encoding="utf-8")
    pd.Series(report).rename("rows").to_csv(OUT / "match_report.csv")
    n = report["understat"]
    print(f"Players: {n:,} player-club-seasons; FBref matched {report.get('fbref_matched', 0) / n:.0%}, "
          f"ESPN {report['espn_matched'] / n:.0%}, photos {report['photos'] / n:.0%}")
    print(f"Lineups: {lu.event_id.nunique():,} matches; probable XIs for {xi.team.nunique()} clubs")


if __name__ == "__main__":
    main()
