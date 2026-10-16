// Run in the Claude browser on https://www.simracerhub.com/scoring/season_standings.php?season_id=28439&view=team
await new Promise(r => setTimeout(r, 1500));
for (let i = 0; i < 30 && document.querySelectorAll('table').length < 1; i++) await new Promise(r => setTimeout(r, 500));
const hd = x => [...(x.rows[0]?.cells || [])].map(c => c.innerText.replace(/\s+/g, ' ').trim());
// Header is POS|CHG|TEAM|STARTS|DRIVERS COUNTED|TOT PTS|PEN PTS|BEH LEAD|BEH NEXT|WINS|INCS ("DRIVERS COUNTED" since Oct 2026)
const t = [...document.querySelectorAll('table')].find(x => hd(x)[0] === 'POS' && hd(x).includes('TEAM') && hd(x).includes('TOT PTS'));
JSON.stringify([...t.rows].slice(1).map(r => [...r.cells].map(c => c.innerText.replace(/\s+/g, ' ').trim())).map(c => [c[0], c[2], c[3], c[4], c[5], c[6], c[7], c[9], c[10]]));
