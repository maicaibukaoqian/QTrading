"""健康检查 router"""

from fastapi import APIRouter, Request
from src.api.schemas import HealthOut
from src.config.settings import get_settings
from src.data.cache import get_cache_size


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(request: Request):
    """服务存活 + 关键状态"""
    store = request.app.state.task_store
    running = [t for t in store.list() if t.status == "running"]
    settings = get_settings()
    return HealthOut(
        status="ok",
        ai_enabled=settings.ai_enabled,
        cache_size_bytes=get_cache_size(),
        running_tasks=len(running),
    )
