"""Season/rank score tracking: rank points are the seasonal progression.

Scores are server-computed (military from combat, economic from economy).
Verified live: leaders are ~96% economic — economy activity is the farm lever.
"""
from datetime import date, datetime


def summarize(rank_progress):
    """Rank progress mentah jadi angka rapi; rusak jadi default."""
    if not isinstance(rank_progress, dict):
        return {'overall': 0, 'military': 0, 'economic': 0,
                'global_rank': 0, 'level': 0, 'title': '?'}
    def number(value):
        if isinstance(value, bool):
            return 0
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    return {'overall': number(rank_progress.get('overallScore', 0)),
            'military': number(rank_progress.get('militaryScore', 0)),
            'economic': number(rank_progress.get('economicScore', 0)),
            'global_rank': number(rank_progress.get('globalRank', 0)),
            'military_rank': number(rank_progress.get('militaryRank', 0)),
            'economic_rank': number(rank_progress.get('economicRank', 0)),
            'level': number(rank_progress.get('currentRankLevel', 0))}


def delta(baseline, current):
    """Selisih skor vs baseline; baseline rusak jadi 0 semua."""
    base = baseline if isinstance(baseline, dict) else {}
    gains = {}
    for key in ('overall', 'military', 'economic'):
        try:
            gains[key] = int(current.get(key, 0)) - int(base.get(key, 0))
        except (TypeError, ValueError):
            gains[key] = 0
    return gains


def today():
    return date.today().isoformat()


def parse_season_date(value):
    """Tanggal season ('YYYY-MM-DD HH:MM:SS' atau epoch) jadi detik; rusak jadi 0."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        number = float(value)
        return number / 1000 if number > 1e12 else number
    if isinstance(value, str):
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(value.strip(), fmt).timestamp()
            except ValueError:
                continue
    return 0


def active_season(seasons, now=0):
    """Season yang sedang berjalan (visible + rentang tanggal); tidak ada jadi {}."""
    import time as _time
    now = now or _time.time()
    if not isinstance(seasons, dict):
        return {}
    best = {}
    for key, entry in seasons.items():
        if not isinstance(entry, dict) or not entry.get('visible', True):
            continue
        start = parse_season_date(entry.get('fromDate', 0))
        end = parse_season_date(entry.get('toDate', 0))
        if start <= now <= (end or float('inf')):
            try:
                sid = int(entry.get('id', key))
            except (TypeError, ValueError):
                continue
            if not best or sid > best.get('id', -1):
                best = {'id': sid, 'name': str(entry.get('name', '?')),
                        'score_type': str(entry.get('scoreType', '?')),
                        'required_score': entry.get('requiredScore', 0),
                        'ends_at': entry.get('toDate', '?')}
    return best


def summarize_season_user(details):
    """Detail skor season akun; rusak jadi default."""
    if not isinstance(details, dict):
        return {'score': 0, 'position': 0, 'unlocked': False}
    unlock = details.get('unlockStatus', {})
    unlocked = unlock.get('unlocked', False) if isinstance(unlock, dict) else False
    def number(value):
        try:
            return int(float(value)) if not isinstance(value, bool) else 0
        except (TypeError, ValueError):
            return 0
    return {'score': number(details.get('score', 0)),
            'position': number(details.get('position', 0)),
            'unlocked': bool(unlocked)}
