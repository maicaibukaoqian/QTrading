"""analyze router：单股综合分析（同步）"""

from fastapi import APIRouter

from src.api.schemas import AnalyzeRequest, AnalyzeResult
from src.api.services.analyze_service import analyze_stock, read_analysis

router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/analyze", response_model=AnalyzeResult)
def post_analyze(req: AnalyzeRequest):
    """单股综合分析（秒级，同步），落盘 data/outputs/{code}_analysis.md"""
    res = analyze_stock(
        code=req.code,
        min_roe=req.min_roe,
        min_gross_margin=req.min_gross_margin,
        max_debt=req.max_debt,
        check_years=req.check_years,
    )
    return AnalyzeResult(**res)


@router.get("/analyze/{code}")
def get_analyze(code: str):
    """读取已生成的分析 markdown"""
    return {"code": code, "markdown": read_analysis(code)}
