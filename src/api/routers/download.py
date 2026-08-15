"""download router：数据下载（全部异步）"""

from fastapi import APIRouter, Depends, status

from src.api.deps import get_task_runner
from src.api.errors import InvalidRequestError
from src.api.schemas import (
    DownloadFundamentalsRequest,
    DownloadKlinesRequest,
    DownloadFromResultRequest,
    TaskRef,
)
from src.api.tasks.runner import TaskRunner


router = APIRouter(prefix="/api/download", tags=["download"])


@router.post(
    "/universe",
    response_model=TaskRef,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_download_universe(runner: TaskRunner = Depends(get_task_runner)):
    """下载/刷新全市场列表 + PE/PB（~30s）"""
    from src.api.services.download_service import download_universe
    def fn(reporter, params):
        return download_universe(reporter)
    tid = runner.submit("download_universe", {}, fn)
    return TaskRef(task_id=tid, status="pending", type="download_universe",
                   message="已开始下载全市场列表")


@router.post(
    "/fundamentals",
    response_model=TaskRef,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_download_fundamentals(
    req: DownloadFundamentalsRequest,
    runner: TaskRunner = Depends(get_task_runner),
):
    """批量下载所有股票财务指标（ROE/毛利率/资产负债率），全市场约 1 小时"""
    from src.api.services.download_service import download_fundamentals
    params = req.model_dump()
    def fn(reporter, p):
        return download_fundamentals(
            max_stocks=p.get("max_stocks"),
            skip_existing=p.get("skip_existing", True),
            reporter=reporter,
        )
    tid = runner.submit("download_fundamentals", params, fn)
    return TaskRef(task_id=tid, status="pending", type="download_fundamentals",
                   message="已开始下载财务数据")


@router.post(
    "/klines",
    response_model=TaskRef,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_download_klines(
    req: DownloadKlinesRequest,
    runner: TaskRunner = Depends(get_task_runner),
):
    """批量下载 K 线数据（数小时）"""
    from src.api.services.download_service import download_klines
    params = req.model_dump()
    def fn(reporter, p):
        return download_klines(
            codes=p.get("codes"),
            max_stocks=p.get("max_stocks"),
            start_date=p.get("start_date"),
            reporter=reporter,
        )
    tid = runner.submit("download_klines", params, fn)
    return TaskRef(task_id=tid, status="pending", type="download_klines",
                   message="已开始下载 K 线")


@router.post(
    "/from-result",
    response_model=TaskRef,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_download_from_result(
    req: DownloadFromResultRequest,
    runner: TaskRunner = Depends(get_task_runner),
):
    """从选股结果 CSV 下载 K 线（只下选中的股票）"""
    if not req.csv_path and not req.codes:
        raise InvalidRequestError("csv_path 和 codes 必须二选一")
    from src.api.services.download_service import download_from_result
    params = req.model_dump()
    def fn(reporter, p):
        return download_from_result(
            csv_path=p.get("csv_path"),
            codes=p.get("codes"),
            reporter=reporter,
        )
    tid = runner.submit("download_from_result", params, fn)
    return TaskRef(task_id=tid, status="pending", type="download_from_result",
                   message="已开始从选股结果下载 K 线")


@router.post(
    "/all",
    response_model=TaskRef,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_download_all(runner: TaskRunner = Depends(get_task_runner)):
    """一键下载：universe → fundamentals → klines（数小时）"""
    from src.api.services.download_service import download_all
    def fn(reporter, params):
        return download_all(reporter)
    tid = runner.submit("download_all", {}, fn)
    return TaskRef(task_id=tid, status="pending", type="download_all",
                   message="已开始一键下载（universe→fundamentals→klines）")
