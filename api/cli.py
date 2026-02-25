#!/usr/bin/env python3
"""
Supremacy WW3 Bot — CLI Interface

Usage:
  python cli.py <command> [args]

Commands:
  status          Full game dashboard
  resources       List resources
  armies          List all armies with units
  provinces       List provinces (--cities for cities only)
  cities          List cities with buildings/production
  players         List all players (--africa for Africa only)
  ranking         Leaderboard
  map             ASCII map of Africa
  intel           Intelligence report (--africa, --enemies)

  attack <prov>   Attack province (auto-selects army)
  move <army> <prov>  Move army to province
  conquer         Auto-send idle armies to enemy provinces
  war <player>    Declare war
  peace <player>  Offer peace
  diplomacy <player> <type>  Change relation (war/peace/row/intel...)

  produce <city> [--unit TYPE]  Produce unit in city
  buy <city> <unit>  Buy unit (shortcut names: infantry, mot, tank...)
  auto-produce    Auto-produce in all idle cities
  build <city> <building_id>   Build building
  research <id>   Start research

  spy list|recruit|deploy <prov>|recall <id>
  message <player> <text>  Send message
  market prices|buy|sell   Market operations
  exploits report|morale|speedup-*  Run exploits

Examples:
  python cli.py status
  python cli.py conquer
  python cli.py buy 612 infantry
  python cli.py attack 212
  python cli.py intel --africa --enemies
  python cli.py spy deploy 212 --mission military
"""

import sys, os

COMMANDS = {
    'status': 'status.py',
    'resources': 'list_resources.py',
    'armies': 'list_armies.py',
    'provinces': 'list_provinces.py',
    'cities': 'list_cities.py',
    'players': 'list_players.py',
    'ranking': 'ranking.py',
    'map': 'map.py',
    'intel': 'intel.py',
    'attack': 'attack.py',
    'move': 'move_army.py',
    'conquer': 'conquer.py',
    'war': 'war.py',
    'peace': 'peace.py',
    'diplomacy': 'diplomacy.py',
    'produce': 'produce.py',
    'buy': 'buy_unit.py',
    'auto-produce': 'auto_produce.py',
    'build': 'build.py',
    'research': 'research.py',
    'spy': 'spy.py',
    'message': 'message.py',
    'market': 'market.py',
    'exploits': 'exploits.py',
    'agent': 'agent.py',
    'auto': 'agent.py --auto',
    'bypass': 'bypass.py',
    'bypass-loop': 'bypass.py --loop 15',
    'bypass-status': 'bypass.py --status',
    'tui': 'tui_agent.py',
    'tui-simple': 'tui_agent.py --simple',
    'games': 'games.py',
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help', 'help']:
        print(__doc__)
        print("Available commands:")
        for cmd in sorted(COMMANDS.keys()):
            print(f"  {cmd}")
        return
    
    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"❌ Unknown command: {cmd}")
        print(f"Available: {', '.join(sorted(COMMANDS.keys()))}")
        return
    
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), COMMANDS[cmd])
    sys.argv = [script] + sys.argv[2:]
    
    with open(script) as f:
        code = f.read()
    exec(compile(code, script, 'exec'), {'__name__': '__main__', '__file__': script})

if __name__ == '__main__':
    main()
