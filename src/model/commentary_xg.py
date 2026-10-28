"""Commentary xG: an expected-goals model built from ESPN's text commentary, for competitions Understat does not
cover (the Champions League).

Run from the project root (needs the cached ESPN summaries from src.collect.history and src.collect.ucl):
    python -m src.model.commentary_xg

Each shot in ESPN's commentary is described in a fixed pattern: body part, location ("from the centre of the box",
"from outside the box", "from a difficult angle on the left"), how it was created ("Assisted by X with a cross",
"following a corner", "following a fast break") and the outcome ("Goal!", "Attempt saved/missed/blocked").
Only pre-shot information is used as features; the outcome is the label. Penalties get the conventional 0.76.

Trained on 2025/26 league shots, tested on 2026/27 league shots: shot-level AUC and Brier score, and how closely the
summed match xG follows Understat's match xG (correlation, mean absolute error). Writes
models/commentary_xg.joblib, data/processed/ucl/ucl_shots.parquet, data/processed/ucl/ucl_xg.csv and
reports/phaseB_commentary_xg.md.
"""
import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "raw" / "espn" / "json"
HIST = ROOT / "data" / "processed" / "history"
OUT = ROOT / "data" / "processed" / "ucl"
MODEL = ROOT / "models" / "commentary_xg.joblib"
REPORT = ROOT / "reports" / "phaseB_commentary_xg.md"
LEAGUE_DIRS = {"ENG": "eng.1", "ESP": "esp.1", "ITA": "ita.1"}
PENALTY_XG = 0.76

SHOT = re.compile(r"^(Goal!|Attempt (saved|missed|blocked)\.|Penalty (saved|missed)!)")
TEAM_IN_TEXT = re.compile(r"^[^(]*?([A-Z][^()]*?) \(([^()]+)\) (right footed shot|left footed shot|header|shot)")
ZONES = [("very close range", "very_close"), ("six yard box", "six_yard"), ("centre of the box", "box_centre"),
         ("left side of the box", "box_side"), ("right side of the box", "box_side"),
         ("difficult angle and long range", "long_angle"), ("difficult angle", "angle"),
         ("more than 35 yards", "long_range"), ("long range", "long_range"), ("outside the box", "outside")]
FEATURES = ["zone", "body", "assist", "situation"]


def parse_shot(text: str) -> dict | None:
    """Features and outcome of one commentary line, or None if it is not a shot."""
    if not SHOT.match(text) or "Own Goal" in text:
        return None
    lower = text.lower()
    m = re.search(r"\) (right footed shot|left footed shot|header|shot)", text)
    who = re.search(r"(?:Goal! [^.]*\. |Attempt \w+\. |Penalty \w+! )([^(]+) \(([^)]+)\)", text)
    penalty = "penalty" in lower and ("converts the penalty" in lower or lower.startswith("penalty"))
    zone = next((z for k, z in ZONES if k in lower), "box_centre" if penalty else "unknown")
    if "cross" in lower and "assisted by" in lower:
        assist = "cross"
    elif "through ball" in lower:
        assist = "through_ball"
    elif "headed pass" in lower:
        assist = "headed_pass"
    elif "assisted by" in lower:
        assist = "pass"
    else:
        assist = "none"
    situation = ("corner" if "following a corner" in lower else "set_piece" if "set piece" in lower
                 else "fast_break" if "fast break" in lower else "free_kick" if "free kick" in lower and "direct" in lower
                 else "open_play")
    body = {"right footed shot": "foot", "left footed shot": "foot", "header": "head"}.get(m.group(1), "other") if m else "other"
    return {"player": who.group(1).strip() if who else "", "team": who.group(2).strip() if who else "",
            "zone": zone, "body": body, "assist": assist, "situation": situation, "penalty": penalty,
            "goal": text.startswith("Goal!") or "converts the penalty" in lower}


def minute(clock: dict | None) -> float:
    txt = (clock or {}).get("displayValue", "") if isinstance(clock, dict) else str(clock or "")
    nums = [int(x) for x in re.findall(r"\d+", txt)]
    return float(sum(nums[:2])) if nums else np.nan


def shots_from_summary(s: dict) -> pd.DataFrame:
    rows = []
    for c in s.get("commentary", []):
        p = parse_shot(c.get("text", ""))
        if p:
            rows.append({**p, "minute": minute(c.get("time"))})
    return pd.DataFrame(rows)


def load_shots(code: str, events: list) -> pd.DataFrame:
    frames = []
    for e in events:
        f = CACHE / code / f"summary_{e}.json"
        if f.exists():
            df = shots_from_summary(json.loads(f.read_text(encoding="utf-8")))
            if len(df):
                frames.append(df.assign(event_id=str(e)))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def side_of(shots: pd.DataFrame, home: str, away: str) -> pd.Series:
    """'home'/'away' for each shot. Commentary names differ from ESPN's ('Inter Milan' vs 'Internazionale'), so
    within one match each commentary name goes to the more similar of the two ESPN names."""
    from difflib import SequenceMatcher
    import unicodedata

    def fold(x: str) -> str:
        return unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().lower()

    sim = lambda a, b: SequenceMatcher(None, fold(a), fold(b)).ratio()  # noqa: E731
    names = shots.team.dropna().unique()
    mapping = {}
    if len(names) == 2:
        a, b = names
        straight = sim(a, home) + sim(b, away)
        mapping = {a: "home", b: "away"} if straight >= sim(a, away) + sim(b, home) else {a: "away", b: "home"}
    else:
        mapping = {n: "home" if sim(n, home) >= sim(n, away) else "away" for n in names}
    return shots.team.map(mapping)


def design(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    X = pd.get_dummies(df[FEATURES].astype(str), dtype=float)
    return X.reindex(columns=columns, fill_value=0.0) if columns is not None else X


def predict(model: dict, shots: pd.DataFrame) -> np.ndarray:
    if shots.empty:
        return np.array([])
    p = model["clf"].predict_proba(design(shots, model["columns"]))[:, 1] * model.get("scale", 1.0)
    return np.where(shots.penalty, PENALTY_XG, np.clip(p, 0, 0.99))


def league_shots() -> pd.DataFrame:
    tm = pd.read_parquet(HIST / "team_match.parquet", columns=["event_id", "season", "league"]).dropna()
    frames = []
    for (season, league), g in tm.groupby(["season", "league"]):
        code = LEAGUE_DIRS[league[:3]]
        frames.append(load_shots(code, sorted(g.event_id.astype("int64").unique())).assign(season=season))
    return pd.concat(frames, ignore_index=True)


def match_check(shots: pd.DataFrame) -> pd.DataFrame:
    """Commentary xG per team-match next to Understat's match xG (ESPN team names -> our names)."""
    tm = pd.read_parquet(HIST / "team_match.parquet", columns=["event_id", "team", "xg"]).dropna(subset=["event_id"])
    tm["event_id"] = tm.event_id.astype("int64").astype(str)
    ref = pd.concat([pd.read_csv(ROOT / "data" / "reference" / f) for f in ("teams.csv", "teams_promoted_2627.csv")])
    names = dict(zip(ref.espn, ref.team))
    agg = shots.assign(team=shots.team.map(names).fillna(shots.team)).groupby(["event_id", "team"]).cxg.sum()
    return tm.join(agg, on=["event_id", "team"]).dropna(subset=["cxg"])


def main() -> None:
    shots = league_shots()
    train, test = shots[shots.season == shots.season.min()], shots[shots.season > shots.season.min()]
    open_train = train[~train.penalty]
    clf = LogisticRegression(max_iter=2000, C=1.0).fit(design(open_train), open_train.goal)
    model = {"clf": clf, "columns": list(design(open_train).columns), "penalty_xg": PENALTY_XG}
    # Put the totals on Understat's scale (the xG the app shows for league matches), fitted on 2025/26 only.
    raw = train.assign(cxg=predict(model, train))
    fit = match_check(raw)
    model["scale"] = float(fit.xg.sum() / fit.cxg.sum())
    MODEL.parent.mkdir(exist_ok=True)
    joblib.dump(model, MODEL)

    shots["cxg"] = predict(model, shots)
    t = shots[shots.season > shots.season.min()]
    auc, brier = roc_auc_score(t.goal, t.cxg), brier_score_loss(t.goal, t.cxg)
    chk = match_check(t)
    r = chk[["xg", "cxg"]].corr().iloc[0, 1]
    mae = (chk.xg - chk.cxg).abs().mean()
    totals = (t.cxg.sum(), t.goal.sum())

    # Champions League: every cached summary from our UCL seasons
    ucl = pd.concat([pd.read_csv(p).assign(season=int(p.parent.name)) for p in (ROOT / "data" / "raw" / "ucl").glob("*/ucl_stats.csv")])
    us = load_shots("uefa.champions", sorted(ucl.event_id.unique()))
    us["cxg"] = predict(model, us)
    # Attach each shot to the ESPN team of its side (home/away) in that match.
    ev = ucl.drop_duplicates("event_id").set_index(ucl.drop_duplicates("event_id").event_id.astype(str))
    parts = []
    for e, g in us.groupby("event_id"):
        if e not in ev.index:
            continue
        side = side_of(g, ev.at[e, "espn_home"], ev.at[e, "espn_away"])
        parts.append(g.assign(side=side, espn_team=np.where(side == "home", ev.at[e, "espn_home"], ev.at[e, "espn_away"])))
    us = pd.concat(parts, ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    us.to_parquet(OUT / "ucl_shots.parquet", index=False)
    us.groupby(["event_id", "espn_team"]).agg(cxg=("cxg", "sum"), shots=("cxg", "size"),
                                               goals=("goal", "sum")).reset_index().to_csv(OUT / "ucl_xg.csv", index=False)
    coefs = pd.Series(clf.coef_[0], index=model["columns"]).sort_values()
    REPORT.write_text("\n".join([
        "# Commentary xG (for Champions League matches)", "",
        f"Trained on {len(open_train):,} non-penalty 2025/26 league shots parsed from ESPN commentary; tested on "
        f"{len(t):,} 2026/27 league shots. Penalties use {PENALTY_XG}. Non-penalty probabilities are multiplied by "
        f"{model['scale']:.3f}, fitted on 2025/26 so team totals match Understat's scale.", "",
        "| Test (2026/27 league) | Value |", "|---|---|",
        f"| Shot-level ROC AUC | {auc:.3f} |", f"| Brier score | {brier:.4f} |",
        f"| Total xG vs goals | {totals[0]:.0f} vs {int(totals[1])} |",
        f"| Team-match correlation with Understat xG | r = {r:.3f} (n = {len(chk):,}) |",
        f"| Mean absolute difference per team-match | {mae:.2f} xG |", "",
        "Features: shot zone, body part, assist type and situation, all from the text before the outcome.", "",
        "## Coefficients (log-odds)", "", coefs.round(2).to_frame("coef").to_markdown(), "",
        f"Applied to {us.event_id.nunique()} Champions League matches ({len(us):,} shots).", ""]), encoding="utf-8")
    print(f"AUC {auc:.3f}, Brier {brier:.4f}, match r vs Understat {r:.3f}, MAE {mae:.2f}; "
          f"UCL: {us.event_id.nunique()} matches, {len(us):,} shots")


if __name__ == "__main__":
    main()
