## team_match_stats rows=380
- league_id
- season_id
- game_id
- date
- home_team_id
- away_team_id
- home_team
- away_team
- away_team_code
- home_team_code
- away_points
- away_expected_points
- away_goals
- away_xg
- away_np_xg
- away_np_xg_difference
- away_ppda
- away_deep_completions
- home_points
- home_expected_points
- home_goals
- home_xg
- home_np_xg
- home_np_xg_difference
- home_ppda
- home_deep_completions

sample:
                                                 league_id  season_id  game_id                date  home_team_id  away_team_id home_team  away_team away_team_code home_team_code  away_points  away_expected_points  away_goals   away_xg  away_np_xg  away_np_xg_difference  away_ppda  away_deep_completions  home_points  home_expected_points  home_goals  home_xg  home_np_xg  home_np_xg_difference  home_ppda  home_deep_completions
league      season game                                                                                                                                                                                                                                                                                                                                                                                                                     
ITA-Serie A 2526   2025-08-23 AC Milan-Cremonese         2       2025    29846 2025-08-23 18:45:00           111           272  AC Milan  Cremonese            CRE            MIL            3                0.2555           2  0.363576    0.363576              -1.721404       17.4                      0            0                2.6003           1  2.08498     2.08498               1.721404  13.647059                     19
                   2025-08-23 Genoa-Lecce                2       2025    29844 2025-08-23 16:30:00           101           243     Genoa      Lecce            LEC            GEN            1                1.2407           0   0.55094     0.55094               -0.01469   8.058824                      4            1                1.3175           0  0.56563     0.56563                0.01469   5.434783                      3
                   2025-08-23 Roma-Bologna               2       2025    29847 2025-08-23 18:45:00            95            97      Roma    Bologna            BOL            ROM            0                0.5099           0  0.443508    0.443508              -1.033402       12.2                      0            3                2.2535           1  1.47691     1.47691               1.033402    7.96875                      5

## shot_events rows=9373
- league_id
- season_id
- game_id
- date
- shot_id
- team_id
- player_id
- assist_player_id
- assist_player
- xg
- location_x
- location_y
- minute
- body_part
- situation
- result

### situation values
situation
Open Play          6868
From Corner        1466
Set Piece           653
Direct Freekick     280

### result values
result
Missed Shot     3559
Blocked Shot    2622
Saved Shot      2094
Goal             900
Shot On Post     176
Own Goal          22