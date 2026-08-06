from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.schemas import ApiResponse, PageData, error, success

router = APIRouter(prefix="/api/v1/funds", tags=["funds"])


@router.get("", response_model=ApiResponse[PageData[schemas.FundOut]])
def list_funds(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    keyword: str | None = Query(None, description="按基金代码/名称模糊搜索"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    items, total = crud.fund.list_funds(db, page, page_size, keyword)
    return success(PageData(items=items, total=total, page=page, page_size=page_size))


# 注意：/summary 必须声明在 /{fund_id} 之前，否则会被当作 fund_id 解析
@router.get("/summary", response_model=ApiResponse[schemas.SummaryOut])
def summarize_funds(db: Session = Depends(get_db)) -> ApiResponse:
    return success(crud.fund.summarize_funds(db))


@router.post("", response_model=ApiResponse[schemas.FundOut])
def create_fund(
    payload: schemas.FundCreate, db: Session = Depends(get_db)
) -> ApiResponse:
    if crud.fund.get_fund_by_code(db, payload.fund_code):
        return error(40001, f"基金代码 {payload.fund_code} 已存在")
    return success(crud.fund.create_fund(db, payload))


@router.get("/{fund_id}", response_model=ApiResponse[schemas.FundDetail])
def get_fund_detail(fund_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    fund = crud.fund.get_fund_with_purchases(db, fund_id)
    if fund is None:
        return error(40400, f"基金 {fund_id} 不存在")
    return success(fund)


@router.put("/{fund_id}", response_model=ApiResponse[schemas.FundOut])
def update_fund(
    fund_id: int, payload: schemas.FundUpdate, db: Session = Depends(get_db)
) -> ApiResponse:
    fund = crud.fund.get_fund(db, fund_id)
    if fund is None:
        return error(40400, f"基金 {fund_id} 不存在")
    if payload.fund_code:
        existed = crud.fund.get_fund_by_code(db, payload.fund_code)
        if existed is not None and existed.id != fund_id:
            return error(40001, f"基金代码 {payload.fund_code} 已存在")
    return success(crud.fund.update_fund(db, fund, payload))


@router.delete("/{fund_id}", response_model=ApiResponse)
def delete_fund(fund_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    fund = crud.fund.get_fund(db, fund_id)
    if fund is None:
        return error(40400, f"基金 {fund_id} 不存在")
    if crud.fund.count_purchases(db, fund_id) > 0:
        return error(40002, f"基金 {fund.fund_code} 存在买入记录，不允许删除")
    crud.fund.delete_fund(db, fund)
    return success(message="删除成功")
