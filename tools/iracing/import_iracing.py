#!/usr/bin/env python3
"""Import iRacing league results (from extract_league.js) into a season file, scored by tools/scoring/points.py.

  python3 tools/iracing/import_iracing.py EXPORT.json --series cup [--data data.json] [--dry-run]

- Matches each iRacing race to the schedule by date (+/- 1 day) and track; stores its subsession id on the race.
- Maps drivers by iRacing customer id (learned and saved on the driver as custId), else by name; new names become new drivers.
- Stage top 10: race['stageOverride'] (list of driver ids, set by a steward) wins over the lap-chart stage.
- Penalties: entries in data['penalties'] with raceId and points come off that race; scoring then rebuilds the standings.
Results are marked source 'iracing'. The Chase reset is not applied yet (see tools/scoring/README.md).
"""
import json, os, re, sys, datetime, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scoring')); sys.path.insert(0, os.path.join(HERE, '..', 'sync'))
import points
from apply import track_key

NICK = {'tony': 'anthony', 'mike': 'michael', 'matt': 'matthew', 'jake': 'jacob', 'joe': 'joseph'}
def nkey(name):
    w = re.sub(r'[^a-z ]', '', name.lower()).split()
    w = [re.sub(r'\d+$', '', x) for x in w]
    return ' '.join([NICK.get(w[0], w[0])] + w[1:]) if w else ''
slug = lambda s: re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('export'); ap.add_argument('--series', required=True)
    ap.add_argument('--data', default='data.json'); ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    X = json.load(open(a.export)); D = json.load(open(a.data))
    drivers = {d['id']: d for d in D['drivers']}
    by_cust = {str(d.get('custId')): d['id'] for d in D['drivers'] if d.get('custId')}
    by_name = {}
    for d in D['drivers']:
        by_name.setdefault(nkey(d['name']), d['id'])
    def who(r):
        c = str(r['cust'])
        if c in by_cust: return by_cust[c]
        did = by_name.get(nkey(r['name']))
        if not did:
            did = slug(r['name']); n = 2
            while did in drivers: did = '%s-%d' % (slug(r['name']), n); n += 1
            drivers[did] = {'id': did, 'name': r['name'], 'number': r['car'], 'custId': c, 'team': '', 'active': True}
            D['drivers'].append(drivers[did]); print('  new driver:', r['name'], '->', did)
        drivers[did]['custId'] = c; by_cust[c] = did
        return did
    pens = {}
    for p in D.get('penalties', []):
        if p.get('included', True) and p.get('raceId'):
            pens.setdefault((p['raceId'], p['driverId']), 0); pens[(p['raceId'], p['driverId'])] -= abs(p.get('points') or 0)
    done = []
    for x in X['races']:
        day = datetime.datetime.fromisoformat(x['launch'].replace('Z', '+00:00')).astimezone(datetime.timezone(datetime.timedelta(hours=-5))).date()
        cand = [r for r in D['races'] if abs((datetime.date.fromisoformat(r['date'][:10]) - day).days) <= 1 and track_key(r['track']) == track_key(x['track'])]
        if not cand:
            print('  no scheduled race for', x['track'], day, '(subsession %s) - skipped' % x['subsession']); continue
        r = cand[0]; r['irSubsession'] = x['subsession']
        duel = 'duel' in (r.get('name') or '').lower()
        ids = {res['cust']: who(res) for res in x['results']}
        stage_ids = r.get('stageOverride') or [ids[c] for c in x['stage'] if c in ids]
        spos = {did: i + 1 for i, did in enumerate(stage_ids)}
        ents = [{'driverId': ids[res['cust']], 'fin': res['fin'], 'stagePos': spos.get(ids[res['cust']]),
                 'fastest': res['cust'] == x['fastest'], 'pen': pens.get((r['id'], ids[res['cust']]), 0), 'duelPos': res['fin']} for res in x['results']]
        P = points.score_race(a.series, ents, 'duel' if duel else 'race', non_points=bool(r.get('nonPoints')))
        r['results'] = [{'driverId': ids[res['cust']], 'fin': res['fin'], 'start': res['start'], 'car': res['car'] or drivers[ids[res['cust']]].get('number', ''),
                         'pts': P[ids[res['cust']]]['total'], 'stage': P[ids[res['cust']]]['stage'], 'bonus': P[ids[res['cust']]]['bonus'],
                         'pen': P[ids[res['cust']]]['pen'], 'lapsComp': res['laps'], 'lapsLed': res['led'], 'inc': res['inc'],
                         'status': res['status'] or 'Running', 'bestLap': res['best']} for res in sorted(x['results'], key=lambda q: q['fin'])]
        r['status'] = 'complete'; r['source'] = 'iracing'; r['stageLap'] = x['stageLap']
        done.append((r['round'], r['track'], x['stageLap'], len(x['results'])))
    print('imported:', done or 'nothing')
    if a.dry_run:
        print('dry run: nothing written'); return D
    json.dump(D, open(a.data, 'w'), separators=(',', ':'))
    return D

if __name__ == '__main__':
    main()
