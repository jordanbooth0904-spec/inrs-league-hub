# INRS points engine

Replaces SimRacerHub's scoring. `points.py` scores races and builds standings from `rules.json`;
`compare.py` re-scores a finished season and checks it against SimRacerHub's official numbers.

    python3 tools/scoring/compare.py data.json cup
    python3 tools/scoring/compare.py data/trucks-2026.json trucks

## Rules (2026, kept for 2027)
- Finish: P1 55, P2 35, P3 34, then 1 less per position; P36 and below get 1.
- Stage: one stage per race, top 10 at the stage end get 10..1.
- Fastest race lap: +1 (Cup and Trucks).
- Daytona Duels (Cup only): 10..1 for the top 10 of each Duel, scored as one round. No stage or bonus.
- Penalties come off in full, so a race can go below 0; they still count when that race is dropped. Some penalties are season-level.
- Non-points races (e.g. Cup Dover 2026) score 0 for everyone and don't count toward drops.
- Drops: each driver's best (points races - 2) races count, judged before penalties. Duel points always count.
- Not modeled yet: the Chase reset (to be defined for 2027).

## 2026 check
Cup: 1,063 results, every season total outside the Chase reset and every "races counted" value match.
Trucks: 461 results and every season total match. The only differences are two Cup Talladega races that
SimRacerHub displays as 0 while taking the full penalty off the season total, as the engine does.
