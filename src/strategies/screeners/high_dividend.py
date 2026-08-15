"""高股息选股策略（红利策略）
红利策略适合长期投资者，吃分红+股价增值，熊市抗跌
筛选条件：
- 基本面门槛同价值选股
- 股息率 > 阈值（默认3%）
数据来源：
- baostock：基础财务数据
- AkShare：补充股息率数据
"""

import pandas as pd
import time

from ...data.baostock_api import get_kline, get_financial_indicators
from ...data.akshare_api import get_dividend_yield
from ...data.cache import load_cached_kline, save_kline_cache, load_cached_finance, save_finance_cache
from ...data.indicators import calculate_all_indicators
from ...data.processor import check_roe_consistency, check_gross_margin, check_debt_ratio
from ..base import BaseScreener


class HighDividendScreener(BaseScreener):
    """高股息红利选股."""

    name = "high_dividend"
    description = "高股息红利策略：基本面合格 + 股息率 > 3%"

    def __init__(self, max_pe: float = 30.0, min_roe: float = 8.0,
                 min_gross_margin: float = 15.0, max_debt_ratio: float = 70.0,
                 min_dividend_yield: float = 3.0, check_years: int = 3):
        self.max_pe = max_pe
        self.min_roe = min_roe
        self.min_gross_margin = min_gross_margin
        self.max_debt_ratio = max_debt_ratio
        self.min_dividend_yield = min_dividend_yield
        self.check_years = check_years

    def screen(self, universe: pd.DataFrame) -> pd.DataFrame:
        """执行高股息选股."""
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

            # PE筛选
            if pd.isna(row['pe']) or row['pe'] > self.max_pe or row['pe'] <= 0:
                continue

            # 基本面筛选：优先读财务缓存
            fin_df = load_cached_finance(code)
            if fin_df is not None and not fin_df.empty:
                cached_used += 1
            elif login_ok:
                # 缓存不存在，登录成功才能下载
                fin_df = get_financial_indicators(code, self.check_years + 2)
                if fin_df is not None and not fin_df.empty:
                    save_finance_cache(code, fin_df)
                    downloaded += 1
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
            margin_ok = check_gross_margin(fin_df, self.min_gross_margin, self.check_years)
            debt_ok = check_debt_ratio(fin_df, self.max_debt_ratio)

            if not (roe_ok and margin_ok and debt_ok):
                continue

            # 获取最新收盘价（K线也缓存）
            kline = load_cached_kline(code)
            if kline is None and login_ok:
                from src.config.settings import get_settings
                kline = get_kline(code, start_date=get_settings().kline_start_date)
                if kline is not None:
                    kline = calculate_all_indicators(kline)
                    save_kline_cache(code, kline)

            if kline is None or kline.empty:
                continue

            latest_close = kline.iloc[-1]['close']

            # 用AkShare获取股息率
            dy = get_dividend_yield(code)
            if dy is None:
                # 获取失败，跳过
                missing += 1
                continue

            # 股息率门槛检查
            if dy < self.min_dividend_yield:
                continue

            latest = fin_df.iloc[0]
            result.append({
                'code': code,
                'name': row['name'],
                'pe': row['pe'],
                'pb': row['pb'],
                'dividend_yield': dy,
                'latest_roe': latest['roe'],
                'latest_close': round(latest_close, 2),
            })

            # AkShare限流
            time.sleep(0.3)

            if (idx + 1) % 100 == 0:
                print(f"[dividend-screen] 进度 {idx+1}/{total}, 使用缓存 {cached_used}, 新下载 {downloaded}, 跳过 {missing}, 已选出 {len(result)} 只")

        # 检查是否真的需要logout（避免logout failed）
        if login_ok:
            bs.logout()

        out_df = pd.DataFrame(result)
        # 按PE排序（如果有数据）
        if not out_df.empty:
            out_df = out_df.sort_values('pe').reset_index(drop=True)
        print(f"[dividend-screen] 选股完成，共选出 {len(out_df)} 只高股息候选")
        return out_df
