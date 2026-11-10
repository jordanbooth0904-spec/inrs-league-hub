#!/usr/bin/env python3
"""Score a finished season with points.py from its raw results and compare against SimRacerHub's official numbers.
  python3 tools/scoring/compare.py data.json cup
  python3 tools/scoring/compare.py data/trucks-2026.json trucks
SimRacerHub leaves the Truck bonus column empty, so the Truck fastest-lap point is inferred from the leftover point.
Inputs are derived from SimRacerHub's per-result fields only where the live system will supply them itself:
finish position, stage position (top 10), fastest-lap flag and penalties."""
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import points

f, series = sys.argv[1], sys.argv[2]
d = json.load(open(f)); nm = {x['id']: x['name'] for x in d['drivers']}
races = [r for r in sorted(d['races'], key=lambda r: r['round']) if r['status'] == 'complete']
bad, scored, n, nonpts_rounds = [], [], 0, []
for r in races:
    duel = 'duel' in (r.get('name') or '').lower()
    nonpts = bool(r['results']) and all(not (x['pts'] or 0) for x in r['results'])  # SimRacerHub scored the whole race as 0
    nonpts_rounds.append(r['round']) if nonpts else None
    ents = []
    for x in r['results']:
        ents.append({'driverId': x['driverId'], 'fin': x['fin'], 'stagePos': (11 - x['stage']) if x['stage'] else None,
                     'fastest': bool(x['bonus']) or (series == 'trucks' and not x['bonus'] and (x['pts'] or 0) - points._table(points.RULES[series]['finish'], x['fin'], 1) - (x['stage'] or 0) - (x['pen'] or 0) == 1), 'pen': x['pen'] or 0, 'duelPos': (x['fin'] + 1) // 2})
    P = points.score_race(series, ents, 'duel' if duel else 'race', non_points=nonpts)
    for x in r['results']:
        P[x['driverId']]['fin'] = x['fin']; n += 1
        if P[x['driverId']]['total'] != (x['pts'] or 0):
            bad.append((r['round'], r['track'][:24], nm[x['driverId']], x['fin'], P[x['driverId']]['total'], x['pts']))
    scored.append({'round': r['round'], 'kind': 'duel' if duel else 'race', 'nonPoints': nonpts, 'points': P})
print('%s: %d races, %d driver results, %d mismatches' % (series, len(races), n, len(bad)))
for b in bad[:15]:
    print('  Rd %s %s: %s P%s engine %s vs SimRacerHub %s' % b)
# season-level penalties: the standings' penalty column minus what was already taken off individual races
spen = {}
for o in d['official']['rows']:
    raced = sum((x['pen'] or 0) for r in races for x in r['results'] if x['driverId'] == o['driverId'])
    extra = (o.get('penPts') or 0) - raced
    if extra: spen[o['driverId']] = extra
print('non-points races:', nonpts_rounds or 'none', '| season-level penalties:', {nm[k]: v for k, v in spen.items()} or 'none')
S = {t['driverId']: t for t in points.standings(series, scored, spen)}
off = d['official']; cut = off.get('chaseCutoff') or 0
chk = [o for o in off['rows'] if o['pos'] > cut]
miss = [(nm[o['driverId']], S.get(o['driverId'], {}).get('pts'), o['pts']) for o in chk if S.get(o['driverId'], {}).get('pts') != o['pts']]
print('season totals (drivers outside the Chase reset): %d checked, %d mismatches' % (len(chk), len(miss)))
for m in miss[:10]:
    print('  %s engine %s vs SimRacerHub %s' % m)
cnt = [(nm[o['driverId']], S[o['driverId']]['counted'], o.get('counted')) for o in off['rows'] if o.get('counted') is not None and S.get(o['driverId'], {}).get('counted') != o.get('counted')]
print('races counted per driver: %d drivers checked, %d mismatches' % (len(off['rows']), len(cnt)), cnt[:5])
