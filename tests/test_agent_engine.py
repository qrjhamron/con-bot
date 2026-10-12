import asyncio
import copy
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from sww3bot.agent_engine import SYSTEM_PROMPT, Engine, Outcome, Runtime, TaskManager
from sww3bot.agent_tools import Registry, ToolResult
from sww3bot.meta_client import MetaClient, MetaError
from sww3bot.settings import MODEL, META_URL


def call(name='get_status', args=None, identifier='c1'):
    return {'id': identifier, 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(args or {})}}


class FakeMeta:
    def __init__(self, *messages):
        self.messages = list(messages)
        self.requests = []

    async def complete(self, messages, tools=None):
        self.requests.append(copy.deepcopy(messages))
        result = self.messages.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeExecutor:
    def __init__(self, result=None):
        def read():
            pass
        self.registry = Registry([{'name': 'get_status', 'description': 'status', 'fn': read, 'parameters': {}}])
        self.calls = []
        self.result = result or ToolResult(ok=True, data={'day': 5})

    async def execute(self, game_id, name, args, runtime):
        self.calls.append((game_id, name, args))
        tool, validated = self.registry.validate(name, args)
        return self.result if tool else validated


def runtime(settings, store):
    task = store.new_task(42, 'cek status')
    return Runtime(task, settings, store, AsyncMock())


def test_doctrine_covers_war_economy_and_memory():
    for marker in ('get_war_map', 'get_enemy_production', 'record_lesson',
                   'Doktrin WW3 4x', 'Recruiting Office', 'morale'):
        assert marker in SYSTEM_PROMPT


async def test_lessons_injected_into_system_prompt(settings, store):
    store.set_preference('lessons:42', [{'text': 'jangan serang produsen top', 'day': 5}])
    meta = FakeMeta({'content': 'siap'})
    engine = Engine(settings, meta, FakeExecutor(), store)
    await engine.run(42, 'cek status', runtime(settings, store))
    system = meta.requests[0][0]['content']
    assert 'jangan serang produsen top' in system


async def test_no_lessons_no_brief_block(settings, store):
    meta = FakeMeta({'content': 'siap'})
    engine = Engine(settings, meta, FakeExecutor(), store)
    await engine.run(42, 'cek status', runtime(settings, store))
    assert 'Pelajaran dari sesi lalu' not in meta.requests[0][0]['content']


async def test_native_tool_loop_and_game_isolation(settings, store):
    meta = FakeMeta({'tool_calls': [call()]}, {'content': 'Hari 5.'})
    executor = FakeExecutor()
    engine = Engine(settings, meta, executor, store)
    result = await engine.run(42, 'cek status', runtime(settings, store))
    assert result.text == 'Hari 5.'
    assert executor.calls == [(42, 'get_status', {})]
    assert meta.requests[1][-1]['role'] == 'tool'
    assert meta.requests[1][-1]['tool_call_id'] == 'c1'
    assert store.history(43) == []


async def test_plain_json_is_never_executed(settings, store):
    meta = FakeMeta({'content': '{"name":"get_status","parameters":{}}'})
    executor = FakeExecutor()
    await Engine(settings, meta, executor, store).run(42, 'status', runtime(settings, store))
    assert executor.calls == []


async def test_cancel_mid_batch_completes_protocol_without_second_action(settings, store):
    meta = FakeMeta({'tool_calls': [call(identifier='a'), call(identifier='b')]})
    executor = FakeExecutor()
    rt = runtime(settings, store)
    original = executor.execute

    async def execute(*args):
        result = await original(*args)
        rt.cancelled.set()
        return result
    executor.execute = execute
    result = await Engine(settings, meta, executor, store).run(42, 'status', rt)
    assert result.status == 'cancelled'
    assert len(executor.calls) == 1
    assert [m['tool_call_id'] for m in store.history(42) if m['role'] == 'tool'] == ['a', 'b']


async def test_ambiguity_pauses_and_skips_other_calls(settings, store):
    meta = FakeMeta({'tool_calls': [call(identifier='a'), call(identifier='b')]})
    executor = FakeExecutor(ToolResult(ok=False, error={'code': 'ambiguous', 'message': 'Pilih target',
        'candidates': [{'id': 1, 'label': 'Sudan'}, {'id': 2, 'label': 'South Sudan'}], 'field': 'player_id'}))
    result = await Engine(settings, meta, executor, store).run(42, 'pilih Sudan', runtime(settings, store))
    assert result.status == 'waiting'
    assert len(result.choices) == 2
    assert len(executor.calls) == 1


async def test_tool_budget_and_partial_results(settings, store):
    settings.max_tools = 1
    meta = FakeMeta({'tool_calls': [call(identifier='a'), call(identifier='b')]})
    executor = FakeExecutor()
    rt = runtime(settings, store)
    step = store.start_step(rt.task_id, 'move', {})
    store.finish_step(step, {'ok': True})
    result = await Engine(settings, meta, executor, store).run(42, 'status', rt)
    assert result.status == 'limited'
    assert '1 berhasil' in result.text
    assert len(executor.calls) == 1


async def test_round_budget(settings, store):
    settings.max_rounds = 1
    executor = FakeExecutor()
    meta = FakeMeta({'tool_calls': [call()]})
    result = await Engine(settings, meta, executor, store).run(42, 'status', runtime(settings, store))
    assert result.status == 'limited'


async def test_malformed_arguments_and_unknown_tool(settings, store):
    bad = call()
    bad['function']['arguments'] = 'not json'
    meta = FakeMeta({'tool_calls': [bad, call('unknown', identifier='u')]}, {'content': 'Argumen salah.'})
    executor = FakeExecutor()
    await Engine(settings, meta, executor, store).run(42, 'status', runtime(settings, store))
    results = [json.loads(m['content']) for m in store.history(42) if m['role'] == 'tool']
    assert [r['error']['code'] for r in results] == ['invalid_arguments', 'unknown_tool']


async def test_history_compaction_keeps_complete_tool_groups(settings, store):
    history = []
    for i in range(8):
        history.extend([{'role': 'user', 'content': 'x' * 4000},
                        {'role': 'assistant', 'tool_calls': [call(identifier=str(i))]},
                        {'role': 'tool', 'tool_call_id': str(i), 'content': '{}'},
                        {'role': 'assistant', 'content': 'done'}])
    store.save_history(42, history)
    meta = FakeMeta({'content': 'Ringkasan tujuan dan aksi.'}, {'content': 'OK'})
    await Engine(settings, meta, FakeExecutor(), store).run(42, 'lanjut', runtime(settings, store))
    kept = store.history(42)
    assert len(kept) < len(history)
    calls = {c['id'] for m in kept for c in m.get('tool_calls', [])}
    results = {m['tool_call_id'] for m in kept if m['role'] == 'tool'}
    assert calls == results


async def test_redacts_configured_credentials(settings, store):
    meta = FakeMeta({'content': settings.model_api_key.get_secret_value()})
    result = await Engine(settings, meta, FakeExecutor(), store).run(42, settings.bot_pass.get_secret_value(), runtime(settings, store))
    assert result.text == '[redacted]'
    assert 'fake-password-secret' not in json.dumps(store.history(42))


async def test_queue_is_sequential_and_cancel_queued(settings, store):
    active = 0
    maximum = 0
    started = asyncio.Event()
    release = asyncio.Event()

    class QueueEngine:
        def __init__(self):
            self.settings, self.store = settings, store

        async def run(self, game, prompt, rt):
            nonlocal active, maximum
            if rt.cancelled.is_set():
                return Outcome('cancelled', 'cancelled')
            active += 1
            maximum = max(maximum, active)
            started.set()
            await release.wait()
            active -= 1
            return Outcome('OK')

    completed = AsyncMock()
    manager = TaskManager(QueueEngine(), AsyncMock(), completed)
    manager.start()
    first = manager.submit(42, 'first')
    await started.wait()
    second = manager.submit(42, 'second')
    assert manager.cancel(second)
    release.set()
    await manager.queue.join()
    assert maximum == 1
    assert store.task(first)['status'] == 'completed'
    assert store.task(second)['status'] == 'cancelled'
    await manager.close()


async def test_meta_model_endpoint_and_native_tools_only(settings):
    def handler(request):
        payload = json.loads(request.content)
        assert str(request.url) == META_URL
        assert payload['model'] == MODEL
        assert request.headers['Authorization'] == 'Bearer fake-meta-secret'
        assert payload['parallel_tool_calls'] is False
        return httpx.Response(200, json={'choices': [{'message': {'content': 'OK'}}]})
    client = MetaClient(settings.model_api_key.get_secret_value(), httpx.MockTransport(handler))
    assert await client.complete([{'role': 'user', 'content': 'test'}], tools=[{}]) == {'content': 'OK'}
    await client.close()


@pytest.mark.parametrize('status', [401, 403, 400])
async def test_meta_nonretryable_errors(settings, status):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(status)
    client = MetaClient('test', httpx.MockTransport(handler))
    with pytest.raises(MetaError):
        await client.complete([])
    assert len(requests) == 1
    await client.close()


@pytest.mark.parametrize('failure', [429, 503, 'network'])
async def test_meta_retries_exactly_three_times(settings, monkeypatch, failure):
    requests = []
    def handler(request):
        requests.append(request)
        if failure == 'network':
            raise httpx.ConnectError('offline', request=request)
        return httpx.Response(failure, headers={'Retry-After': '1'})
    monkeypatch.setattr('sww3bot.meta_client.asyncio.sleep', AsyncMock())
    client = MetaClient('test', httpx.MockTransport(handler))
    with pytest.raises(MetaError):
        await client.complete([])
    assert len(requests) == 3
    await client.close()


async def test_meta_failure_reports_partial(settings, store):
    rt = runtime(settings, store)
    step = store.start_step(rt.task_id, 'move', {})
    store.finish_step(step, {'ok': True})
    meta = FakeMeta(MetaError('Tidak terhubung'))
    result = await Engine(settings, meta, FakeExecutor(), store).run(42, 'status', rt)
    assert result.status == 'failed'
    assert '1 berhasil' in result.text


async def test_executor_failure_keeps_all_call_result_pairs(settings, store):
    meta = FakeMeta({'tool_calls': [call(identifier='a'), call(identifier='b')]})
    executor = FakeExecutor()
    executor.execute = AsyncMock(side_effect=RuntimeError('unexpected'))
    result = await Engine(settings, meta, executor, store).run(42, 'status', runtime(settings, store))
    assert result.status == 'interrupted'
    assert executor.execute.call_count == 1
    assert [m['tool_call_id'] for m in store.history(42) if m['role'] == 'tool'] == ['a', 'b']


async def test_secret_with_json_characters_is_redacted(settings, store):
    from pydantic import SecretStr
    secret = 'password"with\\slashes'
    settings.bot_pass = SecretStr(secret)
    executor = FakeExecutor(ToolResult(ok=True, data={'detail': secret}))
    meta = FakeMeta({'tool_calls': [call()]}, {'content': 'OK'})
    await Engine(settings, meta, executor, store).run(42, 'status', runtime(settings, store))
    result = json.loads(next(m['content'] for m in store.history(42) if m['role'] == 'tool'))
    assert result['data']['detail'] == '[redacted]'


async def test_budget_persists_when_waiting_task_resumes(settings, store):
    settings.max_rounds = 1
    rt = runtime(settings, store)
    executor = FakeExecutor(ToolResult(ok=False, error={'code': 'ambiguous', 'message': 'Pilih',
        'candidates': [{'id': 1, 'label': 'One'}], 'field': 'player_id'}))
    meta = FakeMeta({'tool_calls': [call()]})
    engine = Engine(settings, meta, executor, store)
    first = await engine.run(42, 'pilih', rt)
    assert first.status == 'waiting'
    resumed = Runtime(rt.task_id, settings, store, AsyncMock())
    assert resumed.tools == 1
    assert resumed.rounds == 1
    result = await engine.run(42, 'target 1', resumed)
    assert result.status == 'limited'
    assert len(meta.requests) == 1


async def test_native_assistant_fields_preserved_for_next_turn(settings, store):
    message = {'role': 'assistant', 'content': None, 'tool_calls': [call()],
               'reasoning_content': 'test context'}
    meta = FakeMeta(message, {'content': 'OK'})
    await Engine(settings, meta, FakeExecutor(), store).run(42, 'status', runtime(settings, store))
    assert meta.requests[1][-2]['reasoning_content'] == 'test context'
