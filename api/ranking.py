#!/usr/bin/env python3
"""Show game leaderboard/ranking."""

import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, get_locations, get_players

def main():
    parser = argparse.ArgumentParser(description='Show ranking')
    parser.add_argument('--top', type=int, default=20, help='Show top N players')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    locs = get_locations(raw)
    players = get_players(raw)
    
    # Count provinces per player
    prov_counts = {}
    for loc in locs:
        if isinstance(loc, dict):
            owner = loc.get('o', -1)
            if owner > 0:
                prov_counts[owner] = prov_counts.get(owner, 0) + 1
    
    # Sort by VP
    ranked = sorted(players.items(), key=lambda x: -x[1].get('vps', 0))
    
    print(f"{'#':>3} {'Nation':<22} {'VP':>5} {'Provs':>6} {'Player':<20}")
    print(f"{'─'*3} {'─'*22} {'─'*5} {'─'*6} {'─'*20}")
    
    for i, (pid, p) in enumerate(ranked[:args.top], 1):
        nation = p.get('nationName', '?')
        vp = p.get('vps', 0)
        provs = prov_counts.get(pid, 0)
        name = p.get('name', '?')
        marker = ' *' if pid == 88 else (' >' if pid == 87 else '')
        print(f"{i:>3} {nation:<22} {vp:>5} {provs:>6} {name:<20}{marker}")

if __name__ == '__main__':
    main()
