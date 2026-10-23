# Phase 0: Data-source audit for the 2025/26 season

Audit run on 2026-10-23. The probe scripts are in `src/collect/audit_*.py`, and their raw column dumps are in `reports/audit/`.

## 1. Source status

| Source | Access | 2025/26 coverage | Level | Verdict |
|---|---|---|---|---|
| **Understat** (soccerdata) | Works | EPL 380 matches, 9,524 shots. ESP/ITA: see section 4 | Match, plus every shot with x/y. Team pages give season breakdowns | **Primary source** for xG, goals, shots, deep completions, counter-attack (attack speed "Fast") and penalty-area shots |
| **ESPN** public API | Works (direct JSON). soccerdata's `read_matchsheet` crashes with `KeyError: 'form'` | All 3 leagues, same stat set | Match | **Primary source** for possession, passes, pass %, crosses, long balls, shots on target |
| **FBref** (soccerdata) | Works (Selenium) | 20 teams per league | Season | **Degraded.** Only `standard`, `shooting` and `misc` tables remain, so no xG, passing, possession-touches or GCA. Use for cross-checks: Poss, Sh, SoT%, G/Sh, Crs |
| **StatsBomb Open Data** | n/a | Does not include 2025/26 domestic leagues | n/a | **Not usable** for this scope |
| **Sofascore** | **HTTP 403 (bot-blocked)** | n/a | n/a | **Not usable.** I didn't try to get around the block |
| **WhoScored** (Opta events) | Not probed | Has everything (through balls, box touches, fast breaks) | Event | **Not recommended.** Its terms forbid scraping, it needs Selenium anti-bot workarounds, and it means ~1,140 heavy match pages |
| **FotMob** | Not in soccerdata. Its API needs a signed header | n/a | n/a | **Not usable** without bypassing its protection |
| **Opta Analyst** | Website only, no API | Season tables | Season | **Manual spot-checks only** |
| **Kaggle** | Needs your Kaggle account | Depends on whether someone has published a 2025/26 dataset | Varies | **Optional.** Only option for through balls and box touches, if a dataset exists |

## 2. Feature mapping (Table 3.1 → available data)

| Proposal feature | Status | Source and definition we can use |
|---|---|---|
| Possession % | ✅ | ESPN `possessionPct`, match-level, season mean. Cross-check with FBref `Poss` |
| Ball Control | ⚠️ redefine | Proposal leaves it undefined. Proposed: **pass accuracy %** (ESPN `accuratePasses/totalPasses`) |
| Passes per match | ✅ | ESPN `accuratePasses` (completed) per match |
| Progressive passes | ❌ → proxy | Not available free. Proxies: **Understat deep completions** per 90 (passes completed within ~20 m of goal) for penetration, and **long-ball share** (ESPN `totalLongBalls/totalPasses`) for directness |
| Through balls | ❌ | No free automated source. **Drop**, or use Kaggle if a dataset exists |
| Crosses | ✅ | ESPN `totalCrosses` per match. Cross-check with FBref `Crs` |
| Shots | ✅ | Understat shots per match (ESPN `totalShots` for cross-check) |
| Shots on target % | ✅ | ESPN `shotsOnTarget/totalShots`. Also derivable from Understat shot results; FBref `SoT%` |
| Expected Goals (xG) | ✅ | Understat `xg` per match (also non-penalty xG) |
| Goals | ✅ | Understat / ESPN |
| Goals per shot | ✅ | Understat (derived). FBref `G/Sh` |
| Counter attacks | ⚠️ proxy | Understat team page `attackSpeed["Fast"]`: **shots and xG from fast attacks** per 90, season-level only |
| Touches in penalty area | ⚠️ proxy | Understat shot locations / `shotZone`: **share of shots taken inside the penalty area**. A shot-based proxy, not true touches |

Net result: **9 of 13 features are directly available, 3 work through documented proxies, and 1 (through balls) is lost**, unless Kaggle has a 2025/26 dataset that includes it.

## 3. Implications for the method
- **Match-level data exists** for possession, passes, crosses, long balls, shots, SoT, xG, goals and deep completions, for all three leagues. That supports:
  - split-half validation (first half vs second half of the season);
  - the match-level "who attacked more" prediction model (~1,140 matches).
- **The counter-attack and box-shot proxies are season-level only**, from Understat team pages. For split-half validation they can be rebuilt from shot events by date, but only the penalty-area share can be; attack speed cannot.
- **Methodology chapter changes needed:**
  - replace StatsBomb/FBref as primary sources with Understat and ESPN;
  - document the proxies;
  - define Ball Control;
  - justify dropping Through Balls.

## 4. La Liga and Serie A coverage
| Source | EPL | La Liga | Serie A |
|---|---|---|---|
| Understat matches / shots | 380 / 9,524 | 380 / 9,523 | 380 / 9,373 |
| ESPN match stats | ✅ same 28 stats | ✅ same 28 stats | ✅ same 28 stats |
| FBref season tables | standard, shooting, misc (20 teams) | standard, shooting, misc (20 teams) | standard, shooting, misc (20 teams) |

All 60 clubs are covered in every usable source, so no club needs to be excluded for missing data.
