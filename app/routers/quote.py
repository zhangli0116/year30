from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import ApiResponse, QuoteListOut, error, success
from app.services import datasource
from app.services.price import FUND_TYPE_OTC

router = APIRouter(prefix="/api/v1/quotes", tags=["quotes"])


@router.get("", response_model=ApiResponse[QuoteListOut])
def get_quotes(
    codes: str = Query(..., description="逗号分隔的基金/ETF 代码，如 513500,513100"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """实时行情（含五档盘口），按该标的的 fund_type 取对应数据源。

    场外基金（otc）无实时盘口，直接跳过不取数。
    """
    code_list = [
        c.strip()
        for c in codes.split(",")
        if c.strip().isdigit() and len(c.strip()) == 6
    ]
    if not code_list:
        return error(40004, "请提供合法的 6 位基金代码")
    # 按 fund_type 分组：otc 场外基金无盘口，跳过；etf 走 etf 组数据源
    code_types = dict(
        db.execute(
            select(models.Fund.fund_code, models.Fund.fund_type).where(
                models.Fund.fund_code.in_(code_list)
            )
        ).all()
    )
    etf_codes = [c for c in code_list if code_types.get(c) != FUND_TYPE_OTC]
    provider = datasource.get_provider(db, "etf")
    symbol_map = datasource.resolve_symbols(db, etf_codes)
    symbols = [symbol_map[c] for c in etf_codes if c in symbol_map]
    quotes = provider.fetch_quotes(symbols)
    return success(QuoteListOut(quotes=quotes, source=provider.name))
