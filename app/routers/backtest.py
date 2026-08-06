from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.logger import logger
from app.schemas import ApiResponse, error, success
from app.services import backtest as backtest_service

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


def _split_symbols(raw: str | None) -> list[str]:
    return [s.strip() for s in (raw or "").split(",") if s.strip()]


@router.get("/coverage", response_model=ApiResponse[schemas.BacktestCoverageOut])
def coverage(
    plan_id: int = Query(..., description="方案ID"),
    start_date: date = Query(..., description="回测起始日"),
    end_date: date = Query(..., description="回测结束日"),
    benchmarks: str | None = Query(None, description="逗号分隔的基准 symbol，如 sh000300"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """数据覆盖检查：各方案基金 + 所选基准在 [start, end] 的缺失情况，引导去补历史。"""
    if crud.plan.get_plan(db, plan_id) is None:
        return error(40403, f"方案 {plan_id} 不存在")
    data = backtest_service.run_coverage(db, plan_id, start_date, end_date, _split_symbols(benchmarks))
    return success(schemas.BacktestCoverageOut(**data))


@router.get("", response_model=ApiResponse[schemas.BacktestOut])
def run(
    plan_id: int = Query(..., description="方案ID"),
    start_date: date = Query(..., description="回测起始日（第一笔定投日）"),
    end_date: date | None = Query(None, description="回测结束日，缺省今天"),
    amount: Decimal | None = Query(None, description="每期金额覆盖，缺省用方案 amount"),
    benchmarks: str | None = Query(None, description="逗号分隔的基准 symbol"),
    year_end_rebalance: bool = Query(True, description="年末卖出式再平衡开关"),
    unlisted_mode: str = Query(
        "park",
        description="未上市标的处理：park=现金停泊(默认) / redistribute=比例重分配",
    ),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """回测：每期入账+买入式平衡，每年末卖出式再平衡，算年化回报并对比基准。"""
    plan = crud.plan.get_plan(db, plan_id)
    if plan is None:
        return error(40403, f"方案 {plan_id} 不存在")
    if unlisted_mode not in ("park", "redistribute"):
        return error(40006, f"未知未上市处理方式：{unlisted_mode}")
    data = backtest_service.run_backtest(
        db,
        plan,
        start_date=start_date,
        end_date=end_date,
        amount=amount,
        benchmark_symbols=_split_symbols(benchmarks),
        year_end_rebalance=year_end_rebalance,
        unlisted_mode=unlisted_mode,
    )
    logger.info(
        f"回测 方案{plan_id} {start_date}~{end_date or date.today()} "
        f"XIRR={data['metrics']['xirr']} TWR={data['metrics']['twr']}"
    )
    return success(schemas.BacktestOut(**data))
