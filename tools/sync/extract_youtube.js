// Run in the Claude browser on https://www.youtube.com/@40XLIRacing/videos
const h = await fetch('/@40XLIRacing/videos').then(r => r.text());
const ids = [...new Set([...h.matchAll(/"videoId":"([\w-]{11})"/g)].map(m => m[1]))].slice(0, 15);
const out = [];
for (const id of ids) { const w = await fetch('/watch?v=' + id).then(r => r.text());
  out.push([id, (w.match(/"title":"([^"]+)","lengthSeconds"/) || [])[1] || '', ((w.match(/"shortDescription":"((?:[^"\\]|\\.)*)"/) || [])[1] || '').slice(0, 160),
    (w.match(/"publishDate":"([^"]+)"/) || [])[1] || '', (w.match(/"lengthSeconds":"(\d+)"/) || [])[1] || '']); }
JSON.stringify(out);
