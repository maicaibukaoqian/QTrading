"""任务管理 router：查询状态、日志、取消"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_task_store
from src.api.schemas import TaskStatus, TaskLogs
from src.api.tasks.store import TaskStore

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskStatus])
def list_tasks(
    status: Optional[str] = Query(default=None, description="pending/running/success/failed/cancelled"),
    store: TaskStore = Depends(get_task_store),
):
    return [TaskStatus(**t.to_dict()) for t in store.list(status=status)]


@router.get("/{task_id}", response_model=TaskStatus)
def get_task(task_id: str, store: TaskStore = Depends(get_task_store)):
    t = store.get(task_id)
    return TaskStatus(**t.to_dict())


@router.get("/{task_id}/logs", response_model=TaskLogs)
def get_task_logs(
    task_id: str,
    offset: int = Query(default=0, ge=0),
    store: TaskStore = Depends(get_task_store),
):
    t, logs = store.get_logs_since(task_id, offset)
    return TaskLogs(
        task_id=t.id,
        offset=offset,
        next_offset=offset + len(logs),
        logs=logs,
    )


@router.delete("/{task_id}", response_model=TaskStatus)
def cancel_task(task_id: str, store: TaskStore = Depends(get_task_store)):
    t = store.request_cancel(task_id)
    return TaskStatus(**t.to_dict())
