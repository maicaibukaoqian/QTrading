"""screen 模块的 Pydantic 模型"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StrategyInfo(BaseModel):
    """GET /api/screen/strategies 单个策略信息"""
    key: str
    cn_name: str
    description: str
    default_params: Dict[str, Any]
    default_output: str


class StrategiesOut(BaseModel):
    """GET /api/screen/strategies 响应"""
    strategies: List[StrategyInfo]


class ScreenRow(BaseModel):
    """选股结果单行（screen_all CSV 中文列名 → 英文 alias）"""
    code: str
    name: Optional[str] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    latest_roe: Optional[float] = None
    # 来自 screen_all
    hit_count: Optional[int] = Field(default=None, alias="命中策略数", serialization_alias="hit_count")
    hit_strategies: Optional[str] = Field(default=None, alias="命中策略", serialization_alias="hit_strategies")
    # 来自 dividend
    dividend_yield: Optional[float] = None
    # 来自 kline
    latest_close: Optional[float] = None

    class Config:
        populate_by_name = True


class ScreenResultPage(BaseModel):
    """GET /api/screen/results 响应"""
    file: str
    path: str
    total_before_filter: int
    total: int
    page: int
    size: int
    rows: List[Dict[str, Any]]


class ScreenRunResult(BaseModel):
    """单策略 / 全策略选股结果（异步任务的 result 字段）"""
    strategy: Optional[str] = None
    cn_name: Optional[str] = None
    count: int
    resonance_count: Optional[int] = None
    output_path: Optional[str] = None
    rows: List[Dict[str, Any]]


class ScreenAllRequest(BaseModel):
    """POST /api/screen/all body"""
    output_path: Optional[str] = None
    min_roe: Optional[float] = None
    overrides: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="按策略 key 覆盖默认参数，例如 {'value': {'max_pe': 25.0}}",
    )


# ============= 5 个策略的 Pydantic 参数模型（挂到 StrategySpec.params_model） =============

class ValueParams(BaseModel):
    """value / 520 共用基础参数"""
    max_pe: float = Field(default=30.0, ge=0, le=200)
    min_roe: float = Field(default=10.0, ge=0, le=100)
    min_gross_margin: float = Field(default=20.0, ge=0, le=100)
    max_debt_ratio: float = Field(default=70.0, ge=0, le=100)
    check_years: int = Field(default=3, ge=1, le=10)


class Trend520Params(ValueParams):
    """520 与 value 同字段，单独建类便于 /api/screen/strategies 区分"""
    max_pe: float = Field(default=40.0, ge=0, le=200)


class DoubleLowParams(BaseModel):
    """doublelow: PE+PB 双低"""
    max_pe: float = Field(default=20.0, ge=0, le=200)
    max_pb: float = Field(default=2.0, ge=0, le=20)
    min_roe: float = Field(default=8.0, ge=0, le=100)
    max_debt_ratio: float = Field(default=70.0, ge=0, le=100)
    check_years: int = Field(default=3, ge=1, le=10)


class HighDividendParams(BaseModel):
    """dividend: 高股息"""
    max_pe: float = Field(default=30.0, ge=0, le=200)
    min_roe: float = Field(default=8.0, ge=0, le=100)
    min_gross_margin: float = Field(default=15.0, ge=0, le=100)
    max_debt_ratio: float = Field(default=70.0, ge=0, le=100)
    min_dividend_yield: float = Field(default=3.0, ge=0, le=50)
    check_years: int = Field(default=3, ge=1, le=10)


class XiaoyangParams(BaseModel):
    """xiaoyang: 小阳建仓"""
    min_days: int = Field(default=5, ge=2, le=30)
    max_pe: float = Field(default=40.0, ge=0, le=200)
    min_roe: float = Field(default=8.0, ge=0, le=100)
    check_years: int = Field(default=3, ge=1, le=10)
