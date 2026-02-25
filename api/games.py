#!/usr/bin/env python3
"""
Game selector — check available games, IDs, nations.
Set which game to play.

Usage:
    python games.py                    # List all games
    python games.py select <game_id>   # Select a game to play
    python games.py info <game_id>     # Get game details
"""

import sys, os, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sww3bot.auth import BytroAuth

CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', '.game_config.json')

BOT_USER = os.environ.get("BOT_USER", "")
BOT_PASS = os.environ.get("BOT_PASS", "")


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        'game_id': 10687600,
        'player_id': 88,
        'nation': 'Nigeria',
        'mode': 'ww3_4x',
    }


def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)


def list_games():
    """List all active games for the bot account."""
    auth = BytroAuth()
    auth.login(BOT_USER, BOT_PASS)

    games = auth.get_games() if hasattr(auth, 'get_games') else []
    if not games:
        # Fallback: try to get from user profile
        try:
            import requests
            r = requests.get(
                f'https://www.conflictnations.com/api/users/{auth.user_id}/games',
                cookies=auth.session.cookies if hasattr(auth, 'session') else {},
                timeout=15,
            )
            if r.ok:
                games = r.json().get('games', [])
        except:
            pass

    cfg = load_config()
    print("╔══════════════════════════════════════════════╗")
    print("║  🎮 AVAILABLE GAMES                          ║")
    print("╠══════════════════════════════════════════════╣")

    if games:
        for g in games:
            gid = g.get('gameID', g.get('id', '?'))
            mode = g.get('scenarioName', g.get('mode', '?'))
            nation = g.get('nationName', '?')
            active = '✅' if gid == cfg.get('game_id') else '  '
            print(f"║  {active} Game {gid} | {mode} | {nation}")
    else:
        print(f"║  Could not fetch game list from API")

    print("╠══════════════════════════════════════════════╣")
    print(f"║  🎯 Active: Game {cfg['game_id']} | P{cfg['player_id']} | {cfg['nation']}")
    print(f"║  📋 Mode: {cfg['mode']}")
    print("╚══════════════════════════════════════════════╝")
    return cfg


def select_game(game_id, player_id=None, nation=None):
    """Select a game to play."""
    cfg = load_config()
    cfg['game_id'] = int(game_id)
    if player_id:
        cfg['player_id'] = int(player_id)
    if nation:
        cfg['nation'] = nation
    save_config(cfg)
    print(f"✅ Selected Game {game_id} | P{cfg['player_id']} | {cfg['nation']}")
    return cfg


def game_info(game_id):
    """Get info about a specific game."""
    auth = BytroAuth()
    auth.login(BOT_USER, BOT_PASS)
    try:
        ga = auth.get_game_auth(int(game_id))
        print(f"╔══════════════════════════════════════════════╗")
        print(f"║  🎮 Game {game_id}")
        print(f"║  Server: {ga.get('gs', '?')}")
        print(f"║  Auth: {'OK' if ga.get('auth') else 'FAIL'}")
        print(f"╚══════════════════════════════════════════════╝")
        return ga
    except Exception as e:
        print(f"❌ Cannot access game {game_id}: {e}")
        return None


def get_active_config():
    """Get the currently active game config."""
    return load_config()


def main():
    if len(sys.argv) < 2:
        list_games()
        return

    cmd = sys.argv[1]
    if cmd == 'select' and len(sys.argv) >= 3:
        pid = int(sys.argv[4]) if len(sys.argv) > 4 else None
        nation = sys.argv[3] if len(sys.argv) > 3 else None
        select_game(sys.argv[2], pid, nation)
    elif cmd == 'info' and len(sys.argv) >= 3:
        game_info(sys.argv[2])
    else:
        list_games()


if __name__ == '__main__':
    main()
