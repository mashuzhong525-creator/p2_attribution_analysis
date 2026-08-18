"""messages.task_id：结果消息关联分析任务，刷新后右侧六段式结果可回填

Revision ID: 0002_message_task_id
Revises: 0001_initial
Create Date: 2026-08-18

说明：0001 以当前 ORM metadata create_all 建表，全新库可能已含 task_id 列，
因此本迁移先查 information_schema 再 ALTER，并对存量 result 消息按
analysis_results.conversation_id 回填 task_id。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0002_message_task_id"
down_revision: str | None = "0001_initial"
branch_labels: str | None = None
depends_on: str | None = None


def _column_exists(bind, column: str) -> bool:
    row = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'messages' AND column_name = :c"
        ),
        {"c": column},
    ).scalar()
    return bool(row)


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "task_id"):
        op.add_column("messages", sa.Column("task_id", sa.String(length=32), nullable=True))
        op.create_index("ix_msg_task", "messages", ["task_id"])
        # 存量回填：结果消息 -> 对应 analysis_result 的 task_id
        op.execute(
            "UPDATE messages m "
            "JOIN analysis_results r ON r.conversation_id = m.conversation_id "
            "SET m.task_id = r.task_id "
            "WHERE m.message_type = 'result' AND m.task_id IS NULL"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "task_id"):
        op.drop_index("ix_msg_task", table_name="messages")
        op.drop_column("messages", "task_id")
