"""每日选股日报 service

把 main.py `daily report` 逻辑搬过来。
"""

import os
import re
from datetime import datetime
from typing import Optional, List

import pandas as pd

from src.config.settings import get_settings
from src.agent.ai_commenter import generate_stock_comment
from src.api.errors import MissingDataError
from src.api.tasks.progress import ProgressReporter


def list_reports(daily_dir: Optional[str] = None) -> List[str]:
    """列出所有日报日期（YYYY-MM-DD 降序）"""
    d = daily_dir or get_settings().daily_dir
    if not os.path.isdir(d):
        return []
    files = [f for f in os.listdir(d) if re.match(r"\d{4}-\d{2}-\d{2}\.md$", f)]
    dates = [f[:-3] for f in files]
    dates.sort(reverse=True)
    return dates


def read_report(date: str, daily_dir: Optional[str] = None) -> str:
    """读取某日日报 markdown"""
    d = daily_dir or get_settings().daily_dir
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        from src.api.errors import ReportNotFoundError
        raise ReportNotFoundError(f"非法日期格式: {date}")
    path = os.path.join(d, f"{date}.md")
    if not os.path.exists(path):
        from src.api.errors import ReportNotFoundError
        raise ReportNotFoundError(f"日报 {date} 不存在", detail={"path": path})
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def generate(
    input_csv: Optional[str],
    output_dir: Optional[str],
    ai: bool,
    max_ai_comments: Optional[int],
    reporter: ProgressReporter,
) -> dict:
    """生成今日日报 markdown"""
    settings = get_settings()
    in_csv = input_csv or settings.screen_all_csv
    out_dir = output_dir or settings.daily_dir
    ai_limit = max_ai_comments if max_ai_comments is not None else settings.max_ai_comments

    if not os.path.exists(in_csv):
        raise MissingDataError(
            f"输入文件不存在: {in_csv}",
            detail={"hint": "请先 POST /api/screen/all 生成选股结果"},
        )

    reporter.step(f"读取选股结果 {in_csv}")
    df = pd.read_csv(in_csv, dtype={"code": str})
    if df.empty:
        raise MissingDataError(
            f"输入文件为空: {in_csv}",
            detail={"hint": "请先 POST /api/screen/all 生成非空结果"},
        )

    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{today}.md")

    total = len(df)
    resonance = df[df["命中策略数"] >= 2] if "命中策略数" in df.columns else df.iloc[0:0]
    n_resonance = len(resonance)

    # AI 点评
    ai_comments: dict = {}
    ai_generated = 0
    if ai and settings.ai_enabled:
        reporter.step(f"AI 点评：{n_resonance} 只共振股，最多 {ai_limit} 条")
        for idx, (_, row) in enumerate(resonance.iterrows()):
            if idx >= ai_limit:
                break
            reporter.check_cancel()
            code = str(row["code"]).zfill(6)
            name = row.get("name", "")
            try:
                pe = float(row["pe"]) if pd.notna(row.get("pe")) else 0.0
                pb = float(row["pb"]) if pd.notna(row.get("pb")) else 0.0
                roe = float(row["latest_roe"]) if pd.notna(row.get("latest_roe")) else 0.0
            except (TypeError, ValueError):
                pe = pb = roe = 0.0
            strategies = str(row.get("命中策略", ""))
            comment = generate_stock_comment(code, name, pe, pb, roe, strategies)
            if comment:
                ai_comments[code] = comment
                ai_generated += 1
                reporter.log(f"AI 点评 [{ai_generated}] {code} {name}: {comment}")
            reporter.advance(idx + 1, min(n_resonance, ai_limit), "AI 点评")
    elif ai and not settings.ai_enabled:
        reporter.log("AI 点评未启用（API Key 未配置），跳过")

    # 拼装 markdown
    lines: list = []
    lines.append(f"# A股每日选股日报 {today}")
    lines.append("")
    lines.append(
        f"今日共选出 **{total}** 只股票，其中 **{n_resonance}** 只共振股（被2个及以上策略同时选中）。"
    )
    if ai_generated > 0:
        lines.append(f"已为前 {ai_generated} 只共振股生成AI点评。")
    lines.append("")
    lines.append("---")
    lines.append("")

    if n_resonance > 0:
        lines.append("## ⭐ 共振股（多策略共振，优先级最高）")
        lines.append("")
        if ai_generated > 0:
            lines.append("| 代码 | 名称 | PE | PB | ROE(%) | 命中策略 | AI 点评 |")
            lines.append("|------|------|----|----|--------|----------|-----------|")
        else:
            lines.append("| 代码 | 名称 | PE | PB | ROE(%) | 命中策略 |")
            lines.append("|------|------|----|----|--------|----------|")
        for _, row in resonance.iterrows():
            code = str(row["code"]).zfill(6)
            name = row.get("name", "")
            pe = f"{row['pe']:.2f}" if pd.notna(row.get("pe")) else "-"
            pb = f"{row['pb']:.2f}" if pd.notna(row.get("pb")) else "-"
            roe = f"{row['latest_roe']:.2f}" if pd.notna(row.get("latest_roe")) else "-"
            strategies = row.get("命中策略", "")
            if code in ai_comments:
                lines.append(f"| {code} | {name} | {pe} | {pb} | {roe} | {strategies} | {ai_comments[code]} |")
            elif ai_generated > 0:
                lines.append(f"| {code} | {name} | {pe} | {pb} | {roe} | {strategies} | - |")
            else:
                lines.append(f"| {code} | {name} | {pe} | {pb} | {roe} | {strategies} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    strategy_names = {
        "价值": "价值选股（PE<30 + ROE达标）",
        "双低": "双低选股（低PE + 低PB）",
        "高股息": "高股息策略（股息率>3% + ROE达标）",
        "520": "趋势 520（基本面合格 + 5 日线金叉 20 日线）",
        "小阳": "小阳建仓（低位连续小阳线吸筹）",
    }
    lines.append("## 各策略选股结果")
    lines.append("")
    if "命中策略" in df.columns:
        for s_name, desc in strategy_names.items():
            subset = df[df["命中策略"].str.contains(s_name, na=False)]
            if subset.empty:
                continue
            lines.append(f"### {s_name}：{desc}")
            lines.append(f"共选出 {len(subset)} 只")
            lines.append("")
            lines.append("| 代码 | 名称 | PE | ROE(%) |")
            lines.append("|------|------|----|--------|")
            for _, row in subset.head(10).iterrows():
                code = str(row["code"]).zfill(6)
                name = row.get("name", "")
                pe = f"{row['pe']:.2f}" if pd.notna(row.get("pe")) else "-"
                roe = f"{row['latest_roe']:.2f}" if pd.notna(row.get("latest_roe")) else "-"
                lines.append(f"| {code} | {name} | {pe} | {roe} |")
            if len(subset) > 10:
                lines.append("| ... | ... | ... | ... |（显示前10只，完整结果看CSV）")
            lines.append("")

    content = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    reporter.log(f"日报已生成: {out_path}")
    return {
        "date": today,
        "path": out_path,
        "total": total,
        "resonance_count": n_resonance,
        "ai_generated": ai_generated,
    }
