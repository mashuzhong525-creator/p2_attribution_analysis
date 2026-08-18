"""initial schema (17 tables: 13 business + 4 auth)

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-18

基线迁移：以 ORM `app.db.base.Base.metadata` 为单一事实源建表，确保 DDL 与
`docs/design/数据模型设计.md` 字段级定义完全一致（models 已严格对齐）。
含全部索引/唯一约束/逻辑外键列。软删除列、JSON 列、UUIDv7 主键均已落地。
"""
from __future__ import annotations

from alembic import op

import app.models.auth  # noqa: F401  注册认证表
import app.models.business  # noqa: F401  注册业务表
from app.db.base import Base

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
