# FYP: Clustering attacking philosophies (EPL, La Liga, Serie A, 2025/26)

Source proposal: `C:\Users\I-AM-VENGEANCE\Desktop\fyp1_2240310.pdf` (FYP1 research proposal, NDUM, Bachelor of Operations Research with Data Science).

## What the system must deliver
- **RO1**: Collect and pre-process team-level attacking stats for all ~60 clubs (EPL, La Liga, Serie A, season 2025/26), per-90 normalised.
- **RO2**: StandardScaler, then PCA, then compare KMeans / Agglomerative / DBSCAN. Pick k with elbow plus silhouette; also report Davies-Bouldin and Calinski-Harabasz, plus PCA explained variance. Profile and label the clusters from the evidence. Cross-tab cluster by league, then chi-square.
- **Validation**: unit tests, fixed seeds, bootstrap stability, split-half (first half vs second half of the season), face validity.
- **RO3**: Web dashboard: team attacking profile, two-team comparison, and a prediction of "which team is more attacking". This is NOT a match winner or score prediction. Use logistic regression or gradient boosting on match-level data. Add disclaimers: data-driven abstraction, probabilistic, not for gambling.

## App vision (user's main goal)
The user wants a polished, professional-quality Streamlit app. It extends their earlier single-club soccerdata+Streamlit project (Man Utd season analytics) to all 60 clubs. Pages:
1. **Overview / Style Map**
   - PCA scatter of the 60 clubs, coloured by cluster, with a league filter.
   - Cluster "philosophy cards" with evidence-based labels.
2. **Club Profile** (the core page)
   - Identity card: cluster label and a percentile radar against all 60 clubs.
   - Matchweek timelines: rolling xG, possession, shots.
   - First half vs second half of the season.
   - Attack-speed and situation breakdowns.
   - Shot map on a pitch (Understat x/y).
   - Most similar clubs across leagues (scouting use).
3. **Head-to-Head**
   - Overlaid radars, stat bars, the two clusters and recent form.
   - "More attacking" prediction with probability and reasons. This is NOT a winner or score prediction.
4. **League Comparison**: cluster share per league, chi-square result, league averages.
5. **Methodology**: sources, proxies, validity metrics, disclaimers.

Style: dark professional theme, Plotly, custom CSS, consistent club colours.

## Phase 0 result (done 2026-10-23, see reports/phase0_data_audit.md)
- **Primary sources:**
  - **Understat** (soccerdata): match xG, goals, deep completions, shots with x/y. Team pages via `/getTeamData/{team}/{season}` give the `attackSpeed` and `shotZone` breakdowns.
  - **ESPN public API** (`site.api.espn.com/.../summary?event=`): match possession, passes, crosses, long balls, shots on target. soccerdata's `ESPN.read_matchsheet` is broken (`KeyError: 'form'`), so call the API directly.
- **FBref:** cross-check only. Just the standard, shooting and misc tables remain.
- **Not usable:** Sofascore (403, do not bypass), StatsBomb (no 2025/26 data), WhoScored and FotMob (anti-bot protection or terms of service).
- **Proxies:** progressive passes → deep completions + long-ball share; counter attacks → Understat "Fast" attack shots/xG; box touches → share of shots inside the penalty area; Ball Control → pass accuracy %.
- **Dropped:** through balls, unless a Kaggle 2025/26 dataset turns up.
- **Python env:** `.venv` uses Python 3.13 (not 3.12).

## Original feature set (Table 3.1), with candidate sources from before the audit
| Feature | Candidate source |
|---|---|
| Possession % | FBref / FotMob / Sofascore |
| Ball Control (undefined in proposal: define it, or drop it) | touches per 90 or pass completion % |
| Passes per match | FBref / FotMob / Sofascore |
| Progressive passes | FBref (check that it still exists after the Opta change); else a proxy such as final-third passes |
| Through balls | Sofascore / WhoScored / FotMob (verify) |
| Crosses | FBref / Sofascore / FotMob |
| Shots, Shots on target % | Understat / FBref |
| xG | Understat (free, covers all 3 leagues) |
| Goals, Goals per shot | any |
| Counter attacks | Sofascore "fast breaks" or Understat attack-speed "Fast" (verify) |
| Touches in penalty area | FBref / FotMob |

League and Season are grouping variables only. They are never used as clustering features.

## Known risks
- StatsBomb Open Data does NOT cover the 2025/26 domestic leagues, so statsbombpy cannot be the main source.
- FBref reportedly lost its Opta advanced stats in early 2026. Check which columns still exist.
- Opta Analyst has no API. Use it only for manual cross-checks, and respect its terms of service.
- n is about 60 teams, which is small. DBSCAN is fragile at this size, so treat it as outlier detection.
- Split-half validation and the prediction model both need **match-level** team stats, not only season totals.

## Plan
0. Data audit: confirm which source provides each feature for 2025/26. Freeze the feature list.
1. `src/collect/`: soccerdata scrapers. Cache the raw data to `data/raw/` and log the source versions.
2. `src/process/`: name harmonisation, merge, per-90 conversion, missing values, then `data/processed/*.csv` + SQLite.
3. `notebooks/`: EDA and correlations.
4. `src/model/`: scaling, PCA, clustering comparison, validity indices, profiling and labels, chi-square, stability tests.
5. `src/predict/`: match-level "more attacking" label from a composite attacking index. Features are the teams' pre-match rolling stats. Train with LogReg / GBM and report AUC.
6. `app/`: Streamlit dashboard (Plotly charts). It reads only precomputed artefacts and never scrapes at runtime.
7. `tests/`: pytest for the processing functions.
8. Deploy: GitHub repo, then Streamlit Community Cloud (free).

## Environment notes
- System Python is 3.14. Prefer a Python 3.12 venv (`.venv`) for library compatibility.
- The home folder `C:\Users\I-AM-VENGEANCE` is itself a git repo. Run `git init` inside `FYP` so the project has its own repo.
- `~/soccerdata/data/FBref` already holds cached **2024/25** EPL pages from an earlier run. These are the wrong season, so use them for testing only.
