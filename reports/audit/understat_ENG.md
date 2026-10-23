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
- home_points
- home_expected_points
- home_goals
- home_xg
- home_np_xg
- home_np_xg_difference
- home_ppda
- home_deep_completions
- away_points
- away_expected_points
- away_goals
- away_xg
- away_np_xg
- away_np_xg_difference
- away_ppda
- away_deep_completions

sample:
                                                                  league_id  season_id  game_id                date  home_team_id  away_team_id    home_team         away_team away_team_code home_team_code  home_points  home_expected_points  home_goals   home_xg  home_np_xg  home_np_xg_difference  home_ppda  home_deep_completions  away_points  away_expected_points  away_goals   away_xg  away_np_xg  away_np_xg_difference  away_ppda  away_deep_completions
league             season game                                                                                                                                                                                                                                                                                                                                                                                                                                          
ENG-Premier League 2526   2025-08-15 Liverpool-Bournemouth                1       2025    28778 2025-08-15 19:00:00            87            73    Liverpool       Bournemouth            BOU            LIV            3                 1.877           4   2.33007     2.33007                0.75704   8.764706                      9            0                0.8954           2   1.57303     1.57303               -0.75704  11.583333                      8
                          2025-08-16 Aston Villa-Newcastle United         1       2025    28779 2025-08-16 11:30:00            71            86  Aston Villa  Newcastle United            NEW            AVL            1                0.4258           0  0.318601    0.318601              -1.082379  18.916667                      2            1                2.3371           0   1.40098     1.40098               1.082379   6.083333                      6
                          2025-08-16 Brighton-Fulham                      1       2025    28780 2025-08-16 14:00:00           220           228     Brighton            Fulham            FLH            BRI            1                1.8562           1   1.44008    0.678909              -0.223974   8.928571                      5            1                 0.835           1  0.902883    0.902883               0.223974  16.222222                      6

## shot_events rows=9524
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
Open Play          6951
From Corner        1674
Set Piece           559
Direct Freekick     248

### result values
result
Missed Shot     3294
Blocked Shot    2905
Saved Shot      2068
Goal            1004
Shot On Post     212
Own Goal          41