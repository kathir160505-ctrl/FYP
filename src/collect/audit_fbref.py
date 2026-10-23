"""Phase 0 audit: which FBref team-season stat tables exist for 2025/26, and with which columns."""
import sys
from pathlib import Path

import soccerdata as sd

OUT = Path(__file__).resolve().parents[2] / "reports" / "audit"
OUT.mkdir(parents=True, exist_ok=True)

LEAGUES = ["ENG-Premier League", "ESP-La Liga", "ITA-Serie A"]
STAT_TYPES = ["standard", "shooting", "passing", "passing_types", "goal_shot_creation", "possession", "misc"]

league = sys.argv[1] if len(sys.argv) > 1 else LEAGUES[0]
fbref = sd.FBref(leagues=league, seasons="2526")
lines = []
for st in STAT_TYPES:
    try:
        df = fbref.read_team_season_stats(stat_type=st)
        cols = [" | ".join(str(c) for c in col if c) if isinstance(col, tuple) else str(col) for col in df.columns]
        lines.append(f"## {st}  rows={len(df)}\n" + "\n".join(f"- {c}" for c in cols))
    except Exception as exc:  # noqa: BLE001 - audit wants every failure recorded
        lines.append(f"## {st}  FAILED: {type(exc).__name__}: {exc}")
(OUT / f"fbref_{league.split('-')[0]}.md").write_text("\n\n".join(lines), encoding="utf-8")
print("\n\n".join(lines))
