"""后台任务执行器：单 worker 线程池，严格串行（保护 baostock 全局登录状态）"""

import time
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from .store import TaskStore
from .progress import ProgressReporter, TaskCancelled

logger = logging.getLogger("api.tasks.runner")


class TaskRunner:
    """单 worker 后台任务执行器

    设计约束：
    - max_workers=1：保证 download/screen/daily 任务严格串行执行
    - baostock bs.login() 是全局有状态，并发会冲突
    - 任务提交不拒绝，排队；用户可通过 DELETE /api/tasks/{id} 取消
    """

    def __init__(self, store: TaskStore, max_workers: int = 1):
        if max_workers != 1:
            raise ValueError("TaskRunner 必须单 worker（baostock 全局登录状态并发不安全）")
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="task-worker")

    def submit(self, task_type: str, params: dict, runner_fn: Callable) -> str:
        """提交一个任务，返回 task_id

        runner_fn(reporter, params) -> result_dict
        """
        task = self.store.create(task_type, params)
        task_id = task.id
        # 提交到 worker
        self.executor.submit(self._run, task_id, runner_fn, params)
        return task_id

    def _run(self, task_id: str, runner_fn: Callable, params: dict):
        """worker 线程入口"""
        task = self.store.update(task_id, status="running", started_at=time.time())
        reporter = ProgressReporter(self.store, task_id)
        try:
            reporter.log(f"任务开始: {task.type}")
            result = runner_fn(reporter, params)
            self.store.update(
                task_id,
                status="success",
                progress=100,
                result=result if isinstance(result, dict) else {"value": str(result)},
                finished_at=time.time(),
            )
            reporter.log("任务完成")
        except TaskCancelled:
            self.store.update(
                task_id, status="cancelled", error="用户取消", finished_at=time.time(),
            )
            reporter.log("任务被取消")
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"任务 {task_id} 失败: {e}\n{tb}")
            self.store.update(
                task_id,
                status="failed",
                error=f"{type(e).__name__}: {e}",
                finished_at=time.time(),
            )
            reporter.log(f"任务失败: {type(e).__name__}: {e}")

    def shutdown(self, wait: bool = True):
        self.executor.shutdown(wait=wait)

    @property
    def pending_count(self) -> int:
        """当前还有多少 pending 任务（含 running）"""
        with self.store._lock:
            return sum(1 for t in self.store._tasks.values()
                       if t.status in ("pending", "running"))
