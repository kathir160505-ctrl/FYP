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

## Phases 1–2 done (2026-10-23)
- **Collect:** run `cd src/collect; python understat.py; python espn.py; python fbref.py; python check_coverage.py`. Raw data goes to `data/raw/`, which is gitignored. ESPN takes about 25 minutes uncached.
- **Build:** run `python -m src.process.build_dataset` from the project root. This writes `data/processed/{team_match,team_season,team_half,shots}.csv` and `fyp.sqlite`.
- **Cross-check:** run `python -m src.process.crosscheck`. Output goes to `reports/phase2_crosscheck.md`; r ≥ 0.977 against FBref.
- **Feature definitions:** `src/process/features.py`, `CLUSTER_FEATURES` (13 features). Club names: `data/reference/teams.csv`.
- **Gotcha:** a stale `~/soccerdata/data/FBref/seasons_*.html` cache can map "2526" to FBref's current-season URL. `check_coverage.py` guards against this with an MP == 38 check.
- **Tests:** `python -m pytest tests`.
- **Gotcha:** soccerdata's Understat label maps miss the raw values "Head", "OtherBodyPart" and "Penalty", which would leave those shots with blank labels. `src/collect/understat.py` patches the maps before reading. Fixed 2026-10-28; shot counts and xG were never affected.
- **Excel export:** run `python -m src.process.export_excel`. It writes `data/FYP_dataset_2025-26.xlsx`, a README/data-dictionary sheet plus 5 data sheets.
## Phases 3–4 done (2026-10-23)
- **Run:** `python -m src.model.eda`, then `python -m src.model.clustering`. Reports are `reports/phase3_eda.md` and `reports/phase4_clustering.md`; figures are in `reports/figures/`.
- **Model:** StandardScaler → PCA with 4 components (Kaiser rule, 87.4% variance) → KMeans k = 4 (seed 42). Saved to `models/cluster_model.joblib`.
  - k = 2 has the best silhouette but is just "big clubs vs rest", so it is kept as `top_level`.
  - k = 4 is the most stable choice for k ≥ 3 (bootstrap ARI 0.64) and sits at the elbow.
- **Clusters:** Dominant Possession (12), Controlled Build-up (13), Direct & Cross-Oriented (26), Long-Ball Low Block (9). Names are assigned by PC1 rank and verified by `check_names()`.
- **DBSCAN:** a consensus over 24 settings. "Unique" clubs are Barcelona, Villarreal, Inter, Hellas Verona and Getafe.
- **Split-half:** 80% of clubs keep the same cluster.
- **League chi-square:** not significant (permutation p = 0.45, Cramér's V = 0.22). This is a real finding, so report it honestly.
- **App data:** `data/processed/{clusters,cluster_profiles,similar_clubs,model_selection}.csv`.
## Phases 5–6 done (2026-10-23)
- **Prediction:** `python -m src.predict.model`. Logistic regression gets AUC 0.805 on the held-out last 30% (CV 0.832; baseline 0.734). The app explains each prediction by grouping coefficient contributions into themes, because raw coefficients flip sign due to collinearity.
- **App:** run `streamlit run app/streamlit_app.py` (launch config "fyp-dashboard" in `.claude/launch.json`).
  - Structure: `app/data.py` (cached loaders and prediction), `app/charts.py` (Plotly), `app/ui.py` (CSS and cards), `app/views/*.py` (5 pages, via `st.navigation`).
  - Theme lives in `.streamlit/config.toml`.
- **Gotcha:** Streamlit does not hot-reload the modules imported from `app/`. Restart the server after editing `charts.py`, `data.py` or `views`.
- **Requirements:** `requirements.txt` is the lean app runtime, with scikit-learn pinned for the joblib models. `requirements-dev.txt` is the full pipeline.
## UI and Matchday (2026-10-28)
- **Workflow:** the user wants to build and test locally first; commit locally and push only when asked.
- **Theme:** white sports-media look in the style of ESPN, DAZN and OneFootball.
  - Light theme in `.streamlit/config.toml`; Barlow Condensed headings; one red accent (#D50000); no gradients.
  - Top navigation via `st.navigation(position="top")`.
- **Matchday page** (`app/views/matchday.py`, data layer `app/live.py`):
  - ESPN news and fixtures are fetched at view time and cached for 5–15 minutes. Times are shown in MYT (UTC+8).
  - Attacking-edge predictions use `data/live/team_form.csv`, which is current-season form.
- **Refresh current-season form:** run `python -m src.collect.live`. The first run takes about 10 minutes; later runs are incremental. Outputs go to `data/live/`.
  - Promoted clubs are mapped in `data/reference/teams_promoted_2627.csv`.
- **Dev preview:** launch config `fyp-dashboard-dev` uses port 8510, so it doesn't clash with the user's own server on 8501.

## Feature roadmap (agreed 2026-10-28; build one at a time, then deploy on Azure)
Data checks are done for all of these:
- Understat has seasons back to 2014/15.
- ESPN has UCL box stats (no xG) and historical league matches.
- Understat player attacking stats are available. FBref player misc gives defensive stats (Int, TklW); FBref keeper gives GK stats.
- Wikidata SPARQL gives managers with tenures (P286 + P580/P582) and honours (P1346 on season editions, which need de-duplication).

Phases:
- **A. DONE (2026-10-28): seasons 2025/26 and 2026/27 only.** The user does NOT want older seasons; by "history" they mean club honours (Phase D).
  - Collect with `python -m src.collect.history` (`FIRST_SEASON = "2526"`), then build with `python -m src.process.build_history`. Output goes to `data/processed/history/`.
  - Club names are matched automatically per season (by date + score).
  - Styles are projected with the unchanged 2025/26 model; 2025/26 reproduces the thesis data exactly.
  - App: season selector on Overview, a "2025/26 vs 2026/27" tab on Clubs, and the style mix per season on Leagues.
  - Weekly refresh of everything: `python -m src.refresh`.
- **B. Champions League.**
  - ESPN UCL fixtures, results and news in Matchday.
  - UCL match stats for the 60 clubs (no xG; documented).
- **C. Player profiles.**
  - All players of the three leagues: attacking (Understat) plus defensive and GK (FBref), per season.
  - Position-peer percentile radars and squad tables. Name matching between Understat and FBref is needed.
- **D. Manager and club legacy.**
  - Wikidata managers and honours (curated competition list).
  - Manager record and attacking style under each manager, computed from our match data.
- **E. Azure deployment.**
  - Dockerfile, then Azure Container Apps or App Service, plus a scheduled job for refreshes and storage for data.
  - Budget is about RM600/month.

The thesis core stays the 2025/26 analysis from the proposal; these are app extensions.

## Phase 7: deploy
- **GitHub repo (private):** https://github.com/NITIYAHSELVAN/fyp-attacking-philosophies, branch `main`. Pushed 2026-10-24.
- **GitHub CLI:** installed at `C:\Program Files\GitHub CLI\gh.exe` and logged in as NITIYAHSELVAN.
- **Streamlit Community Cloud settings:** main file `app/streamlit_app.py`, Python 3.13. The user deploys it on share.streamlit.io.
- **Verified:** a clean venv with only `requirements.txt` runs all 5 pages via Streamlit AppTest.

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
