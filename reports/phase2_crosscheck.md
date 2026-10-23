# Phase 2 cross-check: our features vs FBref

Clubs matched: 60 / 60

| Feature | Pearson r | Mean ours | Mean FBref | Mean abs diff | Max abs diff (club) |
|---|---|---|---|---|---|
| possession | 1.000 | 50.00 | 50.05 | 0.08 | 0.24 (Arsenal) |
| shots | 1.000 | 12.43 | 12.43 | 0.03 | 0.37 (Real Oviedo) |
| sot_pct | 0.990 | 32.72 | 33.58 | 0.86 | 1.97 (Inter) |
| goals | 0.997 | 1.31 | 1.27 | 0.04 | 0.11 (Arsenal) |
| goals_per_shot | 0.977 | 0.10 | 0.10 | 0.00 | 0.01 (Elche) |
| crosses | 0.999 | 17.58 | 17.48 | 0.11 | 0.47 (Barcelona) |

Different providers define shots, on-target shots and crosses slightly differently (Understat/ESPN vs Opta-era FBref), so small level differences are expected. High correlations confirm the clubs are ranked consistently.