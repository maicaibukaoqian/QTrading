"""daily 模块的 Pydantic 模型"""

from typing import List, Optional
from pydantic import BaseModel, Field


class DailyReportRequest(BaseModel):
    """POST /api/daily/report"""
    input_csv: Optional[str] = Field(default=None, description="选股结果 CSV 路径")
    output_dir: Optional[str] = Field(default=None, description="日报输出目录")
    ai: bool = Field(default=True, description="是否启用 AI 点评")
    max_ai_comments: Optional[int] = Field(default=None, ge=0, le=500)


class DailyReportResult(BaseModel):
    """daily_report 任务的 result 字段"""
    date: str
    path: str
    total: int
    resonance_count: int
    ai_generated: int


class DailyReportList(BaseModel):
    """GET /api/daily/reports"""
    dates: List[str]
