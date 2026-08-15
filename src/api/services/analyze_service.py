"""单股分析 service

把 main.py `analyze` 逻辑搬过来。
"""

import os
from pathlib import Path

from src.agent.analyzer import StockAgentAnalyzer
from src.agent.generator import generate_answer
from src.config.settings import get_settings
from src.api.errors import AnalyzeError, ResultNotFoundError


def analyze_stock(
    code: str,
    min_roe: float,
    min_gross_margin: float,
    max_debt: float,
    check_years: int,
) -> dict:
    """分析单只股票，返回 markdown + 落盘路径"""
    settings = get_settings()
    try:
        analyzer = StockAgentAnalyzer(
            min_roe=min_roe,
            min_gross_margin=min_gross_margin,
            max_debt_ratio=max_debt,
            check_years=check_years,
        )
        report = analyzer.analyze(code)
        answer = generate_answer(report, f"分析{code}")

        out_dir = Path(settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(out_dir / f"{code}_analysis.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(answer)

        return {
            "code": code,
            "markdown": answer,
            "saved_path": out_path,
        }
    except AnalyzeError:
        raise
    except Exception as e:
        raise AnalyzeError(f"分析 {code} 失败: {e}", detail={"code": code}) from e


def read_analysis(code: str) -> str:
    """读取已生成的分析 markdown"""
    settings = get_settings()
    out_path = str(Path(settings.output_dir) / f"{code}_analysis.md")
    if not os.path.exists(out_path):
        raise ResultNotFoundError(f"{code} 的分析报告不存在", detail={"path": out_path})
    with open(out_path, "r", encoding="utf-8") as f:
        return f.read()
