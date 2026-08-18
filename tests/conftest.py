"""pytest 公共配置：保证从任意目录运行都能导入 app 包。"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.database import init_db  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(settings, "db_path", db_path)
    init_db()
    return db_path
