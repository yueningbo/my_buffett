from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.store.json_store import reset_store_for_tests


@pytest.fixture()
def store(tmp_path):
    return reset_store_for_tests(tmp_path)
