# Phase 4: Clustering attacking styles

## 1. Dimensionality reduction (PCA)

Features were z-scored and reduced by PCA. **4 components** have eigenvalue > 1 (Kaiser criterion) and together explain **87.4%** of the variance (PC1 58.0%, PC2 11.8%, PC3 9.8%, PC4 7.8%).

|                   |   PC1 |   PC2 |   PC3 |   PC4 |
|:------------------|------:|------:|------:|------:|
| possession        |  0.33 |  0.11 | -0.09 | -0.26 |
| pass_accuracy     |  0.32 | -0.06 | -0.23 | -0.28 |
| passes_completed  |  0.34 | -0.02 | -0.15 | -0.25 |
| deep_completions  |  0.33 |  0.11 |  0.14 |  0.03 |
| long_ball_share   | -0.33 |  0.06 |  0.17 |  0.26 |
| crosses           |  0    |  0.55 |  0.49 | -0.2  |
| shots             |  0.31 |  0.36 | -0.03 |  0.09 |
| sot_pct           |  0.17 | -0.48 | -0.02 |  0.13 |
| xg                |  0.33 |  0.14 |  0.13 |  0.21 |
| goals             |  0.34 | -0.03 |  0.11 |  0.15 |
| goals_per_shot    |  0.26 | -0.41 |  0.21 |  0.18 |
| fast_attack_shots |  0.14 |  0.26 | -0.28 |  0.74 |
| box_shot_share    |  0.12 | -0.22 |  0.69 |  0.08 |

- **PC1, attacking dominance:** possession, passing volume and accuracy, deep completions, shots, xG and goals, against long balls.
- **PC2, crossing volume vs finishing efficiency:** crosses and shots against shots on target % and goals per shot.
- **PC3, box presence:** share of shots inside the penalty area and crosses.
- **PC4, counter-attack:** fast-attack shots.

## 2. Model selection

KMeans and Ward agglomerative clustering were compared for k = 2–8 on the retained components. KMeans stability is the mean adjusted Rand index (ARI) over 200 bootstrap resamples.

| algorithm            |   k |   silhouette |   davies_bouldin |   calinski_harabasz |   inertia |   min_cluster_size |   bootstrap_ari |
|:---------------------|----:|-------------:|-----------------:|--------------------:|----------:|-------------------:|----------------:|
| KMeans               |   2 |        0.361 |            1.03  |              43.705 |   388.8   |                 23 |           0.836 |
| Agglomerative (Ward) |   2 |        0.335 |            1.108 |              39.045 |   nan     |                 27 |         nan     |
| KMeans               |   3 |        0.268 |            1.259 |              32.615 |   317.935 |                 10 |           0.548 |
| Agglomerative (Ward) |   3 |        0.296 |            1.109 |              29.551 |   nan     |                  4 |         nan     |
| KMeans               |   4 |        0.257 |            1.238 |              30.015 |   261.424 |                  9 |           0.635 |
| Agglomerative (Ward) |   4 |        0.215 |            1.229 |              26.957 |   nan     |                  4 |         nan     |
| KMeans               |   5 |        0.264 |            1.203 |              28.062 |   224.201 |                  4 |           0.588 |
| Agglomerative (Ward) |   5 |        0.237 |            1.228 |              26.084 |   nan     |                  4 |         nan     |
| KMeans               |   6 |        0.264 |            1.113 |              26.249 |   198.74  |                  3 |           0.556 |
| Agglomerative (Ward) |   6 |        0.235 |            1.217 |              24.728 |   nan     |                  4 |         nan     |
| KMeans               |   7 |        0.212 |            1.166 |              25.014 |   177.928 |                  4 |           0.464 |
| Agglomerative (Ward) |   7 |        0.22  |            1.163 |              24.199 |   nan     |                  4 |         nan     |
| KMeans               |   8 |        0.234 |            1.093 |              24.675 |   157.758 |                  3 |           0.529 |
| Agglomerative (Ward) |   8 |        0.23  |            1.147 |              24.297 |   nan     |                  4 |         nan     |

**Chosen: KMeans, k = 4.** Silhouette is highest at k = 2. That solution only separates possession-dominant clubs from the rest, so it is kept as a top-level split (`top_level` in clusters.csv). Among k ≥ 3, k = 4 has the highest bootstrap stability, sits at the elbow of the within-cluster sum of squares, and gives interpretable, reasonably balanced groups within the 3–6 range expected in H2. Final indices: silhouette 0.257, Davies–Bouldin 1.238, Calinski–Harabasz 30.0, bootstrap ARI 0.64. Agreement with Ward clustering at the same k: ARI = 0.53.

Silhouette values of 0.25–0.40 indicate moderate, overlapping structure. This is typical for team-level style data, where styles sit on a continuum rather than in sharply separated groups (Gu et al., 2025).

## 3. Cluster profiles

### Dominant Possession (12 clubs)

Monopolise the ball and the opposition half: the most passes, deep completions, shots and xG, with the fewest long balls.

- Highest features: shots (+1.5 SD), xg (+1.5 SD), deep_completions (+1.4 SD)
- Lowest features: long_ball_share (-1.2 SD), crosses (+0.0 SD), sot_pct (+0.2 SD)
- Clubs: Barcelona, Inter, Real Madrid, Manchester City, Juventus, Como, Arsenal, Liverpool, Chelsea, Manchester United, Atalanta, Real Betis

### Controlled Build-up (13 clubs)

Patient, accurate passing that rarely goes long or wide: few crosses, but the highest share of shots on target and strong finishing efficiency.

- Highest features: sot_pct (+1.0 SD), pass_accuracy (+0.7 SD), goals_per_shot (+0.7 SD)
- Lowest features: long_ball_share (-0.7 SD), crosses (-0.7 SD), fast_attack_shots (-0.4 SD)
- Clubs: Atlético Madrid, Napoli, Roma, Villarreal, AC Milan, Aston Villa, Celta Vigo, Brighton, Real Sociedad, Elche, Lazio, Girona, Sassuolo

### Direct & Cross-Oriented (26 clubs)

Below-average possession, with more long balls and crosses: attacks reach the box quickly and from wide areas rather than through sustained build-up.

- Highest features: long_ball_share (+0.4 SD), crosses (+0.4 SD), box_shot_share (+0.0 SD)
- Lowest features: passes_completed (-0.5 SD), pass_accuracy (-0.4 SD), deep_completions (-0.4 SD)
- Clubs: Newcastle United, Bournemouth, Brentford, Fulham, Rayo Vallecano, Bologna, Athletic Club, Tottenham, Fiorentina, Nottingham Forest, Leeds United, Crystal Palace, Mallorca, Valencia, Osasuna, Sevilla, Everton, Alavés, West Ham, Udinese, Levante, Genoa, Torino, Cagliari, Sunderland, Espanyol

### Long-Ball Low Block (9 clubs)

The most direct passing profile and the lowest possession and pass accuracy, with the lowest attacking output and finishing return.

- Highest features: long_ball_share (+1.4 SD), crosses (-0.2 SD), fast_attack_shots (-0.7 SD)
- Lowest features: goals (-1.4 SD), goals_per_shot (-1.4 SD), xg (-1.3 SD)
- Clubs: Burnley, Cremonese, Real Oviedo, Wolves, Parma, Pisa, Hellas Verona, Lecce, Getafe

Mean raw values per cluster:

|                   |   Dominant Possession |   Controlled Build-up |   Direct & Cross-Oriented |   Long-Ball Low Block |
|:------------------|----------------------:|----------------------:|--------------------------:|----------------------:|
| possession        |                 58.15 |                 52.24 |                     47.67 |                 42.63 |
| pass_accuracy     |                 86.65 |                 85.12 |                     80.82 |                 77.41 |
| passes_completed  |                462.86 |                404.79 |                    323.33 |                272.17 |
| deep_completions  |                  9.21 |                  6.86 |                      5.4  |                  3.75 |
| long_ball_share   |                  8.46 |                  9.83 |                     13.27 |                 16.2  |
| crosses           |                 17.64 |                 15.86 |                     18.61 |                 16.97 |
| shots             |                 15.63 |                 12.04 |                     12.03 |                  9.86 |
| sot_pct           |                 33.3  |                 35.68 |                     31.8  |                 30.28 |
| xg                |                  1.99 |                  1.5  |                      1.39 |                  1    |
| goals             |                  1.83 |                  1.41 |                      1.21 |                  0.77 |
| goals_per_shot    |                  0.12 |                  0.12 |                      0.1  |                  0.08 |
| fast_attack_shots |                  0.92 |                  0.63 |                      0.71 |                  0.58 |
| box_shot_share    |                 64.26 |                 64.14 |                     63.3  |                 59.71 |

## 4. Statistically unique clubs (DBSCAN)

DBSCAN is used as an outlier detector. At n = 60 it cannot form stable groups, and any single setting is highly sensitive to `min_samples` and `eps`. It was therefore run over 24 settings (min_samples 3–10; eps at 0.9, 1.0 and 1.1 × the knee of the k-distance curve). A club's *uniqueness* is the share of settings in which it is a noise point. Clubs above 50% are flagged:

| team            | league             | cluster                 |   uniqueness |
|:----------------|:-------------------|:------------------------|-------------:|
| Barcelona       | ESP-La Liga        | Dominant Possession     |         0.83 |
| Villarreal      | ESP-La Liga        | Controlled Build-up     |         0.83 |
| Inter           | ITA-Serie A        | Dominant Possession     |         0.71 |
| Hellas Verona   | ITA-Serie A        | Long-Ball Low Block     |         0.62 |
| Getafe          | ESP-La Liga        | Long-Ball Low Block     |         0.54 |
| Real Betis      | ESP-La Liga        | Dominant Possession     |         0.5  |
| Celta Vigo      | ESP-La Liga        | Controlled Build-up     |         0.5  |
| Real Madrid     | ESP-La Liga        | Dominant Possession     |         0.38 |
| Rayo Vallecano  | ESP-La Liga        | Direct & Cross-Oriented |         0.38 |
| Manchester City | ENG-Premier League | Dominant Possession     |         0.33 |

Flagged as statistically unique: **Barcelona, Villarreal, Inter, Hellas Verona, Getafe**.

## 5. Validation

- **Bootstrap stability:** mean ARI 0.64 over 200 resamples.
- **Split-half:** the model was refitted without the season-only counter-attack feature (ARI vs the 13-feature solution: 0.81). First-half and second-half profiles were then assigned. **80% of clubs keep the same cluster** across the two halves (ARI H1 vs H2 = 0.55).
- **Face validity:** see the cluster memberships above, compared with the clubs' documented reputations.

Clubs whose cluster changed between halves:

- Aston Villa: Controlled Build-up → Dominant Possession
- Brentford: Controlled Build-up → Direct & Cross-Oriented
- Brighton: Controlled Build-up → Direct & Cross-Oriented
- Espanyol: Direct & Cross-Oriented → Long-Ball Low Block
- Levante: Long-Ball Low Block → Direct & Cross-Oriented
- Real Sociedad: Direct & Cross-Oriented → Controlled Build-up
- Sevilla: Direct & Cross-Oriented → Long-Ball Low Block
- AC Milan: Dominant Possession → Controlled Build-up
- Como: Controlled Build-up → Dominant Possession
- Genoa: Long-Ball Low Block → Direct & Cross-Oriented
- Roma: Controlled Build-up → Dominant Possession
- Udinese: Long-Ball Low Block → Controlled Build-up

## 6. Cluster distribution across leagues (RQ2)

| league         |   Dominant Possession |   Controlled Build-up |   Direct & Cross-Oriented |   Long-Ball Low Block |
|:---------------|----------------------:|----------------------:|--------------------------:|----------------------:|
| La Liga        |                     3 |                     6 |                         9 |                     2 |
| Premier League |                     5 |                     2 |                        11 |                     2 |
| Serie A        |                     4 |                     5 |                         6 |                     5 |

χ² = 5.96, df = 6, asymptotic p = 0.428, permutation p = 0.454 (10,000 permutations), Cramér's V = 0.22. 75% of expected counts are below 5, so the permutation p-value is the one to report.

## Figures

- `figures/cluster_pca_variance.png`
- `figures/cluster_pca_loadings.png`
- `figures/cluster_model_selection.png`
- `figures/cluster_style_map.png`
- `figures/cluster_profiles.png`
- `figures/cluster_dendrogram.png`