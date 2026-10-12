import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.error import RetryAfter
from sww3bot.agent_engine import Engine, Outcome
from sww3bot.telegram_bot import TelegramBot, split_text


@pytest.fixture
def bot(settings, store):
    executor = SimpleNamespace(list_games=AsyncMock(return_value=[{'id': 42, 'label': 'Game 42'}]),
        validate_game=AsyncMock(), session=lambda gid: SimpleNamespace(player_id=7))
    engine = Engine(settings, AsyncMock(), executor, store)
    value = TelegramBot(settings, store, engine)
    value.app = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    return value


def update(text='/help', uid=123, chat_type='private', update_id=1, callback=None):
    return SimpleNamespace(effective_user=SimpleNamespace(id=uid), effective_chat=SimpleNamespace(type=chat_type),
                           effective_message=SimpleNamespace(text=text), update_id=update_id, callback_query=callback)


async def test_owner_only_and_private_chat(bot):
    for uid, chat_type in [(999, 'private'), (123, 'group'), (123, 'supergroup')]:
        await bot.handle(update(uid=uid, chat_type=chat_type), None)
    bot.app.bot.send_message.assert_not_called()
    assert bot.store.tasks() == []


async def test_deduplicates_text_and_callback(bot):
    bot.manager.submit = MagicMock(return_value=10)
    await bot.handle(update(text='cek status'), None)
    await bot.handle(update(text='cek status'), None)
    assert bot.manager.submit.call_count == 1
    callback = SimpleNamespace(data='cancel:10', answer=AsyncMock())
    bot.manager.cancel = MagicMock(return_value=True)
    await bot.handle(update(update_id=2, callback=callback), None)
    await bot.handle(update(update_id=2, callback=callback), None)
    assert bot.manager.cancel.call_count == 1
    assert callback.answer.call_count == 2


async def test_game_switch_blocked_by_pending_task(bot):
    bot.manager.submit(42, 'status')
    await bot.select_game(43)
    bot.engine.executor.validate_game.assert_not_called()
    assert bot.game_id == 42


async def test_game_switch_validates_and_disables_autoplay(bot):
    bot.auto_task = asyncio.create_task(asyncio.sleep(999))
    await bot.select_game(43)
    bot.engine.executor.validate_game.assert_awaited_once_with(43)
    assert bot.game_id == 43
    assert bot.store.preference('game_id') == 43
    assert bot.auto_task is None


async def test_game_connection_error_preserves_selected_game(bot):
    bot.engine.executor.validate_game.side_effect = ValueError('bad')
    await bot.select_game(43)
    assert bot.game_id == 42


async def test_ambiguity_buttons_resume_once_and_stale_click_is_ignored(bot):
    task = bot.store.new_task(42, 'serang target')
    bot.store.finish_task(task, 'waiting')
    await bot.completed(task, 42, Outcome('Pilih', 'waiting', [{'id': 8, 'label': 'Sudan'}], 'player_id'))
    markup = bot.app.bot.send_message.call_args.kwargs['reply_markup']
    assert markup.inline_keyboard[0][0].callback_data == f'choice:{task}:0'
    await bot.callback(f'choice:{task}:0')
    assert bot.store.task(task)['status'] == 'queued'
    assert bot.manager.queue.qsize() == 1
    await bot.callback(f'choice:{task}:0')
    assert bot.manager.queue.qsize() == 1


async def test_reset_blocked_until_tasks_complete(bot):
    bot.store.save_history(42, [{'role': 'user', 'content': 'hello'}])
    task = bot.manager.submit(42, 'status')
    await bot.handle(update('/reset'), None)
    assert bot.store.history(42)
    bot.manager.pending.clear()
    bot.store.finish_task(task, 'completed')
    await bot.handle(update('/reset', update_id=2), None)
    assert bot.store.history(42) == []


async def test_message_split_escapes_no_markdown_and_preserves_unicode(bot):
    text = '😀' * 5000 + '_literal_' + '<x>'
    assert ''.join(split_text(text)) == text
    await bot.send(text)
    calls = bot.app.bot.send_message.call_args_list
    assert len(calls) > 1
    assert all(len(c.kwargs['text'].encode('utf-16-le')) // 2 <= 3500 for c in calls)
    assert all('parse_mode' not in c.kwargs for c in calls)


async def test_telegram_rate_limit_retry(bot, monkeypatch):
    monkeypatch.setenv('PTB_TIMEDELTA', '1')
    bot.app.bot.send_message.side_effect = [RetryAfter(1), None]
    monkeypatch.setattr('sww3bot.telegram_bot.asyncio.sleep', AsyncMock())
    await bot.send('OK')
    assert bot.app.bot.send_message.call_count == 2


async def test_autoplay_explicit_and_does_not_overlap(bot):
    assert bot.auto_task is None
    await bot.auto('on')
    await asyncio.sleep(0)
    assert bot.manager.queue.qsize() == 1
    task = bot.auto_task
    await bot.auto('on')
    assert bot.auto_task is task
    await bot.auto('off')
    assert bot.auto_task is None
    assert bot.manager.queue.qsize() == 1


async def test_waiting_task_blocks_new_command_and_game_switch(bot):
    task = bot.store.new_task(42, 'choice')
    bot.store.finish_task(task, 'waiting')
    await bot.submit('new')
    assert bot.manager.queue.empty()
    await bot.select_game(43)
    assert bot.game_id == 42
    assert bot.manager.cancel(task)
    await bot.submit('new')
    assert bot.manager.queue.qsize() == 1


def test_application_wires_handlers_without_network(bot):
    app = bot.application()
    assert len(app.handlers[0]) == 25
    assert app.post_init == bot.startup
    assert app.post_stop == bot.shutdown


def test_auto_status_never_enabled(store):
    from sww3bot.telegram_bot import auto_status_text
    text = auto_status_text(store, 42, now=1000.0)
    assert 'nonaktif' in text
    assert 'Belum ada hasil' in text


def test_auto_status_active_shows_queue_pause_and_next_check(store):
    from sww3bot.telegram_bot import auto_status_text
    now = 2000.0
    store.set_preference('overnight_control', {
        'enabled': True, 'mode': 'commander', 'game_id': 42,
        'deadline': now + 7200, 'next_check': now + 240,
        'last_checked': now - 120, 'last_result': 'Commander: 1 perintah diproses.'})
    store.enqueue_commander(42, 7, 'build', {'city_id': 10, 'item_id': 100})
    store.enqueue_commander(42, 7, 'produce', {'city_id': 20, 'item_id': 201})
    store.set_preference('commander_paused:42', True)
    text = auto_status_text(store, 42, now=now)
    assert 'aktif' in text
    assert 'sisa 2.0 jam' in text
    assert 'antrean 2 menunggu' in text
    assert 'jeda: ya' in text
    assert 'cek berikutnya' in text
    assert '2 mnt lalu' in text
    assert 'Commander: 1 perintah diproses.' in text


def test_auto_status_warns_on_game_mismatch_and_reason(store):
    from sww3bot.telegram_bot import auto_status_text
    now = 3000.0
    store.set_preference('overnight_control', {
        'enabled': False, 'mode': 'economy', 'game_id': 99,
        'deadline': now - 10, 'reason': 'owner_stopped',
        'last_result': 'Kontrol dihentikan.'})
    text = auto_status_text(store, 42, now=now)
    assert 'nonaktif' in text
    assert 'owner_stopped' in text
    assert 'game kontrol 99' in text
    assert 'game aktif 42' in text


async def test_overnight_status_reports_queue_and_pause(bot):
    import time
    now = time.time()
    bot.store.set_preference('overnight_control', {
        'enabled': True, 'mode': 'full_auto', 'game_id': 42,
        'deadline': now + 3600, 'next_check': now + 600,
        'last_checked': now - 30, 'last_result': 'Cek selesai.'})
    bot.store.enqueue_commander(42, 7, 'research', {'item_id': 90})
    await bot.overnight('status')
    sent = bot.app.bot.send_message.call_args.kwargs['text']
    assert 'aktif' in sent
    assert 'antrean 1 menunggu' in sent
    assert 'jeda: tidak' in sent
