#!/usr/bin/env python3
"""Import iRacing league results (from extract_league.js) into a season file, scored by tools/scoring/points.py.

  python3 tools/iracing/import_iracing.py EXPORT.json --series cup [--data data.json] [--dry-run]

- Matches each iRacing race to the schedule by date (+/- 1 day) and track; stores its subsession id on the race.
- Maps drivers by iRacing customer id (learned and saved on the driver as custId), else by name; new names become new drivers.
- Stage top 10: a steward's stage lap (--stewards export) wins, scored from the export's top 10 on that lap; else
  race['stageOverride'] (list of driver ids); else the lap-chart stage from the rule.
- Penalties: entries in data['penalties'] with raceId and points come off that race. With --stewards, the published
  steward decisions for each race replace that race's 'stw-' penalties first (incident points + applied penalties).

  --stewards FILE   the published steward reports, saved by tools/iracing/extract_stewards.js on the league site
  --admin FILE      the admin's schedule edits and entry list, saved by tools/iracing/extract_admin.js (applied first;
                    a fixed stage lap from the schedule is used unless a steward set one for that race)
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
    ap.add_argument('--stewards'); ap.add_argument('--admin')
    a = ap.parse_args()
    X = json.load(open(a.export)); D = json.load(open(a.data))
    FIXED = {}
    if a.admin:  # schedule edits made in the site's Admin tab
        for rid, v in (json.load(open(a.admin)).get('overrides') or {}).items():
            r = next((q for q in D['races'] if q['id'] == rid), None)
            if v.get('removed'):
                if r and r.get('status') != 'complete': D['races'].remove(r); print('  removed from schedule:', rid)
                continue
            if r is None:
                if not v.get('added'): continue
                r = {'id': rid, 'round': v.get('round') or len(D['races']) + 1, 'status': 'scheduled', 'results': [], 'recapUrl': '', 'dateOnly': True, 'srhId': None}
                D['races'].append(r); print('  added to schedule:', rid)
            for k in ('date', 'track', 'name', 'note', 'laps', 'round'):
                if v.get(k) not in (None, ''): r[k] = v[k]
            if v.get('nonPoints'): r['exhibition'] = True
            if v.get('stageLap'): FIXED[rid] = int(v['stageLap'])
        D['races'].sort(key=lambda q: (q.get('round') or 0))
        ent = json.load(open(a.admin)).get('entries') or {}
        if ent:  # the entry list: entered drivers get number/team/tier (and iRacing ID); everyone else is inactive
            byid = {d['id']: d for d in D['drivers']}
            for d in D['drivers']: d['active'] = d['id'] in ent
            for did, e in ent.items():
                d = byid.get(did)
                if d is None:
                    d = {'id': did, 'name': e.get('name') or did, 'custId': ''}; D['drivers'].append(d); print('  new driver from entry list:', d['name'])
                d.update({'number': str(e.get('number') or ''), 'team': e.get('team') or '', 'tier': int(e.get('tier') or 3), 'active': True})
                if e.get('name'): d['name'] = e['name']
                if e.get('custId'): d['custId'] = str(e['custId'])
                if e.get('free'): d['freeEntry'] = True
    STW = json.load(open(a.stewards))['races'] if a.stewards else {}
    if STW:  # published steward decisions become this race's penalties (replacing earlier copies)
        today = datetime.date.today().isoformat()
        D['penalties'] = [p for p in D.get('penalties', []) if not (str(p.get('id', '')).startswith('stw-') and p.get('raceId') in STW)]
        for rid, sd in STW.items():
            for k, i in (sd.get('inc') or {}).items():
                if (i.get('pts') or 0) > 0 and i.get('appeal') != 'overturned':
                    D['penalties'].append({'id': 'stw-%s-%s' % (rid, k), 'raceId': rid, 'driverId': i['driverId'], 'points': int(i['pts']), 'included': True,
                                           'infraction': i.get('offense', ''), 'decision': (i.get('sanction') or '') or '-%d pts' % i['pts'], 'created': today})
            for k, q in (sd.get('pen') or {}).items():
                D['penalties'].append({'id': 'stw-%s-%s' % (rid, k), 'raceId': rid, 'driverId': q['driverId'], 'points': int(q.get('pts') or 0), 'included': True,
                                       'infraction': q.get('reason') or 'Steward decision', 'decision': q.get('sanction', ''), 'created': today})
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
        stage_lap = x['stageLap']
        sl = (STW.get(r['id']) or {}).get('stageLap') or FIXED.get(r['id'])
        if sl and not duel:
            top = (x.get('tops') or {}).get(str(int(sl)))
            if top:
                stage_ids, stage_lap = [ids[c] for c in top if c in ids], int(sl)
                print('  Rd %s: stage lap %d (set by a steward or fixed on the schedule)' % (r['round'], stage_lap))
            else:
                print('  Rd %s: steward set stage lap %s but this export has no lap-by-lap order; re-export the race' % (r['round'], sl))
        spos = {did: i + 1 for i, did in enumerate(stage_ids)}
        ents = [{'driverId': ids[res['cust']], 'fin': res['fin'], 'stagePos': spos.get(ids[res['cust']]),
                 'fastest': res['cust'] == x['fastest'], 'pen': pens.get((r['id'], ids[res['cust']]), 0), 'duelPos': res['fin']} for res in x['results']]
        P = points.score_race(a.series, ents, 'duel' if duel else 'race', non_points=bool(r.get('nonPoints') or r.get('exhibition')))
        r['results'] = [{'driverId': ids[res['cust']], 'fin': res['fin'], 'start': res['start'], 'car': res['car'] or drivers[ids[res['cust']]].get('number', ''),
                         'pts': P[ids[res['cust']]]['total'], 'stage': P[ids[res['cust']]]['stage'], 'bonus': P[ids[res['cust']]]['bonus'],
                         'pen': P[ids[res['cust']]]['pen'], 'lapsComp': res['laps'], 'lapsLed': res['led'], 'inc': res['inc'],
                         'status': res['status'] or 'Running', 'bestLap': res['best']} for res in sorted(x['results'], key=lambda q: q['fin'])]
        r['status'] = 'complete'; r['source'] = 'iracing'; r['stageLap'] = stage_lap
        done.append((r['round'], r['track'], stage_lap, len(x['results'])))
    print('imported:', done or 'nothing')
    if a.dry_run:
        print('dry run: nothing written'); return D
    json.dump(D, open(a.data, 'w'), separators=(',', ':'))
    return D

if __name__ == '__main__':
    main()
