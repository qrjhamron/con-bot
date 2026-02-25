#!/usr/bin/env python3
"""
Supremacy WW3 Bot — Quick Launcher

Usage:
  python3 play.py                    # Show status dashboard
  python3 play.py --auto             # Run auto-play loop
  python3 play.py --auto --ticks 5   # Run 5 auto-play ticks
  python3 play.py --move 17000145 420  # Move army to province
  python3 play.py --attack 17000145 17000200  # Attack enemy army
  python3 play.py --intel            # Full intel dump
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sww3bot.auth import BytroAuth
from sww3bot.api import SupremacyWW3
from sww3bot.controller import GameController
from sww3bot.autoplay import AutoPlayer


BOT_USER = os.environ.get("BOT_USER", "")
BOT_PASS = os.environ.get("BOT_PASS", "")
GAME_ID = int(os.environ.get("GAME_ID", "10687600"))
PLAYER_ID = int(os.environ.get("PLAYER_ID", "88"))


def connect():
    """Authenticate and connect to game server."""
    auth = BytroAuth()
    auth.login(BOT_USER, BOT_PASS)
    game_auth = auth.get_game_auth(GAME_ID)

    client = SupremacyWW3(
        game_id=str(GAME_ID),
        server_url=f"https://{game_auth['gs']}",
        player_id=PLAYER_ID,
        auth_token=game_auth['auth'],
        auth_hash=game_auth['authHash'],
        auth_tstamp=game_auth['authTstamp'],
        site_user_id=auth.user_id,
    )
    return GameController(client)


def main():
    parser = argparse.ArgumentParser(description="Supremacy WW3 Bot")
    parser.add_argument('--auto', action='store_true', help='Run auto-play loop')
    parser.add_argument('--ticks', type=int, default=0, help='Max auto-play ticks (0=infinite)')
    parser.add_argument('--interval', type=int, default=60, help='Poll interval (seconds)')
    parser.add_argument('--status', action='store_true', help='Show game status')
    parser.add_argument('--intel', action='store_true', help='Full intel dump')
    parser.add_argument('--move', nargs=2, type=int, metavar=('ARMY', 'PROVINCE'),
                       help='Move army to province')
    parser.add_argument('--attack', nargs=2, type=int, metavar=('ARMY', 'TARGET'),
                       help='Attack enemy army')
    parser.add_argument('--build', nargs=2, type=int, metavar=('PROVINCE', 'UNIT'),
                       help='Build unit in province')
    parser.add_argument('--row', type=int, metavar='PLAYER',
                       help='Offer Right of Way to player')
    parser.add_argument('--war', type=int, metavar='PLAYER',
                       help='Declare war on player')
    parser.add_argument('--dashboard', action='store_true', help='Show dashboard')
    args = parser.parse_args()

    print("Connecting to game server...")
    ctrl = connect()
    print("Connected!\n")

    if args.auto:
        player = AutoPlayer(ctrl, config={
            'poll_interval': args.interval,
            'auto_diplomacy': True,
        })
        player.run_loop(max_ticks=args.ticks)

    elif args.move:
        army_id, province = args.move
        result = ctrl.move_army(army_id, province)
        ar = result.get('result', result).get('actionResults', {})
        for k, v in ar.items():
            if k != '@c':
                status = "SUCCESS" if isinstance(v, (int, float)) and v > 0 else f"FAIL ({v})"
                print(f"Move army #{army_id} → P{province}: {status}")

    elif args.attack:
        army_id, target = args.attack
        result = ctrl.attack_army(army_id, target)
        ar = result.get('result', result).get('actionResults', {})
        for k, v in ar.items():
            if k != '@c':
                status = "SUCCESS" if isinstance(v, (int, float)) and v > 0 else f"FAIL ({v})"
                print(f"Attack #{army_id} → #{target}: {status}")

    elif args.build:
        province, unit = args.build
        result = ctrl.build_unit(province, unit)
        ar = result.get('result', result).get('actionResults', {})
        for k, v in ar.items():
            if k != '@c':
                status = "SUCCESS" if isinstance(v, (int, float)) and v > 0 else f"FAIL ({v})"
                print(f"Build U{unit} in P{province}: {status}")

    elif args.row:
        ctrl.offer_right_of_way(args.row)
        print(f"Offered ROW to P{args.row}")

    elif args.war:
        ctrl.declare_war(args.war)
        print(f" Declared war on P{args.war}")

    elif args.intel:
        intel = ctrl.get_full_intel()
        print(json.dumps(intel, indent=2, default=str))

    elif args.dashboard:
        print(ctrl.render_dashboard())

    else:
        # Default: show auto-play status
        player = AutoPlayer(ctrl)
        print(player.render_status())


if __name__ == '__main__':
    main()
