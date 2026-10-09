"""CLI adapter for the same Meta engine used by Telegram."""
import argparse
import asyncio

from .agent_engine import Engine, Runtime
from .agent_store import Store
from .agent_tools import GameExecutor
from .instance_lock import InstanceLock
from .meta_client import MetaClient
from .settings import Settings


async def run(settings, arguments):
    store = Store(settings.db_path)
    store.recover()
    meta = MetaClient(settings.model_api_key.get_secret_value())
    executor = GameExecutor(settings)
    engine = Engine(settings, meta, executor, store)
    game_id = arguments.game or store.preference('game_id', settings.game_id)

    async def notify(text):
        if not arguments.quiet:
            print(text)

    async def execute(prompt):
        task_id = store.new_task(game_id, settings.redact(prompt))
        store.finish_task(task_id, 'running')
        runtime = Runtime(task_id, settings, store, notify)
        operation = asyncio.create_task(engine.run(game_id, prompt, runtime))
        interrupted = False
        try:
            result = await asyncio.shield(operation)
        except asyncio.CancelledError:
            interrupted = True
            runtime.cancelled.set()
            result = await operation
        store.finish_task(task_id, result.status, result.text)
        print(result.text)
        if interrupted:
            raise asyncio.CancelledError()
        if result.choices:
            for i, choice in enumerate(result.choices, 1):
                print(f"{i}. {choice['label']} ({choice['id']})")
            store.finish_task(task_id, 'completed', result.text + ' Pilih target pada perintah berikutnya.')

    try:
        if not game_id:
            raise ValueError('Isi GAME_ID atau gunakan --game ID_GAME.')
        if arguments.command:
            await execute(' '.join(arguments.command))
        elif arguments.auto:
            while True:
                await execute('Jalankan full_conquest_cycle dan laporkan hasil setiap tahap.')
                await asyncio.sleep(arguments.interval * 60)
        else:
            print(f'Meta Commander — game {game_id}. Ketik /quit untuk keluar.')
            while True:
                try:
                    prompt = await asyncio.to_thread(input, '> ')
                except EOFError:
                    break
                if prompt.strip() in ('/quit', '/exit'):
                    break
                if prompt.strip():
                    await execute(prompt)
    finally:
        await meta.close()
        executor.close()
        store.close()


def main():
    parser = argparse.ArgumentParser(description='Meta Muse Spark game commander')
    parser.add_argument('command', nargs='*')
    parser.add_argument('--game', type=int)
    parser.add_argument('--auto', action='store_true')
    parser.add_argument('--interval', type=int, default=30, help='Autoplay interval in minutes')
    parser.add_argument('--quiet', '-q', action='store_true')
    parser.add_argument('--simple', action='store_true', help='Compatibility option: CLI is always text-based')
    arguments = parser.parse_args()
    if arguments.interval <= 0 or (arguments.game is not None and arguments.game <= 0):
        parser.error('game and interval must be positive')
    try:
        settings = Settings.load()
        lock = InstanceLock(settings.db_path)
        try:
            asyncio.run(run(settings, arguments))
        finally:
            lock.close()
    except KeyboardInterrupt:
        pass
    except ValueError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == '__main__':
    main()
