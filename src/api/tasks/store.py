"""任务存储：内存中的 TaskStore，带锁，支持进度/日志/状态查询
设计原则：单进程；任务状态完全在内存（重启清空，不持久化）
"""

import time
import uuid
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# 终态（不再变化）
TERMINAL_STATUSES = {"success", "failed", "cancelled"}

# 终态任务保留上限（避免内存无限增长）
TERMINAL_KEEP = 200

# 单任务日志缓冲长度
LOG_BUFFER_SIZE = 500


@dataclass
class Task:
    """单个后台任务"""
    id: str
    type: str           # download_universe / download_fundamentals / ... / screen_value / screen_all / daily_report
    params: dict = field(default_factory=dict)

    status: str = "pending"   # pending / running / success / failed / cancelled
    progress: int = 0         # 0-100
    step: str = ""            # 人类可读进度描述

    result: Optional[dict] = None
    error: Optional[str] = None

    logs: deque = field(default_factory=lambda: deque(maxlen=LOG_BUFFER_SIZE))
    log_offset: int = 0       # 已经消费过的日志条数（用于增量拉取）

    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    cancel_requested: bool = False

    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def append_log(self, line: str) -> int:
        """追加一行日志，返回当前日志总条数（供 offset 计算）"""
        ts = time.strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {line}")
        return len(self.logs)

    def to_dict(self, include_logs: bool = False) -> dict:
        d = {
            "id": self.id,
            "type": self.type,
            "params": self.params,
            "status": self.status,
            "progress": self.progress,
            "step": self.step,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "cancel_requested": self.cancel_requested,
            "log_count": len(self.logs),
        }
        if include_logs:
            d["logs"] = list(self.logs)
        return d


class TaskStore:
    """线程安全的内存任务存储"""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.RLock()

    def create(self, type_: str, params: dict) -> Task:
        task = Task(id=uuid.uuid4().hex[:12], type=type_, params=params)
        with self._lock:
            self._tasks[task.id] = task
            self._gc_locked()
        return task

    def get(self, task_id: str) -> Task:
        with self._lock:
            t = self._tasks.get(task_id)
            if t is None:
                from src.api.errors import TaskNotFoundError
                raise TaskNotFoundError(f"任务 {task_id} 不存在")
            return t

    def list(self, status: Optional[str] = None) -> list[Task]:
        with self._lock:
            tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        # 倒序：最新的在前
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks

    def update(self, task_id: str, **kwargs) -> Task:
        with self._lock:
            t = self._tasks.get(task_id)
            if t is None:
                from src.api.errors import TaskNotFoundError
                raise TaskNotFoundError(f"任务 {task_id} 不存在")
            for k, v in kwargs.items():
                if hasattr(t, k):
                    setattr(t, k, v)
            return t

    def get_logs_since(self, task_id: str, offset: int) -> Tuple["Task", List[str]]:
        """从 offset 开始取日志"""
        t = self.get(task_id)
        logs = list(t.logs)
        return t, logs[offset:]

    def request_cancel(self, task_id: str) -> Task:
        with self._lock:
            t = self._tasks.get(task_id)
            if t is None:
                from src.api.errors import TaskNotFoundError
                raise TaskNotFoundError(f"任务 {task_id} 不存在")
            if t.status == "pending":
                t.status = "cancelled"
                t.finished_at = time.time()
            elif t.status == "running":
                t.cancel_requested = True
            else:
                # 终态不能取消
                pass
            return t

    def _gc_locked(self):
        """清理超出数量的终态任务（必须在持锁状态下调用）"""
        terminals = [t for t in self._tasks.values() if t.is_terminal()]
        if len(terminals) <= TERMINAL_KEEP:
            return
        terminals.sort(key=lambda t: t.created_at)
        to_delete = terminals[: len(terminals) - TERMINAL_KEEP]
        for t in to_delete:
            del self._tasks[t.id]
