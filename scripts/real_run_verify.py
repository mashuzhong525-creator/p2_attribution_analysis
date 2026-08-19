"""实跑一次真实分析（admin 登录 → 新会话绑定 scenario_goods → 提问），
确认 data_sources.host=mysql 修复后真实归因可产出（不是 LLM 瞎编）。

成功标准：六段式 conclusion_text 含真实数字（如"信息流 6 月点击 X vs 5 月 Y，下滑 ~59%"）。
"""
from __future__ import annotations

import os
import sys
import time

import httpx

BASE = os.environ.get("BIA_BASE", "http://localhost:8000").rstrip("/")
USER = "admin"
PASS = "admin123"
Q = "为什么 6 月信息流渠道点击量下滑？请做归因分析。"

# trust_env=False：忽略系统/环境代理，确保本机直连测试目标（Windows 系统代理会劫持 localhost 请求返回 502）
client = httpx.Client(base_url=BASE, timeout=15.0, trust_env=False)


def main() -> None:
    print(f"== 实跑真实分析：{BASE}  user={USER}")
    r = client.post("/api/auth/login", json={"username": USER, "password": PASS})
    code = r.json().get("code")
    if r.status_code != 200 or not code:
        sys.exit(f"登录失败：{r.status_code} {r.text[:200]}")
    r = client.post("/api/auth/token", json={
        "grant_type": "authorization_code", "code": code,
        "client_id": "bia-web", "redirect_uri": "http://localhost:8080/auth/callback",
    })
    token = r.json().get("access_token")
    H = {"Authorization": f"Bearer {token}"}

    # 1. 取 scenario_goods 数据源
    r = client.get("/api/admin/datasources", headers=H)
    ds = next((d for d in r.json() if d.get("database") == "scenario_goods" and d.get("is_enabled")), None)
    if not ds:
        sys.exit("未找到启用的 scenario_goods 数据源")
    print(f"[OK] 数据源：{ds['name']} id={ds['id']}")

    # 2. 建会话（标题加时间戳避免与演示/历史混淆）
    title = f"实跑验证-{int(time.time())}"
    r = client.post("/api/chat/create", headers=H,
                    json={"title": title, "data_source_id": ds["id"]})
    conv = r.json()
    cid = conv.get("conversation_id")
    print(f"[OK] 会话创建：{cid} title={title}")

    # 3. 发送问题
    r = client.post("/api/chat/send", headers=H,
                    json={"conversation_id": cid, "content": Q})
    task_id = r.json().get("task_id")
    print(f"[OK] 已发送，task={task_id}，轮询任务…")

    # 4. 轮询
    deadline = time.time() + 120
    final = {}
    while time.time() < deadline:
        r = client.get(f"/api/tasks/{task_id}", headers=H)
        t = r.json()
        if t.get("task_status") in ("success", "failed", "cancelled"):
            final = t
            break
        time.sleep(2)
    status = final.get("task_status")
    print(f"[{'OK' if status == 'success' else 'FAIL'}] 任务终态：{status} step={final.get('current_step')} err={final.get('error_message') or ''}")

    if status != "success":
        sys.exit(f"任务未成功：{final}")

    # 5. 拿六段式结果
    r = client.get(f"/api/results/{task_id}", headers=H)
    res = r.json()
    print(f"[OK] 六段式获取：problem={res['problem_definition'][:50]}...")
    print(f"     指标数={len(res['key_metrics'])} 证据数={len(res['evidence_list'])}")
    print(f"     结论前120字：\n     {res['conclusion_text'][:200]}")
    # 判定：结论里是否含真实数字（vs "方法论推断"瞎编）
    if "方法论推断" in res["conclusion_text"] or "Errno" in res["conclusion_text"]:
        sys.exit("\n[FAIL] 结论仍含'方法论推断'/Errno，说明 LLM 仍在瞎编！")
    if not any(m.get("metric_value") for m in res["key_metrics"]):
        sys.exit("\n[FAIL] 关键指标为空，未产出真实数据")
    print("\n== 实跑成功：基于真实数据产出六段式归因 ==")


if __name__ == "__main__":
    main()