"""经营归因分析系统 · 端到端冒烟测试。

覆盖链路：健康检查 → 登录 → 换取 token → 选数据源 → 建会话 →
发送归因问题 → 轮询任务 → 校验六段式结果 → 会话历史 → WS token → 清理。

用法（默认连本机 8000 端口的 backend）：
    python -m scripts.smoke_test

可用环境变量：
    BIA_BASE     后端地址，默认 http://localhost:8000
    BIA_USER     账号，默认 admin
    BIA_PASS     密码，默认 admin123
    BIA_QUESTION 归因问题，默认演示问题
"""

from __future__ import annotations

import json
import os
import sys
import time

import httpx

BASE = os.environ.get("BIA_BASE", "http://localhost:8000").rstrip("/")
USER = os.environ.get("BIA_USER", "admin")
PASS = os.environ.get("BIA_PASS", "admin123")
PASS2 = os.environ.get("BIA_PASS2", "Admin@123456")
QUESTION = os.environ.get(
    "BIA_QUESTION", "为什么6月信息流渠道点击量下滑？请做归因分析"
)
QUESTION2 = os.environ.get(
    "BIA_QUESTION2", "华东仓 SKU0001 缺货原因是什么？请做归因分析"
)
TIMEOUT = 60.0

client = httpx.Client(base_url=BASE, timeout=15.0)


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def run_scenario(headers: dict, ds: dict, question: str) -> None:
    # 新建会话（指定数据源）
    r = client.get("/health")
    r = client.post(
        "/api/chat/create",
        headers=headers,
        json={"title": f"冒烟测试-{ds['database']}", "data_source_id": ds["id"]},
    )
    conv = r.json()
    conv_id = conv.get("conversation_id")
    check(f"新建会话({ds['database']})", r.status_code == 200 and bool(conv_id))

    try:
        # 发送归因问题
        r = client.post(
            "/api/chat/send",
            headers=headers,
            json={"conversation_id": conv_id, "content": question},
        )
        send = r.json()
        task_id = send.get("task_id")
        check(f"发送问题({ds['database']})", r.status_code == 200 and bool(task_id))

        # 轮询任务到终态
        deadline = time.time() + TIMEOUT
        task = {}
        while time.time() < deadline:
            r = client.get(f"/api/tasks/{task_id}", headers=headers)
            task = r.json()
            if task.get("task_status") in ("success", "failed", "cancelled"):
                break
            time.sleep(1.0)
        status = task.get("task_status")
        check(
            f"任务终态({ds['database']})",
            status == "success",
            f"status={status} error={task.get('error_message') or ''}",
        )

        # 六段式结果
        r = client.get(f"/api/results/{task_id}", headers=headers)
        res = r.json()
        six = [
            "problem_definition",
            "key_metrics",
            "evidence_list",
            "conclusion_text",
            "missing_data_text",
            "next_action_text",
        ]
        missing = [k for k in six if not res.get(k)]
        check(
            f"六段式结果({ds['database']})",
            r.status_code == 200 and not missing,
            f"缺失字段={missing or '无'} 指标数={len(res.get('key_metrics') or [])} 证据数={len(res.get('evidence_list') or [])}",
        )

        # 会话历史包含用户消息与结果消息
        r = client.get(f"/api/chat/ls/{conv_id}", headers=headers)
        items = r.json().get("items", [])
        roles = {m.get("role") for m in items}
        check(
            f"会话历史({ds['database']})",
            r.status_code == 200 and "user" in roles and "assistant" in roles,
            f"消息数={len(items)} roles={sorted(roles)}",
        )

        # WS 一次性 token
        r = client.post("/api/chat/ws-token", headers=headers, json={"conversation_id": conv_id})
        ws = r.json()
        check(f"WS token({ds['database']})", r.status_code == 200 and bool(ws.get("websocket_token")))
    finally:
        # 清理：删除测试会话（级联删除消息/任务/结果）
        r = client.post(
            "/api/chat/delete", headers=headers, json={"conversation_ids": [conv_id]}
        )
        print(f"[INFO] 清理会话 status={r.status_code}")


def main() -> None:
    print(f"== 冒烟测试：{BASE}  user={USER}")

    # 1. 健康检查
    r = client.get("/health")
    body = r.json()
    check("健康检查", r.status_code == 200 and body.get("status") == "ok", str(body))

    # 2. 登录：优先初始口令；若上次运行中断导致口令已变，自动改用 PASS2 自愈
    pass_used = PASS
    r = client.post("/api/auth/login", json={"username": USER, "password": pass_used})
    if r.status_code != 200 or not r.json().get("code"):
        pass_used = PASS2
        r = client.post("/api/auth/login", json={"username": USER, "password": pass_used})
    code = r.json().get("code")
    check("登录", r.status_code == 200 and bool(code), f"status={r.status_code} pass_used={pass_used}")

    def exchange() -> tuple[dict, str]:
        r = client.post(
            "/api/auth/token",
            json={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": "bia-web",
                "redirect_uri": "http://localhost:8080/auth/callback",
            },
        )
        token = r.json().get("access_token", "")
        check("换取 token", r.status_code == 200 and bool(token))
        return {"Authorization": f"Bearer {token}"}, token

    # 3. 授权码换 token
    headers, _ = exchange()

    # 4. 当前用户 + 首次登录强制改密流程
    r = client.get("/api/auth/me", headers=headers)
    me = r.json()
    check("当前用户", r.status_code == 200 and me.get("username") == USER, str(me))
    if me.get("must_change_password"):
        # 4.1 未改密前业务接口应被拦截
        r = client.get("/api/chat/ls", headers=headers, params={"page": 1, "page_size": 1})
        blocked = r.status_code == 403 and r.json().get("code") == "PASSWORD_CHANGE_REQUIRED"
        check("改密前业务接口拦截", blocked, f"status={r.status_code} body={r.text[:120]}")
        # 4.2 原密码错误应被拒绝
        r = client.post(
            "/api/auth/change-password",
            headers=headers,
            json={"old_password": "wrong-old-password", "new_password": PASS2},
        )
        check("错误原密码被拒绝", r.status_code == 403, f"status={r.status_code}")
        # 4.3 正式改密（初始口令 → PASS2）
        r = client.post(
            "/api/auth/change-password",
            headers=headers,
            json={"old_password": pass_used, "new_password": PASS2},
        )
        check("修改密码", r.status_code == 200, f"status={r.status_code} body={r.text[:120]}")
        # 4.4 用新口令重新登录，改密标记应清除
        r = client.post("/api/auth/login", json={"username": USER, "password": PASS2})
        code = r.json().get("code")
        headers, _ = exchange()
        pass_used = PASS2
        r = client.get("/api/auth/me", headers=headers)
        me = r.json()
        check("改密后标记清除", r.status_code == 200 and not me.get("must_change_password"), str(me))

    # 5. 数据源列表（管理员接口），取启用的示例库
    r = client.get("/api/admin/datasources", headers=headers)
    dss = [d for d in r.json() if d.get("is_enabled")]
    check("数据源列表", r.status_code == 200 and len(dss) > 0, f"共 {len(dss)} 个")
    scenario = [d for d in dss if d.get("database", "").startswith("scenario_")]
    if len(scenario) >= 2:
        run_scenario(headers, scenario[0], QUESTION)
        run_scenario(headers, scenario[1], QUESTION2)
    else:
        run_scenario(headers, dss[0], QUESTION)

    print("\n== 冒烟测试全部通过 ==")


def restore_password() -> None:
    """恢复初始口令（仅当测试期间口令变为 PASS2 时执行，保证演示账号可用）。"""
    try:
        r = client.post("/api/auth/login", json={"username": USER, "password": PASS2})
        code = r.json().get("code")
        if not code:
            return
        r = client.post(
            "/api/auth/token",
            json={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": "bia-web",
                "redirect_uri": "http://localhost:8080/auth/callback",
            },
        )
        token = r.json().get("access_token", "")
        if not token:
            return
        r = client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"old_password": PASS2, "new_password": PASS},
        )
        if r.status_code == 200:
            print("[INFO] 已恢复初始口令 admin123")
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] 恢复口令失败（可 docker compose down -v 重建初始化）: {e}")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as e:
        print(f"[FAIL] 请求异常: {e}")
        sys.exit(1)
    finally:
        restore_password()
