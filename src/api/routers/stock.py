"""股票数据端点（context / risk 等）"""

from fastapi import APIRouter

from src.data.stock_context import get_stock_context
from src.agent.risk_scorer import evaluate_stock

router = APIRouter(prefix="/api/stock", tags=["stock"])


@router.get("/{code}/context")
def get_context(code: str):
    """单只股票的实时上下文（前端行情卡 / 任何 UI 可复用）"""
    return get_stock_context(code)


@router.get("/{code}/risk")
def get_risk(code: str):
    """单只股票的 7 维风险评分 + 综合星级 + 警告列表

    返回字段：
      - code, name, industry
      - score: 加权综合分（1-5，越低越安全）
      - stars: 反向星级（1-5，越高越安全）
      - level: 人话等级（低风险 / 中低 / 中 / 中高 / 高风险）
      - dimensions: 7 维详细 (score / reason / evidence)
      - warnings: 触发警告的人话短句（>=4 分的维度）
      - raw: 关键原始指标（前端 tooltip 用）
    """
    return evaluate_stock(code).to_dict()
