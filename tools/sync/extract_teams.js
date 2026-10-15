// Run in the Claude browser on https://www.simracerhub.com/scoring/season_standings.php?season_id=28439&view=team
await new Promise(r => setTimeout(r, 1500));
const t = [...document.querySelectorAll('table')].find(x => /TEAM/.test(x.rows[0]?.innerText || '') && !/DRIVER/.test(x.rows[0]?.innerText || ''));
JSON.stringify([...t.rows].slice(1).map(r => [...r.cells].map(c => c.innerText.replace(/\s+/g, ' ').trim())).map(c => [c[0], c[2], c[3], c[4], c[5], c[6], c[7], c[9], c[10]]));
