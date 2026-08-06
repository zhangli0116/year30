from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.logger import logger
from app.schemas import ApiResponse, error, success

router = APIRouter(prefix="/api/v1/cash", tags=["cash"])


def _resolve_plan_id(db: Session, plan_id: int | None) -> int | None:
    """plan_id 缺省时回退第一个 active 方案兜底。"""
    if plan_id is not None:
        return plan_id
    plans = [p for p in crud.plan.list_plans(db) if p.active]
    return plans[0].id if plans else None


@router.get("", response_model=ApiResponse[list[schemas.CashOut]])
def get_cash(
    start_date: date = Query(..., description="起始日期"),
    end_date: date = Query(..., description="结束日期"),
    plan_id: int | None = Query(None, description="方案ID，缺省用默认方案"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    pid = _resolve_plan_id(db, plan_id)
    if pid is None:
        return error(40004, "尚无可用方案")
    return success(crud.cash.list_cash(db, pid, start_date, end_date))


@router.post("/check", response_model=ApiResponse[schemas.CashCheckOut])
def check_cash_missing(
    payload: schemas.CashGenerateIn, db: Session = Depends(get_db)
) -> ApiResponse:
    """先确认：该区间缺失的日历日（未生成现金流的天数），供前端确认后再生成。"""
    pid = _resolve_plan_id(db, payload.plan_id)
    if pid is None:
        return error(40004, "尚无可用方案")
    missing_days, ms, me = crud.cash.check_missing(
        db, pid, payload.start_date, payload.end_date
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
    pid = _resolve_plan_id(db, payload.plan_id)
    if pid is None:
        return error(40004, "尚无可用方案")
    count = crud.cash.generate(db, pid, payload.start_date, payload.end_date)
    logger.info(f"生成每日现金流 {payload.start_date}~{payload.end_date}：{count} 天")
    return success(
        schemas.CashGenerateOut(
            generated=count,
            range_start=payload.start_date,
            range_end=payload.end_date,
        )
    )
