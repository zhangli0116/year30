from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.logger import logger
from app.schemas import ApiResponse, PageData, error, success

router = APIRouter(prefix="/api/v1/purchases", tags=["purchases"])


@router.get("", response_model=ApiResponse[PageData[schemas.PurchaseOut]])
def list_purchases(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    fund_id: int | None = Query(None, description="按基金筛选"),
    start_date: date | None = Query(None, description="开始日期（含）"),
    end_date: date | None = Query(None, description="结束日期（含）"),
    exclude_cash: bool = Query(True, description="默认排除现金基金(000000)记录"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    items, total = crud.purchase.list_purchases(
        db, page, page_size, fund_id, start_date, end_date, exclude_cash
    )
    return success(PageData(items=items, total=total, page=page, page_size=page_size))


@router.post("", response_model=ApiResponse[schemas.PurchaseOut])
def create_purchase(
    payload: schemas.PurchaseCreate, db: Session = Depends(get_db)
) -> ApiResponse:
    if crud.fund.get_fund(db, payload.fund_id) is None:
        return error(40003, f"基金 {payload.fund_id} 不存在")
    record = crud.purchase.create_purchase(db, payload)
    logger.info(f"新增购买记录 id={record.id} 基金{payload.fund_id} 类型{payload.type} 金额{record.total_amount}")
    return success(record)


@router.post("/batch", response_model=ApiResponse[list[schemas.PurchaseOut]])
def create_purchases_batch(
    payload: list[schemas.PurchaseCreate], db: Session = Depends(get_db)
) -> ApiResponse:
    """批量创建购买记录（如季度一键录入：4 只基金 + 现金）。"""
    if not payload:
        return error(40000, "记录列表不能为空")
    for p in payload:
        if crud.fund.get_fund(db, p.fund_id) is None:
            return error(40003, f"基金 {p.fund_id} 不存在")
    records = crud.purchase.create_purchases(db, payload)
    logger.info(f"批量录入购买记录 {len(records)} 条")
    return success(records)


@router.get("/{purchase_id}", response_model=ApiResponse[schemas.PurchaseOut])
def get_purchase(purchase_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    record = crud.purchase.get_purchase(db, purchase_id)
    if record is None:
        return error(40401, f"购买记录 {purchase_id} 不存在")
    return success(record)


@router.put("/{purchase_id}", response_model=ApiResponse[schemas.PurchaseOut])
def update_purchase(
    purchase_id: int,
    payload: schemas.PurchaseUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse:
    record = crud.purchase.get_purchase(db, purchase_id)
    if record is None:
        return error(40401, f"购买记录 {purchase_id} 不存在")
    if payload.fund_id is not None and crud.fund.get_fund(db, payload.fund_id) is None:
        return error(40003, f"基金 {payload.fund_id} 不存在")
    updated = crud.purchase.update_purchase(db, record, payload)
    logger.info(f"编辑购买记录 id={record.id} 基金{record.fund_id}")
    return success(updated)


@router.delete("/{purchase_id}", response_model=ApiResponse)
def delete_purchase(purchase_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    record = crud.purchase.get_purchase(db, purchase_id)
    if record is None:
        return error(40401, f"购买记录 {purchase_id} 不存在")
    crud.purchase.delete_purchase(db, record)
    logger.info(f"删除购买记录 id={purchase_id}")
    return success(message="删除成功")
