#!/usr/bin/env python3
"""Apply a SimRacerHub / YouTube extract to data.json.

  python3 tools/sync/apply.py --known
      Print the SimRacerHub schedule ids already stored as complete (paste into window.__KNOWN).

  python3 tools/sync/apply.py MAIN.json [--teams TEAMS.json] [--youtube YT.json] [--today YYYY-MM-DD]
      MAIN.json is the output of extract_main.js, TEAMS.json of extract_teams.js, YT.json of extract_youtube.js.
      Updates data.json in place, prints a summary, and writes tools/sync/out/db_docs.json:
      the Claude app database documents that changed ({collection, doc_id, data, exists}).
"""
import json, re, sys, os, datetime
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA = os.path.join(ROOT, 'data.json')
OUT = os.path.join(os.path.dirname(__file__), 'out')
TZ = ZoneInfo('America/Indiana/Indianapolis')

TRACKS = [(r'Daytona', 'daytona'), (r'Charlotte.*Roval', 'charlotte-roval'), (r'Charlotte', 'charlotte'), (r'Gateway|World Wide Technology', 'gateway'),
          (r'Sonoma', 'sonoma'), (r'Nashville', 'nashville'), (r'Road America', 'road-america'), (r'Atlanta', 'atlanta'), (r'New Hampshire', 'new-hampshire'),
          (r'Pocono', 'pocono'), (r'Indianapolis.*Road', 'indy-road'), (r'Indianapolis', 'indianapolis'), (r'Michigan', 'michigan'), (r'Richmond', 'richmond'),
          (r'Watkins Glen', 'watkins-glen'), (r'Darlington', 'darlington'), (r'Kansas', 'kansas'), (r'Bristol.*Dirt', 'bristol-dirt'), (r'Bristol', 'bristol'),
          (r'Texas', 'texas'), (r'Talladega', 'talladega'), (r'Las Vegas|Vegas', 'las-vegas'), (r'Homestead|Miami', 'homestead'), (r'Martinsville', 'martinsville'),
          (r'Phoenix', 'phoenix'), (r'Coliseum', 'la-coliseum'), (r'Auto Club', 'auto-club'), (r'Circuit of the Americas|COTA', 'cota'), (r'Dover', 'dover'),
          (r'North Wilkesboro|Wilkesboro', 'north-wilkesboro'), (r'Chicago Street', 'chicago-street'), (r'Chicagoland', 'chicagoland'), (r'Iowa', 'iowa'),
          (r'Coronado|San Diego', 'san-diego')]


def track_key(name):
    for pat, key in TRACKS:
        if re.search(pat, name or '', re.I):
            return key
    return re.sub(r'[^a-z0-9]+', '-', (name or '').lower()).strip('-')


slug = lambda s: re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def num(v):
    try:
        x = float(str(v).replace(',', ''))
        return int(x) if x == int(x) else x
    except Exception:
        return None


def checksum(rows):
    n = lambda v: num(v) or 0
    return [len(rows), round(sum(n(x[0]) * 7 + n(x[1]) * 3 + n(x[2]) + n(x[4]) * 11 + n(x[5]) * 13 + n(x[6]) * 17 + n(x[7]) * 19 + n(x[8]) + n(x[9]) * 23 + n(x[10]) * 29 + n(x[12]) * 10 for x in rows))]


def main():
    d = json.load(open(DATA))
    if '--known' in sys.argv:
        print(json.dumps([r['srhId'] for r in d['races'] if r.get('status') == 'complete' and r.get('srhId')]))
        return
    args = sys.argv[1:]
    get = lambda flag: args[args.index(flag) + 1] if flag in args else None
    main_in = json.load(open(args[0]))
    today = get('--today') or datetime.date.today().isoformat()
    races = {r['id']: r for r in d['races']}
    drivers = {x['id']: x for x in d['drivers']}
    pens = {p['id']: p for p in d['penalties']}
    changed = set()
    log = []

    # schedule
    for rd, date, ev, track, laps, sid in main_in['sched']:
        rid = 'r%02d' % int(rd)
        dt = datetime.datetime.strptime(date, '%b %d, %Y').replace(hour=20, tzinfo=TZ).isoformat()
        r = races.get(rid) or {'round': int(rd), 'status': 'scheduled', 'results': [], 'recapUrl': '', 'dateOnly': True}
        new = dict(r, round=int(rd), name=ev, track=track, date=dt, laps=num(laps), srhId=sid or r.get('srhId', ''))
        if rid not in races:
            new['id'] = rid
            log.append('new race on schedule: Rd %s %s' % (rd, track))
        if new != r:
            races[rid] = new
            changed.add(('races', rid))

    # newly completed races
    for rd, blob in sorted(main_in['races'].items(), key=lambda kv: int(kv[0])):
        rows = [x.split('~') for x in blob['r'].split('^') if x]
        exp = main_in['check'].get(rd)
        got = checksum(rows)
        if exp and got != exp:
            sys.exit('Checksum mismatch for round %s: got %s expected %s. Re-run the extract; do not hand-edit.' % (rd, got, exp))
        rid = 'r%02d' % int(rd)
        res = []
        for x in rows:
            did = slug(x[3])
            if did not in drivers:
                drivers[did] = {'id': did, 'name': x[3], 'number': x[2], 'custId': '', 'team': '', 'active': True}
                changed.add(('drivers', did))
                log.append('new driver: %s #%s' % (x[3], x[2]))
            elif str(drivers[did].get('number')) != x[2]:
                drivers[did]['number'] = x[2]
                changed.add(('drivers', did))
            res.append({'driverId': did, 'fin': int(x[0]), 'start': num(x[1]), 'car': x[2], 'pts': num(x[4]) or 0, 'stage': num(x[5]) or 0,
                        'bonus': num(x[6]) or 0, 'pen': num(x[7]) or 0, 'lapsComp': num(x[8]), 'lapsLed': num(x[9]) or 0, 'inc': num(x[10]) or 0,
                        'status': x[11] or 'Running', 'rating': num(x[12])})
        r = races[rid]
        races[rid] = dict(r, results=res, status='complete')
        changed.add(('races', rid))
        win = next((q for q in res if q['fin'] == 1), None)
        log.append('results added: Rd %s %s (%d drivers, winner %s)' % (rd, r['track'], len(res), drivers[win['driverId']]['name'] if win else '?'))
        for i, p in enumerate([p for p in blob['p'].split('^') if p]):
            a = p.split('~')
            pid = 'srh-%s-%d' % (rd, i + 1)
            pens[pid] = {'id': pid, 'raceId': rid, 'driverId': slug(a[0]), 'infraction': a[2], 'decision': '-%s pts' % a[1], 'points': int(float(a[1])),
                         'included': True, 'created': r['date'][:10]}
            changed.add(('penalties', pid))

    # official standings
    S = main_in['standings']
    H = S['H']
    col = lambda name: H.index(name)
    names = {x['name'].upper(): x['id'] for x in drivers.values()}
    rows = []
    for r in S['rows']:
        g = lambda name: num(r[col(name)])
        did = names.get(r[col('DRIVER')]) or slug(r[col('DRIVER')])
        if did not in drivers:
            sys.exit('Standings driver %s not found among drivers. Stop and report.' % r[col('DRIVER')])
        team = r[col('TEAM')]
        if drivers[did].get('team') != team:
            drivers[did]['team'] = team
            changed.add(('drivers', did))
        rows.append({'pos': int(r[0]), 'driverId': did, 'starts': g('STARTS'), 'counted': g('RACES COUNTED'), 'pts': g('TOT PTS'), 'behLead': g('BEH LEAD') or 0,
                     'behNext': g('BEH NEXT') or 0, 'wins': g('WINS'), 'led': g('LAPS LED'), 't5': g('T-5'), 't10': g('T-10'), 'stgWins': g('STG WINS'),
                     'stgPts': g('STG PTS'), 'bnsPts': g('BNS PTS'), 'penPts': g('PEN PTS'), 'laps': g('LAPS'), 'inc': g('INCS'), 'incPerRace': g('INC/ RACE'),
                     'poles': g('POLES'), 'podiums': g('PODIUMS'), 'rating': g('AVG RATING'), 'team': team})
    done_rounds = [r['round'] for r in races.values() if r.get('status') == 'complete' and r.get('results')]
    off = dict(d.get('official') or {}, rows=rows, asOf=today, afterRound=max(done_rounds) if done_rounds else 0)
    off.setdefault('chaseCutoff', 16)
    off.setdefault('source', 'SimRacerHub')

    if get('--teams'):
        T = json.load(open(get('--teams')))
        off['teams'] = [{'pos': int(t[0]), 'team': t[1], 'starts': num(t[2]), 'counted': num(t[3]), 'pts': num(t[4]), 'pen': num(t[5]),
                         'behLead': num(t[6]) or 0, 'wins': num(t[7]), 'inc': num(t[8])} for t in T]
    d['official'] = off
    changed.add(('official', 'standings'))

    # recaps from YouTube
    if get('--youtube'):
        vids = json.load(open(get('--youtube')))
        used = {r.get('recapUrl', '') for r in races.values()}
        for vid, title, desc, pub, length in vids:
            url = 'https://www.youtube.com/watch?v=' + vid
            if url in used or not re.search(r'recap', title, re.I) or not pub:
                continue
            pdate = pub[:10]
            key = track_key(title + ' ' + desc)
            cands = [r for r in races.values() if r.get('status') == 'complete' and not r.get('recapUrl') and track_key(r['track']) == key and r['date'][:10] <= pdate]
            if not cands:
                log.append('recap not matched (check by hand): %s "%s"' % (url, title))
                continue
            r = max(cands, key=lambda r: r['date'])
            races[r['id']] = dict(r, recapUrl=url)
            changed.add(('races', r['id']))
            log.append('recap linked: Rd %s %s <- "%s"' % (r['round'], r['track'], title))

    d['races'] = sorted(races.values(), key=lambda r: r['round'])
    d['drivers'] = sorted(drivers.values(), key=lambda x: x['id'])
    d['penalties'] = sorted(pens.values(), key=lambda x: x['id'])
    d['updated'] = today
    json.dump(d, open(DATA, 'w'), separators=(',', ':'))

    os.makedirs(OUT, exist_ok=True)
    coll = {'races': 'league/main/races', 'drivers': 'league/main/drivers', 'penalties': 'league/main/penalties', 'official': 'league/main/official'}
    docs = []
    for kind, did in sorted(changed):
        if kind == 'official':
            data = off
        else:
            src = {'races': races, 'drivers': drivers, 'penalties': pens}[kind][did]
            data = {k: v for k, v in src.items() if k != 'id'}
        fn = os.path.join(OUT, '%s__%s.json' % (kind, did))
        json.dump(data, open(fn, 'w'))
        docs.append({'collection': coll[kind], 'doc_id': did, 'file_path': fn})
    json.dump(docs, open(os.path.join(OUT, 'db_docs.json'), 'w'), indent=1)
    lead = rows[0] if rows else None
    print('\n'.join(log) or 'no new races')
    print('standings: %d drivers, leader %s %s pts, after round %s' % (len(rows), drivers[lead['driverId']]['name'] if lead else '-', lead['pts'] if lead else '-', off['afterRound']))
    print('db docs to write: %d (see tools/sync/out/db_docs.json)' % len(docs))


if __name__ == '__main__':
    main()
