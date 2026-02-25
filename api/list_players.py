#!/usr/bin/env python3
"""Show all players in the game with their stats."""

import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, get_locations, get_players

def main():
    parser = argparse.ArgumentParser(description='List all players')
    parser.add_argument('--africa', action='store_true', help='Africa only')
    parser.add_argument('--sort', choices=['vp', 'provs', 'name'], default='vp')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    locs = get_locations(raw)
    players = get_players(raw)
    
    # Count provinces
    prov_counts = {}
    africa_owners = set()
    for loc in locs:
        if isinstance(loc, dict):
            owner = loc.get('o', -1)
            if owner > 0:
                prov_counts[owner] = prov_counts.get(owner, 0) + 1
                c = loc.get('c', {})
                if isinstance(c, dict):
                    x, y = c.get('x', 0), c.get('y', 0)
                    if 5500 <= x <= 9600 and 2500 <= y <= 6800:
                        africa_owners.add(owner)
    
    # Get relations (from neighborRelations + diplomaticRelations)
    rels_data = raw.get('states', {}).get('5', {}).get('relations', {})
    nr = rels_data.get('neighborRelations', {})
    our_rels = dict(nr.get('88', nr.get(88, {})))
    # Merge diplomaticRelations
    dr = rels_data.get('diplomaticRelations', {})
    our_dr = dr.get('88', dr.get(88, {}))
    if isinstance(our_dr, dict):
        for pk, rel in our_dr.items():
            if pk not in our_rels:
                our_rels[pk] = rel
    # Merge warRelations
    for key in ['warRelations', 'wars']:
        wr = rels_data.get(key, [])
        if isinstance(wr, list) and len(wr) > 1:
            for w in wr[1]:
                if isinstance(w, dict):
                    p1, p2 = w.get('player1', 0), w.get('player2', 0)
                    if p1 == 88: our_rels[str(p2)] = -2
                    elif p2 == 88: our_rels[str(p1)] = -2
    rel_names = {-2:'WARWAR', -1:'CEASE', 0:'EMBARGO', 1:'PEACE',
                 2:'NAP', 3:'ROW', 4:'MIL', 5:'PROT', 6:'INTEL', 7:'CMD'}
    
    items = []
    for pid, p in players.items():
        if args.africa and pid not in africa_owners:
            continue
        items.append((pid, p))
    
    if args.sort == 'vp':
        items.sort(key=lambda x: -x[1].get('vps', 0))
    elif args.sort == 'provs':
        items.sort(key=lambda x: -prov_counts.get(x[0], 0))
    else:
        items.sort(key=lambda x: x[1].get('nationName', ''))
    
    print(f"{'#':>3} {'Nation':<22} {'VP':>5} {'Provs':>6} {'Relation':<10} {'Player'}")
    print(f"{'─'*3} {'─'*22} {'─'*5} {'─'*6} {'─'*10} {'─'*20}")
    
    for i, (pid, p) in enumerate(items, 1):
        nation = p.get('nationName', '?')
        vp = p.get('vps', 0)
        provs = prov_counts.get(pid, 0)
        name = p.get('name', '?')
        rel = our_rels.get(str(pid), our_rels.get(pid, None))
        rel_str = rel_names.get(rel, '') if rel is not None else ''
        ai = ' [AI]' if p.get('computerPlayer') else ''
        marker = ' *' if pid == 88 else (' >' if pid == 87 else '')
        print(f"{i:>3} {nation:<22} {vp:>5} {provs:>6} {rel_str:<10} {name}{ai}{marker}")

if __name__ == '__main__':
    main()
