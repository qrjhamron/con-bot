"""All agent tests are offline; accidentally sending a game request fails the test."""
import pytest
import requests
from sww3bot.settings import Settings
from sww3bot.agent_store import Store


@pytest.fixture(autouse=True)
def deny_game_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Real game HTTP requests are forbidden in tests')
    monkeypatch.setattr(requests.Session, 'request', blocked)


@pytest.fixture
def settings():
    return Settings(model_api_key='fake-meta-secret', bot_user='test-account',
                    bot_pass='fake-password-secret', telegram_bot_token='123:fake-telegram-secret',
                    telegram_owner_id=123, game_id=42, db_path=':memory:')


@pytest.fixture
def store():
    value = Store(':memory:')
    yield value
    value.close()
