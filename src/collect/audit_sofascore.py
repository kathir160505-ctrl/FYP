"""Phase 0 audit: Sofascore team-season and per-match statistics for 2025/26.

soccerdata only wraps Sofascore's schedule/table, so this reuses its HTTP session
(caching + TLS fingerprinting) to probe the statistics endpoints directly.
"""
import json
import sys
from pathlib import Path

import soccerdata as sd
from soccerdata.sofascore import SOFASCORE_API

OUT = Path(__file__).resolve().parents[2] / "reports" / "audit"
OUT.mkdir(parents=True, exist_ok=True)

league = sys.argv[1] if len(sys.argv) > 1 else "ENG-Premier League"
ss = sd.Sofascore(leagues=league, seasons="2526")
season = ss.read_seasons().iloc[0]
lid, sid = int(season.league_id), int(season.season_id)
lines = [f"league_id={lid} season_id={sid}"]


def get_json(path: str, cache_name: str) -> dict:
    reader = ss.get(SOFASCORE_API + path, ss.data_dir / "matches" / cache_name)
    return json.load(reader)


standings = get_json(f"unique-tournament/{lid}/season/{sid}/standings/total", f"standings_{lid}_{sid}.json")
rows = standings["standings"][0]["rows"]
lines.append(f"teams in table: {len(rows)}")
team = rows[0]["team"]

team_stats = get_json(
    f"team/{team['id']}/unique-tournament/{lid}/season/{sid}/statistics/overall",
    f"teamstats_{team['id']}_{sid}.json",
)["statistics"]
lines.append(f"## team season statistics ({team['name']}) — {len(team_stats)} fields")
lines += [f"- {k}: {v}" for k, v in sorted(team_stats.items())]

schedule = ss.read_schedule()
game_id = int(schedule.iloc[0]["game_id"])
match_stats = get_json(f"event/{game_id}/statistics", f"eventstats_{game_id}.json")
lines.append(f"## per-match statistics (event {game_id}, period ALL)")
for period in match_stats["statistics"]:
    if period["period"] != "ALL":
        continue
    for group in period["groups"]:
        for item in group["statisticsItems"]:
            lines.append(f"- [{group['groupName']}] {item['name']} ({item.get('key')}): home={item.get('home')} away={item.get('away')}")

(OUT / f"sofascore_{league.split('-')[0]}.md").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
