"""Must be imported before backend.db by every test module.

Tests always use a new temporary database, never the user's demo ledger.
"""
import atexit
import os
import tempfile
from pathlib import Path

TEMP_DIR = tempfile.TemporaryDirectory(prefix='sothuchi-tests-')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(TEMP_DIR.name) / 'tests.sqlite3')

def _cleanup():
    try:
        from backend.db import engine
        engine.dispose()
    except Exception:
        pass

atexit.register(_cleanup)
