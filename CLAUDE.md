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
- **B. REMOVED (2026-10-31): Champions League.** Built, then removed at the user's request so the app follows the proposal (three leagues only). Collector, build, commentary-xG model, UCL tabs and charts are deleted. Matchday, last-5 form and line-ups are league-only.
- **C. DONE (2026-10-28): players, line-ups, probable XI, trophy cabinet.**
  - Collect with `python -m src.collect.players` (`--current` refreshes only this season). FBref is slow, about 1–3 minutes per page.
  - Build with `python -m src.process.build_players`. Output goes to `data/processed/players/{players.csv, lineups.parquet, probable_xi.csv}`. Both are part of `src.refresh`.
  - Base: Understat player-club-seasons. FBref and ESPN are matched by club and normalised name (`norm` folds Ø/ß/æ etc.; fuzzy match ≥ 0.8 and unambiguous): 96% / 98%.
  - Line-ups are parsed from the cached ESPN summaries (`rosters`: formation, formationPlace, position abbreviations, subs).
  - Probable XI: the most used formation in the last 5 league matches, then the most frequent recency-weighted starter per slot.
  - Pitch layout: formation lines plus ESPN position codes (`charts.POSITION_XY`).
  - Photos: ESPN headshots are 404, so photos come from Wikidata P18 (Commons, `?width=240`).
    - First matched by club (P54) and name, then by exact name and birth year.
    - Coverage is 59% of all players, 71% of regulars. Otherwise an initials avatar (`data.avatar`).
  - App:
    - a Players page (card, percentile wedges, similar players, match log, leaders);
    - a Clubs "Squad & line-ups" tab (probable XI vs the next ESPN fixture, any match's line-up, squad table);
    - a drawn SVG trophy cabinet (`app/cabinet.py`) on Honours. It's drawn, not photographed, because of image rights.
  - Promoted clubs' crests come from `data/live/team_meta.csv` (merged into `data.history()`).
- **Match centre (2026-10-28):** a hidden page `match?event=<ESPN id>&code=<league code>`, opened by clicking a Matchday fixture row (`a.fx`).
  - Data layer is `app/matchcentre.py`, using the live ESPN summary (cached 10 minutes).
  - Past matches:
    - both XIs on one pitch (`charts.match_pitch`) with ⚽/👟/🟨/🟥/▼ badges from roster stats;
    - key events (scorer plus assister);
    - ESPN stat bars;
    - Understat xG race when the event is in `team_match.parquet`.
  - Upcoming matches: confirmed ESPN line-ups if published, else the probable XI; attacking edge plus theme reasons; form chips; season table.
  - Highlights are played when `YOUTUBE_API_KEY` is in `.streamlit/secrets.toml` (gitignored; see `secrets.example.toml`). The YouTube search must name both clubs plus "highlight". Without a key, a YouTube search link is shown, plus ESPN clip links.
  - Similar kit colours: the away side switches to its ESPN alternate colour.
  - Redesign (user feedback: emoji looked "AI", not professional):
    - Line-ups, subs, stats and the timeline are now plain HTML/CSS in `app/pitch.py`, with SVG icons from `app/icons.py` (no emoji).
    - Subs show as one row per team (green arrow plus minute). Stats are rows: value | label | value plus a split bar.
    - The timeline has home events on the left and away on the right, with running-score badges and HT/FT dividers.
  - The YouTube key is configured (the user's own key, in the gitignored `secrets.toml`). Official broadcaster channels are preferred (`OFFICIAL_CHANNELS`).
  - **Quota gotcha (2026-10-31):** each search costs 100 of the 10,000 daily units, and AppTest runs with empty caches used up the quota, so the app showed only a search link.
    - Lookups are now cached on disk in `data/cache/highlights.json` (gitignored). A found video is never searched again; a match with no video yet is retried at most every 6 h, and only for 7 days.
    - `{"quota": True}` triggers a note.
    - Don't run many match-centre AppTests with the key active.
  - News: the ESPN match `article` plus summary `news` filtered to stories that mention either club.
  - Team news: ESPN soccer injury fields are empty, and FotMob/Transfermarkt are off-limits, so no injury list. Instead:
    - "went off injured" comes from substitution text, and "suspended" from a red card in the previous match;
    - "not in squad" = players with at least 3 apps this season who are missing from the sheet (the reason is unknown, and the page says so).
- **Real time (2026-10-28):**
  - Scoreboards and match summaries are cached for 30 s.
  - Matchday's board is an `st.fragment` with `run_every=60`.
  - The match centre body is a fragment with `run_every=30` while live or within 1 hour of kick-off.
  - "Last 5" uses `live.recent_results(team)`: ESPN `/all/teams/{id}/schedule` across all competitions (friendlies excluded), with team ids from `live.team_ids()`. Used by match-centre form chips and Head-to-head.
  - Not yet seen running during a live game.
- **Completeness pass (2026-10-28):**
  - Every `st.dataframe` uses `placeholder="–"`, so no "None" appears in tables.
  - Commentary xG model: removed with the UCL (2026-10-31).
  - Photos: `src.collect.photos` (Wikipedia lead images with `pilicense=free`, plus Wikidata name search filtered by footballer and birth year) → `photos_extra.csv` → fallback in `build_players`.
  - Line-up players (match centre pitch, benches, Clubs tab) link to `players?season&club&player` via `data.player_links()`. The Clubs line-ups now use `pitch.team_pitch` (HTML).
  - **Injury lists: REMOVED (2026-10-31)** at the user's request. They conflicted with the proposal's ethics statement (3.13: no health information published).
    - Removed: `app/injuries.py`, the FPL and API-Football sources, "went off injured" notes and the injury icons.
    - Team news now shows only "not in squad" (no reason) and "sent off" (suspension).
    - `data.probable_lineup(team)` still exists; it gets no injury input.
  - `matchcentre.names_in` now matches whole words only. "ham" (West Ham) used to match "Southampton", which affected injury mapping and highlight matching. Exact accent-folded names win first (`Atletico Madrid` → `Atlético Madrid`).
- **Proposal alignment (2026-10-31):**
  - The Methodology page lists the proposal's 12 research-process stages (FYP1 Figure 3.1), each with what we did.
  - It also has a Face validity panel; see `reports/phase4_face_validity.md`. Average finish by style: 3.9 / 7.7 / 12.7 / 16.9.
- **Extensions switch (2026-10-31): ON by default.** The user was upset when thesis mode hid Players, Matchday, line-ups and highlights. They had only asked to remove the UCL. **Never hide or remove features unless explicitly asked.**
  - `data.EXTENSIONS` reads `SHOW_EXTENSIONS` (secrets.toml or env). It is on unless it is set to false.
  - False leaves only the five proposal pages (Overview, Clubs, Head-to-head, Leagues, Methodology) with 2025/26 data, as an option for formal presentations.
  - Head-to-head's last five shows 2025/26 matches in thesis mode and live ESPN results with extensions.
  - Don't add new features without being asked: the user worries about out-of-scope questions, but wants the existing ones kept.
  - Methodology "From raw data to results" panel: the data at each step (match rows → 60×13 features → z-scores → PCA scores + cluster) with downloads. Re-predicting with the saved pipeline matches the stored clusters 100%.
  - Reproducibility checked 2026-10-31: re-running build_dataset, eda, clustering and predict reproduced every CSV, report, figure and model byte for byte. Only `fyp.sqlite` changes bytes, not content.
  - Handover: `FYP_Project_Handover.docx` (where it is, how to run it, the requirements table). The viva study guide is a Claude doc.
- **Gotcha:** CSS class names are global. My `.chip` (form chips) once overrode the Overview's `.chip` trait labels, so form chips are now `.fchip`.
- **D. DONE (2026-10-28): honours and managers.**
  - Collect with `python -m src.collect.legacy` (Wikidata SPARQL, batches of 12 clubs; the search API returns 429, so use SPARQL only). Build with `python -m src.process.build_legacy`, then check with `python -m src.process.check_legacy`. Output goes to `data/processed/legacy/`. Also part of `src.refresh`.
  - Club → QID mapping: `data/reference/clubs_wikidata.csv`.
  - Honours: competition QID → category map. Only season items and finals count, never single matches; one trophy per club, category and season.
  - Old First Division after 1992 and "Segunda/Serie B" labels count as second-tier titles.
  - Super cups are excluded (Wikidata has about 1/3 of them).
  - Hand fixes are in `data/reference/legacy_corrections.csv` (revoked titles, missing finals) and `manager_corrections.csv`.
  - Check: 95/95 published counts (league, domestic cup, European Cup, UEFA Cup) match up to 2024/25. See `reports/phaseD_legacy_check.md`.
  - Managers: Wikidata dates can be month- or year-precision. End dates are extended to the end of the period, then capped at today.
  - Matches go to the latest spell that started before them.
  - The build prints "check <club>" when a current-season club's latest match isn't credited to its current manager; fix that via `manager_corrections.csv`.
  - App: "Honours & managers" tab on Clubs, and a note on Methodology.
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
