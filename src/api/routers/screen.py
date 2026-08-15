"""screen router：选股"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request, status, Body
from pydantic import ValidationError

from src.api.deps import get_task_runner
from src.api.errors import InvalidStrategyError
from src.api.schemas import (
    StrategiesOut,
    StrategyInfo,
    ScreenResultPage,
    ScreenAllRequest,
    TaskRef,
)
from src.api.services.screen_service import (
    STRATEGY_REGISTRY,
    DEFAULT_PARAMS,
    run_single,
    run_all,
    get_strategy,
)
from src.api.services.result_service import read_csv_page
from src.api.tasks.runner import TaskRunner


router = APIRouter(prefix="/api", tags=["screen"])


@router.get("/screen/strategies", response_model=StrategiesOut)
def get_strategies():
    """列出 5 个策略的元信息 + 默认参数"""
    items = [
        StrategyInfo(
            key=key,
            cn_name=spec.cn_name,
            description=spec.description,
            default_params=DEFAULT_PARAMS[key],
            default_output=spec.default_output,
        )
        for key, spec in STRATEGY_REGISTRY.items()
    ]
    return StrategiesOut(strategies=items)


@router.post(
    "/screen/all",
    response_model=TaskRef,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_screen_all(
    req: ScreenAllRequest = Body(default_factory=ScreenAllRequest),
    runner: TaskRunner = Depends(get_task_runner),
):
    """全策略共振选股（异步）"""
    params = req.model_dump()
    def fn(reporter, p):
        return run_all(
            overrides=p.get("overrides"),
            output_path=p.get("output_path"),
            min_roe=p.get("min_roe"),
            reporter=reporter,
        )
    tid = runner.submit("screen_all", params, fn)
    return TaskRef(task_id=tid, status="pending", type="screen_all",
                   message="全策略选股已提交")


@router.post(
    "/screen/{strategy}",
    response_model=TaskRef,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_screen_single(
    strategy: str,
    body: Optional[Dict[str, Any]] = Body(default=None),
    runner: TaskRunner = Depends(get_task_runner),
):
    """单策略选股（异步）

    body 透传给 screener 构造函数，字段见 GET /api/screen/strategies 的 default_params
    入参会用 STRATEGY_REGISTRY.params_model 做 Pydantic 校验，类型/范围错误立即 422
    """
    if strategy not in STRATEGY_REGISTRY:
        raise InvalidStrategyError(
            f"未知策略: {strategy}",
            detail={"available": list(STRATEGY_REGISTRY.keys())},
        )
    spec = get_strategy(strategy)
    user_params = body or {}
    try:
        spec.params_model.model_validate(user_params)
    except ValidationError as e:
        # 主动抛 RequestValidationError 风格的错误，统一走 app.py 的 422 handler
        from fastapi.exceptions import RequestValidationError
        from starlette.requests import Request as StarletteRequest
        raise RequestValidationError(errors=e.errors())
    params = {"strategy": strategy, "params": user_params, "output_path": None}
    def fn(reporter, p):
        return run_single(
            key=p["strategy"],
            params=p.get("params", {}),
            output_path=p.get("output_path"),
            reporter=reporter,
        )
    tid = runner.submit(f"screen_{strategy}", params, fn)
    return TaskRef(task_id=tid, status="pending", type=f"screen_{strategy}",
                   message=f"策略 {strategy} 选股已提交")


@router.get("/screen/results", response_model=ScreenResultPage)
def get_screen_results(
    file: str = Query(default="screen_all", description="screen_all/value/520/dividend/doublelow/xiaoyang"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    min_hits: Optional[int] = Query(default=None, ge=1),
    max_pe: Optional[float] = Query(default=None, ge=0),
    strategy: Optional[str] = Query(default=None, description="命中策略包含的关键字"),
):
    """分页读选股结果 CSV"""
    return ScreenResultPage(**read_csv_page(
        file_name=file, page=page, size=size,
        min_hits=min_hits, max_pe=max_pe, strategy=strategy,
    ))
