"""端到端冒烟：登录 / 会话 / WS 分析 / 结果 / 导出 / 配置（python scripts/smoke_check.py）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def main() -> None:
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        token = r.json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        print("login:", r.status_code)

        conv = c.post("/api/chat/create", headers=h, json={"title": "冒烟会话"}).json()
        cid = conv["id"]
        print("conversation:", conv.get("id"))

        wt = c.post("/api/chat/ws-token", headers=h, json={"conversation_id": cid}).json()
        print("ws-token:", "websocket_token" in wt)

        events = []
        with c.websocket_connect(f"/api/chat/ws/chat?token={wt['websocket_token']}&conversation_id={cid}") as ws:
            ws.send_json({"type": "question", "question": "为什么 7 月华东仓库存周转率下降？"})
            while True:
                evt = ws.receive_json()
                events.append(evt.get("event"))
                if evt.get("event") == "done":
                    break
        print("ws events:", events)

        task_id = None
        for evt in events:
            pass
        tasks = c.get("/api/tasks/1", headers=h)
        print("task:", tasks.status_code, tasks.json().get("task_status"))

        results = c.get("/api/results/1", headers=h)
        print("result:", results.status_code, results.json().get("problem_definition", "")[:30])
        exp = c.get("/api/results/1/export?format=md", headers=h)
        print("export md:", exp.status_code, len(exp.content))

        print("reload:", c.post("/api/admin/reload", headers=h).status_code)
        print("logs:", c.get("/api/admin/logs", headers=h).status_code)

        # 第二场景：客户行为（转化率）
        conv2 = c.post("/api/chat/create", headers=h, json={"title": "客户行为场景"}).json()
        cid2 = conv2["id"]
        wt2 = c.post("/api/chat/ws-token", headers=h, json={"conversation_id": cid2}).json()
        events2 = []
        with c.websocket_connect(f"/api/chat/ws/chat?token={wt2['websocket_token']}&conversation_id={cid2}") as ws:
            ws.send_json({"type": "question", "question": "为什么 7 月下单转化率下降？"})
            while True:
                evt = ws.receive_json()
                events2.append(evt.get("event"))
                if evt.get("event") == "done":
                    break
        print("scenario2 events:", events2)

        # 附件上传
        up = c.post(
            "/api/attachment/upload",
            headers=h,
            files={"file": ("demo.csv", b"sku_id,date,sales_qty\nSKU001,2026-07-01,10", "text/csv")},
            data={"conversation_id": cid},
        )
        print("attachment:", up.status_code, up.json().get("file_name"))

        # JSON 导出
        expj = c.get("/api/results/1/export?format=json", headers=h)
        print("export json:", expj.status_code, len(expj.content))


if __name__ == "__main__":
    main()
