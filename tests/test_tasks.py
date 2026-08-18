"""分析任务状态机与同会话单任务互斥。"""

import pytest

from app.database import get_connection
from app.tasks import create_task, list_tasks, transition


def test_valid_transitions(db):
    with get_connection() as conn:
        task_id = create_task(conn, conversation_id=1, user_id=1, input_text="为什么库存下降")
        transition(conn, task_id, "running")
        transition(conn, task_id, "success")
        task = list_tasks(conn, task_id=task_id)[0]
        assert task["task_status"] == "success"


def test_invalid_transition_raises(db):
    with get_connection() as conn:
        task_id = create_task(conn, conversation_id=1, user_id=1, input_text="问题")
        transition(conn, task_id, "running")
        transition(conn, task_id, "success")
        with pytest.raises(ValueError):
            transition(conn, task_id, "running")


def test_single_running_task_per_conversation(db):
    with get_connection() as conn:
        first = create_task(conn, conversation_id=1, user_id=1, input_text="问题A")
        transition(conn, first, "running")
        with pytest.raises(ValueError):
            create_task(conn, conversation_id=1, user_id=1, input_text="问题B")
