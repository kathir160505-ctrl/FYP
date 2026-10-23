"""Collect FBref 2025/26 team-season tables (standard, shooting, misc) for cross-checking.

Output: data/raw/fbref/team_season_stats.csv, one row per team.
"""
import pandas as pd
import soccerdata as sd

from config import LEAGUES, RAW, SEASON, log_step

OUT = RAW / "fbref"
STAT_TYPES = ("standard", "shooting", "misc")


def flatten(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [f"{prefix}_" + "_".join(p for p in col if p) if isinstance(col, tuple) else f"{prefix}_{col}"
                  for col in df.columns]
    return df


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fbref = sd.FBref(leagues=list(LEAGUES), seasons=SEASON)
    tables = [flatten(fbref.read_team_season_stats(stat_type=st), st) for st in STAT_TYPES]
    df = pd.concat(tables, axis=1).reset_index()
    df.to_csv(OUT / "team_season_stats.csv", index=False)
    log_step("fbref", soccerdata=sd.__version__, rows=len(df), stat_types=list(STAT_TYPES))
    print(f"FBref: {len(df)} teams")


if __name__ == "__main__":
    main()
