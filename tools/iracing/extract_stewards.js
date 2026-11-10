// Run in the Claude built-in browser on the league site (https://jordanbooth0904-spec.github.io/inrs-league-hub/).
// Saves the PUBLISHED steward reports for one season (stage-lap overrides, incidents, penalties) as a download for
// import_iracing.py --stewards. Unpublished drafts are not included, so publish a race's report before importing it.
// Prefix with:  window.__STW = {season: 'cup-2027', file: 'inrs-stewards-cup-2027-<YYYYMMDD>.json'}
const CFG = window.__STW, DB = 'https://inrs-league-hub-default-rtdb.firebaseio.com';
const races = {};
await Promise.all(Array.from({length: 45}, (_, i) => 'r' + String(i + 1).padStart(2, '0')).map(async id => {
  const r = await fetch(DB + '/stewards/' + CFG.season + '/' + id + '.json', {cache: 'no-store'});
  if (r.ok) { const j = await r.json(); if (j && j.published === true) races[id] = j; }
}));
const out = {season: CFG.season, exported: new Date().toISOString(), races};
const blob = new Blob([JSON.stringify(out)], {type: 'application/json'});
const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = CFG.file; document.body.appendChild(a); a.click(); a.remove();
await new Promise(r => setTimeout(r, 4000));
JSON.stringify({file: CFG.file, published: Object.keys(races).sort(), incidents: Object.values(races).reduce((n, x) => n + Object.keys(x.inc || {}).length, 0)});
