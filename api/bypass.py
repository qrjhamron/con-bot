#!/usr/bin/env python3
"""
Bypass & Auto-Management System.

Handles all the repetitive game management automatically:
- Re-declare expired wars
- Auto-conquer with smart targeting
- Auto-produce in all idle cities
- Auto-build infrastructure in new cities
- Resource optimization
- Morale management

Usage:
    python bypass.py              # Run once
    python bypass.py --loop 15    # Run every 15 minutes
    python bypass.py --status     # Just show what it would do
"""

import sys, os, time, math, argparse
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from _conn import (connect, get_locations, get_armies, get_players,
                    get_properties, army_units, army_hp, unit_name, building_name)


def run_bypass(dry_run=False):
    """Run all bypass/auto systems. Returns summary dict."""
    ctrl, ge, raw = connect()
    locs = get_locations(raw)
    armies_data = get_armies(raw)
    players = get_players(raw)
    props = get_properties(raw)
    now_ms = time.time() * 1000

    summary = {'wars': [], 'armies': [], 'production': [], 'buildings': [], 'errors': []}

    # ═══════════════════════════════════════════════════════
    # 1. AUTO WAR — re-declare on all weak AI bots
    # ═══════════════════════════════════════════════════════
    nr = raw.get('states', {}).get('5', {}).get('relations', {}).get('neighborRelations', {})
    our_rels = nr.get('88', {})
    at_war = {int(k) for k, v in our_rels.items() if isinstance(v, (int, float)) and v == -2}

    # Find weak AI bots not at war
    for pid, p in players.items():
        if not p.get('computerPlayer'):
            continue
        provs = sum(1 for l in locs if isinstance(l, dict) and l.get('o') == pid)
        if provs <= 0 or provs > 15:
            continue
        if pid in at_war:
            continue

        if not dry_run:
            try:
                r = ctrl.declare_war(pid)
                ar = _extract_ar(r)
                if ar == 1:
                    summary['wars'].append(f"⚔️ WAR → {p.get('nationName','')} ({provs}p)")
                    at_war.add(pid)
            except Exception as e:
                summary['errors'].append(f"War P{pid}: {e}")
        else:
            summary['wars'].append(f"[DRY] WAR → {p.get('nationName','')} ({provs}p)")

    # ═══════════════════════════════════════════════════════
    # 2. SMART ARMY DEPLOYMENT
    # ═══════════════════════════════════════════════════════
    # Find idle armies
    idle_armies = []
    for aid, a in armies_data.items():
        if not isinstance(a, dict) or a.get('o') != 88:
            continue
        if a.get('s') == 1:  # IDLE
            # Check if army already has queued commands
            cmds = a.get('c', [])
            cmd_count = len(cmds) - 1 if isinstance(cmds, list) else 0
            if cmd_count <= 0:
                idle_armies.append((int(aid), a))

    # Find enemy provinces sorted by priority
    enemy_provs = []
    for loc in locs:
        if not isinstance(loc, dict):
            continue
        ow = loc.get('o')
        if ow and ow in at_war:
            provs = sum(1 for l in locs if isinstance(l, dict) and l.get('o') == ow)
            # Priority: fewer provinces = easier target
            enemy_provs.append((provs, loc))
    enemy_provs.sort(key=lambda x: x[0])  # weakest first

    def army_pos(a):
        p = a.get('p', {})
        return (p.get('x', 0), p.get('y', 0)) if isinstance(p, dict) else (0, 0)

    assigned = set()
    for aid, a in sorted(idle_armies, key=lambda x: -army_hp(x[1])):
        ax, ay = army_pos(a)
        best, best_d = None, float('inf')
        for _, loc in enemy_provs:
            lid = loc.get('id')
            if lid in assigned:
                continue
            c = loc.get('c', {})
            if not isinstance(c, dict):
                continue
            d = math.hypot(c.get('x', 0) - ax, c.get('y', 0) - ay)
            if d < best_d:
                best_d, best = d, loc
        if best:
            assigned.add(best['id'])
            ow = best.get('o')
            nation = players.get(ow, {}).get('nationName', '?')
            if not dry_run:
                try:
                    r = ctrl.move_army(aid, best['id'])
                    ar = _extract_ar(r)
                    if ar == 1:
                        summary['armies'].append(f"🚀 #{aid} ({army_hp(a):.0f}HP) → P{best['id']} ({nation})")
                except Exception as e:
                    summary['errors'].append(f"Move #{aid}: {e}")
            else:
                summary['armies'].append(f"[DRY] #{aid} → P{best['id']} ({nation})")

    # ═══════════════════════════════════════════════════════
    # 3. AUTO-PRODUCE — all idle cities (refresh state for fresh queueableProductions)
    # ═══════════════════════════════════════════════════════
    priority_units = [10141, 3294, 3308, 3322, 3373]  # Infantry → Mot.Inf → Heli → MBT → SAM

    try:
        ctrl.refresh_state()
        locs = get_locations(ctrl.state)
        props = get_properties(ctrl.state)
    except:
        pass

    for loc in locs:
        if not isinstance(loc, dict) or loc.get('o') != 88 or loc.get('plv', 0) < 4:
            continue
        pid = loc.get('id', 0)
        if loc.get('pi'):
            continue  # already producing

        p = props.get(str(pid), {})
        qp = p.get('queueableProductions', [])
        items = qp[1] if isinstance(qp, list) and len(qp) > 1 else []

        for uid in priority_units:
            avail = any(isinstance(it, dict) and it.get('unit', {}).get('t') == uid
                       for it in (items if isinstance(items, list) else []))
            if not avail:
                continue

            if not dry_run:
                try:
                    r = ctrl.produce_unit(pid, uid)
                    ar = _extract_ar(r)
                    if ar == 1:
                        summary['production'].append(f"🏭 P{pid}: {unit_name(uid)}")
                        break
                except:
                    continue
            else:
                summary['production'].append(f"[DRY] P{pid}: {unit_name(uid)}")
                break

    # ═══════════════════════════════════════════════════════
    # 4. AUTO-BUILD — infrastructure in new/empty cities
    # ═══════════════════════════════════════════════════════
    essential_buildings = [2245, 2250, 2271, 2016]  # Recruiting Office, Local Industry, Army Base, Arms Industry

    for loc in locs:
        if not isinstance(loc, dict) or loc.get('o') != 88 or loc.get('plv', 0) < 4:
            continue
        pid = loc.get('id', 0)

        # Check existing buildings
        us = loc.get('us', [])
        existing = set()
        under_construction = False
        if isinstance(us, list) and len(us) > 1:
            for b in us[1]:
                if isinstance(b, dict):
                    existing.add(b.get('id'))
                    if b.get('built') is False and b.get('cn'):
                        under_construction = True

        # Check construction queue
        cos = loc.get('cos')
        if cos:
            under_construction = True

        if under_construction:
            continue  # already building something

        # Find first missing essential building
        for bid in essential_buildings:
            if bid not in existing:
                if not dry_run:
                    try:
                        r = ctrl.build_building(pid, bid)
                        ar = _extract_ar(r)
                        if ar == 1:
                            summary['buildings'].append(f"🏗️ P{pid}: {building_name(bid)}")
                            break
                    except:
                        continue
                else:
                    summary['buildings'].append(f"[DRY] P{pid}: {building_name(bid)}")
                    break

    return summary


def _extract_ar(response):
    res = response.get('result', response)
    ar = res.get('actionResults', {})
    for k, v in ar.items():
        if k != '@c':
            return v
    return 0


def print_summary(summary):
    """Print bypass cycle summary."""
    print(f"\n{'='*50}")
    print(f"  🔄 BYPASS CYCLE COMPLETE — {time.strftime('%H:%M:%S')}")
    print(f"{'='*50}")

    if summary['wars']:
        print(f"\n  ⚔️ Wars Declared ({len(summary['wars'])})")
        for w in summary['wars'][:10]:
            print(f"    {w}")
        if len(summary['wars']) > 10:
            print(f"    ... +{len(summary['wars'])-10} more")

    if summary['armies']:
        print(f"\n  🚀 Armies Deployed ({len(summary['armies'])})")
        for a in summary['armies']:
            print(f"    {a}")

    if summary['production']:
        print(f"\n  🏭 Production Started ({len(summary['production'])})")
        for p in summary['production']:
            print(f"    {p}")

    if summary['buildings']:
        print(f"\n  🏗️ Buildings Queued ({len(summary['buildings'])})")
        for b in summary['buildings']:
            print(f"    {b}")

    if summary['errors']:
        print(f"\n  ❌ Errors ({len(summary['errors'])})")
        for e in summary['errors'][:5]:
            print(f"    {e}")

    total = len(summary['wars']) + len(summary['armies']) + len(summary['production']) + len(summary['buildings'])
    print(f"\n  📊 Total actions: {total}")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description='SWW3 Bypass & Auto System')
    parser.add_argument('--loop', type=int, metavar='MINS', help='Loop every N minutes')
    parser.add_argument('--status', action='store_true', help='Dry run — show what would happen')
    args = parser.parse_args()

    if args.loop:
        print(f"🔄 Auto-bypass loop: every {args.loop} minutes")
        print("   Press Ctrl+C to stop\n")
        while True:
            try:
                summary = run_bypass(dry_run=False)
                print_summary(summary)
                print(f"\n💤 Next cycle in {args.loop} minutes...")
                time.sleep(args.loop * 60)
            except KeyboardInterrupt:
                print("\n🛑 Stopped.")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(60)
    else:
        summary = run_bypass(dry_run=args.status)
        print_summary(summary)


if __name__ == '__main__':
    main()
