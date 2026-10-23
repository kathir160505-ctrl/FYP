## Understat getTeamData keys: ['dates', 'players', 'statistics']

### situation: ['OpenPlay', 'FromCorner', 'SetPiece', 'DirectFreekick', 'Penalty']

### formation: ['4-3-3', '4-2-3-1', '4-1-4-1', '4-4-2', '3-4-3']

### gameState: ['Goal diff 0', 'Goal diff +1', 'Goal diff > +1', 'Goal diff -1']

### timing: ['1-15', '16-30', '31-45', '46-60', '61-75', '76+']

### shotZone: ['ownGoals', 'shotOboxTotal', 'shotPenaltyArea', 'shotSixYardBox']

### attackSpeed: ['Normal', 'Standard', 'Slow', 'Fast']

### result: ['MissedShots', 'BlockedShot', 'SavedShot', 'Goal', 'ShotOnPost']

attackSpeed detail:
{
 "Normal": {
  "stat": "Normal",
  "shots": 305,
  "goals": 33,
  "xG": 39.95729193650186,
  "against": {
   "shots": 191,
   "goals": 16,
   "xG": 17.635757468640804
  }
 },
 "Standard": {
  "stat": "Standard",
  "shots": 162,
  "goals": 27,
  "xG": 30.095831130631268,
  "against": {
   "shots": 71,
   "goals": 7,
   "xG": 8.777284819632769
  }
 },
 "Slow": {
  "stat": "Slow",
  "shots": 59,
  "goals": 6,
  "xG": 7.074158746749163,
  "against": {
   "shots": 28,
   "goals": 3,
   "xG": 5.477298629004508
  }
 },
 "Fast": {
  "stat": "Fast",
  "shots": 31,
  "goals": 5,
  "xG": 6.855083391070366,
  "against": {
   "shots": 21,
   "goals": 1,
   "xG": 3.5684551801532507
  }
 }
}

## ESPN FAILED: KeyError: 'form'