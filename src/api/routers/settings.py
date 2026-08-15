"""运行时设置 router"""

from fastapi import APIRouter

from src.api.schemas.settings import (
    AISettingsOut,
    AISettingsUpdate,
    AISettingsTestRequest,
    AISettingsTestResult,
)
from src.api.services import settings_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/ai", response_model=AISettingsOut)
def get_ai_settings():
    """读当前大模型配置（密钥只返回掩码）"""
    return settings_service.read_ai_settings()


@router.put("/ai", response_model=AISettingsOut)
def put_ai_settings(payload: AISettingsUpdate):
    """更新大模型配置，持久化到 .env 并即时生效"""
    return settings_service.update_ai_settings(payload)


@router.post("/ai/test", response_model=AISettingsTestResult)
def post_ai_test(payload: AISettingsTestRequest):
    """试连通：用表单值（缺省回落已存配置）发最小请求验证"""
    return settings_service.test_ai_settings(payload)
