"""FastAPI 应用工厂"""

import os
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from src.api.errors import AppError
from src.api.tasks.store import TaskStore
from src.api.tasks.runner import TaskRunner
from src.api.routers import health, tasks, analyze, download, screen, daily, settings, chat, stock

logger = logging.getLogger("api.app")
logging.basicConfig(
    level=os.environ.get("QUANT_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动建 TaskStore + TaskRunner，关闭优雅停机"""
    app.state.task_store = TaskStore()
    app.state.task_runner = TaskRunner(app.state.task_store)
    logger.info("API 服务启动完成，TaskRunner 单 worker 就绪")
    try:
        yield
    finally:
        logger.info("API 服务关闭中...")
        app.state.task_runner.shutdown(wait=True)
        logger.info("TaskRunner 已关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="A股量化交易 API",
        version="1.0.0",
        description=(
            "A 股多策略量化选股 + 风险研判系统后端 API。\n\n"
            "## 重要约束\n"
            "- 服务必须以 `workers=1` 启动（baostock 全局登录状态并发不安全）\n"
            "- 长任务（download/screen/daily）通过 `/api/tasks/{id}` 轮询进度\n"
            "- AI 点评需在 `.env` 配置 `QUANT_AI_API_KEY`，否则 `ai_enabled=false`"
        ),
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 异常处理：AppError → 对应 HTTP 状态码 + 统一结构
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.http_status, content=exc.to_dict())

    # 异常处理：Pydantic 验证错误
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "请求参数验证失败",
                    "detail": {"errors": exc.errors()},
                }
            },
        )

    # 兜底：所有未捕获异常 → 500
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        import traceback
        tb = traceback.format_exc()
        # 安全地 stringify 异常（避免 ValueError 等对象不能 JSON 序列化）
        try:
            exc_name = type(exc).__name__
            exc_msg = str(exc) or repr(exc)
            message = f"{exc_name}: {exc_msg}"
        except Exception:
            message = f"{type(exc).__name__}: <unstringifiable>"
        logger.error(f"未处理异常 {request.method} {request.url.path}: {message}\n{tb}")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": message,
                    "detail": {"path": request.url.path},
                }
            },
        )

    # 路由注册
    app.include_router(health.router)
    app.include_router(tasks.router)
    app.include_router(analyze.router)
    app.include_router(download.router)
    app.include_router(screen.router)
    app.include_router(daily.router)
    app.include_router(settings.router)
    app.include_router(chat.router)
    app.include_router(stock.router)

    # 静态文件（前端）— 可选
    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    else:
        @app.get("/")
        def root():
            return {
                "name": "A股量化交易 API",
                "version": "1.0.0",
                "docs": "/docs",
                "health": "/api/health",
                "frontend": "frontend/ 目录未创建（可选）",
            }

    return app
