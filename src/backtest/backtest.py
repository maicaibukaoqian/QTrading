"""基础回测引擎
按月滚动选股回测：每月末选股 → 下月月初买入 → 持有到下月 → 调仓
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime, timedelta

from ..data.cache import load_cached_kline
from ..data.indicators import calculate_all_indicators


class BacktestResult:
    """回测结果容器"""
    def __init__(self):
        self.dates: List[datetime] = []
        self.nav: List[float] = []  # 累计净值
        self.daily_returns: List[float] = []
        self.position_records: List[Dict] = []
        self.strategy_name: str = ""

    def get_performance(self) -> Dict[str, float]:
        """计算绩效指标"""
        if len(self.daily_returns) < 2:
            return {
                'annual_return': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'win_rate': 0.0,
            }

        returns = np.array(self.daily_returns)
        nav = np.array(self.nav)

        # 年化收益率（按交易日年化，一年252交易日）
        total_days = len(returns)
        if total_days == 0:
            annual_return = 0.0
        else:
            total_return = nav[-1] / nav[0] - 1
            annual_return = ((1 + total_return) ** (252 / total_days)) - 1

        # 最大回撤
        peak = nav[0]
        max_dd = 0.0
        for v in nav:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd

        # 夏普比率（假设无风险利率0）
        if returns.std() == 0:
            sharpe = 0.0
        else:
            sharpe = np.sqrt(252) * (returns.mean() / returns.std())

        # 胜率（按选股月份算，不是按天）
        # 这里简化：每月整体涨算赢
        monthly_gain = 0
        monthly_total = 0
        for i in range(1, len(self.nav)):
            if self.nav[i] > self.nav[i-1]:
                monthly_gain += 1
            monthly_total += 1
        win_rate = monthly_gain / monthly_total if monthly_total > 0 else 0

        return {
            'annual_return': round(annual_return * 100, 2),    # 转百分比
            'max_drawdown': round(max_dd * 100, 2),
            'sharpe_ratio': round(sharpe, 2),
            'win_rate': round(win_rate * 100, 2),
        }

    def to_markdown(self) -> str:
        """生成Markdown绩效报告"""
        perf = self.get_performance()
        lines = []
        lines.append(f'## 回测结果：{self.strategy_name}')
        lines.append('')
        lines.append('| 指标 | 数值 |')
        lines.append('|------|------|')
        lines.append(f'| 年化收益率 | {perf["annual_return"]}% |')
        lines.append(f'| 最大回撤 | {perf["max_drawdown"]}% |')
        lines.append(f'| 夏普比率 | {perf["sharpe_ratio"]} |')
        lines.append(f'| 月度胜率 | {perf["win_rate"]}% |')
        lines.append('')
        lines.append(f'回测周期：从 {self.dates[0].date()} 到 {self.dates[-1].date()}')
        lines.append(f'最终净值：{self.nav[-1]:.2f}（初始净值 1.0）')
        return '\n'.join(lines)


class SimpleMonthlyBacktest:
    """简单月度滚动回测
    - 每月最后一个交易日选股
    - 下月第一个交易日等权买入
    - 持有到下月最后一个交易日，调仓
    """

    def __init__(self, start_year: int = 2020, end_year: int = None, max_hold: int = 30):
        self.start_year = start_year
        self.end_year = end_year if end_year else datetime.now().year
        self.max_hold = max_hold  # 每月最多持有多少只，控制分散度
        self.result = BacktestResult()

    def run(self, screener_func: Callable[[], List[str]]) -> BacktestResult:
        """
        screener_func: 选股函数，返回当前要持有的股票代码列表
        """
        result = BacktestResult()
        result.strategy_name = screener_func.__name__ if hasattr(screener_func, '__name__') else 'unknown'

        # 初始化净值
        current_nav = 1.0
        result.nav.append(current_nav)

        # 获取所有交易日，按月分组
        # 这里简化：我们遍历月份，每月末选股
        # 实际从缓存K线拿日期

        # 占位：具体选股+调仓在strategy_runner里整合
        # 这个类只提供基础框架

        return result
