#!/usr/bin/env python3
"""Send in-game message to a player."""

import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect

def main():
    parser = argparse.ArgumentParser(description='Send message')
    parser.add_argument('player', type=int, help='Target player ID')
    parser.add_argument('message', help='Message text')
    parser.add_argument('--subject', default='', help='Message subject')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    result = ge.send_message(args.player, args.message, args.subject)
    ar = ctrl._extract_action_result(result)
    print(f"{'✅' if ar in [0,1] else '❌'} Message sent to P{args.player} (ar={ar})")

if __name__ == '__main__':
    main()
