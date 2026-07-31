from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.graph import reset_graph_for_tests
from app.store.json_store import reset_store_for_tests


@pytest.fixture(autouse=True)
def _default_test_env(monkeypatch):
    """Deterministic unit tests: mock tools, no live network by default."""
    monkeypatch.setenv("MY_BUFFETT_TOOL_MODE", "mock")


@pytest.fixture()
def store(tmp_path):
    reset_graph_for_tests()
    return reset_store_for_tests(tmp_path)
