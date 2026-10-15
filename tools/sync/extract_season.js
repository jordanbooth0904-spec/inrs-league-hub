// Full-season export. Run in the Claude browser on
//   https://www.simracerhub.com/scoring/season_standings.php?season_id=<SEASON_ID>
// after setting window.__SEASON = {id, series, year, file}. Reads the driver (and team) standings from the
// page, fetches the schedule and every race result, then saves <file> to the Downloads folder.
const CFG = window.__SEASON;
const clean = t => t.replace(/\s+/g, ' ').trim();
const sleep = ms => new Promise(r => setTimeout(r, ms));
for (let i = 0; i < 40 && !document.querySelector('table'); i++) await sleep(500);
const readTable = pred => { const t = [...document.querySelectorAll('table')].find(pred); if (!t) return null;
  return { H: [...t.rows[0].cells].map(c => clean(c.innerText)), rows: [...t.rows].slice(1).map(r => [...r.cells].map(c => clean(c.innerText))) }; };
const drivers = readTable(x => /DRIVER/.test(x.rows[0]?.innerText || '') && /TOT/.test(x.rows[0]?.innerText || ''));
let teams = null;
const tb = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Team Standings');
if (tb) { tb.click(); await sleep(2000); teams = readTable(x => /TEAM/.test(x.rows[0]?.innerText || '') && !/DRIVER/.test(x.rows[0]?.innerText || '') && /TOT/.test(x.rows[0]?.innerText || '')); }
let h = '';
for (let tries = 0; tries < 4 && !/Event/.test(h); tries++) { if (tries) await sleep(2500); h = await fetch('season_schedule.php?season_id=' + CFG.id).then(r => r.text()).catch(() => ''); }
const d = new DOMParser().parseFromString(h, 'text/html');
const st = [...d.querySelectorAll('table')].find(x => /Event/.test(x.innerText));
const sched = [...st.rows].slice(1).map(r => { const c = [...r.cells];
  const parts = [...c[2].querySelectorAll('*')].filter(e => !e.children.length).map(e => e.textContent.trim()).filter(Boolean);
  const sid = [...r.querySelectorAll('a[href*="schedule_id"]')].map(a => a.getAttribute('href').match(/\d+$/)[0])[0] || '';
  return [c[0].innerText.trim(), c[1].innerText.trim(), parts.length > 1 ? parts[0] : '', parts[parts.length - 1] || '', (c[3]?.innerText.match(/\d+/) || [''])[0], sid]; });
const races = {}, missing = [];
for (const s of sched) { if (!s[0] || !s[5]) continue;
  let tabs = [], main = null;
  for (let tries = 0; tries < 4 && !main; tries++) { await sleep(tries ? 2500 : 300);
    const hh = await fetch('season_race.php?schedule_id=' + s[5]).then(r => r.ok ? r.text() : '').catch(() => '');
    const dd = new DOMParser().parseFromString(hh, 'text/html'); tabs = [...dd.querySelectorAll('table')];
    main = tabs.find(x => { const hd = [...(x.rows[0]?.cells || [])].map(c => c.innerText.trim()); return hd[0] === 'Fin' && hd[1] === 'St'; }); }
  if (!main) { missing.push(s[0]); continue; }
  const H = [...main.rows[0].cells].map(c => c.innerText.trim());
  const rows = [...main.rows].slice(1).map(r => [...r.cells].map(c => c.innerText.trim()));
  const tbl = hdr => tabs.filter(x => x.rows[0] && [...x.rows[0].cells].map(c => c.innerText.trim()).join('|') === hdr).flatMap(x => [...x.rows].slice(1).map(r => [...r.cells].map(c => c.innerText.trim())));
  races[s[0]] = { H, rows, pen: tbl('Driver|PTS|Penalty'), bonus: tbl('Driver|PTS|Bonus') }; }
const out = { missing, series: CFG.series, year: CFG.year, seasonId: CFG.id, exported: new Date().toISOString(), drivers, teams, sched, races };
const blob = new Blob([JSON.stringify(out)], { type: 'application/json' });
const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = CFG.file; document.body.appendChild(a); a.click(); a.remove();
JSON.stringify({ file: CFG.file, bytes: blob.size, standings: drivers ? drivers.rows.length : 0, teams: teams ? teams.rows.length : 0, schedule: sched.length, races: Object.keys(races).length, missing });
