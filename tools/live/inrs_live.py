"""INRS live timing helper.

Run on race night while iRacing is open and you are in the league session (driving, spectating or
broadcasting). Every few seconds it reads iRacing's live timing (read-only, through iRacing's official
telemetry SDK) and sends practice, qualifying and race positions to the INRS website's live database,
so the Sportsbook odds can move. Close the window to stop it.

Setup once: put the database URL and secret in inrs_live_config.local.json (same folder). That file is
ignored by git, so the secret never ends up on GitHub. inrs_live_config.json is only the blank template.
"""
import json, os, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_FILE = os.path.join(HERE, 'inrs_live_config.local.json')  # real settings, ignored by git
TEMPLATE = os.path.join(HERE, 'inrs_live_config.json')  # committed blank template
EVERY = 5  # seconds between updates

try:
    import irsdk
except ImportError:
    sys.exit('pyirsdk is missing. Run START_INRS_LIVE.bat (it installs it), or: py -m pip install pyirsdk')


def filled(c):
    sec = (c or {}).get('secret') or ''
    return bool(sec) and 'PASTE' not in sec


def load_cfg():
    """Read the private settings file. If the secret was typed into the committed template instead,
    move it into the private file and blank the template, so a later commit can't publish it."""
    try:
        tpl = json.load(open(TEMPLATE, encoding='utf-8'))
    except Exception:
        tpl = None
    if filled(tpl):
        if not os.path.exists(CFG_FILE):
            json.dump(tpl, open(CFG_FILE, 'w', encoding='utf-8'), indent=2)
        json.dump({'databaseURL': 'PASTE the Realtime Database URL here, like https://inrs-league-hub-default-rtdb.firebaseio.com',
                   'secret': 'PASTE the database secret here'}, open(TEMPLATE, 'w', encoding='utf-8'), indent=2)
        print('Moved your secret from inrs_live_config.json into inrs_live_config.local.json (kept off GitHub).')
    try:
        c = json.load(open(CFG_FILE, encoding='utf-8'))
    except FileNotFoundError:
        sys.exit('Create inrs_live_config.local.json next to this script: copy inrs_live_config.json, '
                 'rename the copy, then fill in databaseURL and secret.')
    except Exception as e:
        sys.exit('Could not read %s: %s' % (CFG_FILE, e))
    url = (c.get('databaseURL') or '').rstrip('/')
    if not url.startswith('https://') or not filled(c):
        sys.exit('Fill in databaseURL and secret in inrs_live_config.local.json first.')
    return url, c['secret']


def put(url, sec, path, data):
    req = urllib.request.Request('%s/%s.json?auth=%s' % (url, path, sec), data=json.dumps(data).encode(), method='PATCH',
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read()


def kind(stype):
    s = (stype or '').lower()
    if 'race' in s:
        return 'race'
    if 'qual' in s:
        return 'qualify'
    if 'practice' in s or 'warmup' in s:
        return 'practice'
    return None


def ms(t):
    try:
        t = float(t)
    except Exception:
        return 0
    return int(round(t * 1000)) if t > 0 else 0


MEMO = {}  # best lap / laps per session, so values iRacing clears at session end are never lost


def snapshot(ir):
    ir.freeze_var_buffer_latest()
    wk, di, si = ir['WeekendInfo'] or {}, ir['DriverInfo'] or {}, ir['SessionInfo'] or {}
    sn = ir['SessionNum']
    sessions = si.get('Sessions') or []
    if sn is None or sn >= len(sessions):
        return None
    sess = sessions[sn]
    k = kind(sess.get('SessionType'))
    if not k:
        return None
    drivers = {d['CarIdx']: d for d in (di.get('Drivers') or []) if not d.get('CarIsPaceCar') and not d.get('IsSpectator') and d.get('UserName')}
    pos = ir['CarIdxPosition'] or []
    laps = ir['CarIdxLapCompleted'] or []
    onlap = ir['CarIdxLap'] or []  # lap each car is on; backup when LapCompleted isn't filled in for other cars
    best = ir['CarIdxBestLapTime'] or []
    res = {r['CarIdx']: r for r in (sess.get('ResultsPositions') or []) if isinstance(r, dict)}
    grid = {}
    q = ir['QualifyResultsInfo'] or {}
    for r in (q.get('Results') or []):
        grid[r['CarIdx']] = r['Position'] + 1
    sid = '%s-%s' % (wk.get('SubSessionID', ''), sn)
    mem = MEMO.setdefault(sid, {})
    cars = []
    for idx, d in drivers.items():
        r = res.get(idx) or {}
        tb = ms(best[idx]) if idx < len(best) else 0
        rb = ms(r.get('FastestTime'))
        b = rb or tb  # official session best when iRacing has it, else live telemetry
        tl = int(laps[idx]) if idx < len(laps) and laps[idx] and laps[idx] > 0 else 0
        if idx < len(onlap) and onlap[idx] and onlap[idx] > 1:
            tl = max(tl, int(onlap[idx]) - 1)
        rl = int(r.get('LapsComplete') or 0) if r else 0
        m = mem.setdefault(d['UserName'], {'b': 0, 'l': 0})
        if b and (not m['b'] or rb or b < m['b']):
            m['b'] = b
        m['l'] = max(m['l'], tl, rl)
        p = int(pos[idx]) if idx < len(pos) and pos[idx] and pos[idx] > 0 else int(r['Position']) if r.get('Position') else 0
        cars.append([str(d.get('CarNumber', '')), d['UserName'], m['b'], p, m['l'], grid.get(idx, 0)])
    if k in ('practice', 'qualify'):  # rank by best lap; no time = no position
        for c in cars:
            c[3] = 0
        timed = sorted([c for c in cars if c[2]], key=lambda c: c[2])
        for i, c in enumerate(timed):
            c[3] = i + 1
    total = sess.get('SessionLaps')
    try:
        total = int(total)
    except Exception:
        total = None
    lead = max([c[4] for c in cars] or [0])
    left = ir['SessionLapsRemainEx']
    if k == 'race' and total:
        left = max(0, total - lead)
    elif not isinstance(left, int) or left > 10000:
        left = None
    return k, {
        'updated': int(time.time() * 1000), 'track': wk.get('TrackDisplayName', ''), 'config': wk.get('TrackConfigName', ''),
        'session': k, 'state': ir['SessionState'], 'lapsTotal': total, 'lapsLeft': left, 'leaderLaps': lead, 'cars': cars}


def main():
    url, sec = load_cfg()
    ir = irsdk.IRSDK()
    print('INRS live timing helper. Waiting for iRacing... (close this window to stop)')
    last_err = ''
    while True:
        try:
            if not (ir.is_initialized and ir.is_connected):
                ir.startup()
                if not (ir.is_initialized and ir.is_connected):
                    time.sleep(3)
                    continue
                print('Connected to iRacing.')
            snap = snapshot(ir)
            if snap:
                k, data = snap
                put(url, sec, 'live', {k: data, 'meta': {'updated': data['updated'], 'track': data['track'], 'session': k}})
                timed = sum(1 for c in data['cars'] if c[2] or c[3])
                print('\r%s  %-9s %2d cars  %s laps left   ' % (time.strftime('%H:%M:%S'), k, timed,
                      data['lapsLeft'] if data['lapsLeft'] is not None else '-'), end='', flush=True)
                last_err = ''
        except urllib.error.HTTPError as e:
            msg = ('Database refused the update (%s). Check the secret in inrs_live_config.local.json.' % e.code if e.code in (401, 403)
                   else 'Database error %s. Retrying.' % e.code)
            if msg != last_err:
                print('\n' + msg)
                last_err = msg
        except Exception as e:
            msg = 'Problem: %s' % e
            if msg != last_err:
                print('\n' + msg)
                last_err = msg
            try:
                ir.shutdown()
            except Exception:
                pass
        time.sleep(EVERY)


if __name__ == '__main__':
    main()
