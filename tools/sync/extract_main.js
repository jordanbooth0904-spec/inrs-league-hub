// Run in the Claude browser on https://www.simracerhub.com/scoring/season_standings.php?season_id=28439
// Set KNOWN to the srhIds already complete in data.json (apply.py --known prints them).
// Returns compact JSON: schedule, any newly completed races, driver standings and checksums.
const KNOWN = new Set(window.__KNOWN || []);
await new Promise(r => setTimeout(r, 1500));
const clean = t => t.replace(/\s+/g, ' ').trim();
const h = await fetch('season_schedule.php?season_id=28439').then(r => r.text());
const d = new DOMParser().parseFromString(h, 'text/html');
const tb = [...d.querySelectorAll('table')].find(x => /Event/.test(x.innerText));
const sched = [...tb.rows].slice(1).map(r => { const c = [...r.cells];
  const parts = [...c[2].querySelectorAll('*')].filter(e => !e.children.length).map(e => e.textContent.trim()).filter(Boolean);
  const sid = [...r.querySelectorAll('a[href*="schedule_id"]')].map(a => a.getAttribute('href').match(/\d+$/)[0])[0] || '';
  return [c[0].innerText.trim(), c[1].innerText.trim(), parts.length > 1 ? parts[0] : '', parts[parts.length - 1] || '', (c[3].innerText.match(/\d+/) || [''])[0], sid]; })
  .filter(x => x[0]);
const st = s => /^running$/i.test(s) ? '' : s;
const races = {}, check = {};
const n = v => { const x = parseFloat(v); return isFinite(x) ? x : 0; };
for (const s of sched) { if (!s[5] || KNOWN.has(s[5])) continue;
  const hh = await fetch('season_race.php?schedule_id=' + s[5]).then(r => r.text());
  const dd = new DOMParser().parseFromString(hh, 'text/html'); const tabs = [...dd.querySelectorAll('table')];
  const main = tabs.find(x => { const hd = [...x.rows[0].cells].map(c => c.innerText.trim()); return hd[0] === 'Fin' && hd[1] === 'St'; });
  if (!main) continue;
  const H = [...main.rows[0].cells].map(c => c.innerText.trim()), ix = k => H.indexOf(k);
  const res = [...main.rows].slice(1).map(r => [...r.cells].map(c => c.innerText.trim()));
  const pick = x => [x[ix('Fin')], x[ix('St')], x[ix('Car #')], x[ix('Driver')], x[ix('TotPts')], x[ix('StagePts')], x[ix('BnsPts')], x[ix('PenPts')], x[ix('Laps')], x[ix('LapsLed')], x[ix('Inc')], st(x[ix('Status')]), x[ix('DriverRating')]];
  const tbl = hdr => tabs.filter(x => x.rows[0] && [...x.rows[0].cells].map(c => c.innerText.trim()).join('|') === hdr).flatMap(x => [...x.rows].slice(1).map(r => [...r.cells].map(c => c.innerText.trim()).join('~'))).join('^');
  races[s[0]] = { r: res.map(x => pick(x).join('~')).join('^'), p: tbl('Driver|PTS|Penalty'), b: tbl('Driver|PTS|Bonus') };
  check[s[0]] = [res.length, Math.round(res.reduce((a, x) => { const v = pick(x); return a + n(v[0]) * 7 + n(v[1]) * 3 + n(v[2]) + n(v[4]) * 11 + n(v[5]) * 13 + n(v[6]) * 17 + n(v[7]) * 19 + n(v[8]) + n(v[9]) * 23 + n(v[10]) * 29 + n(v[12]) * 10; }, 0))]; }
const t = [...document.querySelectorAll('table')].find(x => /DRIVER/.test(x.rows[0]?.innerText || '') && /TEAM/.test(x.rows[0]?.innerText || ''));
const SH = [...t.rows[0].cells].map(c => clean(c.innerText));
const srows = [...t.rows].slice(1).map(r => [...r.cells].map(c => clean(c.innerText)));
const head = clean(document.body.innerText.match(/RACE\s+\d+\s+[A-Z0-9 .()'&-]+?\s+[A-Z]{3} \d{1,2}, \d{4}/)?.[0] || '');
JSON.stringify({ sched, races, check, standings: { H: SH, rows: srows, head } });
