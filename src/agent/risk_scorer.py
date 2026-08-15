"""7 维风险评分模块

为每只股票输出 1-5 星综合风险等级，附每维评分 + 触发原因。
所有维度独立打分，**1=安全 / 5=高风险**。
数据缺字段时按"未知"处理（标 3 + 备注），不抛异常。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

import pandas as pd

from src.data import cache as data_cache
from src.data import akshare_api as ak_api

logger = logging.getLogger(__name__)


# ====== 评分数据结构 ======

@dataclass
class DimensionResult:
    """单个维度的评分结果"""
    score: int                       # 1-5，1=安全 5=高风险
    reason: str                      # 触发原因（人话）
    evidence: dict = field(default_factory=dict)  # 原始数据（前端可展开）


@dataclass
class RiskReport:
    """7 维评分综合结果"""
    code: str
    name: Optional[str]
    industry: Optional[str]
    score: float                     # 加权综合分（保留 2 位小数）
    stars: int                       # 1-5 星（score 四舍五入到整星）
    level: str                       # "低风险" / "中低" / "中" / "中高" / "高风险"
    dimensions: dict                 # key → DimensionResult
    warnings: list                   # 触发警告的人话短句（score>=4 才进）
    raw: dict = field(default_factory=dict)  # 关键原始指标（前端 tooltip）

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ====== 权重（必须总和 = 1.0） ======

WEIGHTS = {
    "valuation": 0.18,    # 估值异常
    "leverage": 0.14,     # 负债
    "profitability": 0.14,  # 盈利下滑
    "st_status": 0.20,    # 特别处理（权重最高——一旦 ST 直接不碰）
    "size": 0.10,         # 规模
    "policy": 0.12,       # 政策风险
    "liquidity": 0.12,    # 流动性
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-6, "WEIGHTS 总和必须为 1.0"


# ====== 政策高风险行业（关键词匹配 CSRC 行业 + 申万 lv1/lv2） ======

# 房地产 / 教育 / 互联网平台 / 教培
POLICY_HIGH_RISK_KEYWORDS = (
    "房地产",          # 证监会 K70 + 申万 lv1
    "教育",            # 中公教育类
    "互联网",          # 平台经济
    "K70",             # 证监会行业代码
    "P82", "P83", "P84",  # 教育大类
    "I63", "I64", "I65",  # 软件/信息技术（互联网平台常落这里）
    "L72",             # 商业经纪
    "互联网平台",
    "网络游戏",        # 版号风险
)


# ====== 数据聚合辅助 ======

def _load_universe_row(code: str) -> Optional[dict]:
    """从 universe 缓存读 name / industry / pe / pb

    直接读 CSV（不走 bs_api.get_all_stocks，避开 baostock 登录 / 增量更新卡顿）。
    """
    import os
    from src.config.settings import get_settings
    try:
        path = str(get_settings().universe_pe_csv)
        if not os.path.exists(path):
            return None
        df = pd.read_csv(path, dtype={"code": str}, encoding="utf-8")
        if df is None or df.empty:
            return None
        rows = df[df["code"].astype(str).str.zfill(6) == code.zfill(6)]
        if rows.empty:
            return None
        row = rows.iloc[0]
        out = {}
        for k in ("name", "pe", "pb", "industry"):
            if k in df.columns and pd.notna(row.get(k)):
                v = row[k]
                if k in ("pe", "pb"):
                    try:
                        out[k] = float(v)
                    except (TypeError, ValueError):
                        out[k] = None
                else:
                    out[k] = str(v).strip() or None
        return out
    except Exception as e:
        logger.debug(f"_load_universe_row({code}) 失败: {e}")
        return None


def _load_kline(code: str) -> Optional[pd.DataFrame]:
    """读 K 线缓存"""
    try:
        return data_cache.load_cached_kline(code)
    except Exception as e:
        logger.debug(f"_load_kline({code}) 失败: {e}")
        return None


def _load_finance(code: str) -> Optional[pd.DataFrame]:
    """读财务缓存"""
    try:
        return data_cache.load_cached_finance(code)
    except Exception as e:
        logger.debug(f"_load_finance({code}) 失败: {e}")
        return None


def _get_market_cap(code: str) -> Optional[float]:
    """流通市值（亿元）—— 调用 akshare。带超时保护（akshare 在线时被封/慢）。"""
    import threading
    holder: dict = {}

    def _call():
        try:
            holder["v"] = ak_api.get_latest_market_cap(code)
        except Exception as e:
            holder["e"] = e

    th = threading.Thread(target=_call, daemon=True)
    th.start()
    th.join(timeout=3.0)  # 3 秒拿不到就放弃
    if th.is_alive():
        logger.debug(f"_get_market_cap({code}) 超时 3s 跳过")
        return None
    if "e" in holder:
        logger.debug(f"_get_market_cap({code}) 失败: {holder['e']}")
        return None
    return holder.get("v")


def _avg_turnover(code: str, days: int = 5) -> Optional[float]:
    """近 N 日日均成交额（元）= close × volume 的平均"""
    df = _load_kline(code)
    if df is None or df.empty:
        return None
    try:
        if "close" not in df.columns or "volume" not in df.columns:
            return None
        recent = df.tail(days)
        amounts = recent["close"] * recent["volume"]
        if amounts.empty:
            return None
        return float(amounts.mean())
    except Exception as e:
        logger.debug(f"_avg_turnover({code}) 失败: {e}")
        return None


# ====== 7 维评分函数 ======

def score_valuation(ctx: dict) -> DimensionResult:
    """维度 1：估值异常"""
    pe = ctx.get("pe")
    if pe is None or (isinstance(pe, float) and pd.isna(pe)):
        return DimensionResult(3, "PE 缺失，按未知处理", {"pe": None})
    if pe < 0:
        return DimensionResult(5, f"PE {pe:.1f} 为负，业绩亏损", {"pe": pe})
    if pe > 100:
        return DimensionResult(4, f"PE {pe:.1f} 过高，估值偏贵", {"pe": pe})
    if pe > 60:
        return DimensionResult(3, f"PE {pe:.1f} 偏高", {"pe": pe})
    if pe > 30:
        return DimensionResult(2, f"PE {pe:.1f} 略偏高", {"pe": pe})
    return DimensionResult(1, f"PE {pe:.1f}，估值合理", {"pe": pe})


def score_leverage(ctx: dict) -> DimensionResult:
    """维度 2：负债"""
    debt = ctx.get("debt_ratio")
    if debt is None:
        return DimensionResult(3, "负债率缺失", {"debt_ratio": None})
    pct = debt * 100 if debt <= 1 else debt  # 兼容 0-1 与百分比
    if pct > 85:
        return DimensionResult(5, f"负债率 {pct:.1f}%，偿债压力大", {"debt_ratio": pct})
    if pct > 70:
        return DimensionResult(4, f"负债率 {pct:.1f}%，高于安全线", {"debt_ratio": pct})
    if pct > 60:
        return DimensionResult(3, f"负债率 {pct:.1f}%，偏高", {"debt_ratio": pct})
    if pct > 40:
        return DimensionResult(2, f"负债率 {pct:.1f}%，适中", {"debt_ratio": pct})
    return DimensionResult(1, f"负债率 {pct:.1f}%，低杠杆", {"debt_ratio": pct})


def score_profitability(ctx: dict) -> DimensionResult:
    """维度 3：盈利下滑（基于最近 2 期 ROE）"""
    roe_history = ctx.get("roe_history")  # list[float]，从旧到新
    if not roe_history or len(roe_history) < 2:
        return DimensionResult(3, "ROE 历史不足 2 期", {"roe_history": roe_history or []})
    a, b = roe_history[-2], roe_history[-1]
    delta = b - a
    if delta <= -5:
        return DimensionResult(4, f"ROE 两期连降 {abs(delta):.1f}pct", {"roe_history": roe_history, "delta": delta})
    if delta <= -3:
        return DimensionResult(3, f"ROE 下降 {abs(delta):.1f}pct", {"roe_history": roe_history, "delta": delta})
    if delta < 0:
        return DimensionResult(2, f"ROE 小降 {abs(delta):.1f}pct", {"roe_history": roe_history, "delta": delta})
    if b > 15:
        return DimensionResult(1, f"ROE {b:.1f}% 上升，盈利强", {"roe_history": roe_history, "delta": delta})
    return DimensionResult(1, f"ROE 稳定在 {b:.1f}%", {"roe_history": roe_history, "delta": delta})


def score_st_status(ctx: dict) -> DimensionResult:
    """维度 4：特别处理"""
    name = (ctx.get("name") or "").strip()
    if "退市" in name or "终止" in name:
        return DimensionResult(5, f"已退市：{name}", {"name": name})
    if "*ST" in name or name.startswith("ST"):
        return DimensionResult(5, f"特别处理 {name}", {"name": name})
    if "停牌" in name:
        return DimensionResult(4, f"停牌中：{name}", {"name": name})
    if not name:
        # name 缺失时默认按正常处理——universe 缓存可能没 name 字段（重建后才会补）
        return DimensionResult(1, "未识别（暂无 ST 标记，按正常交易）", {"name": None})
    return DimensionResult(1, "正常交易", {"name": name})


def score_size(ctx: dict) -> DimensionResult:
    """维度 5：规模（流通市值，亿元）"""
    cap = ctx.get("market_cap_yi")
    if cap is None:
        return DimensionResult(3, "市值数据缺失", {"market_cap_yi": None})
    if cap < 5:
        return DimensionResult(5, f"流通市值 {cap:.1f} 亿，极小盘", {"market_cap_yi": cap})
    if cap < 10:
        return DimensionResult(4, f"流通市值 {cap:.1f} 亿，小盘", {"market_cap_yi": cap})
    if cap < 30:
        return DimensionResult(3, f"流通市值 {cap:.1f} 亿，中小盘", {"market_cap_yi": cap})
    if cap < 100:
        return DimensionResult(2, f"流通市值 {cap:.1f} 亿，中盘", {"market_cap_yi": cap})
    return DimensionResult(1, f"流通市值 {cap:.1f} 亿，大盘", {"market_cap_yi": cap})


def score_policy(ctx: dict) -> DimensionResult:
    """维度 6：政策"""
    industry = (ctx.get("industry") or "").strip()
    if not industry:
        return DimensionResult(2, "行业缺失", {"industry": None})
    hits = [kw for kw in POLICY_HIGH_RISK_KEYWORDS if kw in industry]
    if not hits:
        return DimensionResult(1, f"行业 {industry}，政策风险低", {"industry": industry, "matched": []})
    if any(k in industry for k in ("房地产", "教育", "K70", "P82", "P83")):
        return DimensionResult(4, f"行业 {industry} 命中高风险政策（{','.join(hits)}）", {"industry": industry, "matched": hits})
    return DimensionResult(3, f"行业 {industry} 部分命中政策关键词（{','.join(hits)}）", {"industry": industry, "matched": hits})


def score_liquidity(ctx: dict) -> DimensionResult:
    """维度 7：流动性（5 日均成交额，元）"""
    avg = ctx.get("avg_turnover_5d")
    if avg is None:
        return DimensionResult(3, "成交额数据缺失", {"avg_turnover_5d": None})
    yi = avg / 1e8
    if avg < 1e6:
        return DimensionResult(5, f"日均成交 {yi:.3f} 亿，几乎无成交", {"avg_turnover_5d": avg})
    if avg < 5e6:
        return DimensionResult(4, f"日均成交 {yi:.2f} 亿，流动性差", {"avg_turnover_5d": avg})
    if avg < 2e7:
        return DimensionResult(3, f"日均成交 {yi:.2f} 亿，流动性一般", {"avg_turnover_5d": avg})
    if avg < 1e8:
        return DimensionResult(2, f"日均成交 {yi:.2f} 亿，流动性较好", {"avg_turnover_5d": avg})
    return DimensionResult(1, f"日均成交 {yi:.2f} 亿，流动性好", {"avg_turnover_5d": avg})


# ====== 综合评分 ======

DIMENSION_FUNCS = {
    "valuation": score_valuation,
    "leverage": score_leverage,
    "profitability": score_profitability,
    "st_status": score_st_status,
    "size": score_size,
    "policy": score_policy,
    "liquidity": score_liquidity,
}


def _to_stars(score: float) -> int:
    """综合分 → 星级。**注意：星级语义是"安全等级"，与 score 相反**。
    score 1.0-1.5 → 5 星安全
    score 1.5-2.5 → 4 星
    score 2.5-3.5 → 3 星
    score 3.5-4.5 → 2 星
    score 4.5-5.0 → 1 星
    """
    s = max(1.0, min(5.0, score))
    if s <= 1.5:
        return 5
    if s <= 2.5:
        return 4
    if s <= 3.5:
        return 3
    if s <= 4.5:
        return 2
    return 1


_LEVEL_BY_STARS = {
    5: "低风险",
    4: "中低风险",
    3: "中风险",
    2: "中高风险",
    1: "高风险",
}


def evaluate_stock(code: str) -> RiskReport:
    """评估单只股票的风险等级

    步骤：
      1. 加载 universe / K线 / 财务 / 市值 → 组装 ctx
      2. 跑 7 个维度函数
      3. 加权汇总
      4. 反向映射星级
      5. 收集 score>=4 的维度为 warning
    """
    code = str(code).strip().zfill(6)

    # ===== 1. 组装 ctx =====
    ctx: dict = {}

    u = _load_universe_row(code) or {}
    ctx["name"] = u.get("name")
    ctx["pe"] = u.get("pe")
    ctx["pb"] = u.get("pb")
    ctx["industry"] = u.get("industry")

    fin = _load_finance(code)
    if fin is not None and not fin.empty and "debt_ratio" in fin.columns:
        try:
            cleaned = fin["debt_ratio"].dropna()
            ctx["debt_ratio"] = float(cleaned.iloc[-1]) if not cleaned.empty else None
        except Exception:
            ctx["debt_ratio"] = None
    if fin is not None and not fin.empty:
        for col in ("roe", "roeYear"):
            if col in fin.columns:
                try:
                    series = pd.to_numeric(fin[col], errors="coerce").dropna().tolist()
                    if series:
                        ctx["roe_history"] = [float(x) for x in series[-4:]]
                        break
                except Exception:
                    pass

    ctx["avg_turnover_5d"] = _avg_turnover(code, days=5)
    ctx["market_cap_yi"] = _get_market_cap(code)

    # ===== 2. 跑 7 维 =====
    dimensions = {}
    for key, fn in DIMENSION_FUNCS.items():
        try:
            dimensions[key] = fn(ctx)
        except Exception as e:
            logger.warning(f"维度 {key} 评估失败 ({code}): {e}")
            dimensions[key] = DimensionResult(3, f"评估失败: {e}", {})

    # ===== 3. 加权汇总 =====
    weighted = sum(dimensions[k].score * WEIGHTS[k] for k in WEIGHTS)
    weighted = round(weighted, 2)

    # ===== 4. 星级 =====
    stars = _to_stars(weighted)
    level = _LEVEL_BY_STARS[stars]

    # ===== 5. 警告 =====
    warnings = [d.reason for d in dimensions.values() if d.score >= 4]

    return RiskReport(
        code=code,
        name=ctx.get("name"),
        industry=ctx.get("industry"),
        score=weighted,
        stars=stars,
        level=level,
        dimensions={k: asdict(d) for k, d in dimensions.items()},
        warnings=warnings,
        raw={
            "pe": ctx.get("pe"),
            "pb": ctx.get("pb"),
            "debt_ratio": ctx.get("debt_ratio"),
            "roe_history": ctx.get("roe_history"),
            "market_cap_yi": ctx.get("market_cap_yi"),
            "avg_turnover_5d_yi": (ctx.get("avg_turnover_5d") or 0) / 1e8,
        },
    )
