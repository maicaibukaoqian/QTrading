"""应用错误体系

AppError 基类 + 各业务异常；每个异常带 code、message、http_status。
HTTPException handler 在 app.py 注册，把 AppError 转成统一 JSON 响应。
"""

from typing import Optional


class AppError(Exception):
    """应用层业务异常基类"""
    code: str = "app_error"
    http_status: int = 500

    def __init__(self, message: str, detail: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or {}

    def to_dict(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "detail": self.detail,
            }
        }


class MissingDataError(AppError):
    """必要数据缺失（universe/缓存/输入 CSV 等）"""
    code = "missing_data"
    http_status = 424


class InvalidStrategyError(AppError):
    """未知/非法策略名"""
    code = "invalid_strategy"
    http_status = 400


class ResultNotFoundError(AppError):
    """选股结果 CSV 不存在"""
    code = "result_not_found"
    http_status = 404


class ReportNotFoundError(AppError):
    """日报 markdown 不存在"""
    code = "report_not_found"
    http_status = 404


class TaskNotFoundError(AppError):
    """任务 ID 不存在"""
    code = "task_not_found"
    http_status = 404


class DownloadError(AppError):
    """三层数据源全部失败"""
    code = "download_failed"
    http_status = 502


class ScreenerError(AppError):
    """选股过程出错"""
    code = "screener_error"
    http_status = 500


class AIUnavailableError(AppError):
    """AI 点评不可用（要求 ai=true 但 key 未配置）"""
    code = "ai_unavailable"
    http_status = 503


class AnalyzeError(AppError):
    """单股分析失败"""
    code = "analyze_error"
    http_status = 500


class InvalidRequestError(AppError):
    """请求参数不合法（业务层面校验失败）"""
    code = "invalid_request"
    http_status = 400
