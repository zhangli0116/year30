from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.schemas import ApiResponse, success
from app.services import xirr as xirr_service

router = APIRouter(prefix="/api/v1/xirr", tags=["xirr"])


@router.get("", response_model=ApiResponse[schemas.XirrOut])
def get_xirr(
    plan_id: int | None = Query(None, description="方案ID，缺省为全账户"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """全账户 + 各基金的 XIRR 资金加权年化收益率（可按方案过滤）。"""
    funds_info = xirr_service._funds_with_shares(db, plan_id)
    codes = [f["fund_code"] for f in funds_info]
    prices = xirr_service._price_map(db, codes)  # 行情只拉一次，账户与各基金复用

    account = xirr_service.account_xirr(db, plan_id=plan_id, prices=prices)
    fund_rows = []
    for f in funds_info:
        d = xirr_service.fund_xirr(
            db, f["fund_id"], plan_id=plan_id, price=prices.get(f["fund_code"])
        )
        fund_rows.append(
            schemas.XirrFundOut(
                fund_id=f["fund_id"],
                fund_code=f["fund_code"],
                fund_name=f["fund_name"],
                xirr=d["xirr"],
                current_mv=d["current_mv"],
                invested=d["invested"],
            )
        )
    return success(
        schemas.XirrOut(
            account=schemas.XirrAccountOut(**account),
            funds=fund_rows,
        )
    )
