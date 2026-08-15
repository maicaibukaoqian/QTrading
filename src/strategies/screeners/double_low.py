"""双低选股策略（低PE + 低PB）
深度价值选股，适合保守投资者
筛选条件：
- PE < max_pe
- PB < max_pb
- ROE > min_roe
"""

import pandas as pd

from ...data.baostock_api import get_financial_indicators
from ...data.cache import load_cached_finance, save_finance_cache
from ...data.processor import check_roe_consistency, check_debt_ratio
from ..base import BaseScreener


class DoubleLowScreener(BaseScreener):
    """双低选股（低PE + 低PB）."""

    name = "double_low"
    description = "双低选股：低PE + 低PB + ROE达标"

    def __init__(self, max_pe: float = 20.0, max_pb: float = 2.0,
                 min_roe: float = 8.0, max_debt_ratio: float = 70.0,
                 check_years: int = 3):
        self.max_pe = max_pe
        self.max_pb = max_pb
        self.min_roe = min_roe
        self.max_debt_ratio = max_debt_ratio
        self.check_years = check_years

    def screen(self, universe: pd.DataFrame) -> pd.DataFrame:
        """执行双低选股."""
        result = []
        total = len(universe)
        cached_used = 0
        downloaded = 0
        missing = 0

        import baostock as bs
        lg = bs.login()
        login_ok = (lg.error_code == '0')

        for idx, (_, row) in enumerate(universe.iterrows()):
            code = str(row['code']).zfill(6)

            # PE/PB先筛一遍
            if pd.isna(row['pe']) or pd.isna(row['pb']):
                continue
            if row['pe'] > self.max_pe or row['pe'] <= 0:
                continue
            if row['pb'] > self.max_pb or row['pb'] <= 0:
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
                missing += 1
                continue

            if fin_df is None or fin_df.empty:
                continue

            roe_ok = check_roe_consistency(fin_df, self.min_roe, self.check_years)
            debt_ok = check_debt_ratio(fin_df, self.max_debt_ratio)

            if not (roe_ok and debt_ok):
                continue

            latest = fin_df.iloc[0]
            result.append({
                'code': code,
                'name': row['name'],
                'pe': row['pe'],
                'pb': row['pb'],
                'latest_roe': latest['roe'],
            })

            if (idx + 1) % 100 == 0:
                print(f"[doublelow-screen] 进度 {idx+1}/{total}, 使用缓存 {cached_used}, 新下载 {downloaded}, 跳过 {missing}, 已选出 {len(result)} 只")

        # 检查是否真的需要logout（避免logout failed）
        if login_ok:
            bs.logout()

        out_df = pd.DataFrame(result)
        # 按PE排序，PE低的在前（如果有数据）
        if not out_df.empty:
            out_df = out_df.sort_values('pe').reset_index(drop=True)
        print(f"[doublelow-screen] 选股完成，共选出 {len(out_df)} 只双低股票")
        return out_df
