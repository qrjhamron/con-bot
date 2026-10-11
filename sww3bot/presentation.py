"""Human readable geography and real elapsed time from server game clocks."""
import math
from .protocol import collection


def remaining_hours(raw, end):
    """Return real hours; server timestamps advance at 1 / timeScale."""
    info = raw.get('states', {}).get('12', {})
    stamp = raw.get('timeStamp', info.get('timeStamp'))
    scale = info.get('timeScale')
    # Jackson serializes long timestamps as decimal strings in full state.
    if any(isinstance(v, bool) for v in (end, stamp, scale)):
        return None
    try:
        end, stamp, scale = (float(v) for v in (end, stamp, scale))
    except (TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(v) for v in (end, stamp, scale)):
        return None
    if end <= 0 or stamp <= 0 or scale <= 0:
        return None
    return max(0.0, (end - stamp) * scale / 3600000)


def duration_text(hours):
    if hours is None:
        return 'waktu belum tersedia'
    minutes = math.ceil(hours * 60)
    if minutes == 0:
        return 'menunggu pembaruan server'
    hours, minutes = divmod(minutes, 60)
    return f'{hours} jam {minutes} menit' if hours else f'{minutes} menit'


def province_name(raw, province_id):
    for p in collection(raw.get('states', {}).get('3', {}).get('map', {}).get('locations')):
        if isinstance(p, dict) and str(p.get('id')) == str(province_id):
            for field in ('name', 'n'):
                value = p.get(field)
                if isinstance(value, str) and value.strip() and not value.strip().isdigit():
                    return value
    return f'Wilayah #{province_id} (nama belum tersedia)'


def describe_locations(value, raw):
    """Add labels to tool results while retaining IDs used by commands."""
    if isinstance(value, list):
        return [describe_locations(v, raw) for v in value]
    if not isinstance(value, dict):
        return value
    result = {k: describe_locations(v, raw) for k, v in value.items()}
    for key, label in (('city_id', 'city_name'), ('province_id', 'province_name'),
                       ('target_province', 'target_name'), ('rally_province', 'rally_name'),
                       ('destination_province', 'destination_name'), ('tp', 'target_name')):
        if type(value.get(key)) is int:
            result[label] = province_name(raw, value[key])
    for key in ('province_ids', 'waypoints', 'route'):
        if isinstance(value.get(key), list) and all(type(v) is int for v in value[key]):
            result[key + '_names'] = [province_name(raw, v) for v in value[key]]
    for key in ('hours_remaining', 'remaining_h', 'hours_left', 'next_day_hours'):
        if key in value:
            result[key + '_text'] = duration_text(value[key])
            result['time_basis'] = 'real_hours'
    if value.get('@c') == 'gc' and 'at' in value:
        hours = remaining_hours(raw, value['at'])
        result['arrival_hours_remaining'] = hours
        result['arrival_remaining'] = duration_text(hours)
        result['time_basis'] = 'real_hours'
    # Province construction and production timers use the simulated server clock.
    if isinstance(value.get('u'), dict) and 't' in value and 's' in value:
        hours = remaining_hours(raw, value['t'])
        result['hours_remaining'] = hours
        result['remaining'] = duration_text(hours)
        result['time_basis'] = 'real_hours'
    return result
