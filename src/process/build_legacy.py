"""Phase D: clean the Wikidata honours, managers and club facts, and add each manager's record from our
2025/26-2026/27 match data.

Run from the project root after src.collect.legacy:  python -m src.process.build_legacy

Outputs (data/processed/legacy/):
- honours.csv          one row per trophy won (club, category, competition, season), de-duplicated
- honours_summary.csv  trophy count per club and category, with the most recent win
- managers.csv         every head-coach spell from Wikidata, cleaned, with a 'current' flag
- manager_records.csv  record and attacking profile of each manager in our match data (2025/26 onwards)
- club_info.csv        founded, stadium, capacity, city, nicknames

Wikidata is community-maintained. Title-winning seasons and finals are recorded unevenly, so a season is
counted when either its season item or its final names the club as winner, and each trophy is counted
once per season. src.process.check_legacy compares the totals with published counts.
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW, REF = ROOT / "data" / "raw" / "legacy", ROOT / "data" / "reference"
OUT = ROOT / "data" / "processed" / "legacy"
HIST = ROOT / "data" / "processed" / "history"

# Wikidata competition item -> trophy category. Up to 1991/92 the First Division was the English top flight
# (and the English Football League item's champion was its winner); from 1992/93 it was the second tier.
# Super cups are left out: Wikidata records too few of them (e.g. 7 of Manchester United's 21 Community Shields).
CATEGORIES = {
    "League title": {"Q9448": "Premier League", "Q754839": "First Division", "Q213347": "First Division",
                     "Q324867": "La Liga", "Q15804": "Serie A"},
    "Domestic cup": {"Q11151": "FA Cup", "Q483794": "Copa del Rey", "Q169918": "Coppa Italia"},
    "League Cup": {"Q11152": "EFL Cup"},
    "European Cup": {"Q18756": "European Cup / Champions League"},
    "UEFA Cup": {"Q715496": "UEFA Cup", "Q18760": "Europa League"},
    "Cup Winners' Cup": {"Q40241": "Cup Winners' Cup"},
    "Conference League": {"Q59365764": "Conference League"},
    "UEFA Super Cup": {"Q484028": "UEFA Super Cup"},
    "World club title": {"Q223366": "FIFA Club World Cup", "Q182473": "Intercontinental Cup"},
    "Second-tier title": {"Q19510": "Championship", "Q35615": "Segunda División", "Q194052": "Serie B"},
}
COMP = {q: (cat, name) for cat, comps in CATEGORIES.items() for q, name in comps.items()}
CATEGORY_ORDER = list(CATEGORIES)
MAJOR = ["League title", "Domestic cup", "European Cup", "UEFA Cup", "Cup Winners' Cup", "Conference League"]
TOP_FLIGHT_UNTIL = 1992  # last season (end year) of the old First Division as top flight
OLD_FIRST_DIVISION, EFL = "Q754839", "Q213347"
SECOND_TIER_NAMES = r"Segunda|Serie B|Second Division"
# A season item ("1984–85 European Cup") or a dated final ("1985 European Cup Final"); never single matches.
EVENT = re.compile(r"^(\d{4})(?:[–-](\d{2,4}))?\s+[^\d\s–-]")
EVENT_YEAR = r"^\d{4}(?:[–-]\d{2,4})?\s+"
EXCLUDE = re.compile(r"women|femenin|femminil|youth|juvenil|primavera|reina|u-?\d\d|under-\d\d", re.I)
# Obvious vandalism or bad labels in Wikidata, fixed by hand (checked 2026-10-28).
NAME_FIXES = {"Veljko Paunovićhshsjs": "Veljko Paunović"}
NOT_A_PERSON = {"position not filled"}


def team_names() -> dict[str, str]:
    ref = pd.read_csv(REF / "clubs_wikidata.csv")
    return dict(zip(ref.wikidata, ref.team))


def season_end_year(label: str) -> int | None:
    m = EVENT.match(label)
    if not m:
        return None
    start = int(m.group(1))
    return start + 1 if m.group(2) else start


def season_text(end_year: int, single_year: bool) -> str:
    return str(end_year) if single_year else f"{end_year - 1}/{str(end_year)[-2:]}"


def honours(raw: pd.DataFrame, names: dict) -> pd.DataFrame:
    h = raw.assign(comp_q=raw.comp.fillna(raw.parentComp)).dropna(subset=["comp_q"])
    h = h[h.comp_q.isin(COMP) & ~h.evLabel.str.contains(EXCLUDE, na=False)].copy()
    h["end_year"] = h.evLabel.map(season_end_year)
    h = h.dropna(subset=["end_year"]).astype({"end_year": int})
    h = h[~((h.comp_q == EFL) & (h.end_year > TOP_FLIGHT_UNTIL))]
    h["category"] = h.comp_q.map(lambda q: COMP[q][0])
    h["competition"] = h.comp_q.map(lambda q: COMP[q][1])
    # Some second-tier season items are linked to the top-flight competition, so trust the item's own name too.
    old_first = (h.comp_q == OLD_FIRST_DIVISION) & (h.end_year > TOP_FLIGHT_UNTIL)
    misfiled = (h.category == "League title") & h.evLabel.str.contains(SECOND_TIER_NAMES)
    h.loc[old_first, "competition"] = "First Division (2nd tier)"
    h.loc[misfiled, "competition"] = h.loc[misfiled, "evLabel"].str.replace(EVENT_YEAR, "", regex=True)
    h.loc[old_first | misfiled, "category"] = "Second-tier title"
    h["team"] = h.club.map(names)
    # One trophy per club, category and season: drops the season/final pairs and the EFL/First Division duplicates.
    h = h.sort_values("evLabel").drop_duplicates(["team", "category", "end_year"])
    # A season item spans two years; a final or one-year tournament does not.
    single = ~h.evLabel.str.match(r"^\d{4}[–-]\d{2,4}")
    h["season"] = [season_text(y, s) for y, s in zip(h.end_year, single)]
    h = h.rename(columns={"evLabel": "source_item", "ev": "wikidata"})
    fixes = pd.read_csv(REF / "legacy_corrections.csv")
    key = ["team", "category", "season"]
    h = h[~h.set_index(key).index.isin(fixes[fixes.action == "drop"].set_index(key).index)]
    add = fixes[fixes.action == "add"].assign(source_item=lambda d: "Manual correction: " + d.reason)
    h = pd.concat([h, add[[*key, "end_year", "competition", "source_item"]]], ignore_index=True)
    return (h[["team", "category", "competition", "end_year", "season", "source_item", "wikidata"]]
            .sort_values(["team", "category", "end_year"]).reset_index(drop=True))


def honours_summary(h: pd.DataFrame) -> pd.DataFrame:
    s = (h.groupby(["team", "category"]).agg(count=("end_year", "size"), last_won=("season", "last"),
                                            first_won=("season", "first")).reset_index())
    s["category"] = pd.Categorical(s.category, CATEGORY_ORDER, ordered=True)
    return s.sort_values(["team", "category"]).reset_index(drop=True)


def managers(raw: pd.DataFrame, names: dict) -> pd.DataFrame:
    m = raw.rename(columns={"mLabel": "manager", "m": "wikidata", "countryLabel": "nationality"})
    m = m[~m.manager.isin(NOT_A_PERSON) & ~m.manager.str.fullmatch(r"Q\d+")].copy()
    m["manager"] = m.manager.replace(NAME_FIXES)
    m["team"] = m.club.map(names)
    for col in ("start", "end", "born"):
        m[col] = pd.to_datetime(m[col], utc=True, errors="coerce").dt.tz_localize(None).dt.normalize()
    # Wikidata stores "May 2026" as 1 May 2026; such an end date means the spell ran to the end of that month/year.
    m.loc[m.end_precision == 10, "end"] += pd.offsets.MonthEnd(0)
    m.loc[m.end_precision == 9, "end"] += pd.offsets.YearEnd(0)
    m["end"] = m.end.clip(upper=pd.Timestamp.now().normalize())  # a spell cannot have ended in the future
    # An undated open spell after the club's last dated spell has ended is taken to start the next day.
    last_end = m.dropna(subset=["start"]).sort_values("start").groupby("team").end.last()
    undated = m.start.isna() & m.end.isna() & m.team.map(last_end).notna()
    m.loc[undated, "start"] = m.loc[undated, "team"].map(last_end) + pd.Timedelta(days=1)
    m = m.dropna(subset=["start"])
    m = apply_manager_corrections(m)
    m = m[m.end.isna() | (m.end >= m.start)]  # spells that end before they start are data errors
    # One row per spell (a person with dual nationality appears twice).
    m = (m.sort_values("nationality").groupby(["team", "wikidata", "start"], as_index=False)
         .agg(manager=("manager", "first"), end=("end", "first"), born=("born", "first"),
              nationality=("nationality", lambda s: " / ".join(sorted(s.dropna().unique())))))
    latest = m.groupby("team").start.transform("max")
    m["current"] = m.end.isna() & (m.start == latest)
    m["days"] = ((m.end.fillna(pd.Timestamp.now().normalize()) - m.start).dt.days).astype(int)
    return m.sort_values(["team", "start"], ascending=[True, False]).reset_index(drop=True)


def apply_manager_corrections(m: pd.DataFrame) -> pd.DataFrame:
    """Spells missing from Wikidata (add) and start dates Wikidata gives only as an announcement month (set_start)."""
    fixes = pd.read_csv(REF / "manager_corrections.csv", parse_dates=["start", "end"])
    for _, f in fixes[fixes.action.isin(["set_start", "set_end"])].iterrows():
        col = f.action.removeprefix("set_")
        m.loc[(m.team == f.team) & (m.manager == f.manager) & (m.end.isna() if col == "start" else m.end.notna()),
              col] = f[col]
    add = fixes[fixes.action == "add"].assign(wikidata="manual")[["team", "manager", "start", "end", "wikidata"]]
    return pd.concat([m, add], ignore_index=True)


def assign_managers(tm: pd.DataFrame, m: pd.DataFrame) -> pd.Series:
    """Manager in charge for each club-match: the most recent spell that started on or before the match."""
    out = pd.Series(pd.NA, index=tm.index, dtype="object")
    for team, games in tm.groupby("team"):
        spells = m[m.team == team].sort_values("start")
        for _, s in spells.iterrows():
            on = (games.date >= s.start) & (games.date <= (s.end if pd.notna(s.end) else pd.Timestamp.max))
            out.loc[games.index[on]] = s.manager  # later spells overwrite, so caretakers win their window
    return out


def manager_records(m: pd.DataFrame) -> pd.DataFrame:
    tm = pd.read_parquet(HIST / "team_match.parquet")
    tm["date"] = pd.to_datetime(tm.date).dt.tz_localize(None).dt.normalize()
    tm["manager"] = assign_managers(tm, m)
    tm["result"] = tm.points.map({3: "W", 1: "D", 0: "L"})
    rec = (tm.dropna(subset=["manager"]).groupby(["team", "manager"])
           .agg(league=("league", "last"), first_match=("date", "min"), last_match=("date", "max"),
                matches=("game_id", "size"), wins=("result", lambda r: (r == "W").sum()),
                draws=("result", lambda r: (r == "D").sum()), losses=("result", lambda r: (r == "L").sum()),
                points=("points", "sum"), goals=("goals", "sum"), goals_against=("goals_against", "sum"),
                xg=("xg", "mean"), xg_against=("xg_against", "mean"), possession=("possessionPct", "mean"),
                shots=("shots", "mean"), attacking_index=("attacking_index", "mean"))
           .reset_index())
    rec["ppg"] = rec.points / rec.matches
    rec["win_pct"] = rec.wins / rec.matches * 100
    uncovered = tm.manager.isna().groupby(tm.team).sum()
    rec["club_matches_without_manager"] = rec.team.map(uncovered).astype(int)
    latest = tm[tm.season == tm.season.max()].sort_values("date").groupby("team").manager.last()  # clubs playing now
    current = m[m.current].set_index("team").manager
    for team in latest.index[latest.reindex(current.index).ne(current).reindex(latest.index, fill_value=False)]:
        print(f"  check {team}: latest match credited to {latest[team]}, current manager is {current[team]}")
    return rec.sort_values(["team", "first_match"], ascending=[True, False]).reset_index(drop=True)


def club_info(raw: pd.DataFrame, names: dict) -> pd.DataFrame:
    c = raw.assign(team=raw.club.map(names))
    c["founded"] = pd.to_datetime(c.inception, utc=True, errors="coerce").dt.year
    return (c.groupby("team").agg(wikidata=("club", "first"), official_name=("clubLabel", "first"),
                                  founded=("founded", "min"), stadium=("venueLabel", "first"),
                                  capacity=("capacity", "max"), city=("cityLabel", "first"),
                                  nicknames=("nickname", lambda s: " · ".join(dict.fromkeys(s.dropna()))))
            .reset_index())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    names = team_names()
    h = honours(pd.read_csv(RAW / "honours.csv"), names)
    m = managers(pd.read_csv(RAW / "managers.csv"), names)
    tables = {"honours": h, "honours_summary": honours_summary(h), "managers": m,
              "manager_records": manager_records(m), "club_info": club_info(pd.read_csv(RAW / "club_info.csv"), names)}
    for name, df in tables.items():
        df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8")
        print(f"{name}: {len(df):,} rows")
    (OUT / "retrieved.txt").write_text((RAW / "retrieved.txt").read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    main()
