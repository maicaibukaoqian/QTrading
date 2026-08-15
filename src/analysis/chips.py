"""筹码分析
基于量价关系判断吸筹/出货：低位集中（吸筹）vs 高位分散（派发）
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from ..data.processor import calc_price_position


class ChipsAnalysis:
    """筹码分析器（基于量价关系）."""

    def __init__(self, kline_df: pd.DataFrame):
        self.kline_df = kline_df

    def analyze(self) -> Dict[str, Any]:
        """执行筹码分析."""
        if self.kline_df is None or len(self.kline_df) < 60:
            return {
                'valid': False,
                'reason': '数据不足',
            }

        # 计算近三个月成交量变化
        recent_3m = self.kline_df.tail(60)
        earlier_3m = self.kline_df.tail(120).head(60)

        avg_vol_recent = recent_3m['volume'].mean()
        avg_vol_earlier = earlier_3m['volume'].mean()

        vol_ratio = avg_vol_recent / avg_vol_earlier if avg_vol_earlier > 0 else 1

        # 价格位置
        price_pos = calc_price_position(self.kline_df, 250)

        # 量价关系判断：低位缩量 = 筹码集中；高位放量 = 筹码分散
        # 判断吸筹还是出货

        if price_pos < 0.3:
            # 低位
            if vol_ratio < 0.8:
                # 缩量，浮筹少
                conclusion = '低位缩量，筹码趋于集中，可能主力吸筹中'
                judgment = '偏多'
            elif vol_ratio > 1.5:
                # 低位放量，可能资金进场
                conclusion = '低位放量，资金进场吸筹'
                judgment = '偏多'
            else:
                conclusion = '低位正常换手，筹码稳定'
                judgment = '中性'
        elif price_pos > 0.8:
            # 高位
            if vol_ratio > 1.5:
                conclusion = '高位放量，主力可能出货，筹码分散到散户'
                judgment = '偏空'
            elif vol_ratio < 0.8:
                conclusion = '高位缩量，筹码锁定良好'
                judgment = '中性偏多'
            else:
                conclusion = '高位正常换手，保持警惕'
                judgment = '偏空'
        else:
            # 中位
            if vol_ratio > 1.5:
                conclusion = '中位放量换手，可能震荡洗盘'
                judgment = '中性'
            else:
                conclusion = '中位正常换手，方向不明'
                judgment = '中性'

        return {
            'valid': True,
            'price_position': round(price_pos, 2),
            'recent_avg_vol': round(avg_vol_recent),
            'earlier_avg_vol': round(avg_vol_earlier),
            'vol_ratio': round(vol_ratio, 2),
            'conclusion': conclusion,
            'judgment': judgment,
        }

    def get_report_text(self) -> str:
        """生成筹码分析文本报告."""
        result = self.analyze()

        lines = ['## 筹码分析（量价关系）\n']

        if not result['valid']:
            lines.append(f"❌ **无法分析**：{result['reason']}\n")
            return '\n'.join(lines)

        judgement_map = {
            '偏多': '🟢 偏多',
            '中性': '🟡 中性',
            '中性偏多': '🟢 中性偏多',
            '偏空': '🔴 偏空',
        }

        lines.append(f"- 当前价格位置：**{int(result['price_position'] * 100)}%**（近一年区间）\n")
        lines.append(f"- 近期成交量变化：最近3个月成交量是之前的 **{result['vol_ratio']}倍**\n")
        lines.append(f"- 结论：{result['conclusion']}\n")
        lines.append(f"- 判断：{judgement_map.get(result['judgment'], result['judgment'])}\n")

        lines.append('\n> 量价经验法则：低位筹码集中到主力，后市看涨；高位筹码分散到散户，后市看跌。\n')

        return '\n'.join(lines)
