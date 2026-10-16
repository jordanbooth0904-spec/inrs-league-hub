# Weekly sync: SimRacerHub + YouTube → INRS League Hub

Runs after each Thursday race. Updates `data.json` (the public website at
https://jordanbooth0904-spec.github.io/inrs-league-hub/) and the Claude app database
(artifact https://claude.ai/artifact/8Qg6cyP9iKMDxYcSyXmL29).

Needs: this repo cloned with push access, and the Claude built-in browser on Jordan's PC
(tools `mcp__remote-devices__Claude_Browser__*`). Sites already approved there:
simracerhub.com, youtube.com, github.com. If the browser can't be reached, stop and report it.

## Steps

1. `python3 tools/sync/apply.py --known` → copy the JSON list it prints (KNOWN).
2. Built-in browser: `navigate` to
   `https://www.simracerhub.com/scoring/season_standings.php?season_id=28439`.
   Run `javascript_tool` with `window.__KNOWN = <KNOWN>;` followed by the full text of
   `tools/sync/extract_main.js`. Save the returned JSON string **exactly as returned** to `/tmp/sync_main.json`.
3. (Skipped while `official.teamsManual` is true in data.json: Jordan posts the official team standings himself and they are entered by hand.) Otherwise `navigate` to the same URL with `&view=team`. Run `tools/sync/extract_teams.js`.
   Save the result to `/tmp/sync_teams.json`.
4. `navigate` to `https://www.youtube.com/@40XLIRacing/videos` (if youtube.com needs approval,
   call `request_access` once with scope "site"). Run `tools/sync/extract_youtube.js`.
   Save to `/tmp/sync_yt.json`. If this step fails, skip it (recaps are optional).
5. `python3 tools/sync/apply.py /tmp/sync_main.json --teams /tmp/sync_teams.json --youtube /tmp/sync_yt.json`
   - A "Checksum mismatch" means the JSON was not saved exactly. Re-run step 2 once; if it fails again, stop and report.
   - Any other error: stop and report. Never hand-edit data.json to make it pass.
6. Do step 8b now. Then, if `git status` shows no change under `data/` and the summary shows no "results added", no "recap linked" and no "new race", run
   `git checkout data.json`, report "no new results", and stop.
7. Commit and push:
   `git add data.json data && git commit -m "Sync results through round N" && git push`.
8. Claude app database: read `tools/sync/out/db_docs.json`. For each entry, `ArtifactData get`
   (url above, its collection and doc_id) to learn its current `version` (missing doc = new).
   Then one or more `ArtifactData batch` calls (max 50 writes each) with
   `{op:"set", collection, doc_id, file_path, if_version}` (omit if_version for new docs).
8b. O'Reilly (formerly Xfinity; series key `xfinity`) and Trucks (website only). For each of `xfinity` (season_id 28549)
   and `trucks` (season_id 28550):
   **The O'Reilly Series ends after 2026 (finale: Homestead, Nov 4).** Before exporting `xfinity`, check `data/seasons.json`:
   if the `xfinity-2026` entry has `"done": true`, the series is finished. Skip it for good and only export `trucks`.
   The site switches to the series' legacy page and farewell banner on its own once that season is complete.
   `navigate` to `https://www.simracerhub.com/scoring/season_standings.php?season_id=<id>`, then run `javascript_tool` with
   `window.__SEASON = {id: <id>, series: '<series>', year: 2026, file: 'inrs-<series>-2026-<YYYYMMDD>.json'};`
   followed by the full text of `tools/sync/extract_season.js` (wrap it as `await (async () => { ... })()` and change the
   final expression to `return`). It saves the file to Jordan's Downloads folder (C:\Users\booth\Downloads) and returns a
   summary; `missing` must be empty (if not, run it once more). Copy the files in with `device_stage_files`, then
   `python3 tools/sync/season.py <staged files>` and include `data/` in the step 7 commit (run 8b before step 7).
   If this step fails, skip it and report it; the Cup update still goes out.
9. After ~2 minutes, open the live site in the built-in browser and confirm the Home page shows
   the new result.
10. Report: rounds added (track + winner), points leader and gap, recaps linked, anything that failed.

## Files
- `extract_main.js` – schedule, newly completed races (with checksums), driver standings.
- `extract_teams.js` – team standings.
- `extract_youtube.js` – latest 40XLI Racing videos for recap matching.
- `apply.py` – validates checksums and merges everything into `data.json`.
- `extract_season.js` – full-season export (standings, teams, schedule, every race) for any SimRacerHub season.
- `season.py` – turns season exports into `data/<series>-<year>.json` and rebuilds `data/seasons.json`
  (the header's series/year switcher and per-series track history). Past seasons don't change, so only 2026
  O'Reilly (until its Nov 4 finale is in) and Trucks need re-exporting each week.
