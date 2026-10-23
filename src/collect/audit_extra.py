"""Phase 0 audit: Understat team page breakdowns (attack speed) and ESPN per-match team stats."""
import json
from pathlib import Path

import soccerdata as sd
from soccerdata.understat import UNDERSTAT_URL

OUT = Path(__file__).resolve().parents[2] / "reports" / "audit"
OUT.mkdir(parents=True, exist_ok=True)
lines = []

# Understat: team-level breakdowns (situation, attackSpeed, shotZone, ...) via its JSON endpoint.
us = sd.Understat(leagues="ENG-Premier League", seasons="2526")
us._ensure_cookies()
try:
    data = json.load(us._request_api(UNDERSTAT_URL + "/getTeamData/Arsenal/2025", us.data_dir / "team_Arsenal_2025.json"))
    lines.append(f"## Understat getTeamData keys: {list(data)}")
    stats = data.get("statistics", {})
    for block, values in stats.items():
        lines.append(f"### {block}: {list(values)}")
    if "attackSpeed" in stats:
        lines.append("attackSpeed detail:\n" + json.dumps(stats["attackSpeed"], indent=1)[:1500])
except Exception as exc:  # noqa: BLE001
    lines.append(f"## Understat getTeamData FAILED: {type(exc).__name__}: {exc}")

# ESPN: team stats in one 2025/26 match sheet.
try:
    espn = sd.ESPN(leagues="ENG-Premier League", seasons="2526")
    sched = espn.read_schedule()
    game = sched.iloc[0]
    ms = espn.read_matchsheet(match_id=int(game["game_id"]))
    lines.append(f"## ESPN matchsheet ({len(ms)} rows) columns:\n" + "\n".join(f"- {c}" for c in ms.columns))
    lines.append(ms.head(2).T.to_string())
except Exception as exc:  # noqa: BLE001
    lines.append(f"## ESPN FAILED: {type(exc).__name__}: {exc}")

(OUT / "extra_ENG.md").write_text("\n\n".join(lines), encoding="utf-8")
print("\n\n".join(lines))
