#!/usr/bin/env python3
"""Declare war on a player."""

import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, get_players

def main():
    parser = argparse.ArgumentParser(description='Declare war')
    parser.add_argument('player', type=int, help='Target player ID')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    players = get_players(raw)
    nation = players.get(args.player, {}).get('nationName', f'P{args.player}')
    
    if not args.confirm:
        resp = input(f"Declare WAR on {nation} (P{args.player})? [y/N]: ")
        if resp.lower() != 'y':
            print("Cancelled.")
            return
    
    result = ctrl.declare_war(args.player)
    ar = ctrl._extract_action_result(result)
    print(f"{'OK' if ar in [0,1] else 'FAIL'} WAR declared on {nation} (ar={ar})")

if __name__ == '__main__':
    main()
