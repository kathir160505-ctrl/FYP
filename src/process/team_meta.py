"""Extract club abbreviation, colours and crest URL from cached ESPN scoreboards.

Run from the project root:  python -m src.process.team_meta
Output: data/reference/team_meta.csv (used by the dashboard for club colours and crests).
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ESPN_JSON = ROOT / "data" / "raw" / "espn" / "json"


def main() -> None:
    teams = pd.read_csv(ROOT / "data" / "reference" / "teams.csv")
    meta = {}
    for path in ESPN_JSON.glob("*/scoreboard_*.json"):
        for ev in json.loads(path.read_text(encoding="utf-8")).get("events", []):
            for comp in ev["competitions"][0]["competitors"]:
                t = comp["team"]
                meta[t["displayName"]] = {"espn": t["displayName"], "abbr": t.get("abbreviation"),
                                          "color": "#" + t.get("color", "888888"),
                                          "alt_color": "#" + t.get("alternateColor", "ffffff"), "logo": t.get("logo")}
    df = teams.merge(pd.DataFrame(meta.values()), on="espn", how="left")
    missing = df[df["abbr"].isna()]["team"].tolist()
    if missing:
        raise SystemExit(f"No ESPN metadata for: {missing}")
    df[["league", "team", "abbr", "color", "alt_color", "logo"]].to_csv(
        ROOT / "data" / "reference" / "team_meta.csv", index=False)
    print(f"team_meta: {len(df)} clubs")


if __name__ == "__main__":
    main()
