// Run in the Claude built-in browser on https://members-ng.iracing.com/ while Jordan (a league admin) is signed in.
// Uses the iRacing website's own data route (/bff/pub/proxy/data/...), so no app registration or password is needed.
// Prefix with:  window.__IR = {league: 8467, season: 129399, known: [<subsession ids already imported>],
//                              file: 'inrs-ir-cup-<YYYYMMDD>.json', only: null}
// League ids: Cup 8467, Trucks 11674. `only` can be a list of subsession ids to (re)pull.
// Saves a JSON download and returns a short summary. Stage rule: stage lap = floor(33% of race laps);
// if a caution starts within 5 laps before or on that lap, the stage is scored on the lap after the caution starts.
const CFG = window.__IR;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const ir = async (path, q) => {
  for (let t = 0; t < 4; t++) {
    const r = await fetch('/bff/pub/proxy/data/' + path + (q ? '?' + new URLSearchParams(q) : ''), {credentials: 'include'});
    if (r.status === 401 || r.status === 403) throw new Error('Not signed in to iRacing (HTTP ' + r.status + ')');
    if (r.ok) { const j = await r.json(); return j.link ? await (await fetch(j.link)).json() : j; }
    await sleep(1500 * (t + 1));
  }
  throw new Error('iRacing data request failed: ' + path);
};
const chunks = async j => { let rows = []; if (j && j.chunk_info) for (const f of j.chunk_info.chunk_file_names) rows = rows.concat(await (await fetch(j.chunk_info.base_download_url + f)).json()); return rows; };
const STAGE_PCT = 0.33, CAUTION_WINDOW = 5;
const known = new Set((CFG.known || []).map(String));
const ss = await ir('league/season_sessions', {league_id: CFG.league, season_id: CFG.season, results_only: true});
const todo = (ss.sessions || []).filter(s => CFG.only ? CFG.only.map(String).includes(String(s.subsession_id)) : !known.has(String(s.subsession_id)));
const races = [], skipped = [];
for (const s of todo) {
  const res = await ir('results/get', {subsession_id: s.subsession_id});
  const race = res.session_results.find(x => x.simsession_name === 'RACE');
  if (!race) { skipped.push(s.subsession_id); continue; }
  const laps = Math.max(...race.results.map(x => x.laps_complete));
  const ev = await chunks(await ir('results/event_log', {subsession_id: s.subsession_id, simsession_number: 0}));
  const cautions = ev.filter(e => e.event_code === 6 && /^Caution for/i.test(e.message || '')).map(e => e.lap_number);
  const sched = s.race_laps > 0 ? s.race_laps : laps;  // stage is 33% of the scheduled distance (overtime doesn't move it)
  const base = Math.floor(sched * STAGE_PCT);
  const c = cautions.find(l => l >= base - CAUTION_WINDOW && l <= base);
  const stageLap = c != null ? c + 1 : base;
  const lc = await chunks(await ir('results/lap_chart_data', {subsession_id: s.subsession_id, simsession_number: 0}));
  const tops = {};  // top 10 at the end of every lap, so a steward's stage-lap override can be scored later
  for (const r of lc) if (r.lap_number > 0 && r.lap_position <= 10) (tops[r.lap_number] = tops[r.lap_number] || [])[r.lap_position - 1] = r.cust_id;
  const stage = (tops[stageLap] || []).filter(Boolean);
  const fast = race.results.filter(x => x.best_lap_time > 0).sort((a, b) => a.best_lap_time - b.best_lap_time)[0];
  races.push({subsession: s.subsession_id, launch: s.launch_at, track: (s.track || {}).track_name, config: (s.track || {}).config_name,
    laps, schedLaps: sched, stageBase: base, tops, stageCaution: c ?? null, stageLap, stage, fastest: fast ? fast.cust_id : null, cautions,
    results: race.results.map(x => ({cust: x.cust_id, name: x.display_name, car: String(x.car_number ?? (x.livery || {}).car_number ?? ''),
      fin: x.finish_position + 1, start: x.starting_position + 1, laps: x.laps_complete, led: x.laps_lead, inc: x.incidents,
      best: x.best_lap_time, status: x.reason_out}))});
}
const out = {league: CFG.league, season: CFG.season, exported: new Date().toISOString(), races, skipped};
const blob = new Blob([JSON.stringify(out)], {type: 'application/json'});
const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = CFG.file; document.body.appendChild(a); a.click(); a.remove();
await sleep(4000);
JSON.stringify({file: CFG.file, bytes: blob.size, races: races.map(r => [r.subsession, r.launch.slice(0, 10), r.track, r.laps + ' laps', 'stage lap ' + r.stageLap]), skipped});
