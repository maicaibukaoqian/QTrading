"""运行时设置读写 service

把 AI 配置持久化到项目根目录 .env（pydantic-settings 本来就从这里读），
写完清 get_settings() 的 lru_cache，下一次调用即生效。
"""

import time
from pathlib import Path
from typing import Dict, Optional

import requests

from src.config.settings import get_settings
from src.api.schemas.settings import (
    AISettingsOut,
    AISettingsUpdate,
    AISettingsTestRequest,
    AISettingsTestResult,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = PROJECT_ROOT / ".env"

_ENV_KEYS = {
    "ai_api_key": "QUANT_AI_API_KEY",
    "ai_api_base": "QUANT_AI_API_BASE",
    "ai_model_name": "QUANT_AI_MODEL_NAME",
}


def _mask_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}****{key[-4:]}"


def read_ai_settings() -> AISettingsOut:
    s = get_settings()
    return AISettingsOut(
        ai_api_base=s.ai_api_base,
        ai_model_name=s.ai_model_name,
        ai_enabled=s.ai_enabled,
        has_key=bool(s.ai_api_key),
        key_masked=_mask_key(s.ai_api_key),
        max_ai_comments=s.max_ai_comments,
    )


def _upsert_env(updates: Dict[str, str]) -> None:
    """就地更新 .env：已有键替换、新键追加，注释与其它行原样保留"""
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    remaining = dict(updates)
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                out.append(f"{key}={remaining.pop(key)}")
                continue
        out.append(line)
    for key, val in remaining.items():
        out.append(f"{key}={val}")
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


def update_ai_settings(payload: AISettingsUpdate) -> AISettingsOut:
    updates: Dict[str, str] = {}
    if payload.ai_api_base is not None:
        updates[_ENV_KEYS["ai_api_base"]] = payload.ai_api_base
    if payload.ai_model_name is not None:
        updates[_ENV_KEYS["ai_model_name"]] = payload.ai_model_name
    if payload.clear_key:
        updates[_ENV_KEYS["ai_api_key"]] = ""
    elif payload.ai_api_key:
        updates[_ENV_KEYS["ai_api_key"]] = payload.ai_api_key

    if updates:
        _upsert_env(updates)
        get_settings.cache_clear()

    return read_ai_settings()


def test_ai_settings(payload: AISettingsTestRequest) -> AISettingsTestResult:
    """用表单值（缺省回落到已存配置）发一个最小 chat 请求验证连通性"""
    s = get_settings()
    base = (payload.ai_api_base or s.ai_api_base).rstrip("/")
    if base.endswith("/chat/completions"):
        endpoint = base
    else:
        endpoint = f"{base}/chat/completions"
    model = payload.ai_model_name or s.ai_model_name
    key = payload.ai_api_key or s.ai_api_key

    if not key:
        return AISettingsTestResult(ok=False, message="未配置 API 密钥")

    t0 = time.monotonic()
    try:
        resp = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
            },
            timeout=15,
        )
    except requests.RequestException as e:
        return AISettingsTestResult(ok=False, message=f"网络不通：{e}")

    latency = int((time.monotonic() - t0) * 1000)
    ct = resp.headers.get("content-type", "")
    is_json = "json" in ct
    body = resp.text if is_json else ""
    if resp.status_code == 200:
        return AISettingsTestResult(ok=True, message=f"连通 · {model} 应答正常", latency_ms=latency)
    if resp.status_code in (401, 403):
        return AISettingsTestResult(ok=False, message=f"密钥被拒（HTTP {resp.status_code}）· 核对 key 或权限", latency_ms=latency)
    if resp.status_code == 404:
        return AISettingsTestResult(ok=False, message="端点或模型不存在（HTTP 404）· 核对 api_base 与 model", latency_ms=latency)
    if resp.status_code == 429:
        return AISettingsTestResult(ok=False, message="请求频率超限（HTTP 429）· 稍候再试", latency_ms=latency)
    if resp.status_code >= 500:
        return AISettingsTestResult(ok=False, message=f"服务端错误（HTTP {resp.status_code}）", latency_ms=latency)
    if not is_json:
        # 端点很可能填错了：CDN/网关返回了 HTML 错误页而非 LLM API
        snippet = body[:80].replace("\n", " ")
        return AISettingsTestResult(
            ok=False,
            message=f"端点返回了非 JSON（HTTP {resp.status_code}）· 怀疑 base URL 写错 · {snippet}",
            latency_ms=latency,
        )
    return AISettingsTestResult(ok=False, message=f"HTTP {resp.status_code}：{body[:120]}", latency_ms=latency)
