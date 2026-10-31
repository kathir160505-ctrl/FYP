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
# (command, required). A required step that fails stops the refresh; an optional one (a source that may block
# cloud servers, or data the core pages do not need) is reported and skipped, so the rest still updates.
STEPS = [
    (["-m", "src.collect.history", "--current"], True),
    (["-m", "src.process.build_history"], True),
    (["-m", "src.collect.live"], False),
    (["-m", "src.collect.players", "--current"], False),
    (["-m", "src.process.build_players"], False),
    (["-m", "src.collect.photos"], False),  # cached: only new players hit Wikimedia
    (["-m", "src.process.build_players"], False),
    (["-m", "src.collect.legacy"], False),
    (["-m", "src.process.build_legacy"], False),
]


def main() -> None:
    skipped = []
    for step, required in STEPS:
        t0 = time.time()
        name = " ".join(step)
        print(f"==> python {name}", flush=True)
        result = subprocess.run([sys.executable, *step], cwd=ROOT)
        if result.returncode != 0:
            if required:
                sys.exit(f"Step failed ({result.returncode}): {name}")
            skipped.append(name)
            print(f"    FAILED, skipped (optional): {name}", flush=True)
            continue
        print(f"    done in {time.time() - t0:.0f}s", flush=True)
    if skipped:
        print("Optional steps that failed: " + "; ".join(skipped), flush=True)


if __name__ == "__main__":
    main()
