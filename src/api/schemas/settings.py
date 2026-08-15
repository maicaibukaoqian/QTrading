"""settings 模块的 Pydantic 模型"""

from typing import Optional
from pydantic import BaseModel, Field


class AISettingsOut(BaseModel):
    """GET /api/settings/ai 响应（密钥只返回掩码）"""
    ai_api_base: str
    ai_model_name: str
    ai_enabled: bool
    has_key: bool
    key_masked: Optional[str] = None
    max_ai_comments: int


class AISettingsUpdate(BaseModel):
    """PUT /api/settings/ai 请求体

    字段为 None = 不改动；ai_api_key 传空字符串等同 None（前端空框=不换密钥）。
    clear_key=True 时显式清除已存密钥。
    """
    ai_api_base: Optional[str] = Field(default=None, min_length=1)
    ai_model_name: Optional[str] = Field(default=None, min_length=1)
    ai_api_key: Optional[str] = None
    clear_key: bool = False


class AISettingsTestRequest(BaseModel):
    """POST /api/settings/ai/test 请求体（可在保存前用表单值试连通）"""
    ai_api_base: Optional[str] = None
    ai_model_name: Optional[str] = None
    ai_api_key: Optional[str] = None


class AISettingsTestResult(BaseModel):
    ok: bool
    message: str
    latency_ms: Optional[int] = None
