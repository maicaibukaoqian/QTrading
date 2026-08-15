"""schemas package"""

from .common import ErrorOut, TaskRef, TaskStatus, TaskLogs, HealthOut
from .analyze import AnalyzeRequest, AnalyzeResult
from .download import (
    DownloadFundamentalsRequest,
    DownloadKlinesRequest,
    DownloadFromResultRequest,
)
from .screen import (
    StrategyInfo,
    StrategiesOut,
    ScreenRow,
    ScreenResultPage,
    ScreenRunResult,
    ScreenAllRequest,
    ValueParams,
    Trend520Params,
    DoubleLowParams,
    HighDividendParams,
    XiaoyangParams,
)
from .daily import DailyReportRequest, DailyReportResult, DailyReportList

__all__ = [
    "ErrorOut", "TaskRef", "TaskStatus", "TaskLogs", "HealthOut",
    "AnalyzeRequest", "AnalyzeResult",
    "DownloadFundamentalsRequest", "DownloadKlinesRequest", "DownloadFromResultRequest",
    "StrategyInfo", "StrategiesOut", "ScreenRow", "ScreenResultPage", "ScreenRunResult", "ScreenAllRequest",
    "ValueParams", "Trend520Params", "DoubleLowParams", "HighDividendParams", "XiaoyangParams",
    "DailyReportRequest", "DailyReportResult", "DailyReportList",
]
