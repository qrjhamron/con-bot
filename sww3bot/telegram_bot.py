"""Private Telegram interface using long polling; no public server required."""
import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from telegram.error import RetryAfter, TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from .agent_engine import Engine, TaskManager
from .agent_store import Store
from .agent_tools import GameExecutor
from .instance_lock import InstanceLock
from .meta_client import MetaClient
from .settings import Settings

HELP = """Kirim perintah Bahasa Indonesia, misalnya:
• Cek status dan ancaman di game saya.
• Bangun recruiting office di kota saya yang belum memilikinya.
• Pindahkan pasukan 123 ke provinsi 456.

/games [ID] — pilih game
/status — status game aktif
/tasks [ID] — progres dan hasil tindakan
/cancel [ID] — batalkan tugas
/reset — hapus konteks percakapan game aktif
/auto on|off — autoplay (default 30 menit)
/help — bantuan

Bot aktif selama komputer dan proses ini menyala.
"""


def split_text(text, limit=3500):
    """Split by UTF-16 length, retaining room below Telegram's message limit."""
    parts, chunk, length = [], [], 0
    for char in text:
        width = 2 if ord(char) > 0xffff else 1
        if length + width > limit:
            parts.append(''.join(chunk))
            chunk, length = [], 0
        chunk.append(char)
        length += width
    if chunk:
        parts.append(''.join(chunk))
    return parts or ['(kosong)']


class TelegramBot:
    def __init__(self, settings, store, engine):
        self.settings, self.store, self.engine = settings, store, engine
        self.app = None
        self.manager = TaskManager(engine, self.notify, self.completed)
        self.send_lock = asyncio.Lock()
        self.auto_task = None
        self.selecting = False
        self.progress_time = 0
        self.game_id = store.preference('game_id', settings.game_id)

    async def send(self, text, keyboard=None):
        async with self.send_lock:
            parts = split_text(self.settings.redact(text))
            for i, part in enumerate(parts):
                for attempt in range(3):
                    try:
                        await self.app.bot.send_message(
                            chat_id=self.settings.telegram_owner_id, text=part,
                            reply_markup=keyboard if i == len(parts) - 1 else None)
                        break
                    except RetryAfter as exc:
                        delay = exc.retry_after
                        if hasattr(delay, 'total_seconds'):
                            delay = delay.total_seconds()
                        await asyncio.sleep(float(delay))
                    except TelegramError:
                        # Results remain available in the journal even when Telegram is offline.
                        break

    async def notify(self, text):
        now = asyncio.get_running_loop().time()
        if now - self.progress_time >= 2:
            self.progress_time = now
            await self.send(text)

    async def completed(self, task_id, game_id, result):
        keyboard = None
        if result.choices:
            self.store.set_preference(f'choice:{task_id}', {'game_id': game_id, 'field': result.choice_field,
                                                            'candidates': result.choices})
            keyboard = self.choice_keyboard(task_id, result.choices, 0)
        await self.send(f'Tugas #{task_id} — {result.status}\n{result.text}', keyboard)

    @staticmethod
    def choice_keyboard(task_id, choices, page):
        start = page * 8
        rows = [[InlineKeyboardButton(str(choice['label'])[:80], callback_data=f'choice:{task_id}:{index}')]
                for index, choice in enumerate(choices[start:start + 8], start)]
        nav = []
        if page:
            nav.append(InlineKeyboardButton('Sebelumnya', callback_data=f'page:{task_id}:{page - 1}'))
        if start + 8 < len(choices):
            nav.append(InlineKeyboardButton('Berikutnya', callback_data=f'page:{task_id}:{page + 1}'))
        if nav:
            rows.append(nav)
        rows.append([InlineKeyboardButton('Batal', callback_data=f'cancel:{task_id}')])
        return InlineKeyboardMarkup(rows)

    def authorized(self, update):
        return bool(update.effective_user and update.effective_chat
                    and update.effective_user.id == self.settings.telegram_owner_id
                    and update.effective_chat.type == ChatType.PRIVATE)

    async def handle(self, update, context):
        if not self.authorized(update):
            return
        if update.callback_query:
            await update.callback_query.answer()
        if not self.store.accept_update(update.update_id):
            return
        if update.callback_query:
            await self.callback(update.callback_query.data or '')
            return
        text = (update.effective_message.text or '').strip()
        if not text:
            return
        command, _, argument = text.partition(' ')
        command = command.split('@')[0].casefold()
        if command in ('/start', '/help'):
            await self.send(HELP + f'\nGame aktif: {self.game_id or "belum dipilih"}.')
        elif command == '/games':
            if argument:
                try:
                    gid = int(argument)
                    if gid <= 0:
                        raise ValueError()
                except ValueError:
                    await self.send('Gunakan /games atau /games ID_GAME.')
                    return
                await self.select_game(gid)
            else:
                await self.games()
        elif command == '/tasks':
            await self.tasks(argument)
        elif command == '/cancel':
            try:
                task_id = int(argument) if argument else None
            except ValueError:
                await self.send('Gunakan /cancel atau /cancel ID_TUGAS.')
                return
            cancelled = self.manager.cancel(task_id)
            await self.send('Pembatalan diminta; aksi terkirim tetap berlaku.' if cancelled else 'Tidak ada tugas yang dapat dibatalkan.')
        elif command == '/reset':
            if self.manager.busy() or self.selecting:
                await self.send('Selesaikan atau batalkan tugas sebelum reset.')
            elif not self.game_id:
                await self.send('Pilih game melalui /games dahulu.')
            else:
                self.store.save_history(self.game_id, [])
                await self.send('Konteks percakapan game aktif dihapus. Jurnal tugas tetap tersedia.')
        elif command == '/auto':
            await self.auto(argument)
        elif command == '/status':
            await self.submit('Panggil get_status lalu laporkan keadaan game aktif secara ringkas.')
        elif command.startswith('/'):
            await self.send('Perintah tidak dikenal. Lihat /help.')
        else:
            await self.submit(text)

    async def submit(self, text):
        if not self.game_id:
            await self.send('Pilih game dengan /games ID_GAME dahulu.')
        elif self.selecting:
            await self.send('Pemilihan game sedang berlangsung. Kirim perintah setelah selesai.')
        elif self.store.waiting_tasks():
            await self.send('Pilih target tugas sebelumnya atau gunakan /cancel dahulu.')
        else:
            task_id = self.manager.submit(self.game_id, text)
            await self.send(f'Tugas #{task_id} diterima.', InlineKeyboardMarkup([
                [InlineKeyboardButton('Batal', callback_data=f'cancel:{task_id}')]]))

    async def games(self):
        try:
            games = await self.engine.executor.list_games()
            note = ''
        except Exception:
            games, note = [], '\nDaftar game akun belum bisa diambil. Gunakan /games ID_GAME.'
        if self.game_id and all(g['id'] != self.game_id for g in games):
            games.insert(0, {'id': self.game_id, 'label': f'Game {self.game_id} (aktif)'})
        rows = [[InlineKeyboardButton(g['label'][:80], callback_data=f"game:{g['id']}")] for g in games[:50]]
        await self.send('Pilih game atau kirim /games ID_GAME.' + note, InlineKeyboardMarkup(rows) if rows else None)

    async def select_game(self, game_id):
        if self.manager.busy() or self.selecting:
            await self.send('Selesaikan atau batalkan tugas sebelum berpindah game.')
            return
        self.selecting = True
        try:
            await self.engine.executor.validate_game(game_id)
            await self.stop_auto()
            self.game_id = game_id
            self.store.set_preference('game_id', game_id)
            session = self.engine.executor.session(game_id)
            await self.send(f'Game {game_id} dipilih, pemain {session.player_id}. Autoplay nonaktif.')
        except Exception:
            await self.send('Game tidak dapat dibuka atau pemain belum teridentifikasi. Periksa ID game dan konfigurasi akun/PLAYER_ID.')
        finally:
            self.selecting = False

    async def tasks(self, argument):
        if argument:
            try:
                task_id = int(argument)
            except ValueError:
                await self.send('Gunakan /tasks atau /tasks ID_TUGAS.')
                return
            task = self.store.task(task_id)
            if not task:
                await self.send('Tugas tidak ditemukan.')
                return
            lines = [f"#{task_id} game {task['game_id']} — {task['status']}", task['result'] or task['prompt']]
            lines.extend(f"Langkah {s['id']}: {s['name'].split('.')[-1]} — {s['status']}" for s in self.store.steps(task_id))
            await self.send('\n'.join(lines))
            if task['status'] == 'waiting':
                choice = self.store.preference(f'choice:{task_id}')
                if choice:
                    await self.send('Pilih target:', self.choice_keyboard(task_id, choice['candidates'], 0))
        else:
            rows = self.store.tasks()
            await self.send('\n'.join(f"#{r['id']} game {r['game_id']} — {r['status']}" for r in rows) or 'Belum ada tugas.')

    async def callback(self, data):
        try:
            parts = data.split(':')
            action, identifier = parts[0], int(parts[1])
            if action == 'game':
                await self.select_game(identifier)
            elif action == 'cancel':
                await self.send('Pembatalan diminta.' if self.manager.cancel(identifier) else 'Tugas sudah selesai.')
            elif action in ('choice', 'page'):
                task = self.store.task(identifier)
                choice = self.store.preference(f'choice:{identifier}')
                if not task or task['status'] != 'waiting' or not choice or choice['game_id'] != self.game_id:
                    await self.send('Pilihan sudah tidak aktif. Lihat /tasks.')
                    return
                index = int(parts[2])
                if action == 'page':
                    if index < 0 or index * 8 >= len(choice['candidates']):
                        raise ValueError()
                    await self.send('Pilih target:', self.choice_keyboard(identifier, choice['candidates'], index))
                else:
                    if index < 0:
                        raise ValueError()
                    selected = choice['candidates'][index]
                    prompt = (f"Lanjutkan tugas sebelumnya tanpa mengulang langkah yang sudah dijalankan. "
                              f"Pemilik memilih {choice['field']}={selected['id']} ({selected['label']}).")
                    self.manager.submit(self.game_id, prompt, identifier)
                    await self.send(f'Tugas #{identifier} dilanjutkan.')
        except (ValueError, IndexError, KeyError):
            await self.send('Tombol tidak valid. Lihat /help.')

    async def stop_auto(self):
        if self.auto_task:
            self.auto_task.cancel()
            try:
                await self.auto_task
            except asyncio.CancelledError:
                pass
            self.auto_task = None

    async def auto(self, argument):
        if argument.casefold() == 'off':
            await self.stop_auto()
            await self.send('Autoplay nonaktif. Gunakan /cancel untuk menghentikan siklus yang sedang berjalan.')
        elif argument.casefold() == 'on' and self.game_id and not self.selecting:
            if not self.auto_task:
                self.auto_task = asyncio.create_task(self.auto_loop())
            await self.send(f'Autoplay aktif setiap {self.settings.auto_interval} menit. Siklus pertama dimulai ketika antrean kosong.')
        else:
            await self.send('Pilih game dahulu, lalu gunakan /auto on atau /auto off.')

    async def auto_loop(self):
        while True:
            if not self.manager.busy() and not self.selecting:
                self.manager.submit(self.game_id, 'Jalankan full_conquest_cycle dan laporkan hasil setiap tahap.')
            await asyncio.sleep(self.settings.auto_interval * 60)

    async def startup(self, app):
        self.app = app
        self.manager.start()

    async def shutdown(self, app):
        await self.stop_auto()
        await self.manager.close()

    def application(self):
        app = (Application.builder().token(self.settings.telegram_bot_token.get_secret_value())
               .concurrent_updates(8).post_init(self.startup).post_stop(self.shutdown).build())
        for command in ('start', 'help', 'games', 'status', 'tasks', 'cancel', 'reset', 'auto'):
            app.add_handler(CommandHandler(command, self.handle))
        app.add_handler(CallbackQueryHandler(self.handle))
        app.add_handler(MessageHandler(filters.TEXT, self.handle))

        async def error_handler(update, context):
            # No raw exception logging: URLs may contain the Telegram bot token.
            logging.getLogger(__name__).warning('Telegram update gagal diproses; jurnal tugas tersedia.')
        app.add_error_handler(error_handler)
        return app


def main():
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    try:
        settings = Settings.load(telegram=True)
        lock = InstanceLock(settings.db_path)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    store = Store(settings.db_path)
    meta = MetaClient(settings.model_api_key.get_secret_value())
    executor = GameExecutor(settings)
    bot = TelegramBot(settings, store, Engine(settings, meta, executor, store))
    try:
        app = bot.application()
    except TelegramError:
        store.close()
        lock.close()
        raise SystemExit('Token Telegram tidak valid. Periksa TELEGRAM_BOT_TOKEN.') from None

    async def final_cleanup(application):
        await meta.close()
        executor.close()
    app.post_shutdown = final_cleanup
    try:
        app.run_polling(allowed_updates=['message', 'callback_query'], drop_pending_updates=False)
    except TelegramError:
        raise SystemExit('Telegram tidak dapat terhubung. Periksa token dan koneksi internet.') from None
    finally:
        store.close()
        lock.close()


if __name__ == '__main__':
    main()
