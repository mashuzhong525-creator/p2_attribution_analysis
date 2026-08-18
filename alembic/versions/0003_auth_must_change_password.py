"""auth_users.must_change_password：首次登录强制修改密码

Revision ID: 0003_auth_must_change_password
Revises: 0002_message_task_id
Create Date: 2026-08-18

说明：0001 以当前 ORM metadata create_all 建表，全新库可能已含该列，
因此先查 information_schema 再 ALTER；存量账号统一置为 True（上线前初始化口令）。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0003_auth_must_change_password"
down_revision: str | None = "0002_message_task_id"
branch_labels: str | None = None
depends_on: str | None = None


def _column_exists(bind, table: str, column: str) -> bool:
    row = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).scalar()
    return bool(row)


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "auth_users", "must_change_password"):
        op.add_column(
            "auth_users",
            sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        )
    # 存量账号：上线前初始化口令一律要求首次登录改密
    op.execute("UPDATE auth_users SET must_change_password = TRUE WHERE must_change_password IS NULL")


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "auth_users", "must_change_password"):
        op.drop_column("auth_users", "must_change_password")
