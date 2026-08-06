from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.schemas import ApiResponse, error, success

router = APIRouter(prefix="/api/v1/quarters", tags=["quarters"])


@router.get("", response_model=ApiResponse[list[schemas.QuarterOut]])
def list_quarters(db: Session = Depends(get_db)) -> ApiResponse:
    return success(crud.quarter.list_quarters(db))


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
    if crud.quarter.get_quarter_by_period(db, payload.period):
        return error(40005, f"周期 {payload.period} 已存在")
    return success(crud.quarter.create_quarter(db, payload))


@router.put("/{quarter_id}", response_model=ApiResponse[schemas.QuarterOut])
def update_quarter(
    quarter_id: int,
    payload: schemas.QuarterUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse:
    quarter = crud.quarter.get_quarter(db, quarter_id)
    if quarter is None:
        return error(40402, f"季度 {quarter_id} 不存在")
    return success(crud.quarter.update_quarter(db, quarter, payload))


@router.post("/{quarter_id}/recalc", response_model=ApiResponse[schemas.QuarterOut])
def recalc_quarter(quarter_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    """按本季购买记录重算 equity_amount / cash_amount（一键录入后调用）。"""
    result = crud.quarter.recalc_quarter(db, quarter_id)
    if result is None:
        return error(40402, f"季度 {quarter_id} 不存在")
    return success(result)


@router.delete("/{quarter_id}", response_model=ApiResponse)
def delete_quarter(quarter_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    quarter = crud.quarter.get_quarter(db, quarter_id)
    if quarter is None:
        return error(40402, f"季度 {quarter_id} 不存在")
    crud.quarter.delete_quarter(db, quarter)
    return success(message="删除成功")
