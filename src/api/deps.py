"""依赖注入：app 启动时建 TaskRunner，挂到 app.state 上"""

from fastapi import Request
from src.config.settings import get_settings
from src.api.tasks.store import TaskStore
from src.api.tasks.runner import TaskRunner


def get_task_store(request: Request) -> TaskStore:
    return request.app.state.task_store


def get_task_runner(request: Request) -> TaskRunner:
    return request.app.state.task_runner


def get_settings_dep():
    return get_settings()
