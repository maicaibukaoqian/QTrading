"""基本面分析
基于财务数据：ROE、毛利率、资产负债率、PE、PB
"""

import pandas as pd
from typing import Dict, Optional, Any

from ..data.baostock_api import get_financial_indicators
from ..data.cache import load_cached_finance, save_finance_cache
from ..data.processor import check_roe_consistency, check_gross_margin, check_debt_ratio


class FundamentalAnalysis:
    """基本面分析器."""

    def __init__(self, symbol: str, min_roe: float = 10.0, min_gross_margin: float = 20.0,
                 max_debt_ratio: float = 70.0, check_years: int = 3):
        self.symbol = symbol
        self.min_roe = min_roe
        self.min_gross_margin = min_gross_margin
        self.max_debt_ratio = max_debt_ratio
        self.check_years = check_years
        self.finance_df: Optional[pd.DataFrame] = None

    def load_data(self, use_cache: bool = True) -> pd.DataFrame | None:
        """加载财务数据，优先读缓存."""
        if use_cache:
            cached = load_cached_finance(self.symbol)
            if cached is not None:
                self.finance_df = cached
                return self.finance_df

        # 重新获取
        import baostock as bs
        lg = bs.login()
        self.finance_df = get_financial_indicators(self.symbol, years=self.check_years + 2)
        bs.logout()

        if self.finance_df is not None and use_cache:
            save_finance_cache(self.symbol, self.finance_df)

        return self.finance_df

    def analyze(self) -> Dict[str, Any]:
        """执行基本面分析，返回结果字典."""
        if self.finance_df is None:
            self.load_data()

        if self.finance_df is None or self.finance_df.dropna(subset=['roe', 'gross_margin', 'debt_ratio']).empty:
            return {
                'valid': False,
                'reason': '无法获取足够财务数据',
                'roe_ok': False,
                'margin_ok': False,
                'debt_ok': False,
                'latest_roe': None,
                'latest_gross_margin': None,
                'latest_debt_ratio': None,
            }

        latest = self.finance_df.iloc[0]
        roe_ok = check_roe_consistency(self.finance_df, self.min_roe, self.check_years)
        margin_ok = check_gross_margin(self.finance_df, self.min_gross_margin, self.check_years)
        debt_ok = check_debt_ratio(self.finance_df, self.max_debt_ratio)

        valid = roe_ok and margin_ok and debt_ok

        result = {
            'valid': valid,
            'roe_ok': roe_ok,
            'margin_ok': margin_ok,
            'debt_ok': debt_ok,
            'latest_roe': round(latest['roe'], 2) if not pd.isna(latest['roe']) else None,
            'latest_gross_margin': round(latest['gross_margin'], 2) if not pd.isna(latest['gross_margin']) else None,
            'latest_debt_ratio': round(latest['debt_ratio'], 2) if not pd.isna(latest['debt_ratio']) else None,
            'years_checked': min(len(self.finance_df.dropna(subset=['roe'])), self.check_years),
        }

        if not valid:
            reasons = []
            if not roe_ok:
                reasons.append('ROE不达标')
            if not margin_ok:
                reasons.append('毛利率不达标')
            if not debt_ok:
                reasons.append('资产负债率超标')
            result['reason'] = '，'.join(reasons)

        return result

    def get_report_text(self) -> str:
        """生成基本面分析文本报告."""
        result = self.analyze()

        lines = ['## 基本面分析\n']

        if not result['valid']:
            lines.append(f"❌ **不合格**：{result['reason']}\n")
            return '\n'.join(lines)

        status = "✅ 通过" if result['valid'] else "❌ 不通过"
        lines.append(f"筛选标准：连续{self.check_years}年 ROE ≥ {self.min_roe}%，毛利率 ≥ {self.min_gross_margin}%，资产负债率 ≤ {self.max_debt_ratio}%\n")
        lines.append(f"结果：{status}\n")
        lines.append(f"- 最新ROE：**{result['latest_roe']}%** （要求≥{self.min_roe}%） {'✅' if result['roe_ok'] else '❌'}\n")
        lines.append(f"- 最新毛利率：**{result['latest_gross_margin']}%** （要求≥{self.min_gross_margin}%） {'✅' if result['margin_ok'] else '❌'}\n")
        lines.append(f"- 最新资产负债率：**{result['latest_debt_ratio']}%** （要求≤{self.max_debt_ratio}%） {'✅' if result['debt_ok'] else '❌'}\n")

        return '\n'.join(lines)
