"""共享 LLM 客户端

所有需要调用大模型的服务（chat / weekly / daily）都走这里。
单一职责：把 messages 发到端点，把响应吐回来。
不负责：拼 prompt、存历史、限流、上下文管理。
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Iterator, List, Optional

import requests

from src.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

Message = dict
Messages = List[Message]


class LLMUnavailableError(Exception):
    """AI 未启用（API Key 未配置）"""


class LLMCallError(Exception):
    """LLM 调用失败（HTTP / 网络 / 解析）"""

    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class LLMClient:
    """OpenAI 兼容协议的 LLM 客户端"""

    def __init__(self, settings: Settings):
        self._settings = settings

    def _check_available(self) -> None:
        if not self._settings.ai_api_key:
            raise LLMUnavailableError("未配置 API 密钥")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._settings.ai_api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, messages: Messages, **overrides) -> dict:
        payload = {
            "model": self._settings.ai_model_name,
            "messages": messages,
            "temperature": 0.5,
        }
        payload.update(overrides)
        return payload

    def chat(self, messages: Messages, **overrides) -> str:
        """一次性调用，返回完整回复文本"""
        self._check_available()
        try:
            resp = requests.post(
                self._settings.ai_endpoint,
                headers=self._headers(),
                json=self._payload(messages, **overrides),
                timeout=overrides.pop("timeout", 30),
                stream=False,
            )
        except requests.RequestException as e:
            raise LLMCallError(f"网络不通: {e}") from e

        if resp.status_code != 200:
            snippet = resp.text[:200].replace("\n", " ")
            raise LLMCallError(
                f"LLM 调用失败 HTTP {resp.status_code}: {snippet}",
                status_code=resp.status_code,
                body=resp.text,
            )
        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError) as e:
            raise LLMCallError(f"响应解析失败: {e}; body={resp.text[:200]}") from e

    def stream_chat(self, messages: Messages, **overrides) -> Iterator[str]:
        """流式调用，yield 每个文本 chunk

        协议：OpenAI SSE（data: {...}\\n\\n，data: [DONE]\\n\\n 结尾）。
        客户端断开时通过 generator.close() 触发，requests 底层连接会随之释放。
        """
        self._check_available()
        overrides["stream"] = True
        try:
            resp = requests.post(
                self._settings.ai_endpoint,
                headers=self._headers(),
                json=self._payload(messages, **overrides),
                timeout=overrides.pop("timeout", 60),
                stream=True,
            )
        except requests.RequestException as e:
            raise LLMCallError(f"网络不通: {e}") from e

        if resp.status_code != 200:
            snippet = resp.text[:200].replace("\n", " ")
            raise LLMCallError(
                f"LLM 调用失败 HTTP {resp.status_code}: {snippet}",
                status_code=resp.status_code,
                body=resp.text,
            )

        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                data = json.loads(payload)
                chunk = data["choices"][0].get("delta", {}).get("content")
            except (ValueError, KeyError, IndexError) as e:
                logger.warning(f"流式 chunk 解析失败: {e}; payload={payload[:100]}")
                continue
            if chunk:
                yield chunk


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    return LLMClient(get_settings())
