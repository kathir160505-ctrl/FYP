# Commentary xG (for Champions League matches)

Trained on 27,466 non-penalty 2025/26 league shots parsed from ESPN commentary; tested on 7,144 2026/27 league shots. Penalties use 0.76. Non-penalty probabilities are multiplied by 1.176, fitted on 2025/26 so team totals match Understat's scale.

| Test (2026/27 league) | Value |
|---|---|
| Shot-level ROC AUC | 0.753 |
| Brier score | 0.0802 |
| Total xG vs goals | 821 vs 754 |
| Team-match correlation with Understat xG | r = 0.843 (n = 458) |
| Mean absolute difference per team-match | 0.40 xG |

Features: shot zone, body part, assist type and situation, all from the text before the outcome.

## Coefficients (log-odds)

|                      |   coef |
|:---------------------|-------:|
| situation_free_kick  |  -1.86 |
| zone_long_range      |  -1.38 |
| zone_outside         |  -1.3  |
| zone_box_side        |  -1.09 |
| body_head            |  -0.96 |
| zone_long_angle      |  -0.8  |
| assist_cross         |  -0.67 |
| zone_angle           |  -0.63 |
| situation_open_play  |  -0.55 |
| assist_none          |  -0.34 |
| assist_headed_pass   |  -0.32 |
| body_foot            |  -0.25 |
| assist_pass          |  -0.19 |
| zone_box_centre      |   0.2  |
| situation_set_piece  |   0.21 |
| situation_corner     |   0.25 |
| zone_six_yard        |   0.3  |
| body_other           |   0.39 |
| assist_through_ball  |   0.71 |
| situation_fast_break |   1.14 |
| zone_very_close      |   1.78 |
| zone_unknown         |   2.12 |

Applied to 243 Champions League matches (6,623 shots).
