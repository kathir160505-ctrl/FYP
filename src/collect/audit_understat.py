"""Phase 0 audit: Understat 2025/26 team-match stats and shot events (columns, coverage)."""
import sys
from pathlib import Path

import soccerdata as sd

OUT = Path(__file__).resolve().parents[2] / "reports" / "audit"
OUT.mkdir(parents=True, exist_ok=True)

league = sys.argv[1] if len(sys.argv) > 1 else "ENG-Premier League"
us = sd.Understat(leagues=league, seasons="2526")
lines = []

tm = us.read_team_match_stats()
lines.append(f"## team_match_stats rows={len(tm)}\n" + "\n".join(f"- {c}" for c in tm.columns))
lines.append("sample:\n" + tm.head(3).to_string())

shots = us.read_shot_events()
lines.append(f"## shot_events rows={len(shots)}\n" + "\n".join(f"- {c}" for c in shots.columns))
for col in ("situation", "shot_type", "result", "last_action"):
    if col in shots.columns:
        lines.append(f"### {col} values\n" + shots[col].value_counts().to_string())

(OUT / f"understat_{league.split('-')[0]}.md").write_text("\n\n".join(lines), encoding="utf-8")
print("\n\n".join(lines))
