# INRS live timing helper

Feeds live practice, qualifying and race positions from iRacing to the website's Sportsbook, so the odds
move during race night and live betting stays open until 10 laps to go.

1. Install Python once from https://www.python.org/downloads/ (tick "Add python.exe to PATH").
2. Fill in `inrs_live_config.json` (database URL and secret from the Firebase project).
3. On race night, open iRacing, join the league session (driving, spectating or broadcasting),
   then double-click `START_INRS_LIVE.bat`. Leave the window open; close it after the race.

The helper only reads iRacing's live timing (official read-only SDK) and sends a small update every
5 seconds. If it isn't running, the site uses the pre-race odds and betting closes at 8:30 PM Eastern.
