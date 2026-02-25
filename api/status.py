#!/usr/bin/env python3
"""Full game status dashboard."""

import sys, os, time; sys.path.insert(0, os.path.dirname(__file__))
from _conn import (connect, get_locations, get_armies, get_players,
                    army_units, army_hp, army_status_str, unit_name)

def main():
    ctrl, ge, raw = connect()
    locs = get_locations(raw)
    armies = get_armies(raw)
    players = get_players(raw)
    now_ms = time.time() * 1000
    
    # Game info
    s12 = raw.get('states', {}).get('12', {})
    day = s12.get('dayOfGame', '?')
    next_day = s12.get('nextDayTime', 0)
    hrs_to_day = (next_day - now_ms) / 3600000 if next_day > 0 else 0
    
    # Our info
    p88 = players.get(88, {})
    vp = p88.get('vps', 0)
    our_provs = sum(1 for l in locs if isinstance(l, dict) and l.get('o') == 88)
    
    # Resources
    res = ge.get_resources()
    
    # Armies
    our_armies = []
    for aid, a in armies.items():
        if isinstance(a, dict) and a.get('o') == 88:
            our_armies.append((int(aid), a))
    
    total_units = sum(len(army_units(a)) for _, a in our_armies)
    total_hp = sum(army_hp(a) for _, a in our_armies)
    
    print(f"╔══════════════════════════════════════════╗")
    print(f"║  🎮 SUPREMACY WW3 — DASHBOARD           ║")
    print(f"║  Day {day} | 4x Speed | Nigeria (P88)    ║")
    print(f"║  VP: {vp} | Provinces: {our_provs:<3} | Next: {hrs_to_day:.0f}h ║")
    print(f"╠══════════════════════════════════════════╣")
    
    # Resources
    print(f"║  💰 Resources                            ║")
    for k in ['Money', 'Supplies', 'Manpower', 'Metal', 'Oil', 'Fuel', 'Electronics']:
        r = res.get(k, {})
        a = r.get('amount', 0)
        net = r.get('production', 0) - r.get('consumption', 0)
        s = '+' if net >= 0 else ''
        print(f"║  {k:<12}: {a:>6.0f} ({s}{net:.0f}/d)")
    
    # GM
    gm = ge.get_goldmark()
    print(f"║  💎 Goldmark: {gm}")
    
    print(f"╠══════════════════════════════════════════╣")
    
    # Armies summary
    atk = sum(1 for _, a in our_armies if a.get('s') in [2, 3, 6])
    idle = sum(1 for _, a in our_armies if a.get('s') == 1)
    print(f"║  ⚔️ {len(our_armies)} armies ({total_units}u {total_hp:.0f}HP)")
    print(f"║    {atk} attacking/moving, {idle} idle")
    
    # Unit type breakdown
    unit_types = {}
    for _, a in our_armies:
        for u in army_units(a):
            if isinstance(u, dict):
                ut = u.get('t', 0)
                if ut not in unit_types:
                    unit_types[ut] = 0
                unit_types[ut] += 1
    for ut, cnt in sorted(unit_types.items()):
        print(f"║    {unit_name(ut)}: {cnt}")
    
    print(f"╠══════════════════════════════════════════╣")
    
    # Production
    print(f"║  🏭 Production")
    cities = [l for l in locs if isinstance(l, dict) and l.get('o') == 88 and l.get('plv', 0) >= 4]
    for city in sorted(cities, key=lambda x: x.get('id', 0)):
        pid = city.get('id', 0)
        pi = city.get('pi', {})
        if pi and isinstance(pi, dict) and pi.get('u'):
            su = pi.get('u', {})
            ut = su.get('unit', {}).get('t', su.get('t', 0))
            comp = pi.get('t', 0)
            rem = (comp - now_ms) / 3600000
            print(f"║    P{pid}: ⏳ {unit_name(ut)} ({rem:.1f}h)")
        else:
            print(f"║    P{pid}: 💤 idle")
    
    print(f"╠══════════════════════════════════════════╣")
    
    # Wars — check neighborRelations + armies in enemy territory
    nr = raw.get('states', {}).get('5', {}).get('relations', {}).get('neighborRelations', {})
    our_rels = nr.get('88', nr.get(88, {}))
    war_pids = set()
    for pk, rel in our_rels.items():
        if isinstance(rel, (int, float)) and rel == -2:
            war_pids.add(int(pk))
    # Detect wars from armies attacking/in enemy territory
    for _, a in our_armies:
        cmds = a.get('cmds', [])
        if isinstance(cmds, list) and len(cmds) > 1:
            for cmd in cmds[1:]:
                if isinstance(cmd, dict):
                    tp = cmd.get('tp')
                    if tp:
                        for l in locs:
                            if isinstance(l, dict) and l.get('id') == tp and l.get('o') and l.get('o') != 88:
                                war_pids.add(l.get('o'))
    
    print(f"║  🔥 Wars")
    if not war_pids:
        print(f"║    None")
    for pid in sorted(war_pids):
        nation = players.get(pid, {}).get('nationName', f'P{pid}')
        ep = sum(1 for l in locs if isinstance(l, dict) and l.get('o') == pid)
        print(f"║    vs {nation} ({ep} provs)")
    
    print(f"╚══════════════════════════════════════════╝")

if __name__ == '__main__':
    main()
