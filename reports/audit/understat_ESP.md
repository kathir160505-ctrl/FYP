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
                                                     league_id  season_id  game_id                date  home_team_id  away_team_id   home_team       away_team away_team_code home_team_code  away_points  away_expected_points  away_goals  away_xg  away_np_xg  away_np_xg_difference  away_ppda  away_deep_completions  home_points  home_expected_points  home_goals   home_xg  home_np_xg  home_np_xg_difference  home_ppda  home_deep_completions
league      season game                                                                                                                                                                                                                                                                                                                                                                                                                                
ESP-La Liga 2526   2025-08-15 Girona-Rayo Vallecano          4       2025    29158 2025-08-15 17:00:00           223           145      Girona  Rayo Vallecano            RVL            GIR            3                2.8498           3  3.25355     2.51027               1.714966   7.266667                      4            0                0.0931           1  0.795304    0.795304              -1.714966       24.0                      1
                   2025-08-15 Villarreal-Real Oviedo         4       2025    29159 2025-08-15 19:30:00           154           289  Villarreal     Real Oviedo            OVI            VIL            0                0.2935           0  0.85578    0.112502              -2.494888  40.428571                      0            3                2.5516           2   2.60739     2.60739               2.494888   8.142857                     20
                   2025-08-16 Alaves-Levante                 4       2025    29161 2025-08-16 19:30:00           158           151      Alaves         Levante            LEV            ALA            0                0.5727           1  0.74203     0.74203               -0.98112  20.083333                      2            3                2.1765           2   1.72315     1.72315                0.98112   6.380952                      2

## shot_events rows=9523
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
Open Play          7063
From Corner        1522
Set Piece           556
Direct Freekick     248

### result values
result
Missed Shot     3571
Blocked Shot    2543
Saved Shot      2226
Goal            1003
Shot On Post     157
Own Goal          23