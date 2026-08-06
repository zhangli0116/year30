from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.logger import logger
from app.schemas import ApiResponse, success

router = APIRouter(prefix="/api/v1/cash", tags=["cash"])


@router.get("", response_model=ApiResponse[list[schemas.CashOut]])
def get_cash(
    start_date: date = Query(..., description="起始日期"),
    end_date: date = Query(..., description="结束日期"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    return success(crud.cash.list_cash(db, start_date, end_date))


@router.post("/check", response_model=ApiResponse[schemas.CashCheckOut])
def check_cash_missing(
    payload: schemas.CashGenerateIn, db: Session = Depends(get_db)
) -> ApiResponse:
    """先确认：该区间缺失的日历日（未生成现金流的天数），供前端确认后再生成。"""
    missing_days, ms, me = crud.cash.check_missing(
        db, payload.start_date, payload.end_date
    )
    return success(
        schemas.CashCheckOut(
            start_date=payload.start_date,
            end_date=payload.end_date,
            missing_days=missing_days,
            missing_start=ms,
            missing_end=me,
        )
    )


@router.post("/generate", response_model=ApiResponse[schemas.CashGenerateOut])
def generate_cash(
    payload: schemas.CashGenerateIn, db: Session = Depends(get_db)
) -> ApiResponse:
    """生成/更新 [start, end] 区间的每日现金流（按日历日累计）。"""
    count = crud.cash.generate(db, payload.start_date, payload.end_date)
    logger.info(f"生成每日现金流 {payload.start_date}~{payload.end_date}：{count} 天")
    return success(
        schemas.CashGenerateOut(
            generated=count,
            range_start=payload.start_date,
            range_end=payload.end_date,
        )
    )
