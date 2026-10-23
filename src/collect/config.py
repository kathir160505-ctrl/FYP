"""Shared settings for the Phase 1 collectors."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
LOG_FILE = RAW / "collection_log.jsonl"

SEASON = "2526"            # soccerdata season code
UNDERSTAT_SEASON = "2025"  # Understat names a season by its start year
SEASON_MONTHS = [f"2025{m:02d}" for m in range(8, 13)] + [f"2026{m:02d}" for m in range(1, 7)]

LEAGUES = {
    "ENG-Premier League": {"espn": "eng.1"},
    "ESP-La Liga": {"espn": "esp.1"},
    "ITA-Serie A": {"espn": "ita.1"},
}


def log_step(source: str, **details) -> None:
    """Append one collection step to the reproducibility log."""
    RAW.mkdir(parents=True, exist_ok=True)
    entry = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": source, **details}
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
