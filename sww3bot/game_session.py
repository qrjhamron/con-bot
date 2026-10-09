"""Explicit game context; synchronous adapters use a context-local binding."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any


@dataclass
class GameSession:
    game_id: int
    player_id: int = 0
    ctrl: Any = None
    ge: Any = None
    raw: Any = None


_session = ContextVar("game_session", default=None)


@contextmanager
def bind_session(session):
    token = _session.set(session)
    try:
        yield session
    finally:
        _session.reset(token)


def current_session():
    session = _session.get()
    if session is None:
        # Standalone legacy scripts retain a context local to their execution.
        from api._conn import GAME_ID, PLAYER_ID
        session = GameSession(GAME_ID, PLAYER_ID)
        _session.set(session)
    return session
