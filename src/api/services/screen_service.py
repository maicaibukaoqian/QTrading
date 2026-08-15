"""选股 service

把 main.py 的 `screen` 和 `_screen_all` 逻辑搬到这里。
关键设计：STRATEGY_REGISTRY 是策略元信息唯一来源，main.py 的硬编码参数全归此处。
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Type, Optional, Dict, Any

import pandas as pd
from pydantic import BaseModel

from src.strategies.base import BaseScreener
from src.strategies.screeners.value import ValueStockScreener
from src.strategies.screeners.double_low import DoubleLowScreener
from src.strategies.screeners.high_dividend import HighDividendScreener
from src.strategies.screeners.xiaoyang_build_position import XiaoyangBuildPositionScreener
from src.strategies.screeners.trend_520 import Trend520Screener
from src.data.baostock_api import get_all_stocks
from src.config.settings import get_settings
from src.api.errors import (
    InvalidStrategyError,
    InvalidRequestError,
    MissingDataError,
    ScreenerError,
)
from src.api.schemas.screen import (
    ValueParams,
    Trend520Params,
    DoubleLowParams,
    HighDividendParams,
    XiaoyangParams,
)
from src.api.tasks.progress import ProgressReporter, tee_stdout


@dataclass
class StrategySpec:
    """策略元信息"""
    key: str                 # URL 路径中的 key: value/520/dividend/doublelow/xiaoyang
    cn_name: str             # 中文名，用于 CSV 和日报展示
    cls: Type[BaseScreener]
    params_model: Type[BaseModel]  # 策略的 Pydantic 参数模型（用于校验入参）
    default_output: str      # 默认输出 CSV 路径
    description: str         # 策略描述


# 策略注册表：key -> StrategySpec
# cn_name 与 main.py/_screen_all 中完全一致（影响 CSV `命中策略` 列、API 响应、日报）
STRATEGY_REGISTRY: Dict[str, StrategySpec] = {
    "value": StrategySpec(
        key="value",
        cn_name="价值",
        cls=ValueStockScreener,
        params_model=ValueParams,
        default_output="value_screen_result.csv",
        description="价值选股 PE<30 + 连续ROE>10% + 毛利率>20% + 负债率<70%",
    ),
    "520": StrategySpec(
        key="520",
        cn_name="520",
        cls=Trend520Screener,
        params_model=Trend520Params,
        default_output="520_buy.csv",
        description="趋势 520：基本面合格 + 5 日线金叉 20 日线买点",
    ),
    "dividend": StrategySpec(
        key="dividend",
        cn_name="高股息",
        cls=HighDividendScreener,
        params_model=HighDividendParams,
        default_output="high_dividend.csv",
        description="高股息策略 PE<30 + ROE>8% + 股息率>3% + 毛利率>15%",
    ),
    "doublelow": StrategySpec(
        key="doublelow",
        cn_name="双低",
        cls=DoubleLowScreener,
        params_model=DoubleLowParams,
        default_output="double_low.csv",
        description="双低选股 PE<20 + PB<2 + ROE>8% + 负债率<70%",
    ),
    "xiaoyang": StrategySpec(
        key="xiaoyang",
        cn_name="小阳",
        cls=XiaoyangBuildPositionScreener,
        params_model=XiaoyangParams,
        default_output="xiaoyang_build.csv",
        description="小阳建仓 低位连续小阳线（主力吸筹）",
    ),
}


# 单策略默认参数（替代 main.py 硬编码）
# 注意：value/520 用 min_roe=10，dividend/doublelow/xiaoyang 用 8
DEFAULT_PARAMS: Dict[str, Dict[str, Any]] = {
    "value":     dict(max_pe=30.0, min_roe=10.0, min_gross_margin=20.0, max_debt_ratio=70.0, check_years=3),
    "520":       dict(max_pe=40.0, min_roe=10.0, min_gross_margin=20.0, max_debt_ratio=70.0, check_years=3),
    "dividend":  dict(max_pe=30.0, min_roe=8.0,  min_gross_margin=15.0, max_debt_ratio=70.0, min_dividend_yield=3.0, check_years=3),
    "doublelow": dict(max_pe=20.0, max_pb=2.0,  min_roe=8.0,            max_debt_ratio=70.0, check_years=3),
    "xiaoyang":  dict(min_days=5,    max_pe=40.0, min_roe=8.0,         check_years=3),
}


def get_strategy(key: str) -> StrategySpec:
    """从注册表取策略，找不到抛 InvalidStrategyError"""
    spec = STRATEGY_REGISTRY.get(key)
    if spec is None:
        raise InvalidStrategyError(
            f"未知策略: {key}",
            detail={"available": list(STRATEGY_REGISTRY.keys())},
        )
    return spec


def output_path_for(spec: StrategySpec) -> str:
    """策略的默认输出路径 = settings.output_dir / spec.default_output"""
    return str(Path(get_settings().output_dir) / spec.default_output)


def normalize_result(df: pd.DataFrame) -> pd.DataFrame:
    """补齐缺失列（520/小阳无 `pb`、空结果无列）→ 统一 pe/pb/latest_roe = None"""
    if df is None:
        return pd.DataFrame(columns=["code", "name", "pe", "pb", "latest_roe"])
    for col in ["pe", "pb", "latest_roe"]:
        if col not in df.columns:
            df[col] = None
    if "code" not in df.columns:
        df["code"] = None
    if "name" not in df.columns:
        df["name"] = ""
    return df


def build_screener(key: str, params: Dict[str, Any]) -> BaseScreener:
    """根据 key + params 构造 screener 实例

    用 STRATEGY_REGISTRY.params_model 做 Pydantic 校验后再构造：
    - 类型/范围错误立即抛 InvalidRequestError（→ 400/422）
    - 未识别字段被丢弃，不传给 screener __init__
    """
    spec = get_strategy(key)
    merged = {**DEFAULT_PARAMS[key], **(params or {})}
    try:
        validated = spec.params_model.model_validate(merged)
    except Exception as e:
        raise InvalidRequestError(
            f"策略 {key} 参数校验失败: {e}",
            detail={"params": merged},
        ) from e
    return spec.cls(**validated.model_dump())


def run_single(
    key: str,
    params: Dict[str, Any],
    output_path: Optional[str],
    reporter: ProgressReporter,
) -> dict:
    """跑单个策略，写 CSV，返回结果摘要"""
    spec = get_strategy(key)
    out = output_path or output_path_for(spec)

    reporter.step(f"读取全市场股票列表 [{key}]")
    universe = get_all_stocks(use_cache=True)
    if universe is None or universe.empty:
        raise MissingDataError(
            "全市场股票列表为空，请先 POST /api/download/universe"
        )
    reporter.log(f"全市场共 {len(universe)} 只股票")

    reporter.step(f"执行策略 [{spec.cn_name}] {spec.description}")
    try:
        screener = build_screener(key, params)
        # 捕获 screener 内部 print 到 task logs
        with tee_stdout(reporter):
            result = screener.screen(universe)
    except InvalidStrategyError:
        raise
    except Exception as e:
        raise ScreenerError(f"策略 {spec.cn_name} 执行失败: {e}", detail={"key": key}) from e

    # 归一化结果 + 落盘
    result = normalize_result(result)
    if result.empty:
        reporter.log(f"策略 {spec.cn_name} 未选出股票")
        return {
            "strategy": key,
            "cn_name": spec.cn_name,
            "count": 0,
            "output_path": None,
            "rows": [],
        }

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    result.to_csv(out, index=False, encoding="utf-8-sig")
    reporter.log(f"选出 {len(result)} 只，结果写入 {out}")

    return {
        "strategy": key,
        "cn_name": spec.cn_name,
        "count": len(result),
        "output_path": out,
        "rows": result.head(100).fillna("").to_dict(orient="records"),
    }


def run_all(
    overrides: Optional[Dict[str, Dict[str, Any]]],
    output_path: Optional[str],
    min_roe: Optional[float],
    reporter: ProgressReporter,
) -> dict:
    """跑所有策略 + 合并 + 共振排序 + 落盘"""
    out = output_path or get_settings().screen_all_csv

    reporter.step("读取全市场股票列表")
    universe = get_all_stocks(use_cache=True)
    if universe is None or universe.empty:
        raise MissingDataError(
            "全市场股票列表为空，请先 POST /api/download/universe"
        )
    reporter.log(f"全市场共 {len(universe)} 只股票")

    # 5 个策略各占 20% 进度
    merged: Dict[str, Dict[str, Any]] = {}
    keys = list(STRATEGY_REGISTRY.keys())
    for idx, key in enumerate(keys):
        sub = reporter.sub(idx * 20, 20)
        sub.step(f"执行策略 [{key}]")
        # 计算每个策略的入参
        params: Dict[str, Any] = dict(DEFAULT_PARAMS[key])
        if min_roe is not None and key in ("value", "520"):
            params["min_roe"] = min_roe
        if overrides and key in overrides:
            params.update(overrides[key])
        try:
            spec = get_strategy(key)
            screener = build_screener(key, params)
            with tee_stdout(sub):
                res = screener.screen(universe)
            res = normalize_result(res)
            if res is None or res.empty:
                sub.log(f"策略 {spec.cn_name} 未选出股票")
                continue
            for _, row in res.iterrows():
                code = str(row.get("code", "")).zfill(6) if row.get("code") else ""
                if not code:
                    continue
                if code not in merged:
                    merged[code] = {
                        "code": code,
                        "name": row.get("name", ""),
                        "pe": row.get("pe"),
                        "pb": row.get("pb"),
                        "latest_roe": row.get("latest_roe"),
                        "strategies": [],
                    }
                merged[code]["strategies"].append(spec.cn_name)
                # 补齐可能缺的字段
                for col in ["pb", "latest_roe"]:
                    if merged[code].get(col) is None and col in row and pd.notna(row[col]):
                        merged[code][col] = row[col]
        except Exception as e:
            sub.log(f"策略 {key} 失败: {e}，跳过")
            continue

    if not merged:
        raise MissingDataError(
            "所有策略都没选出股票（可能缺数据），请先 POST /api/download/fundamentals 和 klines"
        )

    # 转 DataFrame
    rows = []
    for code, info in merged.items():
        rows.append({
            "code": info["code"],
            "name": info["name"],
            "pe": info["pe"],
            "pb": info["pb"],
            "latest_roe": info["latest_roe"],
            "命中策略数": len(info["strategies"]),
            "命中策略": "/".join(info["strategies"]),
        })
    out_df = pd.DataFrame(rows)
    out_df = out_df.sort_values(["命中策略数", "pe"], ascending=[False, True]).reset_index(drop=True)

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    out_df.to_csv(out, index=False, encoding="utf-8-sig")
    reporter.log(f"全策略合并完成，共 {len(out_df)} 只（去重），写入 {out}")

    resonance = out_df[out_df["命中策略数"] >= 2]
    return {
        "count": len(out_df),
        "resonance_count": len(resonance),
        "output_path": out,
        "rows": out_df.head(100).fillna("").to_dict(orient="records"),
    }
