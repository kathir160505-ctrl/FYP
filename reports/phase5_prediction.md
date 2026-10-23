# Phase 5: Predicting the more attacking team

**Target.** For each match, the *Attacking Index* of each team is the mean within-league z-score of xg, shots, deep_completions, box_shots, possessionPct. The label is whether team A's index exceeds team B's. This predicts relative attacking *style* in a match, not the winner or the score.

**Features.** Pre-match only: each team's season-to-date and last-5 averages of 11 stats, expressed as A − B differences, plus venue (23 features). Matches where either team has fewer than 5 previous matches are excluded. Each match appears from both perspectives.

**Evaluation.** Temporal hold-out: trained on matches before 2026-03-14, tested on the rest (692 train / 297 test matches). Also 5-fold cross-validation grouped by match, so a match's two rows never sit on both sides of a split.

| model                                  |   AUC |   Accuracy |   Brier |   Log loss |   CV AUC (5-fold, grouped) |   CV AUC sd |
|:---------------------------------------|------:|-----------:|--------:|-----------:|---------------------------:|------------:|
| Baseline (higher season-to-date index) | 0.734 |      0.653 |   0.219 |      0.624 |                    nan     |     nan     |
| Logistic regression                    | 0.805 |      0.731 |   0.184 |      0.542 |                      0.832 |       0.044 |
| Gradient boosting                      | 0.796 |      0.727 |   0.188 |      0.559 |                      0.829 |       0.039 |

The logistic regression reaches **AUC 0.805** and **73.1% accuracy** on the held-out final 30% of the season. It is kept as the final model: it performs at least as well as gradient boosting and its coefficients explain each prediction in the app. Zhong et al. (2026) report AUC 0.70–0.78 for their related cluster-to-outcome models.

## Largest standardised coefficients (final model, all matches)

|                              |   coefficient |
|:-----------------------------|--------------:|
| is_home                      |         0.735 |
| long_ball_share_season_diff  |        -0.72  |
| possessionPct_season_diff    |         0.556 |
| pass_accuracy_season_diff    |        -0.526 |
| long_ball_share_form_diff    |         0.515 |
| possessionPct_form_diff      |         0.47  |
| index_conceded_form_diff     |         0.328 |
| totalCrosses_season_diff     |        -0.302 |
| pass_accuracy_form_diff      |         0.297 |
| deep_completions_season_diff |         0.29  |

## Figures

- `figures/predict_calibration.png`