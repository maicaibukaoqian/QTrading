#!/usr/bin/env python
"""
A股Agent股票分析工具 CLI
基于多策略量化框架 + baostock免费数据源

业务逻辑全部在 src/api/services/ 下，本文件仅做 CLI 薄壳。
REST API 调用请使用: python run_server.py

用法:
  # 分析单只股票
  python main.py analyze 600519

  # 全市场价值选股
  python main.py screen value --output data/outputs/value.csv

  # 筛选当前520战法买点
  python main.py screen 520

  # 一键全策略共振选股
  python main.py screen all

  # 一键下载全市场数据
  python main.py download all

  # 生成今日选股日报
  python main.py daily report
"""

import sys
import time
import click

from src.api.tasks.store import TaskStore
from src.api.tasks.progress import ProgressReporter
from src.api.tasks.runner import TaskRunner


# 全局单例（CLI 进程内）
_store = TaskStore()
_runner = TaskRunner(_store)


def _cli_progress(task_id: str) -> ProgressReporter:
    """CLI 模式：日志直接打到 stdout"""
    return ProgressReporter(_store, task_id, echo=True)


def _wait_for_task(task_id: str):
    """CLI 同步等待任务完成，每 200ms 检查一次，最后打印状态"""
    try:
        while True:
            t = _store.get(task_id)
            if t.is_terminal():
                return t
            time.sleep(0.2)
    except KeyboardInterrupt:
        click.echo("\n[cli] 收到 Ctrl+C，尝试取消任务...")
        try:
            _store.request_cancel(task_id)
        except Exception:
            pass
        sys.exit(1)


@click.group()
def main():
    """A股Agent股票分析工具（CLI）"""
    pass


# ===================== analyze =====================

@main.command('analyze')
@click.argument('code')
@click.option('--min-roe', default=10.0, help='最小ROE要求（%）')
@click.option('--min-gross-margin', default=20.0, help='最小毛利率要求（%）')
@click.option('--max-debt', default=70.0, help='最大资产负债率要求（%）')
@click.option('--check-years', default=3, help='要求连续多少年达标')
def analyze_cmd(code, min_roe, min_gross_margin, max_debt, check_years):
    """分析单只股票，给出多维度报告"""
    from src.api.services.analyze_service import analyze_stock
    click.echo(f"\n开始分析 {code}...\n")
    result = analyze_stock(code, min_roe, min_gross_margin, max_debt, check_years)
    click.echo("=" * 70)
    click.echo(result["markdown"])
    click.echo("=" * 70)
    click.echo(f"\n报告已保存到: {result['saved_path']}")


# ===================== download =====================

@main.group('download')
def download():
    """下载命令：单独下载数据到本地缓存."""
    pass


@download.command('universe')
def download_universe_cmd():
    """下载/更新全市场A股列表 + PE/PB缓存"""
    tid = _runner.submit("download_universe", {}, _run_download_universe)
    t = _wait_for_task(tid)
    if t.status == "success":
        click.echo(f"\n[ok] {t.result}")
    else:
        click.echo(f"\n[fail] {t.error}")
        sys.exit(1)


@download.command('fundamentals')
@click.option('--max-stocks', default=None, type=int)
@click.option('--skip-existing', default=True)
def download_fundamentals_cmd(max_stocks, skip_existing):
    """批量下载所有股票财务指标"""
    params = {"max_stocks": max_stocks, "skip_existing": skip_existing}
    tid = _runner.submit("download_fundamentals", params, _run_download_fundamentals)
    t = _wait_for_task(tid)
    if t.status != "success":
        click.echo(f"\n[fail] {t.error}")
        sys.exit(1)


@download.command('klines')
@click.option('--codes', default=None, help='逗号分隔代码列表')
@click.option('--max-stocks', default=None, type=int)
def download_klines_cmd(codes, max_stocks):
    """批量下载K线数据到本地缓存"""
    params = {
        "codes": [c.strip() for c in codes.split(",")] if codes else None,
        "max_stocks": max_stocks,
    }
    tid = _runner.submit("download_klines", params, _run_download_klines)
    t = _wait_for_task(tid)
    if t.status != "success":
        click.echo(f"\n[fail] {t.error}")
        sys.exit(1)


@download.command('from-result')
@click.argument('result_csv', type=str)
def download_from_result_cmd(result_csv):
    """从选股结果CSV下载K线：只下载结果中列出的股票"""
    params = {"csv_path": result_csv}
    tid = _runner.submit("download_from_result", params, _run_download_from_result)
    t = _wait_for_task(tid)
    if t.status != "success":
        click.echo(f"\n[fail] {t.error}")
        sys.exit(1)


@download.command('all')
def download_all_cmd():
    """一键下载全部数据：universe → fundamentals → klines"""
    tid = _runner.submit("download_all", {}, _run_download_all)
    t = _wait_for_task(tid)
    if t.status != "success":
        click.echo(f"\n[fail] {t.error}")
        sys.exit(1)


# ===================== screen =====================

@main.command('screen')
@click.argument('strategy', type=click.Choice(['value', '520', 'dividend', 'doublelow', 'xiaoyang', 'all']))
@click.option('--output', default=None, help='输出CSV文件路径')
@click.option('--min-roe', default=None, type=float, help='覆盖 value/520 的 min_roe 默认值')
def screen_cmd(strategy, output, min_roe):
    """全市场离线选股

    - value: 价值选股
    - 520: 趋势 520
    - dividend: 高股息红利
    - doublelow: 双低
    - xiaoyang: 小阳建仓
    - all: 全策略共振
    """
    if strategy == 'all':
        params = {"output_path": output, "min_roe": min_roe}
        tid = _runner.submit("screen_all", params, _run_screen_all)
    else:
        params = {"strategy": strategy, "output_path": output, "params": {}}
        tid = _runner.submit(f"screen_{strategy}", params, _run_screen_single)
    t = _wait_for_task(tid)
    if t.status != "success":
        click.echo(f"\n[fail] {t.error}")
        sys.exit(1)
    res = t.result or {}
    if "count" in res:
        click.echo(f"\n共选出 {res['count']} 只")
    if "output_path" in res and res["output_path"]:
        click.echo(f"结果已保存到: {res['output_path']}")


# ===================== daily =====================

@main.group('daily')
def daily():
    """每日选股日报生成."""
    pass


@daily.command('report')
@click.option('--input', default=None, help='选股结果CSV输入路径')
@click.option('--output-dir', default=None, help='日报输出目录')
@click.option('--ai/--no-ai', default=True, help='是否启用 AI 一句话点评')
def daily_report_cmd(input, output_dir, ai):
    """生成今日选股日报Markdown文件"""
    params = {
        "input_csv": input,
        "output_dir": output_dir,
        "ai": ai,
        "max_ai_comments": None,
    }
    tid = _runner.submit("daily_report", params, _run_daily_report)
    t = _wait_for_task(tid)
    res = t.result or {}
    if t.status == "success":
        click.echo(f"\n日报已生成: {res.get('path')}")
        click.echo(f"   总股票数: {res.get('total')}, 共振股: {res.get('resonance_count')}")
        if res.get("ai_generated"):
            click.echo(f"   AI点评生成: {res['ai_generated']} 条")
    else:
        click.echo(f"\n[fail] {t.error}")
        sys.exit(1)


# ===================== runner fns (CLI 入口) =====================

def _run_download_universe(reporter: ProgressReporter, params: dict) -> dict:
    from src.api.services.download_service import download_universe
    return download_universe(reporter)


def _run_download_fundamentals(reporter: ProgressReporter, params: dict) -> dict:
    from src.api.services.download_service import download_fundamentals
    return download_fundamentals(
        max_stocks=params.get("max_stocks"),
        skip_existing=params.get("skip_existing", True),
        reporter=reporter,
    )


def _run_download_klines(reporter: ProgressReporter, params: dict) -> dict:
    from src.api.services.download_service import download_klines
    return download_klines(
        codes=params.get("codes"),
        max_stocks=params.get("max_stocks"),
        start_date=params.get("start_date"),
        reporter=reporter,
    )


def _run_download_from_result(reporter: ProgressReporter, params: dict) -> dict:
    from src.api.services.download_service import download_from_result
    return download_from_result(
        csv_path=params.get("csv_path"),
        codes=params.get("codes"),
        reporter=reporter,
    )


def _run_download_all(reporter: ProgressReporter, params: dict) -> dict:
    from src.api.services.download_service import download_all
    return download_all(reporter)


def _run_screen_single(reporter: ProgressReporter, params: dict) -> dict:
    from src.api.services.screen_service import run_single
    return run_single(
        key=params["strategy"],
        params=params.get("params", {}),
        output_path=params.get("output_path"),
        reporter=reporter,
    )


def _run_screen_all(reporter: ProgressReporter, params: dict) -> dict:
    from src.api.services.screen_service import run_all
    return run_all(
        overrides=params.get("overrides"),
        output_path=params.get("output_path"),
        min_roe=params.get("min_roe"),
        reporter=reporter,
    )


def _run_daily_report(reporter: ProgressReporter, params: dict) -> dict:
    from src.api.services.daily_service import generate
    return generate(
        input_csv=params.get("input_csv"),
        output_dir=params.get("output_dir"),
        ai=params.get("ai", True),
        max_ai_comments=params.get("max_ai_comments"),
        reporter=reporter,
    )


if __name__ == '__main__':
    try:
        main()
    finally:
        _runner.shutdown(wait=False)
