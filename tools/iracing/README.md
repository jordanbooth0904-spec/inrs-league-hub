# Results from iRacing (replacing SimRacerHub)

iRacing has paused new API app registrations, so this uses Jordan's own iRacing website sign-in in the Claude
built-in browser (he is an admin of the INRS leagues). Nothing stores or types his password.

| Series | iRacing league id | 2026 season id |
|---|---|---|
| Cup | 8467 | 129399 |
| Trucks | 11674 | (look up with league/seasons) |

## After a race
1. Built-in browser on `https://members-ng.iracing.com/` (Jordan signed in). If a call returns 401, ask him to sign in again.
2. Run `extract_league.js` with `window.__IR = {league, season, known: [<irSubsession of every imported race>], file: 'inrs-ir-<series>-<YYYYMMDD>.json'}`
   prefixed. `known` comes from the `irSubsession` field on races in the season file. It saves a download.
3. Stage the file, then `python3 tools/iracing/import_iracing.py <file> --series cup --data data.json`
   (Trucks: `--data data/trucks-<year>.json --series trucks`).
4. `python3 tools/scoring/standings.py data.json cup --write` rebuilds the standings table.
5. Test locally, commit, push.

## Stage points
Stage lap = floor(33% of the race laps). If a caution starts within 5 laps before, or on, that lap, the stage is
scored on the lap after the caution starts. Positions come from iRacing's lap chart. A steward can override the
stage top 10 for a race by setting `stageOverride: [driverId x10]` on that race, then re-importing it (`only: [subsession]`).

## Checked against 2026 SimRacerHub
- Stage rule: 22 of 26 Cup races reproduce SimRacerHub's stage top 10 exactly; Atlanta and Bristol differ by one swap at a
  caution; Daytona (summer) and Indianapolis need a steward override. Fastest lap and winner match in all 26.
- Full import (New Hampshire, Talladega, Homestead): every driver's finish, start, points, stage, bonus, laps, laps led
  and incidents identical to SimRacerHub.
- Standings built by `tools/scoring/standings.py` match SimRacerHub's 2026 table for every driver outside the Chase reset.
