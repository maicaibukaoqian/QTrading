"""Agent综合分析调度
调用数据层+分析层，生成完整分析报告
"""

from typing import Optional, Dict, Any
from ..analysis.reporter import StockReportGenerator


class StockAgentAnalyzer:
    """股票Agent分析器."""

    def __init__(self, min_roe: float = 10.0, min_gross_margin: float = 20.0,
                 max_debt_ratio: float = 70.0, check_years: int = 3):
        self.min_roe = min_roe
        self.min_gross_margin = min_gross_margin
        self.max_debt_ratio = max_debt_ratio
        self.check_years = check_years

    def analyze(self, symbol: str) -> str:
        """分析单只股票，返回完整markdown报告."""
        generator = StockReportGenerator(
            symbol,
            min_roe=self.min_roe,
            min_gross_margin=self.min_gross_margin,
            max_debt_ratio=self.max_debt_ratio,
            check_years=self.check_years
        )
        report = generator.generate()
        return report
