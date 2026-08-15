"""数据下载 service

把 main.py 的 download universe/fundamentals/klines/from-result/all 逻辑搬过来。
统一 baostock 登录/登出，捕获 screener 内部 print 为进度日志。
"""

import os
import time
import random
from dataclasses import dataclass, asdict
from typing import List, Optional

import pandas as pd

from src.config.settings import get_settings
from src.data.cache import (
    save_financial_cache,
    has_financial_cache,
    save_kline_cache,
    has_kline_cache,
)
from src.data.baostock_api import get_all_stocks, get_kline, get_financial_indicators
from src.data.akshare_api import get_kline_ak
from src.data.efinance_api import get_kline_ef
from src.data.indicators import calculate_all_indicators
from src.data.session import baostock_session
from src.api.errors import MissingDataError, DownloadError
from src.api.tasks.progress import ProgressReporter


@dataclass
class DownloadStats:
    total: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    ef_fallback: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def _kline_with_fallback(code: str, start_date: str, max_retry: int = 2) -> tuple[Optional[pd.DataFrame], bool]:
    """三层兜底下载 K 线，返回 (df, ef_used)"""
    kline = None
    ef_used = False
    sleep_min = get_settings().download_sleep_min
    sleep_max = get_settings().download_sleep_max

    # 第一层：baostock
    with baostock_session() as login_ok:
        if login_ok:
            for _ in range(max_retry):
                try:
                    kline = get_kline(code, start_date=start_date)
                except Exception:
                    kline = None
                if kline is not None and not kline.empty:
                    break
                time.sleep(1 + random.random())

    # 第二层：AkShare
    if kline is None or kline.empty:
        for _ in range(max_retry):
            try:
                kline = get_kline_ak(code, start_date=start_date)
            except Exception:
                kline = None
            if kline is not None and not kline.empty:
                break
            time.sleep(2 + random.random() * 2)

    # 第三层：efinance
    if kline is None or kline.empty:
        for _ in range(max_retry):
            try:
                kline = get_kline_ef(code, start_date=start_date)
            except Exception:
                kline = None
            if kline is not None and not kline.empty:
                ef_used = True
                break
            time.sleep(2 + random.random() * 2)

    return kline, ef_used


def download_universe(reporter: ProgressReporter) -> dict:
    """刷新全市场股票列表 + PE/PB（~30s）"""
    reporter.step("下载全市场列表 + PE/PB")
    df = get_all_stocks(use_cache=False)  # 强制刷新
    if df is None or df.empty:
        raise DownloadError("下载全市场列表失败：返回为空")
    reporter.log(f"全市场共 {len(df)} 只股票已缓存")
    return {"total": len(df), "saved_path": get_settings().universe_pe_csv}


def download_fundamentals(
    max_stocks: Optional[int],
    skip_existing: bool,
    reporter: ProgressReporter,
) -> dict:
    """批量下载财务指标（ROE/毛利率/资产负债率），全市场约 1 小时"""
    settings = get_settings()
    sleep_sec = settings.fundamentals_sleep

    reporter.step("读取全市场列表")
    universe = get_all_stocks(use_cache=True)
    if universe is None or universe.empty:
        raise MissingDataError("全市场列表为空，请先 POST /api/download/universe")
    if max_stocks:
        universe = universe.head(max_stocks)
    total = len(universe)
    reporter.log(f"准备下载 {total} 只股票的财务数据")

    stats = DownloadStats(total=total)
    sub = reporter.sub(0, 100)

    with baostock_session() as login_ok:
        for idx, (_, row) in enumerate(universe.iterrows()):
            sub.check_cancel()
            code = str(row["code"]).zfill(6)

            if skip_existing and has_financial_cache(code):
                stats.skipped += 1
                sub.advance(idx + 1, total, "财务")
                continue

            if not login_ok:
                # 没登录就跳过下载（不能补缓存）
                stats.failed += 1
                sub.advance(idx + 1, total, "财务")
                continue

            try:
                fin_df = get_financial_indicators(code, years=5)
                if fin_df is not None and not fin_df.empty:
                    save_financial_cache(code, fin_df)
                    stats.downloaded += 1
                else:
                    stats.failed += 1
            except Exception as e:
                reporter.log(f"{code} {row.get('name', '')} 财务下载失败: {e}")
                stats.failed += 1

            time.sleep(sleep_sec)
            sub.advance(idx + 1, total, "财务")

    reporter.log(
        f"财务下载完成: 成功 {stats.downloaded}, 跳过 {stats.skipped}, 失败 {stats.failed}"
    )
    return stats.as_dict()


def download_klines(
    codes: Optional[List[str]],
    max_stocks: Optional[int],
    start_date: Optional[str],
    reporter: ProgressReporter,
) -> dict:
    """批量下载 K 线（数小时）"""
    settings = get_settings()
    start = start_date or settings.kline_start_date

    if codes:
        code_list = [c.strip().zfill(6) for c in codes if c.strip()]
    else:
        reporter.step("读取全市场列表")
        universe = get_all_stocks(use_cache=True)
        if universe is None or universe.empty:
            raise MissingDataError("全市场列表为空，请先 POST /api/download/universe")
        if max_stocks:
            universe = universe.head(max_stocks)
        code_list = universe["code"].astype(str).str.zfill(6).tolist()

    total = len(code_list)
    reporter.log(f"准备下载 {total} 只股票的 K 线（起始 {start}）")
    stats = DownloadStats(total=total)
    sub = reporter.sub(0, 100)

    for idx, code in enumerate(code_list):
        sub.check_cancel()
        if has_kline_cache(code):
            stats.skipped += 1
            sub.advance(idx + 1, total, "K线")
            continue
        try:
            kline, ef_used = _kline_with_fallback(code, start)
            if kline is not None and not kline.empty:
                kline = calculate_all_indicators(kline)
                save_kline_cache(code, kline)
                stats.downloaded += 1
                if ef_used:
                    stats.ef_fallback += 1
            else:
                stats.failed += 1
        except Exception as e:
            reporter.log(f"{code} K线下载失败: {e}")
            stats.failed += 1

        time.sleep(settings.download_sleep_min + random.random() * (settings.download_sleep_max - settings.download_sleep_min))
        sub.advance(idx + 1, total, "K线")

    reporter.log(
        f"K线下载完成: 成功 {stats.downloaded}, 跳过 {stats.skipped}, efinance兜底 {stats.ef_fallback}, 失败 {stats.failed}"
    )
    return stats.as_dict()


def download_from_result(
    csv_path: Optional[str],
    codes: Optional[List[str]],
    reporter: ProgressReporter,
) -> dict:
    """从选股结果 CSV 读 code 列，只下这些股的 K 线"""
    settings = get_settings()
    start = settings.kline_start_date

    if csv_path:
        if not os.path.exists(csv_path):
            raise MissingDataError(
                f"结果文件不存在: {csv_path}",
                detail={"hint": "请先 POST /api/screen/all 生成结果"},
            )
        df = pd.read_csv(csv_path, dtype={"code": str})
        if "code" not in df.columns or df.empty:
            raise MissingDataError(
                f"CSV 中没有找到 code 列或为空: {csv_path}",
            )
        code_list = df["code"].astype(str).str.zfill(6).tolist()
    elif codes:
        code_list = [c.strip().zfill(6) for c in codes if c.strip()]
    else:
        raise MissingDataError("download_from_result 必须提供 csv_path 或 codes")

    total = len(code_list)
    reporter.log(f"从结果读取到 {total} 只股票，开始下载 K 线（起始 {start}）")
    stats = DownloadStats(total=total)
    sub = reporter.sub(0, 100)

    for idx, code in enumerate(code_list):
        sub.check_cancel()
        if has_kline_cache(code):
            stats.skipped += 1
            sub.advance(idx + 1, total, "K线")
            continue
        try:
            kline, ef_used = _kline_with_fallback(code, start, max_retry=2)
            if kline is not None and not kline.empty:
                kline = calculate_all_indicators(kline)
                save_kline_cache(code, kline)
                stats.downloaded += 1
                if ef_used:
                    stats.ef_fallback += 1
            else:
                stats.failed += 1
        except Exception as e:
            reporter.log(f"{code} K线下载失败: {e}")
            stats.failed += 1

        # 大间隔 1-3s（from-result 路径下数据量小，可以慢一点）
        time.sleep(1 + random.random() * 2)
        sub.advance(idx + 1, total, "K线")

    reporter.log(
        f"K线下载完成: 成功 {stats.downloaded}, 跳过 {stats.skipped}, efinance兜底 {stats.ef_fallback}, 失败 {stats.failed}"
    )
    return stats.as_dict()


def download_all(reporter: ProgressReporter) -> dict:
    """一键下载：universe → fundamentals → klines"""
    reporter.step("Step 1/3 全市场列表")
    universe_stats = download_universe(reporter.sub(0, 5))

    reporter.step("Step 2/3 财务数据")
    fin_stats = download_fundamentals(None, True, reporter.sub(5, 45))

    reporter.step("Step 3/3 K线")
    kline_stats = download_klines(None, None, None, reporter.sub(50, 50))

    return {
        "universe": universe_stats,
        "fundamentals": fin_stats,
        "klines": kline_stats,
    }
