"""download 模块的 Pydantic 模型"""

from typing import List, Optional
from pydantic import BaseModel, Field


class DownloadFundamentalsRequest(BaseModel):
    """POST /api/download/fundamentals"""
    max_stocks: Optional[int] = Field(default=None, ge=1, description="最大下载数量")
    skip_existing: bool = Field(default=True, description="跳过已下载的")


class DownloadKlinesRequest(BaseModel):
    """POST /api/download/klines"""
    codes: Optional[List[str]] = Field(default=None, description="指定代码列表（逗号分隔或数组）")
    max_stocks: Optional[int] = Field(default=None, ge=1, description="最大下载数量")
    start_date: Optional[str] = Field(default=None, description="起始日期 YYYY-MM-DD")


class DownloadFromResultRequest(BaseModel):
    """POST /api/download/from-result — 二选一
    校验放在 router 里做（model_validator 抛 ValueError 在 Pydantic v2 + FastAPI 不会自动转 422）
    """
    csv_path: Optional[str] = Field(default=None, description="选股结果 CSV 路径")
    codes: Optional[List[str]] = Field(default=None, description="或者直接给代码列表")
