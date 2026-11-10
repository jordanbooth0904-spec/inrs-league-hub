"""Builds data/cup-2027.json: the 2027 INRS Cup schedule.

Follows NASCAR's 2027 Cup schedule (released Aug 26, 2026). INRS races are on the Thursday before each NASCAR
race at 8 PM Eastern, and the Duels run a week before the Daytona 500, as in 2026. Every race is 50% of the real
distance (rounded up). Where INRS ran the same track layout in 2026 at a different length (COTA, San Diego,
Watkins Glen) the 2026 INRS length is kept. The Clash is not run (INRS skipped it in 2026). The All-Star race is a
non-points exhibition. Stage lap = 33% of the race (floor); a caution within 5 laps of it moves it (see
tools/scoring/rules.json). Re-run after changing the list, then run tools/sync/season.py to rebuild seasons.json.
"""
import json, math, os, datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
# (NASCAR race date, INRS track name, real laps, INRS laps override, name, note, kind)
R = [
    ('2027-02-21', 'Daytona International Speedway Oval', 60, None, 'iNRS Duels @ Daytona', 'Duel points: 10 to the winner down to 1 for 10th', 'duel'),
    ('2027-02-21', 'Daytona International Speedway Oval', 200, None, 'iNRS Daytona 250', '', ''),
    ('2027-02-28', 'EchoPark Speedway (Atlanta) Oval', 260, None, '', '', ''),
    ('2027-03-07', 'Circuit of the Americas NASCAR West', 95, 48, '', '', ''),
    ('2027-03-14', 'Phoenix Raceway Oval w/open dogleg', 312, None, '', '', ''),
    ('2027-03-21', 'Las Vegas Motor Speedway Oval', 267, None, '', '', ''),
    ('2027-04-04', 'Darlington Raceway', 293, None, '', '', ''),
    ('2027-04-11', 'Bristol Motor Speedway Single Pit Roads', 500, None, '', '', ''),
    ('2027-04-18', 'Martinsville Speedway', 400, None, '', '', ''),
    ('2027-04-25', 'Talladega Superspeedway', 188, None, '', '', ''),
    ('2027-05-02', 'Texas Motor Speedway Oval', 267, None, '', '', ''),
    ('2027-05-09', 'Kansas Speedway Oval', 267, None, '', '', ''),
    ('2027-05-16', 'Dover Motor Speedway', 400, None, '', '', ''),
    ('2027-05-23', 'North Wilkesboro Speedway Oval', 250, None, 'iNRS All-Star Race', 'Non-points exhibition', 'exhibition'),
    ('2027-05-30', 'Charlotte Motor Speedway Oval', 400, None, 'iNRS World 300', '', ''),
    ('2027-06-06', 'Nashville Superspeedway', 300, None, '', '', ''),
    ('2027-06-13', 'Pocono Raceway', 160, None, '', '', ''),
    ('2027-06-20', 'Michigan International Speedway', 200, None, '', '', ''),
    ('2027-06-27', 'Chicagoland Speedway', 267, None, '', '', ''),
    ('2027-07-04', 'Iowa Speedway Oval', 350, None, '', '', ''),
    ('2027-07-11', 'Sonoma Raceway Cup Short', 110, None, '', '', ''),
    ('2027-07-18', 'EchoPark Speedway (Atlanta) Oval', 260, None, '', '', ''),
    ('2027-07-25', 'Indianapolis Motor Speedway NASCAR Oval', 160, None, 'iNRS Brickyard 200', '', ''),
    ('2027-08-01', 'Qualcomm Circuit (Naval Base Coronado)', 76, 38, 'San Diego Street Race', '', ''),
    ('2027-08-14', 'Bristol Motor Speedway Single Pit Roads', 500, None, '', '', ''),
    ('2027-08-22', 'World Wide Technology Raceway (Gateway) Oval', 240, None, '', '', ''),
    ('2027-08-28', 'Daytona International Speedway Oval', 160, None, '', '', ''),
    ('2027-09-05', 'Darlington Raceway', 367, None, 'Southern 250', 'Regular-season finale', ''),
    ('2027-09-11', 'Richmond Raceway', 400, None, '', 'The Chase begins', ''),
    ('2027-09-19', 'Watkins Glen International Cup', 100, 50, '', '', ''),
    ('2027-09-26', 'New Hampshire Motor Speedway Oval', 301, None, '', '', ''),
    ('2027-10-03', 'Kansas Speedway Oval', 267, None, '', '', ''),
    ('2027-10-10', 'Las Vegas Motor Speedway Oval', 267, None, '', '', ''),
    ('2027-10-17', 'Charlotte Motor Speedway Oval', 267, None, '', '', ''),
    ('2027-10-24', 'Phoenix Raceway Oval w/open dogleg', 312, None, '', '', ''),
    ('2027-10-31', 'Talladega Superspeedway', 188, None, '', '', ''),
    ('2027-11-07', 'Martinsville Speedway', 500, None, '', '', ''),
    ('2027-11-14', 'Homestead Miami Speedway Oval', 267, None, 'Championship', 'Season finale', ''),
]


def thursday_before(day, kind):
    d = datetime.date.fromisoformat(day)
    d -= datetime.timedelta(days=(d.weekday() - 3) % 7 or 7)  # the Thursday before (a Thursday race moves back a week)
    if kind == 'duel':
        d -= datetime.timedelta(days=7)
    return datetime.datetime(d.year, d.month, d.day, 20, 0, tzinfo=ET).isoformat()


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.join(here, '..', '..')
    main26 = json.load(open(os.path.join(root, 'data.json')))
    races = []
    for i, (day, track, real, laps, name, note, kind) in enumerate(R, 1):
        laps = laps or math.ceil(real / 2)
        r = {'id': 'r%02d' % i, 'round': i, 'name': name, 'track': track, 'date': thursday_before(day, kind), 'dateOnly': True,
             'laps': laps, 'srhId': None, 'recapUrl': '', 'status': 'scheduled', 'results': []}
        if kind != 'duel':
            r['stageLap'] = int(laps * 0.33)
        if kind == 'exhibition':
            r['exhibition'] = True
        if note:
            r['note'] = note
        races.append(r)
    drivers = [dict(d, team=d.get('team', '')) for d in main26['drivers']]
    out = {'series': 'cup', 'year': 2027, 'seasonId': None, 'updated': datetime.datetime.now(ET).isoformat(timespec='seconds'),
           'settings': {'name': 'INRS Cup Series', 'season': '2027', 'maxPerRace': 66, 'hubUrl': ''},
           'drivers': drivers, 'races': races, 'penalties': [],
           'official': {'rows': [], 'teams': [], 'source': 'inrs'}}
    json.dump(out, open(os.path.join(root, 'data', 'cup-2027.json'), 'w'), separators=(',', ':'))
    for r in races:
        print(r['round'], r['date'][:10], r['laps'], r.get('stageLap', '-'), r['track'], r['name'], r.get('note', ''))


if __name__ == '__main__':
    main()
