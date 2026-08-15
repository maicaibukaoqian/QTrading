"""价值选股策略
基本面门槛（多维度量化筛选）：
- PE 低于阈值
- 连续 N 年 ROE 高于阈值
- 连续 N 年毛利率高于阈值
- 资产负债率低于阈值
"""

import pandas as pd
from typing import List

from ...data.baostock_api import get_all_stocks, get_financial_indicators
from ...data.cache import load_cached_finance, save_finance_cache, has_financial_cache
from ...data.processor import check_roe_consistency, check_gross_margin, check_debt_ratio
from ..base import BaseScreener


class ValueStockScreener(BaseScreener):
    """价值选股."""

    name = "value"
    description = "价值选股：PE合理 + 连续ROE达标 + 毛利率达标 + 负债率可控"

    def __init__(self, max_pe: float = 30.0, min_roe: float = 10.0,
                 min_gross_margin: float = 20.0, max_debt_ratio: float = 70.0,
                 check_years: int = 3):
        self.max_pe = max_pe
        self.min_roe = min_roe
        self.min_gross_margin = min_gross_margin
        self.max_debt_ratio = max_debt_ratio
        self.check_years = check_years

    def screen(self, universe: pd.DataFrame = None) -> pd.DataFrame:
        """执行选股，返回筛选结果."""
        if universe is None:
            # 获取全市场
            universe = get_all_stocks()

        result = []
        total = len(universe)
        cached_used = 0
        downloaded = 0
        missing = 0

        import baostock as bs

        # 尝试登录，如果失败继续用缓存
        lg = bs.login()
        login_ok = (lg.error_code == '0')

        for idx, (_, row) in enumerate(universe.iterrows()):
            code = str(row['code']).zfill(6)

            # PE先筛一遍
            if pd.isna(row['pe']) or row['pe'] > self.max_pe or row['pe'] <= 0:
                continue

            # 优先读缓存
            fin_df = load_cached_finance(code)
            if fin_df is not None and not fin_df.empty:
                cached_used += 1
            elif login_ok:
                # 缓存不存在，登录成功才能下载
                fin_df = get_financial_indicators(code, self.check_years + 2)
                if fin_df is not None and not fin_df.empty:
                    save_finance_cache(code, fin_df)
                    downloaded += 1
                    import time
                    time.sleep(0.6)
                else:
                    missing += 1
                    continue
            else:
                # 登录失败，又没缓存，跳过
                missing += 1
                continue

            if fin_df is None or fin_df.empty:
                continue

            # 检查各项条件：至少最近N年达标
            roe_ok = check_roe_consistency(fin_df, self.min_roe, self.check_years)
            margin_ok = check_gross_margin(fin_df, self.min_gross_margin, self.check_years)
            debt_ok = check_debt_ratio(fin_df, self.max_debt_ratio)

            if roe_ok and margin_ok and debt_ok:
                latest = fin_df.iloc[0]
                result.append({
                    'code': code,
                    'name': row['name'],
                    'pe': row['pe'],
                    'pb': row['pb'],
                    'latest_roe': latest['roe'],
                    'latest_gross_margin': latest['gross_margin'],
                    'latest_debt_ratio': latest['debt_ratio'],
                })

            if (idx + 1) % 100 == 0:
                print(f"[value-screen] 进度 {idx+1}/{total}, 使用缓存 {cached_used}, 新下载 {downloaded}, 跳过 {missing}, 已选出 {len(result)} 只")

        # 检查是否真的需要logout（避免logout failed）
        if login_ok:
            bs.logout()

        out_df = pd.DataFrame(result)
        # 按PE排序（如果有数据）
        if not out_df.empty:
            out_df = out_df.sort_values('pe').reset_index(drop=True)
        print(f"[value-screen] 选股完成，使用缓存 {cached_used}, 新下载 {downloaded}, 跳过 {missing}, 共选出 {len(out_df)} 只股票")
        return out_df
