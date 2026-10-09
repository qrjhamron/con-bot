#!/usr/bin/env python3
"""Offline game adapter and Telegram regression tests."""
import subprocess
import sys
from pathlib import Path

if __name__ == '__main__':
    raise SystemExit(subprocess.call([sys.executable, '-m', 'pytest', 'tests/test_agent_tools.py',
                                    'tests/test_telegram_bot.py', '-v'], cwd=Path(__file__).resolve().parents[1]))
