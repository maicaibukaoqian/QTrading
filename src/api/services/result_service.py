"""选股结果读取 service

提供分页、过滤、读现有 CSV 的能力。
"""

import os
from typing import Optional, List

import pandas as pd

from src.config.settings import get_settings
from src.api.errors import ResultNotFoundError


def read_csv_page(
    file_name: str,
    page: int = 1,
    size: int = 20,
    min_hits: Optional[int] = None,
    max_pe: Optional[float] = None,
    strategy: Optional[str] = None,
) -> dict:
    """分页读选股结果 CSV

    Args:
        file_name: 'screen_all' / 'value' / '520' / 'dividend' / 'doublelow' / 'xiaoyang'
        page: 1-based
        size: 每页条数
        min_hits: 最小命中策略数（仅对 screen_all 有效）
        max_pe: 最大 PE 过滤
        strategy: 命中策略包含某关键字（仅 screen_all 有效）
    """
    settings = get_settings()
    # 文件名 → 路径
    if file_name == "screen_all":
        path = settings.screen_all_csv
    elif file_name in ("value", "520", "dividend", "doublelow", "xiaoyang"):
        # 与 screen_service.py 的 default_output 对应
        from src.api.services.screen_service import STRATEGY_REGISTRY, output_path_for
        path = output_path_for(STRATEGY_REGISTRY[file_name])
    else:
        raise ResultNotFoundError(
            f"未知结果文件: {file_name}",
            detail={"available": ["screen_all", "value", "520", "dividend", "doublelow", "xiaoyang"]},
        )

    if not os.path.exists(path):
        raise ResultNotFoundError(
            f"结果文件不存在: {path}",
            detail={"hint": "请先 POST /api/screen/all 或 /api/screen/{strategy}"},
        )

    try:
        df = pd.read_csv(path, dtype={"code": str})
    except pd.errors.EmptyDataError:
        # 空 CSV（只剩 BOM 或 header 缺失）— 当作"未选出股票"
        return {
            "file": file_name,
            "path": path,
            "total_before_filter": 0,
            "total": 0,
            "page": page,
            "size": size,
            "rows": [],
        }
    total_before = len(df)

    # 过滤
    if min_hits is not None and "命中策略数" in df.columns:
        df = df[df["命中策略数"] >= min_hits]
    if max_pe is not None and "pe" in df.columns:
        df = df[df["pe"].notna() & (df["pe"] <= max_pe)]
    if strategy and "命中策略" in df.columns:
        df = df[df["命中策略"].str.contains(strategy, na=False)]

    total = len(df)
    # 分页
    page = max(1, page)
    size = max(1, min(200, size))
    start_idx = (page - 1) * size
    end_idx = start_idx + size
    page_df = df.iloc[start_idx:end_idx]

    return {
        "file": file_name,
        "path": path,
        "total_before_filter": total_before,
        "total": total,
        "page": page,
        "size": size,
        "rows": _serialize_rows(page_df),
    }


def _serialize_rows(df: pd.DataFrame) -> List[dict]:
    """把 DataFrame 行转字典，中文列名 → 英文 alias"""
    rows = []
    for _, row in df.iterrows():
        d = {}
        for col, val in row.items():
            if pd.isna(val):
                d[col] = None
            elif col in ("命中策略数",):
                try:
                    d["hit_count"] = int(val)
                except (TypeError, ValueError):
                    d["hit_count"] = val
            elif col == "命中策略":
                d["hit_strategies"] = str(val)
            else:
                d[col] = val
        rows.append(d)
    return rows
