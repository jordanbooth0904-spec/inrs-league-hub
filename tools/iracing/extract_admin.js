// Run in the Claude built-in browser on the league site. Saves the admin's schedule edits for one season
// (/site/overrides/<season>: changed dates, tracks, laps, fixed stage laps, non-points flags, added/removed races)
// and the entry list (/site/entries/<season>: numbers, teams, tiers, iRacing IDs)
// for import_iracing.py --admin, so the season file matches what the site shows.
// Prefix with:  window.__ADM = {season: 'cup-2027', file: 'inrs-admin-cup-2027-<YYYYMMDD>.json'}
const CFG = window.__ADM;
const r = await fetch('https://inrs-league-hub-default-rtdb.firebaseio.com/site/overrides/' + CFG.season + '.json', {cache: 'no-store'});
const overrides = (r.ok && await r.json()) || {};
const r2 = await fetch('https://inrs-league-hub-default-rtdb.firebaseio.com/site/entries/' + CFG.season + '.json', {cache: 'no-store'});
const entries = (r2.ok && await r2.json()) || {};
const blob = new Blob([JSON.stringify({season: CFG.season, exported: new Date().toISOString(), overrides, entries})], {type: 'application/json'});
const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = CFG.file; document.body.appendChild(a); a.click(); a.remove();
await new Promise(res => setTimeout(res, 4000));
JSON.stringify({file: CFG.file, races: Object.keys(overrides), entries: Object.keys(entries).length});
