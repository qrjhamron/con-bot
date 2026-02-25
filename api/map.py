#!/usr/bin/env python3
"""ASCII map of Africa showing territories and armies."""

import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, get_locations, get_armies, get_players, army_hp

def main():
    ctrl, ge, raw = connect()
    locs = get_locations(raw)
    armies = get_armies(raw)
    players = get_players(raw)
    
    MAP_W, MAP_H = 80, 40
    
    africa_locs = []
    for loc in locs:
        if isinstance(loc, dict):
            c = loc.get('c', {})
            if isinstance(c, dict):
                x, y = c.get('x', 0), c.get('y', 0)
                if 5500 <= x <= 9600 and 2500 <= y <= 6800:
                    africa_locs.append(loc)
    
    if not africa_locs:
        print("No African provinces found.")
        return
    
    min_x = min(l['c']['x'] for l in africa_locs) - 50
    max_x = max(l['c']['x'] for l in africa_locs) + 50
    min_y = min(l['c']['y'] for l in africa_locs) - 50
    max_y = max(l['c']['y'] for l in africa_locs) + 50
    
    def to_map(x, y):
        mx = int((x - min_x) / (max_x - min_x) * (MAP_W - 1))
        my = int((y - min_y) / (max_y - min_y) * (MAP_H - 1))
        return max(0, min(MAP_W-1, mx)), max(0, min(MAP_H-1, my))
    
    grid = [[' '] * MAP_W for _ in range(MAP_H)]
    
    OWNER_CHARS = {88: '█', 87: '▓', 29: '░', 121: '▒'}
    
    for loc in africa_locs:
        owner = loc.get('o', -1)
        if owner <= 0:
            continue
        c = loc['c']
        mx, my = to_map(c['x'], c['y'])
        ch = OWNER_CHARS.get(owner, '·')
        if grid[my][mx] == ' ':
            grid[my][mx] = ch
    
    # Place armies
    loc_map = {l['id']: l for l in locs if isinstance(l, dict)}
    for aid, a in armies.items():
        if not isinstance(a, dict) or a.get('o') != 88:
            continue
        loc = loc_map.get(a.get('l', 0), {})
        c = loc.get('c', {})
        if isinstance(c, dict) and c.get('x'):
            mx, my = to_map(c['x'], c['y'])
            grid[my][mx] = '★' if army_hp(a) >= 50 else '☆'
    
    print(f"╔{'═'*MAP_W}╗")
    print(f"║{'🌍 AFRICA MAP — Nigeria (P88)':^{MAP_W}}║")
    print(f"╠{'═'*MAP_W}╣")
    for row in grid:
        print(f"║{''.join(row)}║")
    print(f"╠{'═'*MAP_W}╣")
    print(f"║{'█=Nigeria ▓=Morocco ░=Ghana ▒=Niger ★☆=Army ·=Other':^{MAP_W}}║")
    print(f"╚{'═'*MAP_W}╝")

if __name__ == '__main__':
    main()
