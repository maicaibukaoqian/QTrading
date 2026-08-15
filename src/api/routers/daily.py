"""daily router：每日选股日报"""

from typing import Optional

from fastapi import APIRouter, Depends, status, Body

from src.api.deps import get_task_runner
from src.api.schemas import (
    DailyReportRequest,
    DailyReportList,
    TaskRef,
)
from src.api.services.daily_service import generate, list_reports, read_report
from src.api.tasks.runner import TaskRunner


router = APIRouter(prefix="/api", tags=["daily"])


@router.post(
    "/daily/report",
    response_model=TaskRef,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_daily_report(
    req: Optional[DailyReportRequest] = Body(default=None),
    runner: TaskRunner = Depends(get_task_runner),
):
    """生成今日选股日报（异步，AI 点评 50×3s）"""
    if req is None:
        req = DailyReportRequest()
    params = req.model_dump()

    def fn(reporter, p):
        return generate(
            input_csv=p.get("input_csv"),
            output_dir=p.get("output_dir"),
            ai=p.get("ai", True),
            max_ai_comments=p.get("max_ai_comments"),
            reporter=reporter,
        )
    tid = runner.submit("daily_report", params, fn)
    return TaskRef(
        task_id=tid, status="pending", type="daily_report",
        message="日报生成已提交",
    )


@router.get("/daily/reports", response_model=DailyReportList)
def get_daily_reports():
    """列出所有日报日期（YYYY-MM-DD 降序）"""
    return DailyReportList(dates=list_reports())


@router.get("/daily/reports/{date}")
def get_daily_report(date: str):
    """读某日日报 markdown（异常通过 AppError handler 转 HTTP 4xx）"""
    return {"date": date, "markdown": read_report(date)}
