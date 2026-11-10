#!/usr/bin/env python3
"""Build a season's standings table (data['official']['rows']) from its race results, using points.py.

  python3 tools/scoring/standings.py data.json cup [--write] [--drop N] [--check]

Rows carry the same fields the site already reads from SimRacerHub. --check compares against the rows currently in
the file (drivers outside the Chase reset, since the reset isn't modeled yet). --write replaces them.
Penalties: race penalties are already in each result's 'pen'; season-level penalties come from data['seasonPenalties']
({driverId: points <= 0}). Teams are left to the manual team standings.
"""
import json, sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import points

def build(D, series, drop=None):
    races = [r for r in sorted(D['races'], key=lambda r: r['round']) if r['status'] == 'complete' and r.get('results')]
    scored = []
    for r in races:
        duel = 'duel' in (r.get('name') or '').lower()
        P = {x['driverId']: {'finish': 0, 'stage': x.get('stage') or 0, 'bonus': x.get('bonus') or 0, 'pen': x.get('pen') or 0,
                             'total': x.get('pts') or 0, 'fin': x['fin']} for x in r['results']}
        scored.append({'kind': 'duel' if duel else 'race', 'nonPoints': bool(r.get('nonPoints')) or all(not (x.get('pts') or 0) for x in r['results']), 'points': P})
    S = {t['driverId']: t for t in points.standings(series, scored, D.get('seasonPenalties'), drop=drop)}
    team = {d['id']: d.get('team', '') for d in D['drivers']}
    rows = []
    for did, t in S.items():
        R = [x for r, sc in zip(races, scored) if sc['kind'] != 'duel' and not sc['nonPoints'] for x in r['results'] if x['driverId'] == did]  # stats skip Duels and non-points races
        n = len(R)
        rows.append({'driverId': did, 'pts': t['pts'], 'starts': n, 'counted': t['counted'], 'wins': sum(x['fin'] == 1 for x in R),
                     'led': sum(x.get('lapsLed') or 0 for x in R), 't5': sum(x['fin'] <= 5 for x in R), 't10': sum(x['fin'] <= 10 for x in R),
                     'podiums': sum(x['fin'] <= 3 for x in R), 'poles': sum((x.get('start') or 0) == 1 for x in R),
                     'stgWins': sum((x.get('stage') or 0) == points.RULES[series]['stage'][0] for x in R), 'stgPts': t['stagePts'],
                     'bnsPts': t['bonusPts'], 'penPts': t['penPts'], 'laps': sum(x.get('lapsComp') or 0 for x in R),
                     'inc': sum(x.get('inc') or 0 for x in R), 'incPerRace': round(sum(x.get('inc') or 0 for x in R) / n, 2) if n else 0,
                     'rating': None, 'team': team.get(did, '')})
    rows.sort(key=lambda o: (-o['pts'], -o['wins'], -o['t5']))
    for i, o in enumerate(rows):
        o['pos'] = i + 1; o['behLead'] = rows[0]['pts'] - o['pts']; o['behNext'] = (rows[i - 1]['pts'] - o['pts']) if i else 0
    return rows, max([r['round'] for r in races] or [0])

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('data'); ap.add_argument('series')
    ap.add_argument('--write', action='store_true'); ap.add_argument('--check', action='store_true'); ap.add_argument('--drop', type=int)
    a = ap.parse_args(); D = json.load(open(a.data))
    rows, after = build(D, a.series, a.drop)
    if a.check:
        cut = D['official'].get('chaseCutoff') or 0
        old = {o['driverId']: o for o in D['official']['rows'] if o['pos'] > cut}
        keys = ['pts', 'starts', 'counted', 'wins', 'led', 't5', 't10', 'podiums', 'poles', 'stgWins', 'stgPts', 'bnsPts', 'penPts', 'laps', 'inc']
        diff = [(o['driverId'], k, o[k], old[o['driverId']].get(k)) for o in rows if o['driverId'] in old for k in keys if old[o['driverId']].get(k) is not None and o[k] != old[o['driverId']].get(k)]
        print('checked %d drivers x %d fields: %d differences' % (len(old), len(keys), len(diff)))
        for x in diff[:20]: print('  ', x)
    if a.write:
        D['official']['rows'] = rows; D['official']['afterRound'] = after; D['official']['source'] = 'INRS points engine'
        json.dump(D, open(a.data, 'w'), separators=(',', ':')); print('standings written:', len(rows), 'drivers')
