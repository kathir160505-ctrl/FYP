# Attacking Philosophies: Europe's Top Three Leagues (2025/26)

Final Year Project, Bachelor of Operations Research with Data Science.
*Unsupervised Machine Learning for Tactical Profiling: Clustering Attacking Philosophies in the Top 3 European Football Leagues.*

The project groups all 60 Premier League, La Liga and Serie A clubs by **how they attack**, then presents the results in an interactive Streamlit dashboard:

- **Style Map:** every club on one PCA map, with the four discovered attacking philosophies and the statistically unique clubs.
- **Club Profile:** for each club, a percentile radar, a matchweek timeline, a shot map, attack-speed breakdowns, first-half vs second-half comparison and similar clubs across leagues.
- **Head-to-Head:** compares two clubs and estimates which will show the more attacking style. This is not a result prediction.
- **League Comparison:** the style mix per league, with a chi-square and permutation test.
- **Methodology:** sources, features, PCA, model selection, validation and limitations.

## Run the dashboard

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

All data the app needs is precomputed in `data/processed/` and `models/`.

## Reproduce the pipeline

```bash
pip install -r requirements-dev.txt
cd src/collect && python understat.py && python espn.py && python fbref.py && python check_coverage.py && cd ../..
python -m src.process.build_dataset      # merged tables -> data/processed/
python -m src.process.team_meta          # club colours and crests
python -m src.process.crosscheck         # agreement with FBref
python -m src.model.eda                  # Phase 3 report and figures
python -m src.model.clustering           # Phase 4 model, report and figures
python -m src.predict.model              # Phase 5 model and report
python -m pytest tests
```

Reports are in `reports/` (`phase0_data_audit.md` to `phase5_prediction.md`), and figures are in `reports/figures/`.

## Method in one paragraph

1. **Data:** Understat (xG, shots with locations, deep completions, attack speed) and ESPN (possession, passing, crosses, long balls) for all 1,140 matches. FBref is used as an independent cross-check (r ≥ 0.977).
2. **Features:** 13 attacking features per club.
3. **Reduction:** z-score scaling, then PCA. Four components are kept (eigenvalue > 1), explaining 87.4% of variance.
4. **Clustering:** K-means with k = 4, chosen against Ward hierarchical clustering and DBSCAN using silhouette, Davies–Bouldin, Calinski–Harabasz, the elbow and bootstrap stability.
5. **Validation:** bootstrap stability, split-half validation (80% of clubs keep their cluster) and face validity.
6. **Prediction:** a logistic regression on pre-match form estimates which team shows the more attacking style (AUC 0.805 on held-out matches).

## Data attribution

Match and shot data: [Understat](https://understat.com), [ESPN](https://www.espn.com), [FBref](https://fbref.com). Club crests are served by ESPN. Used for non-commercial academic research.
