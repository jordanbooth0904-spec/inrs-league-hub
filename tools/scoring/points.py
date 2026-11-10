#!/usr/bin/env python3
"""INRS points engine.

score_race(series, entries, kind='race') -> {driverId: {'finish','stage','bonus','pen','total'}}
  entries: [{'driverId', 'fin', 'stagePos' (1-based or None), 'fastest' (bool), 'pen' (<= 0), 'duelPos' (Duels only)}]
standings(series, races) -> season totals and stats, sorted (no Chase reset yet).
"""
import json, os
RULES = json.load(open(os.path.join(os.path.dirname(__file__), 'rules.json')))

def _table(tbl, pos, floor=0):
    if not pos or pos < 1:
        return 0
    return tbl[pos - 1] if pos <= len(tbl) else floor

def score_race(series, entries, kind='race', non_points=False):
    R = RULES[series]
    out = {}
    for e in entries:
        if non_points:
            out[e['driverId']] = {'finish': 0, 'stage': 0, 'bonus': 0, 'pen': 0, 'total': 0}
            continue
        if kind == 'duel':
            fin = _table(R['duel'] or [], e.get('duelPos') or e['fin'])
            stage = bonus = 0
        else:
            fin = _table(R['finish'], e['fin'], R['finishFloor'])
            stage = _table(R['stage'], e.get('stagePos'))
            bonus = R['fastestLap'] if e.get('fastest') else 0
        pen = e.get('pen') or 0
        out[e['driverId']] = {'finish': fin, 'stage': stage, 'bonus': bonus, 'pen': pen, 'total': fin + stage + bonus + pen}
    return out

def standings(series, races, season_pen=None, drop=None):
    """Season totals. races: [{'kind': 'race'|'duel', 'nonPoints': bool, 'points': score_race(...) with 'fin' added}].
    Only each driver's best N regular races count (judged before penalties; penalties always count), N = points races in the season minus RULES[series]['dropWorst']
    (Duel points always count). season_pen: {driverId: points (<= 0)} taken off the season total, not one race."""
    regular = [r for r in races if r['kind'] != 'duel' and not r.get('nonPoints')]
    drop = RULES[series].get('dropWorst', 0) if drop is None else drop  # pass drop=2 to re-score 2026
    keep = max(0, len(regular) - drop)
    T, per = {}, {}
    for r in races:
        for did, p in r['points'].items():
            t = T.setdefault(did, {'driverId': did, 'pts': 0, 'starts': 0, 'counted': 0, 'wins': 0, 'stagePts': 0, 'bonusPts': 0, 'penPts': 0, 'dropped': []})
            t['stagePts'] += p['stage']; t['bonusPts'] += p['bonus']; t['penPts'] += p['pen']
            if r['kind'] == 'duel':
                t['pts'] += p['total']
            elif not r.get('nonPoints'):
                # drops compare race points before penalties; penalties always count, even in a dropped race
                per.setdefault(did, []).append(p['total'] - p['pen']); t['pts'] += p['pen']; t['starts'] += 1
                t['wins'] += 1 if p.get('fin') == 1 else 0
    for did, L in per.items():
        L = sorted(L, reverse=True)
        T[did]['pts'] += sum(L[:keep]); T[did]['counted'] = min(len(L), keep); T[did]['dropped'] = L[keep:]
    for did, p in (season_pen or {}).items():
        if did in T:
            T[did]['pts'] += p; T[did]['penPts'] += p
    return sorted(T.values(), key=lambda t: (-t['pts'], -t['wins']))
