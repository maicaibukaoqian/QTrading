"""通用 Pydantic 模型"""

from typing import Optional, List, Any
from pydantic import BaseModel


class ErrorOut(BaseModel):
    """统一错误响应"""
    error: dict


class TaskRef(BaseModel):
    """异步任务引用（创建任务后立刻返回）"""
    task_id: str
    status: str = "pending"
    type: str
    message: Optional[str] = None


class TaskStatus(BaseModel):
    """任务完整状态（GET /api/tasks/{id}）"""
    id: str
    type: str
    params: dict
    status: str
    progress: int
    step: str
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    cancel_requested: bool
    log_count: int


class TaskLogs(BaseModel):
    """任务日志（GET /api/tasks/{id}/logs）"""
    task_id: str
    offset: int
    next_offset: int
    logs: List[str]


class HealthOut(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    ai_enabled: bool
    cache_size_bytes: int
    running_tasks: int
    version: str = "1.0"
