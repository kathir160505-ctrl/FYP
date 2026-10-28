"""Export the processed 2025/26 dataset to one Excel workbook with a data dictionary.

Run from the project root:  python -m src.process.export_excel
Output: data/FYP_dataset_2025-26.xlsx
"""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "data" / "FYP_dataset_2025-26.xlsx"

FONT = "Arial"
HEADER_FILL = PatternFill("solid", start_color="1F2A44")
HEADER_FONT = Font(name=FONT, bold=True, color="FFFFFF", size=10)
BODY_FONT = Font(name=FONT, size=10)
TITLE_FONT = Font(name=FONT, bold=True, size=14)
SECTION_FONT = Font(name=FONT, bold=True, size=11)
THIN = Side(style="thin", color="D0D5DD")
LEAGUES = {"ENG-Premier League": "Premier League", "ESP-La Liga": "La Liga", "ITA-Serie A": "Serie A"}

# sheet name -> (description, {column: meaning})
SHEETS = {
    "Season_60_clubs": (
        "Main clustering dataset: one row per club for the full 2025/26 season, with the 13 attacking features "
        "(Table 3.1), context stats and the assigned attacking philosophy.",
        {
            "league": "Competition", "team": "Club",
            "matches": "League matches played (38)", "points": "League points (context, not a clustering input)",
            "possession": "FEATURE · Average possession % (ESPN)",
            "pass_accuracy": "FEATURE · Ball control: completed / attempted passes, % (ESPN)",
            "passes_completed": "FEATURE · Completed passes per match (ESPN)",
            "deep_completions": "FEATURE · Passes completed within ~20 m of goal per match; proxy for progressive passes (Understat)",
            "long_ball_share": "FEATURE · Long balls as % of all passes; directness (ESPN)",
            "crosses": "FEATURE · Crosses attempted per match (ESPN)",
            "shots": "FEATURE · Shots per match, own goals excluded (Understat)",
            "sot_pct": "FEATURE · Shots on target (goals + saved) as % of shots (Understat)",
            "xg": "FEATURE · Expected goals per match (Understat)",
            "goals": "FEATURE · Goals per match (Understat)",
            "goals_per_shot": "FEATURE · Goals / shots, season totals (Understat)",
            "fast_attack_shots": "FEATURE · Shots from fast attacks per match; proxy for counter-attacks (Understat attack speed)",
            "box_shot_share": "FEATURE · % of shots taken inside the penalty area; proxy for box touches (Understat x/y)",
            "goals_against": "Goals conceded per match (context)", "xg_against": "xG conceded per match (context)",
            "np_xg": "Non-penalty xG per match (context)", "ppda": "Passes allowed per defensive action (pressing, context)",
            "fast_attack_shots_total": "Season total shots from fast attacks",
            "fast_attack_xg_total": "Season total xG from fast attacks",
            "fast_attack_shot_share": "Fast-attack shots as % of all shots",
            "cluster": "Attacking philosophy assigned by K-means (k = 4)",
            "top_level": "Coarse k = 2 split (possession-dominant vs reactive/direct)",
            "dbscan_outlier": "TRUE if flagged statistically unique by DBSCAN (noise in >50% of 24 settings)",
            "uniqueness": "Share of DBSCAN settings in which the club is an outlier",
            "silhouette": "How typical the club is of its cluster (-1 to 1)",
            "cluster_h1": "Cluster using matchweeks 1-19 only (split-half validation)",
            "cluster_h2": "Cluster using matchweeks 20-38 only",
            "PC1": "Principal component 1: attacking dominance", "PC2": "PC2: crossing volume vs finishing efficiency",
            "PC3": "PC3: box presence", "PC4": "PC4: counter-attacking",
        },
    ),
    "Matches": (
        "One row per club per league match (1,140 matches x 2 teams). Basis for timelines, split-half and the prediction model.",
        {
            "date": "Kick-off date and time", "matchweek": "The club's match number (1-38)", "half": "H1 = matchweeks 1-19, H2 = 20-38",
            "team": "Club", "opponent": "Opponent", "is_home": "TRUE if the club played at home",
            "goals": "Goals scored", "goals_against": "Goals conceded", "points": "League points from the match",
            "xg": "Expected goals (Understat)", "np_xg": "Non-penalty xG", "xg_against": "xG conceded",
            "deep_completions": "Passes completed within ~20 m of goal", "ppda": "Passes allowed per defensive action",
            "shots": "Shots (Understat, own goals excluded)", "shots_on_target": "Goals + saved shots (Understat)",
            "box_shots": "Shots from inside the penalty area",
            "possessionPct": "Possession % (ESPN)", "accuratePasses": "Completed passes (ESPN)", "totalPasses": "Attempted passes (ESPN)",
            "totalCrosses": "Crosses attempted (ESPN)", "accurateCrosses": "Crosses completed (ESPN)",
            "totalLongBalls": "Long balls attempted (ESPN)", "accurateLongBalls": "Long balls completed (ESPN)",
            "totalShots": "Shots as counted by ESPN (cross-check)", "shotsOnTarget": "Shots on target as counted by ESPN",
            "wonCorners": "Corners won (ESPN)", "game_id": "Understat match id", "event_id": "ESPN match id",
        },
    ),
    "Season_halves": (
        "Same features as Season_60_clubs, split into first half (MW 1-19) and second half (MW 20-38) of the season.",
        {"half": "H1 = matchweeks 1-19, H2 = matchweeks 20-38",
         "note": "Fast-attack shots are season-level only, so they are not available per half."},
    ),
    "Shots": (
        "Every shot in the 2025/26 season (Understat). Pitch coordinates are 0-1; x = 1 is the opponent's goal line.",
        {"player": "Shooter", "assist_player": "Player who made the final pass (blank = unassisted shot)",
         "minute": "Match minute",
         "xg": "Expected-goal value of the shot", "location_x": "Distance up the pitch (0 own goal line, 1 opponent goal line)",
         "location_y": "Position across the pitch (0-1)", "body_part": "Right Foot, Left Foot, Head or Other",
         "situation": "Open Play, From Corner, Set Piece, Direct Freekick or Penalty",
         "result": "Goal, Saved Shot, Missed Shot, Blocked Shot, Shot On Post",
         "in_box": "TRUE if taken inside the penalty area"},
    ),
    "Attack_breakdowns": (
        "Understat season breakdowns per club: attack speed (Fast = counter-attack proxy), shot zone and situation.",
        {"block": "attackSpeed, shotZone or situation", "category": "Category inside the block",
         "shots / goals / xg": "Club's own shots, goals and xG in that category",
         "shots_against / goals_against / xg_against": "The same, conceded"},
    ),
}

PCT_COLS = {"possession", "pass_accuracy", "long_ball_share", "sot_pct", "box_shot_share", "fast_attack_shot_share",
            "possessionPct"}


def load() -> dict[str, pd.DataFrame]:
    season = pd.read_csv(PROC / "team_season.csv")
    clusters = pd.read_csv(PROC / "clusters.csv").drop(columns=["league", "cluster_id", "ward_cluster"])
    season["points"] = (season["points_per_match"] * season["matches"]).round().astype(int)
    season = season.drop(columns=["points_per_match"]).merge(clusters, on="team")
    order = ["league", "team", "matches", "points", "possession", "pass_accuracy", "passes_completed",
             "deep_completions", "long_ball_share", "crosses", "shots", "sot_pct", "xg", "goals", "goals_per_shot",
             "fast_attack_shots", "box_shot_share", "cluster", "top_level", "dbscan_outlier", "uniqueness",
             "silhouette", "cluster_h1", "cluster_h2", "PC1", "PC2", "PC3", "PC4", "goals_against", "xg_against",
             "np_xg", "ppda", "fast_attack_shots_total", "fast_attack_xg_total", "fast_attack_shot_share"]
    season = season[order].sort_values(["league", "points"], ascending=[True, False])

    matches = pd.read_csv(PROC / "team_match.csv", parse_dates=["date"])
    m_order = ["league", "date", "matchweek", "half", "team", "opponent", "is_home", "goals", "goals_against",
               "points", "xg", "np_xg", "xg_against", "shots", "shots_on_target", "box_shots", "deep_completions",
               "ppda", "possessionPct", "accuratePasses", "totalPasses", "totalCrosses", "accurateCrosses",
               "totalLongBalls", "accurateLongBalls", "totalShots", "shotsOnTarget", "wonCorners", "game_id", "event_id"]
    matches = matches[m_order].sort_values(["league", "team", "matchweek"])

    halves = pd.read_csv(PROC / "team_half.csv").sort_values(["league", "team", "half"])
    shots = pd.read_csv(PROC / "shots.csv", parse_dates=["date"]).sort_values(["league", "team", "date", "minute"])
    br = pd.read_csv(PROC / "team_breakdowns.csv").sort_values(["league", "team", "block", "category"])
    frames = {"Season_60_clubs": season, "Matches": matches, "Season_halves": halves, "Shots": shots,
              "Attack_breakdowns": br}
    for df in frames.values():
        df["league"] = df["league"].map(LEAGUES)
    return frames


def write_table(ws, df: pd.DataFrame) -> None:
    ws.append(list(df.columns))
    for row in df.itertuples(index=False):
        ws.append([v.to_pydatetime() if isinstance(v, pd.Timestamp) else (None if pd.isna(v) else v) for v in row])
    for cell in ws[1]:
        cell.font, cell.fill = HEADER_FONT, HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30
    for j, col in enumerate(df.columns, 1):
        letter = get_column_letter(j)
        fmt = "General"
        if col == "date":
            fmt = "yyyy-mm-dd hh:mm"
        elif pd.api.types.is_float_dtype(df[col]):
            fmt = "0.0" if col in PCT_COLS else "0.000" if col in ("goals_per_shot", "xg", "silhouette", "uniqueness") or col.startswith("PC") else "0.00"
        for cell in ws[letter][1:]:
            cell.font = BODY_FONT
            cell.number_format = fmt
        width = max(len(str(col)), *(len(str(v)) for v in df[col].head(200))) if len(df) else len(col)
        ws.column_dimensions[letter].width = min(max(width + 2, 9), 28)
    ws.freeze_panes = "C2" if "team" in df.columns[:2] else "A2"
    ws.auto_filter.ref = ws.dimensions


def write_readme(ws, frames: dict[str, pd.DataFrame]) -> None:
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 110
    ws["A1"] = "FYP dataset · Attacking philosophies in the Premier League, La Liga and Serie A · 2025/26"
    ws["A1"].font = TITLE_FONT
    rows = [
        ("Coverage", "60 clubs (20 per league) · 1,140 matches · 28,420 shots · full 2025/26 league season"),
        ("Sources", "Understat (xG, shots and locations, deep completions, attack speed) · ESPN public API (possession, "
                    "passing, crosses, long balls) · FBref used only as an independent cross-check (r ≥ 0.977)"),
        ("Units", "Counts are per match (= per 90 minutes for team data). Columns marked % are already in percent "
                  "(56.2 means 56.2%). Ratios are computed from season totals."),
        ("Proxies", "Free 2025/26 data lacks four proposal variables, so the closest available measures are used: "
                    "progressive passes → deep completions; counter-attacks → fast-attack shots; touches in box → share "
                    "of shots in the box; ball control → pass accuracy. Through balls are excluded (no free source)."),
        ("Reproduce", "python -m src.process.build_dataset, then python -m src.model.clustering, then "
                      "python -m src.process.export_excel (see README.md)"),
    ]
    r = 3
    for k, v in rows:
        ws.cell(r, 1, k).font = Font(name=FONT, bold=True, size=10)
        c = ws.cell(r, 2, v)
        c.font, c.alignment = BODY_FONT, Alignment(wrap_text=True, vertical="top")
        r += 1
    r += 1
    ws.cell(r, 1, "Sheet").font = HEADER_FONT
    ws.cell(r, 2, "Contents").font = HEADER_FONT
    for c in (1, 2):
        ws.cell(r, c).fill = HEADER_FILL
    r += 1
    for name, (desc, _) in SHEETS.items():
        ws.cell(r, 1, name).font = Font(name=FONT, bold=True, size=10, color="1F4E99")
        ws.cell(r, 1).hyperlink = f"#'{name}'!A1"
        c = ws.cell(r, 2, f"{desc} ({len(frames[name]):,} rows)")
        c.font, c.alignment = BODY_FONT, Alignment(wrap_text=True, vertical="top")
        r += 1
    for name, (_, cols) in SHEETS.items():
        r += 1
        ws.cell(r, 1, f"Columns · {name}").font = SECTION_FONT
        r += 1
        for col, meaning in cols.items():
            ws.cell(r, 1, col).font = Font(name=FONT, size=10, bold=meaning.startswith("FEATURE"))
            c = ws.cell(r, 2, meaning)
            c.font, c.alignment = BODY_FONT, Alignment(wrap_text=True, vertical="top")
            for cc in (1, 2):
                ws.cell(r, cc).border = Border(bottom=THIN)
            r += 1
    ws.freeze_panes = "A2"


def main() -> None:
    frames = load()
    wb = Workbook()
    write_readme(wb.active, frames)
    wb.active.title = "README"
    for name, df in frames.items():
        write_table(wb.create_sheet(name), df)
    wb.save(OUT)
    print(f"Saved {OUT} with sheets: {', '.join(wb.sheetnames)}")


if __name__ == "__main__":
    main()
