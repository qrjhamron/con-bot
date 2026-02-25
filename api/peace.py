#!/usr/bin/env python3
"""Offer peace to a player."""

import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, get_players

def main():
    parser = argparse.ArgumentParser(description='Offer peace')
    parser.add_argument('player', type=int, help='Target player ID')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    players = get_players(raw)
    nation = players.get(args.player, {}).get('nationName', f'P{args.player}')
    
    result = ctrl.offer_peace(args.player)
    ar = ctrl._extract_action_result(result)
    print(f"{'✅' if ar in [0,1] else '❌'} Peace offered to {nation} (ar={ar})")

if __name__ == '__main__':
    main()
