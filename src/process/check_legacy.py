"""Phase D check: compare the Wikidata trophy counts with published totals up to the end of 2024/25.

Run from the project root after src.process.build_legacy:  python -m src.process.check_legacy
Writes reports/phaseD_legacy_check.md.

The reference counts are the clubs' official totals (club and competition records) at the end of the
2024/25 season, for the major categories shown in the app.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LEGACY, REPORT = ROOT / "data" / "processed" / "legacy", ROOT / "reports" / "phaseD_legacy_check.md"
UP_TO = 2025  # end year of the last season covered by the reference counts

PUBLISHED = {
    "League title": {
        "Manchester United": 20, "Liverpool": 20, "Arsenal": 13, "Manchester City": 10, "Everton": 9,
        "Aston Villa": 7, "Chelsea": 6, "Sunderland": 6, "Newcastle United": 4, "Wolves": 3, "Leeds United": 3,
        "Tottenham": 2, "Burnley": 2, "Nottingham Forest": 1, "Ipswich Town": 1,
        "Real Madrid": 36, "Barcelona": 28, "Atlético Madrid": 11, "Athletic Club": 8, "Valencia": 6,
        "Real Sociedad": 2, "Sevilla": 1, "Real Betis": 1, "Deportivo La Coruña": 1,
        "Juventus": 36, "Inter": 20, "AC Milan": 19, "Genoa": 9, "Bologna": 7, "Torino": 7, "Napoli": 4,
        "Roma": 3, "Lazio": 2, "Fiorentina": 2, "Cagliari": 1, "Hellas Verona": 1},
    "European Cup": {
        "Real Madrid": 15, "AC Milan": 7, "Liverpool": 6, "Barcelona": 5, "Inter": 3, "Manchester United": 3,
        "Juventus": 2, "Chelsea": 2, "Nottingham Forest": 2, "Aston Villa": 1, "Manchester City": 1},
    "Domestic cup": {
        "Arsenal": 14, "Manchester United": 13, "Chelsea": 8, "Liverpool": 8, "Tottenham": 8, "Manchester City": 7,
        "Aston Villa": 7, "Newcastle United": 6, "Everton": 5, "Wolves": 4, "Crystal Palace": 1,
        "Barcelona": 32, "Real Madrid": 20, "Atlético Madrid": 10, "Valencia": 8, "Sevilla": 5, "Real Betis": 3,
        "Real Sociedad": 3, "Espanyol": 4, "Mallorca": 1,
        "Juventus": 15, "Inter": 9, "Roma": 9, "Lazio": 7, "Fiorentina": 6, "Napoli": 6, "AC Milan": 5,
        "Torino": 5, "Parma": 3, "Bologna": 3, "Atalanta": 1, "Genoa": 1, "Venezia": 1},
    "UEFA Cup": {
        "Sevilla": 7, "Inter": 3, "Juventus": 3, "Liverpool": 3, "Atlético Madrid": 3, "Tottenham": 3,
        "Real Madrid": 2, "Chelsea": 2, "Parma": 2, "Napoli": 1, "Villarreal": 1, "Manchester United": 1,
        "Valencia": 1, "Atalanta": 1, "Ipswich Town": 1},
}


def compare(h: pd.DataFrame) -> pd.DataFrame:
    got = h[h.end_year <= UP_TO].groupby(["category", "team"]).size()
    rows = [{"category": cat, "team": team, "published": n, "wikidata": int(got.get((cat, team), 0))}
            for cat, teams in PUBLISHED.items() for team, n in teams.items()]
    df = pd.DataFrame(rows)
    df["diff"] = df.wikidata - df.published
    return df


def main() -> None:
    df = compare(pd.read_csv(LEGACY / "honours.csv"))
    summary = (df.assign(exact=df["diff"] == 0, within1=df["diff"].abs() <= 1)
               .groupby("category").agg(clubs=("team", "size"), exact=("exact", "sum"), within_1=("within1", "sum"),
                                        published=("published", "sum"), wikidata=("wikidata", "sum")))
    off = df[df["diff"] != 0].sort_values(["category", "diff"])
    total_exact = int((df["diff"] == 0).sum())
    REPORT.write_text("\n".join([
        "# Phase D: honours check (Wikidata vs published totals)", "",
        f"Trophies won up to the end of 2024/25, for {len(df)} club-category pairs.", "",
        f"**{total_exact} of {len(df)} counts match exactly** "
        f"({total_exact / len(df):.0%}); {int((df['diff'].abs() <= 1).sum())} are within one trophy.", "",
        summary.reset_index().to_markdown(index=False), "", "## Counts that differ", "",
        off.to_markdown(index=False) if len(off) else "None.", "",
        "Corrections applied before this check are listed in `data/reference/legacy_corrections.csv`. "
        "Super cups are excluded from the app because Wikidata records too few of them.", ""]), encoding="utf-8")
    print(summary.to_string())
    print(f"\n{total_exact}/{len(df)} exact. Differences:\n{off.to_string(index=False)}")


if __name__ == "__main__":
    main()
