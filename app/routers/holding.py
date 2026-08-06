from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.schemas import ApiResponse, error, success

router = APIRouter(prefix="/api/v1/holdings", tags=["holdings"])


@router.get("/total", response_model=ApiResponse[list[schemas.HoldingTotalOut]])
def total_equity_series(
    start_date: date = Query(..., description="起始日期"),
    end_date: date = Query(..., description="结束日期"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """全部基金权益市值按日求和（来自每日权益流水）。"""
    rows = db.execute(
        select(
            models.FundHoldingDaily.trade_date,
            func.sum(models.FundHoldingDaily.equity_amount),
        )
        .where(
            models.FundHoldingDaily.trade_date >= start_date,
            models.FundHoldingDaily.trade_date <= end_date,
        )
        .group_by(models.FundHoldingDaily.trade_date)
        .order_by(models.FundHoldingDaily.trade_date)
    ).all()
    return success(
        [
            schemas.HoldingTotalOut(trade_date=r[0], total_equity=r[1])
            for r in rows
        ]
    )


@router.get("", response_model=ApiResponse[list[schemas.HoldingOut]])
def get_holdings(
    fund_id: int = Query(..., description="基金ID"),
    start_date: date = Query(..., description="起始日期"),
    end_date: date = Query(..., description="结束日期"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    return success(crud.holding.list_holdings(db, fund_id, start_date, end_date))


@router.post("/check", response_model=ApiResponse[schemas.HoldingCheckOut])
def check_holdings_missing(
    payload: schemas.HoldingGenerateIn, db: Session = Depends(get_db)
) -> ApiResponse:
    """先确认：该区间缺失的交易日（有历史价但无流水），供前端确认后再生成。"""
    fund = db.get(models.Fund, payload.fund_id)
    if fund is None:
        return error(40400, f"基金 {payload.fund_id} 不存在")
    missing_days, ms, me = crud.holding.check_missing(
        db, payload.fund_id, payload.start_date, payload.end_date
    )
    return success(
        schemas.HoldingCheckOut(
            fund_id=payload.fund_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            missing_days=missing_days,
            missing_start=ms,
            missing_end=me,
        )
    )


@router.post("/generate", response_model=ApiResponse[schemas.HoldingGenerateOut])
def generate_holdings(
    payload: schemas.HoldingGenerateIn, db: Session = Depends(get_db)
) -> ApiResponse:
    """生成/更新某基金 [start, end] 区间的每日权益流水（需先有 fund_price 历史价）。"""
    fund = db.get(models.Fund, payload.fund_id)
    if fund is None:
        return error(40400, f"基金 {payload.fund_id} 不存在")
    count = crud.holding.generate(db, payload.fund_id, payload.start_date, payload.end_date)
    return success(
        schemas.HoldingGenerateOut(
            fund_id=payload.fund_id,
            generated=count,
            range_start=payload.start_date,
            range_end=payload.end_date,
        )
    )
