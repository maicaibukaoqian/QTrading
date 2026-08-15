"""analyze 模块的 Pydantic 模型"""

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """POST /api/analyze"""
    code: str = Field(..., min_length=6, max_length=6, description="6 位股票代码")
    min_roe: float = Field(default=10.0, ge=0, le=100, description="最小 ROE%")
    min_gross_margin: float = Field(default=20.0, ge=0, le=100, description="最小毛利率%")
    max_debt: float = Field(default=70.0, ge=0, le=100, description="最大资产负债率%")
    check_years: int = Field(default=3, ge=1, le=10, description="要求连续达标年数")


class AnalyzeResult(BaseModel):
    """POST /api/analyze 响应"""
    code: str
    markdown: str
    saved_path: str
