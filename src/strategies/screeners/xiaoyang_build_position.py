"""小阳建仓选股策略
低位连续小阳线，主力慢慢吸筹，吸够了就拉升
特征：
- 股价在低位
- 连续多根小阳线（涨幅1%-3%），偶尔夹小阴线
- 成交量温和放大，不放巨量
- 沿5日线慢慢爬升
"""

import pandas as pd
import numpy as np

from ...data.baostock_api import get_kline, get_financial_indicators
from ...data.cache import load_cached_kline, save_kline_cache, load_cached_finance, save_finance_cache
from ...data.indicators import calculate_all_indicators
from ...data.processor import check_roe_consistency, check_gross_margin, check_debt_ratio
from ..base import BaseScreener


class XiaoyangBuildPositionScreener(BaseScreener):
    """小阳建仓选股：低位连续小阳线 + 基本面合格."""

    name = "xiaoyang"
    description = "小阳建仓：低位连续小阳线，主力吸筹"

    def __init__(self, min_days: int = 5, max_days: int = 20,
                 max_pct_per_day: float = 3.0, min_pct_per_day: float = 0.5,
                 max_pe: float = 40.0, min_roe: float = 8.0,
                 min_gross_margin: float = 15.0, max_debt_ratio: float = 70.0,
                 check_years: int = 3):
        self.min_days = min_days        # 最少连续小阳天数
        self.max_days = max_days        # 最多
        self.max_pct_per_day = max_pct_per_day  # 单日最大涨幅，超过不算小阳
        self.min_pct_per_day = min_pct_per_day  # 单日最小涨幅，低于不算
        self.max_pe = max_pe
        self.min_roe = min_roe
        self.min_gross_margin = min_gross_margin
        self.max_debt_ratio = max_debt_ratio
        self.check_years = check_years

    def is_xiaoyang_period(self, df: pd.DataFrame, lookback: int = 20) -> bool:
        """判断最近N天是不是小阳建仓形态."""
        if len(df) < lookback:
            return False

        recent = df.tail(lookback)
        # 计算每日涨跌幅
        recent = recent.copy()
        recent['pct'] = recent['close'].pct_change() * 100

        # 统计小阳天数：涨幅在 min ~ max 之间，阳线
        yang_count = 0
        for _, row in recent.iloc[1:].iterrows():
            if row['pct'] >= self.min_pct_per_day and row['pct'] <= self.max_pct_per_day:
                yang_count += 1

        # 要求至少 min_days 根小阳
        if yang_count < self.min_days:
            return False

        # 要求整体涨幅不大，慢慢涨
        total_pct = (recent.iloc[-1]['close'] / recent.iloc[0]['close'] - 1) * 100
        if total_pct > self.max_pct_per_day * self.max_days * 0.8:
            return False  # 涨太快不是吸筹

        # 价格位置：要求在低位（近一年50%以下位置）
        high_1y = df.tail(250)['close'].max()
        current = recent.iloc[-1]['close']
        if current / high_1y > 0.6:
            return False  # 位置太高不是低位

        # 成交量温和：近期成交量比之前高一点，但不放巨量
        vol_earlier = df.tail(lookback*2).head(lookback)['volume'].mean()
        vol_recent = recent['volume'].mean()
        vol_ratio = vol_recent / vol_earlier if vol_earlier > 0 else 1
        if vol_ratio > 3:
            return False  # 放巨量不是吸筹，大概率出货

        if vol_ratio < 1:
            # 缩量横盘也可能，不一定错，先放过
            pass

        # 沿5日线爬升
        if 'ma5' not in df.columns:
            df = calculate_all_indicators(df)

        above_ma5 = (recent['close'] > recent['ma5']).sum()
        if above_ma5 < len(recent) * 0.7:
            return False  # 大部分时间在5日线上方才对

        return True

    def screen(self, universe: pd.DataFrame) -> pd.DataFrame:
        """执行小阳建仓选股."""
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
            margin_ok = check_gross_margin(fin_df, self.min_gross_margin, self.check_years)
            debt_ok = check_debt_ratio(fin_df, self.max_debt_ratio)

            if not (roe_ok and margin_ok and debt_ok):
                continue

            # 获取K线检查形态（K线也缓存）
            kline = load_cached_kline(code)
            if kline is None and login_ok:
                from src.config.settings import get_settings
                kline = get_kline(code, start_date=get_settings().kline_start_date)
                if kline is not None:
                    kline = calculate_all_indicators(kline)
                    save_kline_cache(code, kline)

            if kline is None or len(kline) < 60:
                continue

            if self.is_xiaoyang_period(kline, 20):
                latest = fin_df.iloc[0]
                latest_close = kline.iloc[-1]['close']
                result.append({
                    'code': code,
                    'name': row['name'],
                    'pe': row['pe'],
                    'latest_roe': latest['roe'],
                    'latest_close': round(latest_close, 2),
                })

            if (idx + 1) % 100 == 0:
                print(f"[xiaoyang-screen] 进度 {idx+1}/{total}, 使用缓存 {cached_used}, 新下载 {downloaded}, 跳过 {missing}, 已选出 {len(result)} 只")

        # 检查是否真的需要logout（避免logout failed）
        if login_ok:
            bs.logout()

        out_df = pd.DataFrame(result)
        # 按PE排序（如果有数据）
        if not out_df.empty:
            out_df = out_df.sort_values('pe').reset_index(drop=True)
        print(f"[xiaoyang-screen] 选股完成，共选出 {len(out_df)} 只小阳建仓形态")
        return out_df
