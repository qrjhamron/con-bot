#!/usr/bin/env python3
"""Game selection CLI backed by the agent's SQLite configuration."""
import argparse
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sww3bot.agent_store import Store
from sww3bot.agent_tools import GameExecutor
from sww3bot.instance_lock import InstanceLock
from sww3bot.settings import Settings


async def run(args, settings):
    store = Store(settings.db_path)
    executor = GameExecutor(settings)
    try:
        if args.game_id:
            await executor.validate_game(args.game_id)
            session = executor.session(args.game_id)
            if args.command == 'select':
                store.set_preference('game_id', args.game_id)
            print(f'Game {args.game_id} | Player {session.player_id}')
        else:
            try:
                for game in await executor.list_games():
                    print(game['label'])
            except Exception:
                print('Game list unavailable. Use: python api/games.py select GAME_ID')
            print(f"Active game: {store.preference('game_id', settings.game_id) or 'none'}")
    finally:
        executor.close()
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['list', 'select', 'info'], nargs='?', default='list')
    parser.add_argument('game_id', type=int, nargs='?')
    args = parser.parse_args()
    if args.command != 'list' and (args.game_id is None or args.game_id <= 0):
        parser.error('A positive GAME_ID is required')
    settings = Settings.load()
    lock = InstanceLock(settings.db_path)
    try:
        asyncio.run(run(args, settings))
    finally:
        lock.close()


if __name__ == '__main__':
    main()
