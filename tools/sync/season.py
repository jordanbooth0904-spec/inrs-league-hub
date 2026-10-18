#!/usr/bin/env python3
"""Convert full-season SimRacerHub exports (from extract_season.js) into the site's season files.

  python3 tools/sync/season.py EXPORT.json [EXPORT.json ...]

Each export becomes data/<series>-<year>.json in the same shape as data.json (drivers, races, penalties,
official). data/seasons.json is rebuilt from every season file present: the list for the header switcher
plus per-series track history ([season, round, date, event, track, pole, winner]).
The live Cup season stays in data.json (MAIN below) and is never written here.
"""
import json, re, sys, os, glob, datetime
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA = os.path.join(ROOT, 'data')
TZ = ZoneInfo('America/Indiana/Indianapolis')
MAIN = ('cup', 2026)
LABEL = {'cup': 'Cup', 'xfinity': 'Xfinity', 'trucks': 'Truck'}
RENAMED = {('xfinity', 2026): "O'Reilly"}  # Xfinity Series became the O'Reilly Series in 2026
FINAL = {'xfinity': 2026}  # last season ever run; once it is complete the weekly sync stops exporting it
SERIES_ORDER = ['cup', 'xfinity', 'trucks']
slug = lambda s: re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def num(v):
    try:
        x = float(str(v).replace(',', ''))
        return int(x) if x == int(x) else x
    except Exception:
        return None


def iso(date):
    return datetime.datetime.strptime(date, '%b %d, %Y').replace(hour=20, tzinfo=TZ).isoformat()


def convert(e):
    series, year = e['series'], int(e['year'])
    races, drivers, pens = [], {}, []
    upper = {}
    chase_next = None
    chase_starts = sum(1 for x in e['sched'] if not x[0] and x[3] == 'Chase Start')
    for rd, date, ev, track, laps, sid in e['sched']:
        if not rd:
            if track == 'Chase Start':
                chase_next = ev or 'Chase'
            continue
        rid = 'r%02d' % int(rd)
        r = {'id': rid, 'round': int(rd), 'name': ev, 'track': track, 'date': iso(date), 'dateOnly': True, 'laps': num(laps),
             'srhId': sid, 'recapUrl': '', 'status': 'scheduled', 'results': []}
        if chase_next:
            r['note'] = 'Chase begins' if chase_next == 'Chase' else chase_next if 'chase' in chase_next.lower() else 'Chase: ' + chase_next
            chase_next = None
        x = e['races'].get(rd)
        if x:
            H = x['H']
            g = lambda row, k: row[H.index(k)] if k in H and H.index(k) < len(row) else ''
            res = []
            for row in x['rows']:
                name = g(row, 'Driver')
                if not name or not g(row, 'Fin'):  # blank finish = registered but did not start
                    continue
                did = slug(name)
                upper[name.upper()] = did
                drivers[did] = {'id': did, 'name': name, 'number': g(row, 'Car #'), 'custId': '', 'team': '', 'active': True}
                st = g(row, 'Status')
                res.append({'driverId': did, 'fin': int(g(row, 'Fin')), 'start': num(g(row, 'St')), 'car': g(row, 'Car #'),
                            'pts': num(g(row, 'TotPts')) or 0, 'stage': num(g(row, 'StagePts')) or 0, 'bonus': num(g(row, 'BnsPts')) or 0,
                            'pen': num(g(row, 'PenPts')) or 0, 'lapsComp': num(g(row, 'Laps')), 'lapsLed': num(g(row, 'LapsLed')) or 0,
                            'inc': num(g(row, 'Inc')) or 0, 'status': st or 'Running', 'rating': num(g(row, 'DriverRating'))})
            r['results'] = res
            if not res:
                continue
            r['status'] = 'complete'
            for i, p in enumerate(x['pen']):
                pens.append({'id': 'srh-%s-%d' % (rd, i + 1), 'raceId': rid, 'driverId': slug(p[0]), 'infraction': p[2],
                             'decision': '-%s pts' % p[1], 'points': num(p[1]) or 0, 'included': True, 'created': r['date'][:10]})
        if r['status'] != 'complete' and r['date'][:10] < e['exported'][:10]:
            continue  # past round with no results on SimRacerHub (exhibition or cancelled)
        races.append(r)

    rows = []
    S = e['drivers']
    H = S['H']
    for r in S['rows']:
        g = lambda k: num(r[H.index(k)]) if k in H else None
        nm = r[H.index('DRIVER')]
        did = upper.get(nm.upper()) or slug(nm)
        if did not in drivers:
            drivers[did] = {'id': did, 'name': nm.title(), 'number': '', 'custId': '', 'team': '', 'active': True}
        team = r[H.index('TEAM')] if 'TEAM' in H else ''
        drivers[did]['team'] = team
        rows.append({'pos': int(r[0]), 'driverId': did, 'starts': g('STARTS'), 'counted': g('RACES COUNTED'), 'pts': g('TOT PTS'),
                     'behLead': g('BEH LEAD') or 0, 'behNext': g('BEH NEXT') or 0, 'wins': g('WINS'), 'led': g('LAPS LED'), 't5': g('T-5'),
                     't10': g('T-10'), 'stgWins': g('STG WINS'), 'stgPts': g('STG PTS'), 'bnsPts': g('BNS PTS'), 'penPts': g('PEN PTS'),
                     'laps': g('LAPS'), 'inc': g('INCS'), 'incPerRace': g('INC/ RACE'), 'poles': g('POLES'), 'podiums': g('PODIUMS'),
                     'rating': g('AVG RATING'), 'team': team})
    # Laps led is missing from some seasons' standings: total it from the race results.
    led = {}
    for rc in races:
        for x in rc['results']:
            led[x['driverId']] = led.get(x['driverId'], 0) + (x['lapsLed'] or 0)
    for o in rows:
        if o['led'] is None:
            o['led'] = led.get(o['driverId'], 0)

    teams = []
    T = e.get('teams')
    if T and 'TEAM' in T['H'] and 'TOT PTS' in T['H']:
        TH = T['H']
        for i, t in enumerate(T['rows']):
            g = lambda k: num(t[TH.index(k)]) if k in TH else None
            teams.append({'pos': g('POS') or i + 1, 'team': t[TH.index('TEAM')], 'starts': g('STARTS'), 'counted': g('RACES COUNTED'),
                          'pts': g('TOT PTS'), 'pen': g('PEN PTS') or 0, 'behLead': g('BEH LEAD') or 0, 'wins': g('WINS'), 'inc': g('INCS')})
        if 'POS' not in TH:  # per-race layout (2022): order by points
            teams.sort(key=lambda t: -(t['pts'] or 0))
            for i, t in enumerate(teams):
                t['pos'] = i + 1

    done = [r['round'] for r in races if r['status'] == 'complete']
    last = max((r['date'][:10] for r in races if r['status'] == 'complete'), default=e['exported'][:10])
    as_of = last if all(r['status'] == 'complete' for r in races) else e['exported'][:10]
    official = {'rows': rows, 'teams': teams, 'asOf': as_of, 'afterRound': max(done) if done else 0,
                'chaseCutoff': 0, 'source': 'SimRacerHub'}
    # 2026 format: one Chase start, top N reset to ~2,000+ pts, straight points after that (no eliminations).
    # N is where the reset shows in the standings (the points more than halve from one driver to the next).
    if year >= 2026 and chase_starts == 1 and any(r.get('note') for r in races if r['status'] == 'complete'):
        pts = [o['pts'] or 0 for o in rows]
        cut = next((i + 1 for i in range(min(len(pts) - 1, 30)) if pts[i] > 1000 and pts[i + 1] * 2 < pts[i]), 0)
        official['chaseCutoff'] = cut
    title = 'INRS %s Series' % RENAMED.get((series, year), LABEL[series])
    settings = {'name': title, 'season': str(year), 'hubUrl': 'https://www.simracerhub.com/scoring/season_standings.php?season_id=%s' % e['seasonId'],
                'maxPerRace': max([x['pts'] for r in races for x in r['results']] or [66])}
    return {'series': series, 'year': year, 'seasonId': e['seasonId'], 'updated': e['exported'][:10], 'settings': settings,
            'drivers': sorted(drivers.values(), key=lambda x: x['id']), 'races': races,
            'penalties': pens, 'official': official}


def lines(s):
    """One row per driver for the career and records pages:
    [id, name, number, pos, pts, starts, wins, t5, t10, poles, led, inc, finSum, finN, team]"""
    fin, cnt = {}, {}
    for r in s['races']:
        if r.get('exhibition'):
            continue
        for x in r['results']:
            c = cnt.setdefault(x['driverId'], dict(starts=0, wins=0, t5=0, t10=0, poles=0, led=0, inc=0))
            f = x.get('fin') or 0
            c['starts'] += 1
            c['wins'] += f == 1
            c['t5'] += 0 < f <= 5
            c['t10'] += 0 < f <= 10
            c['poles'] += x.get('start') == 1
            c['led'] += x.get('lapsLed') or 0
            c['inc'] += x.get('inc') or 0
            if f:
                a = fin.setdefault(x['driverId'], [0, 0])
                a[0] += f
                a[1] += 1
    D = {d['id']: d for d in s['drivers']}
    out = []
    for o in s['official']['rows']:
        d = D[o['driverId']]
        f = fin.get(o['driverId'], [0, 0])
        c = cnt.get(o['driverId'], {})
        # SimRacerHub leaves races like the Daytona Duels out of its counts; the league counts them, so take the
        # higher of SimRacerHub's number and the count from the results (same rule as offMerge in index.html).
        m = {k: max(o.get(k) or 0, c.get(k, 0)) for k in ('starts', 'wins', 't5', 't10', 'poles', 'led', 'inc')}
        out.append([o['driverId'], d['name'], d.get('number', ''), o['pos'], o['pts'], m['starts'], m['wins'], m['t5'],
                    m['t10'], m['poles'], m['led'], m['inc'], f[0], f[1], o.get('team') or ''])
    return out


def history(season):
    out = []
    names = {d['id']: d['name'] for d in season['drivers']}
    for r in season['races']:
        if r['status'] != 'complete':
            continue
        w = next((x for x in r['results'] if x['fin'] == 1), None)
        p = next((x for x in r['results'] if x['start'] == 1), None)
        d = datetime.datetime.fromisoformat(r['date'])
        out.append([season['year'], str(r['round']), d.strftime('%b ') + str(d.day), r['name'], r['track'],
                    names.get(p['driverId'], '') if p else '', names.get(w['driverId'], '') if w else ''])
    return out


def main():
    os.makedirs(DATA, exist_ok=True)
    for f in sys.argv[1:]:
        e = json.load(open(f))
        if (e['series'], int(e['year'])) == MAIN:
            print('skip %s (live season lives in data.json)' % f)
            continue
        fy = FINAL.get(e['series'])
        if fy and int(e['year']) > fy:
            sys.exit('%s: the %s series ended after %d; nothing to import.' % (f, e['series'], fy))
        if e.get('missing'):
            sys.exit('%s is missing races %s; re-export it.' % (f, e['missing']))
        s = convert(e)
        fn = os.path.join(DATA, '%s-%s.json' % (s['series'], s['year']))
        json.dump(s, open(fn, 'w'), separators=(',', ':'))
        lead = s['official']['rows'][0] if s['official']['rows'] else None
        nm = {d['id']: d['name'] for d in s['drivers']}
        print('%s: %d races (%d complete), %d drivers, %d teams, leader %s' % (os.path.basename(fn), len(s['races']),
              sum(r['status'] == 'complete' for r in s['races']), len(s['official']['rows']), len(s['official']['teams']),
              nm.get(lead['driverId']) if lead else '-'))

    seasons, hist = [], {k: [] for k in SERIES_ORDER}
    seasons.append({'key': '%s-%s' % MAIN, 'series': MAIN[0], 'year': MAIN[1], 'main': True})
    for fn in sorted(glob.glob(os.path.join(DATA, '*-*.json'))):
        s = json.load(open(fn))
        done = sum(r['status'] == 'complete' for r in s['races'])
        champ = None
        if done == len(s['races']) and s['official']['rows']:
            champ = next(d['name'] for d in s['drivers'] if d['id'] == s['official']['rows'][0]['driverId'])
        seasons.append({'key': '%s-%s' % (s['series'], s['year']), 'series': s['series'], 'year': s['year'],
                        'file': 'data/' + os.path.basename(fn), 'champion': champ,
                        'championId': s['official']['rows'][0]['driverId'] if champ else None, 'done': done == len(s['races']),
                        'races': done, 'lines': lines(s),
                        'lastRace': max((r['date'][:10] for r in s['races'] if r['status'] == 'complete'), default=None),
                        'final': FINAL.get(s['series']) == s['year']})
        hist[s['series']] += history(s)
    seasons.sort(key=lambda x: (SERIES_ORDER.index(x['series']), -x['year']))
    for k in hist:
        hist[k].sort(key=lambda h: (h[0], int(h[1])))
    idx = {'seasons': seasons, 'labels': LABEL, 'history': hist}
    json.dump(idx, open(os.path.join(DATA, 'seasons.json'), 'w'), separators=(',', ':'))
    print('seasons.json: ' + ', '.join(s['key'] for s in seasons))


if __name__ == '__main__':
    main()
