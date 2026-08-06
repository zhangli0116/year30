from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.logger import logger
from app.schemas import ApiResponse, error, success
from app.services import benchmark as benchmark_service

router = APIRouter(prefix="/api/v1/benchmarks", tags=["benchmarks"])


@router.get("", response_model=ApiResponse[list[schemas.BenchmarkOut]])
def list_benchmarks(db: Session = Depends(get_db)) -> ApiResponse:
    """列出可用对比基准（回测页多选），首次调用自动灌默认基准。"""
    benchmark_service.ensure_seeded(db)
    out = []
    for b in crud.benchmark.list_benchmarks(db):
        out.append(
            schemas.BenchmarkOut(
                id=b.id,
                symbol=b.symbol,
                name=b.name,
                source=b.source,
                fund_id=b.fund_id,
                fund_code=b.fund.fund_code if b.fund else None,
                fund_name=b.fund.fund_name if b.fund else None,
                active=b.active,
            )
        )
    return success(out)


@router.post("/sync", response_model=ApiResponse[schemas.BenchmarkSyncOut])
def sync_benchmark(
    symbol: str = Query(..., description="基准 symbol，如 sh000300 / sz399006"),
    start_date: date = Query(..., description="起始日期"),
    end_date: date = Query(..., description="结束日期"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """按区间增量同步某基准日线（幂等，只补缺失）。"""
    benchmark_service.ensure_seeded(db)
    bm = crud.benchmark.get_by_symbol(db, symbol)
    if bm is None:
        return error(40404, f"基准 {symbol} 不存在")
    try:
        fetched, inserted, existing = benchmark_service.sync(db, bm, start_date, end_date)
    except Exception as e:  # noqa: BLE001
        logger.error(f"同步基准失败 {symbol} {start_date}~{end_date}：{e}")
        return error(50001, f"基准拉取失败：{e}")
    logger.info(f"同步基准 {symbol} {start_date}~{end_date}：拉取{fetched} 新增{inserted} 已有{existing}")
    return success(
        schemas.BenchmarkSyncOut(
            symbol=symbol,
            fetched=fetched,
            inserted=inserted,
            existing=existing,
            range_start=start_date,
            range_end=end_date,
        )
    )
