from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.logger import logger
from app.schemas import ApiResponse, error, success

router = APIRouter(prefix="/api/v1/quarters", tags=["quarters"])


@router.get("", response_model=ApiResponse[list[schemas.QuarterOut]])
def list_quarters(
    plan_id: int | None = Query(None, description="方案ID，缺省返回全部方案季度"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    return success(crud.quarter.list_quarters(db, plan_id))


@router.get("/{quarter_id}", response_model=ApiResponse[schemas.QuarterDetail])
def get_quarter_detail(quarter_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    quarter = crud.quarter.get_quarter_with_purchases(db, quarter_id)
    if quarter is None:
        return error(40402, f"季度 {quarter_id} 不存在")
    return success(quarter)


@router.post("", response_model=ApiResponse[schemas.QuarterOut])
def create_quarter(
    payload: schemas.QuarterCreate, db: Session = Depends(get_db)
) -> ApiResponse:
    if crud.plan.get_plan(db, payload.plan_id) is None:
        return error(40403, f"方案 {payload.plan_id} 不存在")
    if crud.quarter.get_quarter_by_period(db, payload.period, payload.plan_id):
        return error(40005, f"周期 {payload.period} 在该方案下已存在")
    quarter = crud.quarter.create_quarter(db, payload)
    logger.info(f"创建季度 {payload.period} id={quarter.id} 预算{payload.budget}")
    return success(quarter)


@router.put("/{quarter_id}", response_model=ApiResponse[schemas.QuarterOut])
def update_quarter(
    quarter_id: int,
    payload: schemas.QuarterUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse:
    quarter = crud.quarter.get_quarter(db, quarter_id)
    if quarter is None:
        return error(40402, f"季度 {quarter_id} 不存在")
    updated = crud.quarter.update_quarter(db, quarter, payload)
    logger.info(f"更新季度 {quarter.period} id={quarter_id}")
    return success(updated)


@router.post("/{quarter_id}/recalc", response_model=ApiResponse[schemas.QuarterOut])
def recalc_quarter(quarter_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    """按本季购买记录重算 equity_amount / cash_amount（一键录入后调用）。"""
    result = crud.quarter.recalc_quarter(db, quarter_id)
    if result is None:
        return error(40402, f"季度 {quarter_id} 不存在")
    logger.info(f"重算季度 id={quarter_id}：权益{result.equity_amount} 手续费{result.total_fee} 现金{result.cash_amount}")
    return success(result)


@router.delete("/{quarter_id}", response_model=ApiResponse)
def delete_quarter(quarter_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    quarter = crud.quarter.get_quarter(db, quarter_id)
    if quarter is None:
        return error(40402, f"季度 {quarter_id} 不存在")
    crud.quarter.delete_quarter(db, quarter)
    return success(message="删除成功")
