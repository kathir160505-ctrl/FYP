# Phase 3: Exploratory data analysis

Clubs: 60 (20 per league). Features: 13.

## Descriptive statistics

|                   |    mean |    std |     min |     max |   skew |   shapiro_p |
|:------------------|--------:|-------:|--------:|--------:|-------:|------------:|
| possession        |  50     |  6.236 |  40.134 |  68.839 |  0.569 |       0.089 |
| pass_accuracy     |  82.404 |  3.84  |  69.08  |  89.984 | -0.52  |       0.113 |
| passes_completed  | 361.211 | 76.995 | 198.368 | 587.263 |  0.624 |       0.07  |
| deep_completions  |   6.233 |  2.156 |   2.816 |  11.763 |  0.773 |       0.007 |
| long_ball_share   |  12.006 |  3.094 |   5.492 |  22.846 |  0.506 |       0.071 |
| crosses           |  17.577 |  2.586 |  11.395 |  24.237 |  0.085 |       0.689 |
| shots             |  12.427 |  2.089 |   9.105 |  18.211 |  0.776 |       0.022 |
| sot_pct           |  32.715 |  3.053 |  25.201 |  39.164 | -0.507 |       0.172 |
| xg                |   1.475 |  0.36  |   0.894 |   2.623 |  0.737 |       0.051 |
| goals             |   1.312 |  0.384 |   0.658 |   2.5   |  0.77  |       0.015 |
| goals_per_shot    |   0.104 |  0.019 |   0.059 |   0.156 |  0.016 |       0.788 |
| fast_attack_shots |   0.718 |  0.205 |   0.316 |   1.368 |  0.674 |       0.059 |
| box_shot_share    |  63.132 |  4.712 |  53.465 |  73.645 |  0.227 |       0.513 |

## League means (context only; league is not a clustering feature)

| feature           |   Premier League |   La Liga |   Serie A |   anova_p |   kruskal_p |
|:------------------|-----------------:|----------:|----------:|----------:|------------:|
| possession        |           50     |    50     |    50     |     1     |       0.995 |
| pass_accuracy     |           82.089 |    82.503 |    82.619 |     0.903 |       0.642 |
| passes_completed  |          360.468 |   363.922 |   359.241 |     0.981 |       0.942 |
| deep_completions  |            6.791 |     6.097 |     5.811 |     0.341 |       0.082 |
| long_ball_share   |           11.694 |    12.353 |    11.969 |     0.801 |       0.876 |
| crosses           |           18.062 |    17.628 |    17.042 |     0.464 |       0.442 |
| shots             |           12.478 |    12.5   |    12.304 |     0.95  |       0.904 |
| sot_pct           |           32.433 |    33.844 |    31.869 |     0.107 |       0.186 |
| xg                |            1.529 |     1.501 |     1.395 |     0.471 |       0.339 |
| goals             |            1.375 |     1.347 |     1.213 |     0.368 |       0.23  |
| goals_per_shot    |            0.109 |     0.107 |     0.097 |     0.082 |       0.068 |
| fast_attack_shots |            0.712 |     0.737 |     0.704 |     0.873 |       0.974 |
| box_shot_share    |           65.052 |    62.664 |    61.68  |     0.064 |       0.069 |

Possession averages exactly 50% in every league by construction (it is zero-sum within a league), and most volume features are close to that: league averages barely differ. Differences in *style* therefore have to show up in how clubs are spread within each league, which is what the cluster-by-league analysis (Phase 4) tests.

## Strong correlations (|r| >= 0.7)

- pass_accuracy ~ long_ball_share: r = -0.96
- pass_accuracy ~ passes_completed: r = 0.94
- passes_completed ~ long_ball_share: r = -0.94
- possession ~ passes_completed: r = 0.94
- xg ~ goals: r = 0.91
- shots ~ xg: r = 0.89
- deep_completions ~ xg: r = 0.89
- deep_completions ~ goals: r = 0.87
- possession ~ pass_accuracy: r = 0.86
- possession ~ long_ball_share: r = -0.85
- deep_completions ~ shots: r = 0.84
- shots ~ goals: r = 0.83
- goals ~ goals_per_shot: r = 0.82
- passes_completed ~ deep_completions: r = 0.82
- passes_completed ~ goals: r = 0.80
- possession ~ shots: r = 0.79
- possession ~ goals: r = 0.78
- possession ~ deep_completions: r = 0.78
- deep_completions ~ long_ball_share: r = -0.78
- passes_completed ~ xg: r = 0.77
- passes_completed ~ shots: r = 0.76
- possession ~ xg: r = 0.76
- long_ball_share ~ goals: r = -0.75
- pass_accuracy ~ deep_completions: r = 0.72
- long_ball_share ~ xg: r = -0.72
- pass_accuracy ~ goals: r = 0.71
- long_ball_share ~ shots: r = -0.70

27 of 78 feature pairs have |r| >= 0.7, confirming the multicollinearity that motivates PCA before clustering (Gu et al., 2025).

## Outliers (|z| > 3)

- Barcelona: possession (z = 3.02)
- Barcelona: xg (z = 3.19)
- Barcelona: goals (z = 3.09)
- Getafe: pass_accuracy (z = -3.47)
- Getafe: long_ball_share (z = 3.50)
- Rayo Vallecano: fast_attack_shots (z = 3.17)

Outliers are kept: they are real clubs, and identifying statistically unique clubs is an explicit aim of the DBSCAN stage.

## Figures

- `figures/eda_distributions.png`
- `figures/eda_correlation.png`
- `figures/eda_league_boxplots.png`