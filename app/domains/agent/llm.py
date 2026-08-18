"""LLM 客户端（§4.7 llm.py / §8.4）。

OpenAI 兼容：base_url/api_key/model 每次从 ConfigCache 读取（热更新生效）。
mock 模式：未配置 API Key 时返回标记，引擎走离线确定性分析（保证可演示）。
每次调用（含异常）写 llm_calls 一行记账。
"""
from __future__ import annotations

import json
import time

import httpx

from app.core.config import ConfigCache
from app.core.logging import get_logger
from app.core.uuid import uuid7_str
from app.models.business import LLMCall

logger = get_logger("agent.llm")


class LlmClient:
    def __init__(self) -> None:
        self._cfg = ConfigCache()

    def _creds(self) -> tuple[str, str, str]:
        base = self._cfg.get("llm_base_url", "https://api.deepseek.com/v1")
        key = self._cfg.get("llm_api_key", "")
        model = self._cfg.get("llm_model", "deepseek-chat")
        return base.rstrip("/"), (key or ""), model

    @property
    def available(self) -> bool:
        return bool(self._cfg.get("llm_api_key"))

    async def _record(
        self, db, task_id, conv_id, user_id, model, prompt_tokens, completion_tokens,
        latency_ms, status, error=None,
    ) -> None:
        try:
            price_in = self._cfg.get_float("llm_price_prompt_per_1k", 0.001)
            price_out = self._cfg.get_float("llm_price_completion_per_1k", 0.002)
            cost = (prompt_tokens / 1000) * price_in + (completion_tokens / 1000) * price_out
            db.add(LLMCall(
                id=uuid7_str(), task_id=task_id, conversation_id=conv_id, user_id=user_id,
                model=model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens, cost=round(cost, 4),
                latency_ms=latency_ms, status=status, error_message=error,
            ))
            await db.commit()
        except Exception:
            logger.exception("llm_calls 记账失败")

    async def chat_plan(self, db, task_id, conv_id, user_id, system, messages, tools=None) -> dict:
        """非流式规划调用，返回 OpenAI 响应对象（含 tool_calls 或 content）。"""
        base, key, model = self._creds()
        if not key:
            return {"mock": True}
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": 0.2,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=self._cfg.get_int("llm_timeout_seconds", 120)) as c:
                r = await c.post(f"{base}/chat/completions", json=payload,
                                 headers={"Authorization": f"Bearer {key}"})
                r.raise_for_status()
                data = r.json()
            usage = data.get("usage", {})
            msg = data["choices"][0]["message"]
            await self._record(db, task_id, conv_id, user_id, model,
                               usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
                               int((time.time() - t0) * 1000), "success")
            return msg
        except Exception as e:  # noqa: BLE001
            await self._record(db, task_id, conv_id, user_id, model, 0, 0,
                               int((time.time() - t0) * 1000), "failed", error=str(e)[:500])
            raise

    async def stream_conclusion(self, db, task_id, conv_id, user_id, system, messages):
        """流式输出结论；mock 模式 yield 预置文本。返回 (chunks, full_text)。"""
        base, key, model = self._creds()
        chunks: list[str] = []
        if not key:
            full = "（离线模式：未配置 LLM API Key，使用基于真实数据的确定性归因结论。）"
            for i in range(0, len(full), 30):
                chunks.append(full[i:i + 30])
                yield chunks[-1]
            return
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=self._cfg.get_int("llm_timeout_seconds", 120)) as c:
                async with c.stream("POST", f"{base}/chat/completions", json={
                    "model": model,
                    "messages": [{"role": "system", "content": system}, *messages],
                    "temperature": 0.3, "stream": True,
                }, headers={"Authorization": f"Bearer {key}"}) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        d = line[5:].strip()
                        if d == "[DONE]":
                            break
                        try:
                            obj = json.loads(d)
                            delta = obj["choices"][0]["delta"].get("content", "")
                        except Exception:
                            continue
                        if delta:
                            chunks.append(delta)
                            yield delta
            await self._record(db, task_id, conv_id, user_id, model, 0, 0,
                               int((time.time() - t0) * 1000), "success")
        except Exception as e:  # noqa: BLE001
            await self._record(db, task_id, conv_id, user_id, model, 0, 0,
                               int((time.time() - t0) * 1000), "failed", error=str(e)[:500])
            raise

    async def summarize(self, db, task_id, conv_id, user_id, system, messages) -> str:
        base, key, model = self._creds()
        if not key:
            return "（本回合分析已完成，摘要略。）"
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=self._cfg.get_int("llm_timeout_seconds", 120)) as c:
                r = await c.post(f"{base}/chat/completions", json={
                    "model": model,
                    "messages": [{"role": "system", "content": system}, *messages],
                    "temperature": 0.2, "stream": False,
                }, headers={"Authorization": f"Bearer {key}"})
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"]
            await self._record(db, task_id, conv_id, user_id, model, 0, 0,
                               int((time.time() - t0) * 1000), "success")
            return text
        except Exception as e:  # noqa: BLE001
            await self._record(db, task_id, conv_id, user_id, model, 0, 0,
                               int((time.time() - t0) * 1000), "failed", error=str(e)[:500])
            return ""
