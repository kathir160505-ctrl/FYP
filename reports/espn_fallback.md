# ESPN fallback for Understat

Used only for league matches Understat has not published (understat.com has been down since about 3 Nov 2026). Every estimate is trained on 2025/26 and tested on the 2026/27 matches Understat did publish (262 matches, 524 team-matches, 7,144 shots).

| Test (2026/27 league matches) | Value |
|---|---|
| Shot-level ROC AUC (open play) | 0.751 |
| Shot-level Brier score | 0.0796 |
| xG per team-match: correlation with Understat | r = 0.861 |
| xG per team-match: mean absolute difference | 0.39 |
| Shots per team-match: correlation with Understat | r = 0.988 |
| Box shots per team-match: correlation with Understat | r = 0.988 |
| Deep completions per team-match: correlation | r = 0.677 |
| Deep completions per team-match: mean absolute difference | 2.50 |
| PPDA per team-match: correlation | r = 0.772 |
| Fast-attack shots per club-season: correlation | r = 0.552 |

xG scale factor 1.181; fast-break scale factor 1.77 (Understat counts more attacks as 'Fast' than ESPN's commentary calls fast breaks).

## Club-season level: the 13 clustering features and the style

Each 2026/27 club is described twice, once with Understat's numbers and once with every match estimated from ESPN, then both are classified with the unchanged 2025/26 model.

| Feature | r (Understat vs ESPN estimate) |
|---|---|
| possession | 0.997 |
| pass_accuracy | 0.998 |
| passes_completed | 0.999 |
| deep_completions | 0.841 |
| long_ball_share | 0.999 |
| crosses | 0.993 |
| shots | 0.993 |
| sot_pct | 0.982 |
| xg | 0.954 |
| goals | 0.992 |
| goals_per_shot | 0.984 |
| fast_attack_shots | 0.535 |
| box_shot_share | 0.990 |

**Same style for 90% of the 60 clubs** (54 of 60), using the estimates for every match. In the app only matches after Understat's last update are estimated, so the share of estimated data is smaller.
