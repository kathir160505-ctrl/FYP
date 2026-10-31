"""Weekly refresh: bring every dataset the dashboard reads up to date with the current season.

Run from the project root:  python -m src.refresh

1. Re-collect the current season for all three leagues (Understat + ESPN; past seasons are untouched).
2. Rebuild the multi-season tables and re-project styles (data/processed/history/).
3. Rebuild current-season form for the Matchday predictions (data/live/).
4. Refresh current-season player stats, line-ups and photos, and rebuild data/processed/players/.
5. Re-query Wikidata for honours and managers, then rebuild data/processed/legacy/ (manager records use step 2).

The 2025/26 thesis dataset and models are never modified by this script.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ["-m", "src.collect.history", "--current"],
    ["-m", "src.process.build_history"],
    ["-m", "src.collect.live"],
    ["-m", "src.collect.players", "--current"],
    ["-m", "src.process.build_players"],
    ["-m", "src.collect.photos"],  # cached: only new players hit Wikimedia
    ["-m", "src.process.build_players"],
    ["-m", "src.collect.legacy"],
    ["-m", "src.process.build_legacy"],
]


def main() -> None:
    for step in STEPS:
        t0 = time.time()
        print(f"==> python {' '.join(step)}", flush=True)
        result = subprocess.run([sys.executable, *step], cwd=ROOT)
        if result.returncode != 0:
            sys.exit(f"Step failed ({result.returncode}): {' '.join(step)}")
        print(f"    done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
