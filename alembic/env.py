"""Alembic 环境：同步引擎（pymysql）连接，target_metadata 来自 ORM Base。

URL 从 app.core.config 注入（不写死在 alembic.ini，避免密钥落盘）。
所有模型在 upgrade 时通过 Base.metadata.create_all 落地，确保 DDL 与 ORM 单一事实源一致。
"""
from __future__ import annotations

import os
import sys

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# 确保项目根（alembic/ 的父目录）在 sys.path，使 `import app` 可用
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
import app.models.business  # noqa: E402,F401  注册业务表
import app.models.auth  # noqa: E402,F401  注册认证表

config = context.config
config.set_main_option("sqlalchemy.url", settings.SYNC_DB_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.SYNC_DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(settings.SYNC_DB_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
