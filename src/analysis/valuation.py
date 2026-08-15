"""估值分析
PE百分位、PB百分位、高低估判断
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any

from ..data.processor import calc_pe_percentile


class ValuationAnalysis:
    """估值分析器."""

    def __init__(self, kline_df: pd.DataFrame):
        self.kline_df = kline_df

    def analyze(self) -> Dict[str, Any]:
        """执行估值分析."""
        if self.kline_df is None or self.kline_df.empty:
            return {
                'valid': False,
                'reason': '没有K线数据',
            }

        if 'pettm' not in self.kline_df.columns:
            return {
                'valid': False,
                'reason': '没有PE数据',
            }

        pe_percentile = calc_pe_percentile(self.kline_df)
        if np.isnan(pe_percentile):
            return {
                'valid': False,
                'reason': 'PE数据不足',
            }

        current_pe = self.kline_df['pettm'].dropna().iloc[-1]

        # 判断估值区间
        if pe_percentile < 0.2:
            level = '低估'
            suggestion = '估值便宜，可以考虑分批买入'
        elif pe_percentile < 0.4:
            level = '偏低'
            suggestion = '估值合理偏低'
        elif pe_percentile < 0.6:
            level = '合理'
            suggestion = '估值在合理区间'
        elif pe_percentile < 0.8:
            level = '偏高'
            suggestion = '估值偏高，不建议追高'
        else:
            level = '高估'
            suggestion = '估值高估，注意风险'

        return {
            'valid': True,
            'current_pe': round(current_pe, 2),
            'pe_percentile': round(pe_percentile * 100, 1),
            'level': level,
            'suggestion': suggestion,
        }

    def get_report_text(self) -> str:
        """生成估值分析文本报告."""
        result = self.analyze()

        lines = ['## 估值分析\n']

        if not result['valid']:
            lines.append(f"❌ **无法计算**：{result['reason']}\n")
            return '\n'.join(lines)

        emoji_map = {
            '低估': '🟢',
            '偏低': '🟢',
            '合理': '🟡',
            '偏高': '🟠',
            '高估': '🔴',
        }

        emoji = emoji_map.get(result['level'], '⚪')

        lines.append(f"- 当前动态PE：**{result['current_pe']}**\n")
        lines.append(f"- PE历史百分位：**{result['pe_percentile']}%**\n")
        lines.append(f"- 估值水平：{emoji} **{result['level']}**\n")
        lines.append(f"- 建议：{result['suggestion']}\n")

        return '\n'.join(lines)
