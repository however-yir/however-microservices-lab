import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent

sys.path.insert(0, str(PROJECT_DIR))


def pytest_configure():
    os.environ.setdefault("ENABLE_TRACING", "0")
