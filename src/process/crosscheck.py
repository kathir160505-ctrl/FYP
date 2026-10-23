"""Cross-check processed season features against FBref's independent figures.

Run from the project root:  python -m src.process.crosscheck
Writes reports/phase2_crosscheck.md.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

# ours column -> (FBref column, how to convert FBref's season figure to per match)
PAIRS = {
    "possession": ("standard_Poss", 1),
    "shots": ("shooting_Standard_Sh", "per_match"),
    "sot_pct": ("shooting_Standard_SoT%", 1),
    "goals": ("standard_Performance_Gls", "per_match"),
    "goals_per_shot": ("shooting_Standard_G/Sh", 1),
    "crosses": ("misc_Performance_Crs", "per_match"),
}


def main() -> None:
    teams = pd.read_csv(ROOT / "data" / "reference" / "teams.csv")
    ours = pd.read_csv(ROOT / "data" / "processed" / "team_season.csv")
    fb = pd.read_csv(ROOT / "data" / "raw" / "fbref" / "team_season_stats.csv")
    fb["team"] = fb["team"].map(dict(zip(teams["fbref"], teams["team"])))
    df = ours.merge(fb, on=["league", "team"], how="inner", suffixes=("", "_fb"))

    lines = ["# Phase 2 cross-check: our features vs FBref", "",
             f"Clubs matched: {len(df)} / {len(ours)}", "",
             "| Feature | Pearson r | Mean ours | Mean FBref | Mean abs diff | Max abs diff (club) |",
             "|---|---|---|---|---|---|"]
    for col, (fb_col, conv) in PAIRS.items():
        ref = df[fb_col] / df["standard_Playing Time_MP"] if conv == "per_match" else df[fb_col] * conv
        diff = (df[col] - ref).abs()
        worst = df.loc[diff.idxmax(), "team"]
        lines.append(f"| {col} | {df[col].corr(ref):.3f} | {df[col].mean():.2f} | {ref.mean():.2f} | "
                     f"{diff.mean():.2f} | {diff.max():.2f} ({worst}) |")
    lines += ["", "Different providers define shots, on-target shots and crosses slightly differently "
              "(Understat/ESPN vs Opta-era FBref), so small level differences are expected. "
              "High correlations confirm the clubs are ranked consistently."]
    out = ROOT / "reports" / "phase2_crosscheck.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
