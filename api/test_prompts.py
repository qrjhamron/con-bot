#!/usr/bin/env python3
"""Offline prompt/tool-loop regression tests; no real game actions."""
import subprocess
import sys
from pathlib import Path

if __name__ == '__main__':
    raise SystemExit(subprocess.call([sys.executable, '-m', 'pytest', 'tests/test_agent_engine.py', '-v'],
                                    cwd=Path(__file__).resolve().parents[1]))
