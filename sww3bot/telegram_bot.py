"""Private Telegram interface using long polling; no public server required."""
import asyncio
import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ChatType
from telegram.error import RetryAfter, TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from .agent_engine import Engine, TaskManager
from .agent_store import Store
from .agent_tools import GameExecutor
from .instance_lock import InstanceLock
from .meta_client import MetaClient
from .settings import Settings

HELP = """Langsung ngobrol aja, bro. Nggak perlu hafal command.
Contoh:
• Negara gua sekarang aman nggak?
• Bagusnya gua bangun apa dulu?
• Pasukan gua cukup buat bertahan?
• Kenapa resource gua kurang?

Bisa lanjut nanya "kenapa?" atau "terus gimana?" — konteksnya diingat.
Kalau cuma nanya atau minta saran, bot memberi analisis. Untuk menjalankan aksi,
bilang jelas, misalnya "bangun recruiting office di Jakarta".

Tombol di bawah bisa dipakai buat mulai ngobrol.
"""

COMMAND_HELP = """
/games [ID] — pilih game
/status — status game aktif
/tasks [ID] — progres dan hasil tindakan
/cancel [ID] — batalkan tugas
/reset — hapus konteks percakapan game aktif
/auto on|off — autoplay (default 30 menit)
/overnight 8|off|status — kontrol ekonomi terbatas waktu
/commander 8|off|status — ekonomi, produksi, riset, dan pertahanan
/fullauto [8|off|status] — full auto reasoning high (default 8 jam)
/stacks — optimizer komposisi pasukan
/air — pangkalan, patroli dan refuel
/occupation — insurgency dan garnisun kota
/queue [pause|resume] — semua antrean dan kendali jeda
/events — perubahan game teramati
/economy — budget dan cadangan seluruh rencana
/military — pasukan idle dan cakupan pertahanan
/map [negara] — kota dan homeland
/contacts — kontak musuh yang terlihat tanpa spy
/combat [target] — analisis tempur darat
/coordination — progres kelompok dan rally
/help — bantuan

Bot aktif selama komputer dan proses ini menyala.
"""

QUICK_PROMPTS = {
    'status': 'Gimana kondisi negara gua sekarang? Ringkas yang penting aja.',
    'advice': 'Menurut lu, apa yang perlu gua prioritaskan sekarang? Kasih saran aja, jangan jalankan tindakan.',
    'military': 'Pasukan dan pertahanan gua sekarang gimana? Apa kelemahannya? Analisis aja, jangan jalankan tindakan.',
    'economy': 'Ekonomi dan resource gua gimana? Apa yang perlu dibenerin? Kasih saran aja, jangan jalankan tindakan.',
}


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
        self.overnight_task = None
        self.commander_monitor = None
        self.typing_task = None
        self.selecting = False
        self.progress_time = 0
        self.action_notice = None
        self.game_id = store.preference('game_id', settings.game_id)

    @staticmethod
    def chat_keyboard():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton('Kondisi negara', callback_data='quick:status'),
             InlineKeyboardButton('Saran langkah', callback_data='quick:advice')],
            [InlineKeyboardButton('Pasukan', callback_data='quick:military'),
             InlineKeyboardButton('Ekonomi', callback_data='quick:economy')],
        ])

    async def typing(self):
        # Typing is best effort; connectivity errors must not interrupt a task.
        send_action = getattr(self.app.bot, 'send_chat_action', None)
        if send_action:
            try:
                await send_action(chat_id=self.settings.telegram_owner_id, action=ChatAction.TYPING)
            except TelegramError:
                pass

    async def show_typing(self):
        await self.typing()
        if self.typing_task is None or self.typing_task.done():
            self.typing_task = asyncio.create_task(self.keep_typing())

    async def keep_typing(self):
        while self.manager.pending:
            await asyncio.sleep(4)
            if self.manager.pending:
                await self.typing()

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
        if ': mengirim ' in text:
            task = text.partition(': mengirim ')[0]
            if self.action_notice != task:
                self.action_notice = task
                await self.send('Lagi menjalankan tindakan yang lu minta…', InlineKeyboardMarkup([
                    [InlineKeyboardButton('Hentikan', callback_data=f'cancel:{task.split("#")[-1]}')]]))
            return
        now = asyncio.get_running_loop().time()
        if now - self.progress_time >= 2:
            self.progress_time = now
            await self.typing()

    async def completed(self, task_id, game_id, result):
        night = self.store.preference('overnight_control', {})
        monitor_task = self.store.preference('commander_monitor_task', {}).get('task_id')
        if task_id in (night.get('last_task_id'), monitor_task):
            latest = self.store.preference(f'commander_last:{game_id}', {})
            if latest.get('alerts') and latest.get('checked_at', 0) > self.store.preference(f'commander_alerted:{game_id}', 0):
                self.store.set_preference(f'commander_alerted:{game_id}', latest['checked_at'])
                await self.send('Perubahan penting: ' + ', '.join(latest['alerts']) + '. Detail: /events.')
            if result.status == 'failed':
                await self.send(result.text + ' Detail: /queue dan /tasks.')
        if night.get('last_task_id') == task_id:
            if night.get('mode') == 'full_auto' and result.status == 'completed':
                latest = self.store.preference(f'full_auto_last:{game_id}', {})
                now = time.time()
                if latest.get('actions') or latest.get('alerts') or now - night.get('last_report_at', 0) >= 1800:
                    await self.send(result.text + '\nHentikan: /fullauto off. Detail: /queue.')
                    night['last_report_at'] = now
            night.update(last_result=result.text, last_checked=time.time())
            self.store.set_preference('overnight_control', night)
            return
        if self.store.preference('commander_monitor_task', {}).get('task_id') == task_id:
            return
        keyboard = self.chat_keyboard()
        if result.choices:
            self.store.set_preference(f'choice:{task_id}', {'game_id': game_id, 'field': result.choice_field,
                                                            'candidates': result.choices})
            keyboard = self.choice_keyboard(task_id, result.choices, 0)
        text = result.text
        if result.status not in ('completed', 'waiting'):
            text += f'\nDetail tersedia lewat /tasks {task_id}.'
        await self.send(text, keyboard)

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
            help_text = HELP + (COMMAND_HELP if command == '/help' else '')
            await self.send(help_text + f'\nGame aktif: {self.game_id or "belum dipilih"}.', self.chat_keyboard())
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
            if not argument:
                await self.stop_overnight()
                self.store.set_preference(f'commander_paused:{self.game_id}', True)
                monitor = self.store.preference('commander_monitor_task', {})
                if monitor.get('task_id'):
                    self.manager.cancel(monitor['task_id'])
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
        elif command == '/overnight':
            await self.overnight(argument)
        elif command == '/fullauto':
            await self.overnight(argument or '8', mode='full_auto')
        elif command == '/stacks':
            await self.submit('Panggil optimize_army_stacks dan ringkas rekomendasi grup serta alasan unit ditahan. Hanya baca data.')
        elif command == '/air':
            await self.submit('Panggil get_air_operations_plan dan ringkas pangkalan, patroli, refuel serta celah cakupan. Hanya baca data.')
        elif command == '/occupation':
            await self.submit('Panggil get_occupation_plan dan ringkas kota rawan insurgency serta garnisunnya. Hanya baca data.')
        elif command == '/commander':
            await self.overnight(argument, mode='commander')
        elif command == '/queue':
            if argument.casefold() in ('pause', 'resume'):
                paused = argument.casefold() == 'pause'
                self.store.set_preference(f'commander_paused:{self.game_id}', paused)
                if paused:
                    for task_id in (self.store.preference('overnight_control', {}).get('last_task_id'),
                                    self.store.preference('commander_monitor_task', {}).get('task_id')):
                        if task_id:
                            self.manager.cancel(task_id)
                else:
                    self.store.set_preference(f'commander_next:{self.game_id}', 0)
                await self.send('Antrean dijeda; pekerjaan yang sudah dikirim tetap dipantau.' if paused else 'Antrean dilanjutkan.')
            else:
                await self.submit('Panggil get_commander_queue dan ringkas status setiap pekerjaan; accepted belum berarti selesai.')
        elif command == '/map':
            await self.submit(('Cari ID negara ' + argument + ' lewat resolve_target jika perlu. ' if argument else '') +
                              'Panggil get_map_regions dan jelaskan kota, core/homeland, dan pemilik sekarang. Hanya analisis.')
        elif command == '/combat':
            await self.submit('Analisis tempur darat, hanya baca data. ' +
                              ('Cari target ' + argument + ' lewat resolve_target, lalu get_combat_plan. Jelaskan HP, terrain, komposisi, dan alasan maju/tahan.' if argument else
                               'Ringkas kesiapan pasukan dan jelaskan bahwa penilaian pertempuran memerlukan target.'))
        elif command == '/coordination':
            await self.submit('Panggil get_coordinations dan ringkas fase rally, target berikutnya, serta alasan tertahan. Jangan menjalankan tindakan.')
        elif command == '/contacts':
            await self.submit('Panggil get_visible_enemy_units dan laporkan kontak saat ini terpisah dari last_seen. Fog tetap unknown. Jangan menjalankan aksi.')
        elif command in ('/events', '/economy', '/military'):
            tool = {'/events': 'get_game_events', '/economy': 'get_economy_plan', '/military': 'get_military_plan'}[command]
            await self.submit(f'Panggil {tool} lalu beri ringkasan saja, jangan menjalankan tindakan.')
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
            queued = self.manager.busy()
            task_id = self.manager.submit(self.game_id, text)
            if queued:
                await self.send('Pesan lu masuk antrean, gua jawab setelah yang sebelumnya selesai.', InlineKeyboardMarkup([
                    [InlineKeyboardButton('Batal', callback_data=f'cancel:{task_id}')]]))
            else:
                await self.show_typing()

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
            await self.stop_overnight()
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
            if parts[0] == 'quick':
                await self.submit(QUICK_PROMPTS[parts[1]])
                return
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
            if self.store.preference('overnight_control', {}).get('enabled'):
                await self.send('Hentikan kontrol otomatis dengan /fullauto off atau /overnight off sebelum mengaktifkan autoplay perang.')
                return
            if not self.auto_task:
                self.auto_task = asyncio.create_task(self.auto_loop())
            await self.send(f'Autoplay aktif setiap {self.settings.auto_interval} menit. Siklus pertama dimulai ketika antrean kosong.')
        else:
            await self.send('Pilih game dahulu, lalu gunakan /auto on atau /auto off.')

    async def auto_loop(self):
        while True:
            if not self.manager.busy() and not self.manager.pending and not self.selecting:
                self.manager.submit(self.game_id, 'Jalankan full_conquest_cycle dan laporkan hasil setiap tahap.')
            await asyncio.sleep(self.settings.auto_interval * 60)

    async def startup(self, app):
        self.app = app
        self.manager.start()
        if self.store.preference('overnight_control', {}).get('enabled'):
            self.overnight_task = asyncio.create_task(self.overnight_loop())
        self.commander_monitor = asyncio.create_task(self.commander_loop())

    async def stop_overnight(self):
        config = self.store.preference('overnight_control', {})
        if config.get('enabled'):
            config.update(enabled=False, reason='owner_stopped')
            self.store.set_preference('overnight_control', config)
            task_id = config.get('last_task_id')
            if task_id:
                self.manager.cancel(task_id)
        if self.overnight_task:
            self.overnight_task.cancel()
            try:
                await self.overnight_task
            except asyncio.CancelledError:
                pass
            self.overnight_task = None

    async def overnight(self, argument, mode='economy'):
        if argument.casefold() == 'off':
            await self.stop_overnight()
            await self.send('Kontrol otomatis dihentikan. Pekerjaan yang sudah dikirim tetap dipantau.')
            return
        if argument.casefold() in ('', 'status'):
            config = self.store.preference('overnight_control', {})
            remaining = max(0, config.get('deadline', 0) - time.time()) / 3600
            await self.send(f"Kontrol {config.get('mode', 'economy')}: {'aktif' if config.get('enabled') and remaining else 'nonaktif'}; "
                            f"sisa {remaining:.1f} jam. " + config.get('last_result', 'Belum ada hasil.'))
            return
        try:
            hours = float(argument)
            if not 0 < hours <= 8 or not self.game_id or self.selecting or self.manager.busy():
                raise ValueError()
        except ValueError:
            await self.send('Gunakan /overnight 8, /overnight status, atau /overnight off. Selesaikan tugas aktif dahulu.')
            return
        await self.engine.executor.validate_game(self.game_id)
        await self.stop_auto()
        await self.stop_overnight()
        started = time.time()
        self.store.set_preference('overnight_control', {
            'enabled': True, 'game_id': self.game_id,
            'player_id': self.engine.executor.session(self.game_id).player_id,
            'started_at': started, 'deadline': started + hours * 3600, 'next_check': 0, 'mode': mode})
        self.store.set_preference(f'commander_paused:{self.game_id}', False)
        self.overnight_task = asyncio.create_task(self.overnight_loop())
        await self.send(f'Kontrol {mode} aktif {hours:g} jam. ' +
                        ('Cek setiap 5 menit dengan reasoning high: semua unit, occupation, udara, musuh terlihat, resource, riset dan queue. Laporan aksi/perubahan penting serta ringkasan 30 menit. ' if mode == 'full_auto' else
                         'Cek setiap 5 menit: queue, produksi infanteri, riset relevan, industri, dan penempatan pertahanan sendiri. '
                         if mode == 'commander' else 'Cek setiap 10 menit: Arms Industry di kota yang belum punya. ') +
                        'Cadangan resource dijaga. Hentikan melalui /commander off atau /overnight off.')

    async def overnight_loop(self):
        while True:
            config = self.store.preference('overnight_control', {})
            if not config.get('enabled'):
                return
            if config['game_id'] != self.game_id or time.time() >= config['deadline']:
                config.update(enabled=False, reason='time_or_game_changed')
                self.store.set_preference('overnight_control', config)
                if config.get('last_task_id'):
                    self.manager.cancel(config['last_task_id'])
                await self.send('Waktu kontrol otomatis selesai. ' + config.get('last_result', '') + ' Detail: /tasks dan /queue.')
                return
            if not self.manager.busy() and not self.selecting and time.time() >= config.get('next_check', 0):
                async def operation(runtime, snapshot=dict(config)):
                    if snapshot.get('mode') == 'full_auto':
                        from .full_auto import cycle as full_cycle
                        return await full_cycle(self.engine, self.store, runtime, snapshot)
                    if snapshot.get('mode') == 'commander':
                        from .commander import cycle
                    else:
                        from .overnight import cycle
                    return await cycle(self.engine.executor, self.store, runtime, snapshot)
                task_id = self.manager.submit_operation(self.game_id, 'Kontrol otonom sesuai profil yang disetujui.', operation)
                config.update(last_task_id=task_id, next_check=time.time() + (300 if config.get('mode') in ('commander', 'full_auto') else 600))
                self.store.set_preference('overnight_control', config)
            await asyncio.sleep(5)

    async def commander_loop(self):
        from .commander import cycle
        while True:
            config = self.store.preference('overnight_control', {})
            if config.get('enabled') and config.get('mode') == 'full_auto' and (self.overnight_task is None or self.overnight_task.done()):
                await self.stop_auto()
                self.overnight_task = asyncio.create_task(self.overnight_loop())
            waiting = bool(self.store.waiting_tasks())
            auto_cycle = config.get('enabled') and config.get('mode') in ('commander', 'full_auto') and time.time() < config.get('deadline', 0)
            if self.game_id and not self.selecting and not self.manager.pending and (not auto_cycle or waiting) and \
                    time.time() >= self.store.preference(f'commander_next:{self.game_id}', 0):
                gid = self.game_id
                async def operation(runtime, game_id=gid, observe_only=waiting):
                    return await cycle(self.engine.executor, self.store, runtime,
                                       {'game_id': game_id, 'enabled': False, 'observe_only': observe_only})
                task_id = self.manager.submit_operation(gid, 'Pantau event dan jalankan queue yang diminta pemilik.', operation)
                self.store.set_preference('commander_monitor_task', {'task_id': task_id, 'game_id': gid})
                self.store.set_preference(f'commander_next:{gid}', time.time() + 300)
            await asyncio.sleep(5)

    async def shutdown(self, app):
        await self.stop_auto()
        # Preserve the original deadline for recovery after a process restart.
        if self.overnight_task:
            self.overnight_task.cancel()
            try:
                await self.overnight_task
            except asyncio.CancelledError:
                pass
        if self.commander_monitor:
            self.commander_monitor.cancel()
            try:
                await self.commander_monitor
            except asyncio.CancelledError:
                pass
        await self.manager.close()
        if self.typing_task:
            self.typing_task.cancel()
            try:
                await self.typing_task
            except asyncio.CancelledError:
                pass

    def application(self):
        app = (Application.builder().token(self.settings.telegram_bot_token.get_secret_value())
               .concurrent_updates(8).post_init(self.startup).post_stop(self.shutdown).build())
        for command in ('start', 'help', 'games', 'status', 'tasks', 'cancel', 'reset', 'auto', 'overnight',
                        'commander', 'fullauto', 'stacks', 'air', 'occupation', 'queue', 'events', 'economy', 'military', 'map', 'contacts', 'combat', 'coordination'):
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
