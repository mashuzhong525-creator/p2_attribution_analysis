"""演示数据接口验证：登录 → 查会话列表 → 历史消息 → 六段式结果。

幂等只读验证；首次运行时若 analyst 处于"首次登录需改密"状态，会自动改为
Demo@2026（与演示流程一致），并打印最终账号信息。

用法：python -m scripts.verify_demo_data
"""
from __future__ import annotations

import os
import sys

import httpx

BASE = os.environ.get("BIA_BASE", "http://localhost:8000").rstrip("/")
USER = os.environ.get("BIA_USER", "analyst")
PASS = os.environ.get("BIA_PASS", "analyst123")
NEW_PASS = os.environ.get("BIA_NEW_PASS", "Demo@2026")
REDIRECT = "http://localhost:8080/auth/callback"

client = httpx.Client(base_url=BASE, timeout=15.0)


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    sys.exit(1)


def main() -> None:
    print(f"== 演示数据接口验证：{BASE}  user={USER}")

    # 1. 登录拿授权码
    r = client.post("/api/auth/login", json={"username": USER, "password": PASS})
    code = r.json().get("code")
    if r.status_code != 200 or not code:
        fail(f"登录失败 status={r.status_code} body={r.text[:200]}")

    def exchange(c: str) -> str:
        r = client.post("/api/auth/token", json={
            "grant_type": "authorization_code", "code": c,
            "client_id": "bia-web", "redirect_uri": REDIRECT,
        })
        t = r.json().get("access_token")
        if not t:
            fail(f"换 token 失败 status={r.status_code} body={r.text[:200]}")
        return t

    token = exchange(code)
    headers = {"Authorization": f"Bearer {token}"}

    # 2. 首次登录改密（若标记未清）
    me = client.get("/api/auth/me", headers=headers).json()
    if me.get("must_change_password"):
        r = client.post("/api/auth/change-password", headers=headers,
                        json={"old_password": PASS, "new_password": NEW_PASS})
        if r.status_code != 200:
            fail(f"首次改密失败 status={r.status_code} body={r.text[:200]}")
        print(f"[INFO] analyst 已完成首次改密：{PASS} -> {NEW_PASS}")
        code = client.post("/api/auth/login", json={"username": USER, "password": NEW_PASS}).json().get("code")
        headers = {"Authorization": f"Bearer {exchange(code)}"}

    # 3. 会话列表
    r = client.get("/api/chat/ls", headers=headers)
    convs = r.json().get("items", [])
    print(f"[OK] 会话列表：{len(convs)} 个")
    for c in convs:
        print(f"     - {c['title']}  status={c['status']}  last={c.get('last_message_at')}")

    # 4. 逐个会话：历史消息 + 六段式结果（跳过无 task 关联的非演示会话）
    demo_count = 0
    for c in convs:
        cid = c["conversation_id"]
        r = client.get(f"/api/chat/ls/{cid}", headers=headers)
        items = r.json().get("items", [])
        roles = [m["role"] for m in items]
        task_id = next((m.get("task_id") for m in items if m.get("task_id")), None)
        if not task_id:
            print(f"[SKIP] 非演示会话 {c['title']}：{len(items)} 条无 task，跳过")
            continue
        demo_count += 1
        print(f"[OK] 演示会话 {c['title']}：{len(items)} 条 roles={sorted(set(roles))} task={bool(task_id)}")

        r = client.get(f"/api/results/{task_id}", headers=headers)
        res = r.json()
        six = ["problem_definition", "key_metrics", "evidence_list", "conclusion_text",
               "missing_data_text", "next_action_text"]
        missing = [k for k in six if not res.get(k)]
        if missing:
            fail(f"会话 {c['title']} 六段式缺字段：{missing}")
        print(f"     [OK] 六段式齐全 指标={len(res['key_metrics'])} 证据={len(res['evidence_list'])} 结论前40字={res['conclusion_text'][:40]}")

    if demo_count < 2:
        fail(f"演示会话不足 2 个（实际 {demo_count} 个有 task 关联）")
    print(f"\n== 演示数据验证通过：{demo_count} 个完整分析示例可正常回放 ==")


if __name__ == "__main__":
    main()
