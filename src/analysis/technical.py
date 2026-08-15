"""技术面分析
趋势判断、均线、MACD、RSI、支撑压力、位置判断
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

from ..data.baostock_api import get_kline
from ..data.akshare_api import get_kline_ak
from ..data.efinance_api import get_kline_ef
from ..data.cache import load_cached_kline, save_kline_cache
from ..data.indicators import (
    calculate_all_indicators, is_golden_cross, is_death_cross,
    is_bullish_trend, is_bearish_trend, ma
)
from ..data.processor import calc_price_position


class TechnicalAnalysis:
    """技术面分析器."""

    def __init__(self, symbol: str, start_date: str = '2018-01-01'):
        self.symbol = symbol
        self.start_date = start_date
        self.kline_df: Optional[pd.DataFrame] = None

    def load_data(self, use_cache: bool = True) -> pd.DataFrame | None:
        """加载K线数据：优先读缓存，再增量更新到最新交易日.
        三层兜底：baostock → AkShare → Tushare
        """
        cached = load_cached_kline(self.symbol) if use_cache else None

        if cached is not None and not cached.empty:
            self.kline_df = self._update_to_latest(cached)
            if 'ma5' not in self.kline_df.columns:
                self.kline_df = calculate_all_indicators(self.kline_df)
            return self.kline_df

        # 没缓存，全量下载：三层兜底
        import baostock as bs
        lg = bs.login()
        login_ok = (lg.error_code == '0')
        self.kline_df = None

        # 第一层：baostock
        if login_ok:
            self.kline_df = get_kline(self.symbol, start_date=self.start_date)
            bs.logout()

        # 第二层：AkShare
        if self.kline_df is None:
            print(f"[technical] baostock不可用，改用AkShare下载K线: {self.symbol}")
            self.kline_df = get_kline_ak(self.symbol, start_date=self.start_date)

        # 第三层：efinance
        if self.kline_df is None:
            print(f"[technical] AkShare也不行，改用efinance下载K线: {self.symbol}")
            self.kline_df = get_kline_ef(self.symbol, start_date=self.start_date)

        if self.kline_df is not None:
            self.kline_df = calculate_all_indicators(self.kline_df)
            if use_cache:
                save_kline_cache(self.symbol, self.kline_df)
        else:
            print(f"[technical] baostock/AkShare/efinance都无法获取K线: {self.symbol}")

        return self.kline_df

    def _update_to_latest(self, cached: pd.DataFrame) -> pd.DataFrame:
        """增量更新：从缓存最后日期补到今天，失败则用缓存原样返回.
        三层兜底：baostock → AkShare → Tushare
        """
        cached = cached.copy()
        cached['date'] = pd.to_datetime(cached['date'])
        last_date = cached['date'].max()
        today = pd.Timestamp(datetime.now().date())

        # 缓存已到今天，无需更新
        if last_date >= today:
            return cached

        # 从最后日期当天开始补（当天可能是盘中数据，重下覆盖）
        start = last_date.strftime('%Y-%m-%d')
        import baostock as bs
        lg = bs.login()
        login_ok = (lg.error_code == '0')
        new_df = None

        # 第一层：baostock
        if login_ok:
            new_df = get_kline(self.symbol, start_date=start)
            bs.logout()

        # 第二层：AkShare
        if new_df is None or new_df.empty:
            # baostock被封，用AkShare补最新几天
            new_df = get_kline_ak(self.symbol, start_date=start)

        # 第三层：efinance
        if new_df is None or new_df.empty:
            new_df = get_kline_ef(self.symbol, start_date=start)
            if new_df is None:
                print(f"[technical] baostock/AkShare/efinance都不可用，用缓存K线（到 {last_date.date()}）: {self.symbol}")
                return cached

        if new_df is None or new_df.empty:
            return cached

        new_df['date'] = pd.to_datetime(new_df['date'])
        # 合并去重，新数据覆盖旧的
        merged = pd.concat([cached, new_df], ignore_index=True)
        merged = merged.drop_duplicates(subset='date', keep='last')
        merged = merged.sort_values('date').reset_index(drop=True)

        # 重算指标（均线等依赖完整序列）
        merged = calculate_all_indicators(merged)
        save_kline_cache(self.symbol, merged)

        added = len(merged) - len(cached)
        if added > 0:
            print(f"[technical] {self.symbol} K线增量更新 +{added} 根，最新到 {merged['date'].max().date()}")
        return merged


    def analyze(self) -> Dict[str, Any]:
        """执行技术面分析，返回结果字典."""
        if self.kline_df is None:
            self.load_data()

        if self.kline_df is None or self.kline_df.empty:
            return {
                'valid': False,
                'reason': '无法获取K线数据',
            }

        last = self.kline_df.iloc[-1]
        prev = self.kline_df.iloc[-2] if len(self.kline_df) >= 2 else last

        # 趋势判断
        bullish = is_bullish_trend(self.kline_df)
        bearish = is_bearish_trend(self.kline_df)

        # 金叉死叉
        golden_5_20 = is_golden_cross(self.kline_df, 5, 20)
        death_5_20 = is_death_cross(self.kline_df, 5, 20)

        # 价格位置（近一年）
        price_pos = calc_price_position(self.kline_df, 250)

        # MACD状态
        macd_green = last['macd'] < 0
        macd_red = last['macd'] > 0
        macd_cross_up = prev['dif'] < prev['dea'] and last['dif'] > last['dea']
        macd_cross_down = prev['dif'] > prev['dea'] and last['dif'] < last['dea']

        # RSI状态
        rsi14 = last['rsi14'] if 'rsi14' in last else np.nan
        rsi_overbought = rsi14 > 70 if not np.isnan(rsi14) else False
        rsi_oversold = rsi14 < 30 if not np.isnan(rsi14) else False

        # 价格相对于均线
        above_ma5 = last['close'] > last['ma5']
        above_ma20 = last['close'] > last['ma20']
        above_ma250 = last['close'] > last['ma250']

        return {
            'valid': True,
            # 趋势
            'bullish_trend': bullish,
            'bearish_trend': bearish,
            # 金叉死叉
            'golden_cross_5_20': golden_5_20,
            'death_cross_5_20': death_5_20,
            # 位置
            'price_position_1y': round(price_pos, 2),
            'price_position_desc': self._get_position_desc(price_pos),
            # MACD
            'macd_above_zero': macd_red,
            'macd_cross_up': macd_cross_up,
            'macd_cross_down': macd_cross_down,
            # RSI
            'rsi14': round(rsi14, 2) if not np.isnan(rsi14) else None,
            'rsi_overbought': rsi_overbought,
            'rsi_oversold': rsi_oversold,
            # 价格均线关系
            'above_ma5': above_ma5,
            'above_ma20': above_ma20,
            'above_ma250': above_ma250,
            # 最新价格
            'latest_close': round(last['close'], 2),
            'latest_pettm': round(last['pettm'], 2) if 'pettm' in last else None,
        }

    def _get_position_desc(self, pos: float) -> str:
        """价格位置描述."""
        if pos < 0.2:
            return "低位（近20%区间）"
        elif pos < 0.4:
            return "中低位"
        elif pos < 0.6:
            return "中位"
        elif pos < 0.8:
            return "中高位"
        else:
            return "高位（近80%区间以上）"

    def get_report_text(self) -> str:
        """生成技术面分析文本报告."""
        result = self.analyze()

        if not result['valid']:
            return f"## 技术面分析\n\n❌ **失败**：{result['reason']}\n"

        lines = ['## 技术面分析\n']

        # 趋势
        if result['bullish_trend']:
            lines.append("✅ **多头趋势**：短中长期均线多头排列，价格在所有均线上方\n")
        elif result['bearish_trend']:
            lines.append("❌ **空头趋势**：短中长期均线空头排列，价格在所有均线下方\n")
        else:
            lines.append("⚠️ **震荡趋势**：均线没有明确多头发散\n")

        # 金叉死叉
        if result['golden_cross_5_20']:
            lines.append("🟢 **5日线金叉20日线** —— 多头信号\n")
        elif result['death_cross_5_20']:
            lines.append("🔴 **5日线死叉20日线** —— 空头信号\n")

        # 价格位置
        lines.append(f"- 当前价格位置（近一年）：**{result['price_position_desc']}** ({int(result['price_position_1y'] * 100)}%)\n")

        # RSI
        if result['rsi14'] is not None:
            rsi_text = f"RSI(14): **{result['rsi14']}**"
            if result['rsi_overbought']:
                rsi_text += " —— 超买区域，注意回调风险"
            elif result['rsi_oversold']:
                rsi_text += " —— 超卖区域，可能反弹"
            lines.append(f"- {rsi_text}\n")

        # MACD
        macd_text = "MACD: "
        if result['macd_cross_up']:
            macd_text += "DIF上穿DEA，金叉，偏多"
        elif result['macd_cross_down']:
            macd_text += "DIF下穿DEA，死叉，偏空"
        else:
            if result['macd_above_zero']:
                macd_text += "在零轴上方，多头市场"
            else:
                macd_text += "在零轴下方，空头市场"
        lines.append(f"- {macd_text}\n")

        # 均线位置
        ma_status = []
        if result['above_ma5']:
            ma_status.append("站上MA5")
        if result['above_ma20']:
            ma_status.append("站上MA20")
        if result['above_ma250']:
            ma_status.append("站上年线MA250")
        lines.append(f"- 均线状态：{', '.join(ma_status) if ma_status else '在所有均线下方'}\n")

        # 当前价格PE
        if result['latest_pettm'] is not None:
            lines.append(f"- 最新收盘价：**{result['latest_close']}**，动态PE：**{result['latest_pettm']}**\n")
        else:
            lines.append(f"- 最新收盘价：**{result['latest_close']}**\n")

        return '\n'.join(lines)
