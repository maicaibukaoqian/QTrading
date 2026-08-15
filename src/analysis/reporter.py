"""综合分析报告生成器
整合基本面/技术面/估值/筹码四个维度，生成完整markdown报告
"""

from typing import Dict, Any
from .fundamental import FundamentalAnalysis
from .technical import TechnicalAnalysis
from .valuation import ValuationAnalysis
from .chips import ChipsAnalysis


class StockReportGenerator:
    """综合股票分析报告生成器."""

    def __init__(self, symbol: str, min_roe: float = 10.0, min_gross_margin: float = 20.0,
                 max_debt_ratio: float = 70.0, check_years: int = 3):
        self.symbol = symbol
        self.min_roe = min_roe
        self.min_gross_margin = min_gross_margin
        self.max_debt_ratio = max_debt_ratio
        self.check_years = check_years

        # 各个分析器
        self.fa = FundamentalAnalysis(symbol, min_roe, min_gross_margin, max_debt_ratio, check_years)
        self.ta = TechnicalAnalysis(symbol)
        self.va: ValuationAnalysis = None
        self.ca: ChipsAnalysis = None

    def generate(self) -> str:
        """生成完整分析报告markdown."""
        # 加载数据
        self.fa.load_data()
        self.ta.load_data()

        # 各个部分报告
        fa_text = self.fa.get_report_text()
        ta_text = self.ta.get_report_text()

        # 估值和筹码需要kline数据
        if self.ta.kline_df is not None:
            self.va = ValuationAnalysis(self.ta.kline_df)
            va_text = self.va.get_report_text()
            self.ca = ChipsAnalysis(self.ta.kline_df)
            ca_text = self.ca.get_report_text()
        else:
            va_text = "## 估值分析\n\n❌ 无法生成，缺少K线数据\n"
            ca_text = "## 筹码分析\n\n❌ 无法生成，缺少K线数据\n"

        # 综合结论
        conclusion = self._get_conclusion()

        # 拼起来
        report = f"""# {self.symbol} 综合分析报告

> 分析基于多维度量化框架（基本面/估值/技术/筹码），仅做认知交流，不构成投资建议，市场有风险，决策盈亏自负。

{fa_text}

{ta_text}

{va_text}

{ca_text}

{conclusion}

---
分析完成
"""
        return report

    def _get_conclusion(self) -> str:
        """生成综合结论和建议."""
        fa_result = self.fa.analyze()
        if self.ta.kline_df is not None:
            ta_result = self.ta.analyze()
            va_result = self.va.analyze() if self.va else None
            ca_result = self.ca.analyze() if self.ca else None
        else:
            ta_result = None
            va_result = None
            ca_result = None

        lines = ['## 综合结论与建议\n']

        # 基本面门槛
        if not fa_result['valid']:
            lines.append('❌ **基本面不达标**，不符合财务筛选门槛，建议回避。\n')
            return '\n'.join(lines)

        lines.append('✅ **基本面通过筛选**\n')

        if ta_result is None:
            return '\n'.join(lines)

        # 趋势判断
        if ta_result['bullish_trend']:
            lines.append('- 趋势：**多头趋势**，符合进场条件\n')
        elif ta_result['bearish_trend']:
            lines.append('- 趋势：**空头趋势**，建议观望等待\n')
        else:
            lines.append('- 趋势：**震荡整理**，等待方向明确\n')

        # 估值
        if va_result and va_result['valid']:
            lines.append(f'- 估值：**{va_result["level"]}**，{va_result["suggestion"]}\n')

        # 筹码
        if ca_result and ca_result['valid']:
            lines.append(f'- 筹码：{ca_result["conclusion"]}\n')

        # 买卖点信号
        if ta_result['golden_cross_5_20'] and fa_result['valid']:
            lines.append('\n🟢 **技术信号：5 日线金叉 20 日线，符合趋势 520 买点**\n')
        elif ta_result['death_cross_5_20']:
            lines.append('\n🔴 **技术信号：5 日线死叉 20 日线，符合趋势 520 卖点**\n')

        # 交易风险提示
        lines.append('\n---\n')
        lines.append('> **交易风险提示**：\n')
        lines.append('> 1. 仓位管理：单票仓位建议不要超过20%，根据你的总资金合理分配\n')
        lines.append('> 2. 止损：买入前设定止损点，比如跌破20日线止损，严格执行\n')
        lines.append('> 3. 不追高：高位估值泡沫的品种，即使技术好看也谨慎追高\n')
        lines.append('> 4. 自己决策：分析只是框架，最终买卖决策请你自己判断，自己对自己负责\n')

        return '\n'.join(lines)
